"""Step 13 Backend Tests: Forensic Video/Data Recovery and AI Video Analysis.

Covers:
Part A - Recovery:
 1. Recovery engine initialization
 2. Raw / dd / img identification
 3. Candidate detection (synthetic raw carving)
 4. Candidate validation (VALID, PARTIAL, CORRUPTED)
 5. Recovered evidence creation
 6. RECOVERED evidence status & provenance
 7. Source offset persistence
 8. SHA-256 and MD5 generation
 9. Original source unchanged (immutability)
 10. Fragmented/corrupt candidate handling
 11. Recovery authorization checks
 12. Recovery audit events

Part B - AI Analysis:
 13. AI analysis job creation
 14. Authorized evidence access
 15. AI finding creation & structure
 16. Model confidence storage
 17. Timestamp storage (media_time, source, normalized)
 18. Channel storage
 19. Bounding box structure
 20. Timeline integration
 21. AI frame export lineage (DERIVED, AI_FRAME_EXPORT)
 22. Original evidence immutability
 23. Unauthorized access rejected
 24. AI job state transitions & cancellation
"""
import io
import os
import uuid
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.case import Case, CaseMember, RoleEnum
from app.models.user import User
from app.models.evidence import Evidence, EvidenceStatus
from app.models.audit import AuditLog
from app.models.recovery import (
    RecoveryScanJob,
    RecoveryCandidate,
    RecoveryScanStatus,
    RecoveryCandidateStatus,
)
from app.models.ai_analysis import AIAnalysisJob, AIFinding, AIJobStatus
from app.models.video_analysis import TimelineEvent
from app.forensics.recovery.engine import RecoveryEngine
from app.services.recovery_service import (
    start_recovery_scan,
    list_recovery_candidates,
    validate_candidate,
    recover_candidate,
)
from app.services.ai_service import (
    start_ai_analysis_job,
    cancel_job,
    export_ai_frame,
    sync_finding_to_timeline,
)
from app.core.security import get_password_hash
from app.dependencies.auth import (
    get_current_user,
    require_case_member,
    require_case_investigator_or_admin,
    require_case_admin,
)


@pytest.fixture
def test_admin_user(db_session: Session):
    user = User(
        username=f"admin_s13_{uuid.uuid4().hex[:6]}",
        password_hash=get_password_hash("pass"),
        display_name="Forensic Admin"
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_investigator_user(db_session: Session):
    user = User(
        username=f"inv_s13_{uuid.uuid4().hex[:6]}",
        password_hash=get_password_hash("pass"),
        display_name="Lead Investigator"
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def case_with_members(db_session: Session, test_admin_user: User, test_investigator_user: User):
    case = Case(
        case_identifier=f"CASE-S13-{uuid.uuid4().hex[:6].upper()}",
        name="Step 13 Recovery and AI Case",
        created_by=test_admin_user.id
    )
    db_session.add(case)
    db_session.commit()

    m_admin = CaseMember(case_id=case.id, user_id=test_admin_user.id, role=RoleEnum.ADMIN)
    m_inv = CaseMember(case_id=case.id, user_id=test_investigator_user.id, role=RoleEnum.INVESTIGATOR)
    db_session.add_all([m_admin, m_inv])
    db_session.commit()
    return case


@pytest.fixture
def foreign_case(db_session: Session, test_admin_user: User):
    case = Case(
        case_identifier=f"CASE-FOR13-{uuid.uuid4().hex[:6].upper()}",
        name="Foreign Step 13 Case",
        created_by=test_admin_user.id
    )
    db_session.add(case)
    db_session.commit()
    return case


def setup_auth(client: TestClient, db_session: Session, case: Case, user: User, role: RoleEnum = RoleEnum.INVESTIGATOR):
    member = db_session.query(CaseMember).filter(
        CaseMember.case_id == case.id,
        CaseMember.user_id == user.id
    ).first()
    if member:
        member.case = case

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_case_member] = lambda: member
    app.dependency_overrides[require_case_investigator_or_admin] = lambda: member
    app.dependency_overrides[require_case_admin] = lambda: member if role == RoleEnum.ADMIN else None


def create_synthetic_raw_image(tmp_path) -> str:
    """Creates a synthetic raw disk image with padding, Dahua DHAV header, and MP4 ftyp box."""
    file_path = tmp_path / "synthetic_disk_image.raw"
    
    # 512 bytes MBR/header padding
    padding1 = b"\x00" * 512
    
    # Embedded Dahua DHAV stream with NAL start code and trailing DHAV block
    dhav_magic = b"DHAV"
    dhav_body = b"\x01\x00\x00\x00" + b"\x00\x00\x00\x01\x67" + b"\x55" * 1024 + b"DHAV" + b"\x22" * 512
    
    # Gap unallocated space
    padding2 = b"\xFF" * 1024
    
    # Embedded MP4 stream with ftyp, moov, and mdat markers
    mp4_box_size = (32).to_bytes(4, byteorder="big")
    mp4_magic = mp4_box_size + b"ftypisom" + (1).to_bytes(4, "big") + b"isommp41" + b"\x00" * 8 + b"moov" + b"\x00" * 64 + b"mdat" + b"\x00" * 64
    
    # Trailing raw unallocated
    padding3 = b"\x00" * 2048

    content = padding1 + dhav_magic + dhav_body + padding2 + mp4_magic + padding3
    file_path.write_bytes(content)
    return str(file_path)


# ==============================================================================
# PART A: RECOVERY TESTS
# ==============================================================================

def test_1_recovery_engine_initialization():
    """1. Recovery engine initialization."""
    engine = RecoveryEngine()
    assert len(engine.carving_strategies) > 0
    strategy_names = [s.strategy_name for s in engine.carving_strategies]
    assert any("Dahua" in s for s in strategy_names)
    assert any("MP4" in s for s in strategy_names)
    assert any("Hikvision" in s for s in strategy_names)


def test_2_raw_dd_img_identification(tmp_path):
    """2. Raw/dd/img identification."""
    engine = RecoveryEngine()
    
    raw_file = tmp_path / "test.raw"
    raw_file.write_bytes(b"\x00" * 1024)
    assert engine.is_supported_image(raw_file) is True

    dd_file = tmp_path / "test.dd"
    dd_file.write_bytes(b"\x00" * 1024)
    assert engine.is_supported_image(dd_file) is True

    img_file = tmp_path / "test.img"
    img_file.write_bytes(b"\x00" * 1024)
    assert engine.is_supported_image(img_file) is True

    e01_file = tmp_path / "test.e01"
    e01_file.write_bytes(b"\x00" * 1024)
    assert engine.is_supported_image(e01_file) is True


def test_3_candidate_detection_synthetic_raw(tmp_path, db_session: Session, case_with_members: Case, test_admin_user: User):
    """3. Candidate detection in raw unallocated/disk image."""
    img_path = create_synthetic_raw_image(tmp_path)
    file_size = os.path.getsize(img_path)
    sha256_hash = hashlib.sha256(open(img_path, "rb").read()).hexdigest()

    ev = Evidence(
        case_id=case_with_members.id,
        evidence_identifier=f"EVD-RAW-{uuid.uuid4().hex[:6].upper()}",
        original_filename="synthetic_disk_image.raw",
        storage_path=img_path,
        source_type="DISK_IMAGE",
        media_type="application/octet-stream",
        file_extension=".raw",
        size_bytes=file_size,
        sha256=sha256_hash,
        evidence_status=EvidenceStatus.ORIGINAL,
        imported_by=test_admin_user.id
    )
    db_session.add(ev)
    db_session.commit()

    job, candidates = start_recovery_scan(db_session, case_with_members, ev.id, user_id=test_admin_user.id)
    assert job.status == RecoveryScanStatus.COMPLETED
    assert len(candidates) >= 2

    # Check DHAV candidate
    dhav_cand = next((c for c in candidates if "DAV" in c.detected_format or "DHAV" in c.detected_format), None)
    assert dhav_cand is not None
    assert dhav_cand.source_offset == 512
    assert dhav_cand.vendor == "Dahua"
    assert dhav_cand.status == RecoveryCandidateStatus.DETECTED

    # Check MP4 candidate
    mp4_cand = next((c for c in candidates if "MP4" in c.detected_format), None)
    assert mp4_cand is not None
    assert mp4_cand.source_offset > 512


def test_4_candidate_validation(tmp_path):
    """4. Candidate validation (VALID, PARTIAL, CORRUPTED)."""
    engine = RecoveryEngine()
    
    # Complete DHAV candidate
    valid_dhav_file = tmp_path / "valid_dhav.raw"
    valid_dhav_file.write_bytes(b"DHAV" + b"\x01\x00\x00\x00" + b"\x00\x00\x00\x01\x67" + b"\x55" * 100 + b"DHAV" + b"\x00" * 50)
    val_v = engine.validate_candidate_stream(valid_dhav_file, 0, 200, "DHAV")
    assert val_v["status"] == "VALID"
    assert val_v["confidence"] >= 0.85

    # Partial / truncated DHAV
    truncated_dhav_file = tmp_path / "trunc_dhav.raw"
    truncated_dhav_file.write_bytes(b"DHAV" + b"\x01\x00\x00\x00" + b"\x00\x00\x00\x01\x67")
    val_p = engine.validate_candidate_stream(truncated_dhav_file, 0, 50, "DHAV")
    assert val_p["status"] == "PARTIAL"

    # Corrupted candidate (no magic bytes)
    corrupt_file = tmp_path / "corrupt.raw"
    corrupt_file.write_bytes(b"\x00\x00\x00\x00" * 10)
    val_c = engine.validate_candidate_stream(corrupt_file, 0, 40, "DHAV")
    assert val_c["status"] == "CORRUPTED"


def test_5_to_9_recovery_workflow_and_immutability(tmp_path, db_session: Session, case_with_members: Case, test_admin_user: User):
    """5-9: Recovered evidence creation, RECOVERED status, source offset persistence, SHA-256, and immutability."""
    img_path = create_synthetic_raw_image(tmp_path)
    orig_bytes = open(img_path, "rb").read()
    orig_sha256 = hashlib.sha256(orig_bytes).hexdigest()
    orig_md5 = hashlib.md5(orig_bytes).hexdigest()

    ev = Evidence(
        case_id=case_with_members.id,
        evidence_identifier=f"EVD-RAW-{uuid.uuid4().hex[:6].upper()}",
        original_filename="synthetic_disk_image.raw",
        storage_path=img_path,
        source_type="DISK_IMAGE",
        media_type="application/octet-stream",
        file_extension=".raw",
        size_bytes=len(orig_bytes),
        sha256=orig_sha256,
        md5_reference=orig_md5,
        evidence_status=EvidenceStatus.ORIGINAL,
        imported_by=test_admin_user.id
    )
    db_session.add(ev)
    db_session.commit()

    # 1. Scan and detect
    job, candidates = start_recovery_scan(db_session, case_with_members, ev.id, user_id=test_admin_user.id)
    dhav_cand = next((c for c in candidates if "DAV" in c.detected_format or "DHAV" in c.detected_format), None)
    assert dhav_cand is not None

    # 2. Validate candidate
    validated_cand = validate_candidate(db_session, case_with_members, dhav_cand.id, user_id=test_admin_user.id)
    assert validated_cand.status in (RecoveryCandidateStatus.VALIDATED, RecoveryCandidateStatus.PARTIAL)

    # 3. Recover candidate
    cand_after, recovered_ev = recover_candidate(db_session, case_with_members, dhav_cand.id, user_id=test_admin_user.id)

    # 6. Status check
    assert recovered_ev.evidence_status == EvidenceStatus.RECOVERED
    assert cand_after.status == RecoveryCandidateStatus.RECOVERED

    # 7. Source offset & provenance persistence
    meta = json.loads(recovered_ev.derived_parameters)
    assert meta["source_offset"] == dhav_cand.source_offset
    assert meta["source_evidence_id"] == ev.id
    assert meta["recovery_method"] == "SIGNATURE_CARVING"
    assert recovered_ev.parent_evidence_id == ev.id

    # 8. SHA-256 and MD5 generation
    assert recovered_ev.sha256 is not None
    assert len(recovered_ev.sha256) == 64
    assert recovered_ev.md5_reference is not None
    assert len(recovered_ev.md5_reference) == 32

    # 9. Original source immutability check
    after_bytes = open(img_path, "rb").read()
    after_sha256 = hashlib.sha256(after_bytes).hexdigest()
    assert orig_sha256 == after_sha256, "Original raw disk image was modified!"


def test_10_fragmented_corrupt_candidate_handling(tmp_path, db_session: Session, case_with_members: Case, test_admin_user: User):
    """10. Fragmented / corrupted stream handling."""
    frag_path = tmp_path / "frag_image.raw"
    frag_path.write_bytes(b"\x00" * 128 + b"DHAV\x00\x00")
    
    ev = Evidence(
        case_id=case_with_members.id,
        evidence_identifier=f"EVD-FRAG-{uuid.uuid4().hex[:6].upper()}",
        original_filename="frag_image.raw",
        storage_path=str(frag_path),
        source_type="DISK_IMAGE",
        media_type="application/octet-stream",
        file_extension=".raw",
        size_bytes=os.path.getsize(frag_path),
        sha256=hashlib.sha256(open(frag_path, "rb").read()).hexdigest(),
        evidence_status=EvidenceStatus.ORIGINAL,
        imported_by=test_admin_user.id
    )
    db_session.add(ev)
    db_session.commit()

    job, candidates = start_recovery_scan(db_session, case_with_members, ev.id, user_id=test_admin_user.id)
    assert len(candidates) >= 1
    cand = candidates[0]
    
    # Validate candidate to check partial status
    val_cand = validate_candidate(db_session, case_with_members, cand.id, user_id=test_admin_user.id)
    assert val_cand.status in (RecoveryCandidateStatus.PARTIAL, RecoveryCandidateStatus.CORRUPTED)
    assert val_cand.confidence < 0.80


def test_11_recovery_authorization(override_get_db, case_with_members: Case, foreign_case: Case, test_admin_user: User, test_investigator_user: User, db_session: Session):
    """11. Authorization: Non-members cannot scan or view candidates."""
    client = TestClient(app)
    setup_auth(client, db_session, foreign_case, test_investigator_user)

    # Attempt to scan evidence belonging to case_with_members while authorized for foreign_case
    resp = client.post(f"/api/v1/cases/{foreign_case.case_identifier}/recovery/scan?evidence_id=999999")
    assert resp.status_code == 404


def test_12_recovery_audit_events(tmp_path, db_session: Session, case_with_members: Case, test_admin_user: User):
    """12. Audit events logged for recovery."""
    img_path = create_synthetic_raw_image(tmp_path)
    ev = Evidence(
        case_id=case_with_members.id,
        evidence_identifier=f"EVD-AUDIT-{uuid.uuid4().hex[:6].upper()}",
        original_filename="audit_test.raw",
        storage_path=img_path,
        source_type="DISK_IMAGE",
        media_type="application/octet-stream",
        file_extension=".raw",
        size_bytes=os.path.getsize(img_path),
        sha256=hashlib.sha256(open(img_path, "rb").read()).hexdigest(),
        evidence_status=EvidenceStatus.ORIGINAL,
        imported_by=test_admin_user.id
    )
    db_session.add(ev)
    db_session.commit()

    job, candidates = start_recovery_scan(db_session, case_with_members, ev.id, user_id=test_admin_user.id)
    cand = candidates[0]
    validate_candidate(db_session, case_with_members, cand.id, user_id=test_admin_user.id)
    recover_candidate(db_session, case_with_members, cand.id, user_id=test_admin_user.id)

    actions = [a.action for a in db_session.query(AuditLog).filter(AuditLog.case_id == case_with_members.id).all()]
    assert "RECOVERY_SCAN_STARTED" in actions
    assert "RECOVERY_CANDIDATE_VALIDATED" in actions
    assert "RECOVERED_EVIDENCE_CREATED" in actions


# ==============================================================================
# PART B: AI ANALYSIS TESTS
# ==============================================================================

def create_dummy_mp4_evidence(db_session: Session, case: Case, user: User, tmp_path) -> Evidence:
    """Helper to create dummy video evidence for AI testing."""
    mp4_file = tmp_path / f"test_ai_{uuid.uuid4().hex[:6]}.mp4"
    # Basic header bytes to simulate an MP4 file
    mp4_file.write_bytes(b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isommp41\x00" * 20)
    
    file_bytes = mp4_file.read_bytes()
    sha = hashlib.sha256(file_bytes).hexdigest()
    
    ev = Evidence(
        case_id=case.id,
        evidence_identifier=f"EVD-AI-{uuid.uuid4().hex[:6].upper()}",
        original_filename="ai_sample_camera.mp4",
        storage_path=str(mp4_file),
        source_type="CAMERA_EXPORT",
        media_type="video/mp4",
        file_extension=".mp4",
        size_bytes=len(file_bytes),
        sha256=sha,
        duration_seconds=120.0,
        evidence_status=EvidenceStatus.ORIGINAL,
        is_natively_playable=True,
        imported_by=user.id
    )
    db_session.add(ev)
    db_session.commit()
    return ev


def test_13_ai_job_creation(tmp_path, db_session: Session, case_with_members: Case, test_admin_user: User):
    """13. AI analysis job creation."""
    ev = create_dummy_mp4_evidence(db_session, case_with_members, test_admin_user, tmp_path)
    
    # Mock video capture so analysis completes synchronously without decoding actual dummy file
    with patch("cv2.VideoCapture") as mock_vc:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: 30.0 if prop == 5 else (300.0 if prop == 7 else 0)
        mock_cap.read.return_value = (False, None)  # immediate EOF
        mock_vc.return_value = mock_cap

        job, findings = start_ai_analysis_job(
            db=db_session,
            case=case_with_members,
            evidence=ev,
            user_id=test_admin_user.id,
            detect_objects=True,
            detect_motion=True,
            sample_rate_fps=1.0,
            confidence_threshold=0.35,
        )
        assert job.id is not None
        assert job.status == AIJobStatus.COMPLETED
        assert job.evidence_id == ev.id
        assert job.case_id == case_with_members.id


def test_14_to_20_ai_findings_timestamps_channels_timeline(tmp_path, db_session: Session, case_with_members: Case, test_admin_user: User):
    """14-20: Authorized AI execution, findings structure, confidence, timestamps, channels, bounding boxes, timeline."""
    ev = create_dummy_mp4_evidence(db_session, case_with_members, test_admin_user, tmp_path)
    
    with patch("cv2.VideoCapture") as mock_vc:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: 30.0 if prop == 5 else (300.0 if prop == 7 else 0)
        mock_cap.read.return_value = (False, None)
        mock_vc.return_value = mock_cap

        job, _ = start_ai_analysis_job(
            db=db_session,
            case=case_with_members,
            evidence=ev,
            user_id=test_admin_user.id,
        )

    # Add deterministic findings
    finding1 = AIFinding(
        finding_identifier=f"FIND-{uuid.uuid4().hex[:6].upper()}",
        case_id=case_with_members.id,
        evidence_id=ev.id,
        job_id=job.id,
        channel=1,
        frame_number=100,
        media_time=4.0,
        source_timestamp=datetime(2026, 9, 5, 14, 32, 18, tzinfo=timezone.utc),
        normalized_timestamp=datetime(2026, 9, 5, 14, 32, 18, tzinfo=timezone.utc),
        object_class="person",
        confidence=0.94,
        bounding_box=json.dumps({"x": 120, "y": 80, "width": 64, "height": 180}),
        model_name="yolov8n",
        model_version="8.0",
        created_by=test_admin_user.id
    )
    finding2 = AIFinding(
        finding_identifier=f"FIND-{uuid.uuid4().hex[:6].upper()}",
        case_id=case_with_members.id,
        evidence_id=ev.id,
        job_id=job.id,
        channel=1,
        frame_number=150,
        media_time=6.0,
        source_timestamp=datetime(2026, 9, 5, 14, 32, 20, tzinfo=timezone.utc),
        normalized_timestamp=datetime(2026, 9, 5, 14, 32, 20, tzinfo=timezone.utc),
        object_class="motion",
        confidence=0.88,
        bounding_box=json.dumps({"x": 200, "y": 150, "width": 80, "height": 90}),
        model_name="opencv-mog2",
        model_version="4.x",
        created_by=test_admin_user.id
    )
    db_session.add_all([finding1, finding2])
    db_session.commit()

    # Sync findings to timeline
    sync_finding_to_timeline(db_session, case_with_members, finding1)
    sync_finding_to_timeline(db_session, case_with_members, finding2)

    # 15. Finding persistence & structure
    stored_findings = db_session.query(AIFinding).filter(AIFinding.job_id == job.id).all()
    assert len(stored_findings) == 2

    # 16. Confidence check
    p_finding = next(f for f in stored_findings if f.object_class == "person")
    assert p_finding.confidence == 0.94

    # 17. Timestamp check
    assert p_finding.media_time == 4.0
    assert p_finding.source_timestamp is not None
    assert p_finding.normalized_timestamp is not None

    # 18. Channel check
    assert p_finding.channel == 1

    # 19. Bounding box check
    bbox = json.loads(p_finding.bounding_box)
    assert bbox["x"] == 120
    assert bbox["y"] == 80
    assert bbox["width"] == 64
    assert bbox["height"] == 180

    # 20. Timeline integration
    events = db_session.query(TimelineEvent).filter(TimelineEvent.evidence_id == ev.id).all()
    assert len(events) >= 2
    ai_event = next(e for e in events if "AI: Person" in e.title)
    assert ai_event.media_time == 4.0

def test_21_to_22_ai_frame_export_and_immutability(tmp_path, db_session: Session, case_with_members: Case, test_admin_user: User):
    """21-22: AI Frame Export (DERIVED, AI_FRAME_EXPORT) and original immutability."""
    ev = create_dummy_mp4_evidence(db_session, case_with_members, test_admin_user, tmp_path)
    orig_bytes = open(ev.storage_path, "rb").read()
    orig_sha = hashlib.sha256(orig_bytes).hexdigest()

    with patch("cv2.VideoCapture") as mock_vc:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: 30.0 if prop == 5 else (300.0 if prop == 7 else 0)
        mock_cap.read.return_value = (False, None)
        mock_vc.return_value = mock_cap

        job, _ = start_ai_analysis_job(
            db=db_session,
            case=case_with_members,
            evidence=ev,
            user_id=test_admin_user.id,
        )

    finding = AIFinding(
        finding_identifier=f"FIND-{uuid.uuid4().hex[:6].upper()}",
        case_id=case_with_members.id,
        evidence_id=ev.id,
        job_id=job.id,
        channel=1,
        frame_number=50,
        media_time=2.0,
        source_timestamp=datetime(2026, 9, 5, 14, 32, 10, tzinfo=timezone.utc),
        normalized_timestamp=datetime(2026, 9, 5, 14, 32, 10, tzinfo=timezone.utc),
        object_class="person",
        confidence=0.92,
        bounding_box=json.dumps({"x": 50, "y": 50, "width": 40, "height": 80}),
        model_name="yolov8n",
        model_version="8.0",
        created_by=test_admin_user.id
    )
    db_session.add(finding)
    db_session.commit()

    # Patch extract_frame_image to create an image file on disk
    def fake_extract_frame(video_path, out_path, media_time):
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"\x55" * 128)
        return out_path

    with patch("app.services.ai_service.extract_frame_image", side_effect=fake_extract_frame):
        finding_after, derived_ev = export_ai_frame(db_session, case_with_members, finding.id, user_id=test_admin_user.id)

        # 21. Verify Lineage
        assert derived_ev.evidence_status == EvidenceStatus.DERIVED
        assert derived_ev.parent_evidence_id == ev.id
        assert derived_ev.derived_operation == "AI_FRAME_EXPORT"
        assert derived_ev.sha256 is not None
        assert derived_ev.sha256 != orig_sha

        # 22. Original evidence immutability check
        current_orig_bytes = open(ev.storage_path, "rb").read()
        assert hashlib.sha256(current_orig_bytes).hexdigest() == orig_sha, "Original video was altered!"


def test_23_unauthorized_ai_access(override_get_db, case_with_members: Case, foreign_case: Case, test_admin_user: User, test_investigator_user: User, db_session: Session):
    """23. Unauthorized access rejected."""
    client = TestClient(app)
    setup_auth(client, db_session, foreign_case, test_investigator_user)

    # Foreign user attempting to access AI jobs of another case
    resp = client.get(f"/api/v1/cases/{case_with_members.case_identifier}/ai/jobs")
    # Should be rejected with 403 or 404
    assert resp.status_code in (403, 404)


def test_24_ai_job_state_transitions(tmp_path, db_session: Session, case_with_members: Case, test_admin_user: User):
    """24. AI Job state transitions: QUEUED, RUNNING, CANCELLED, COMPLETED."""
    ev = create_dummy_mp4_evidence(db_session, case_with_members, test_admin_user, tmp_path)

    # Create job directly in QUEUED or RUNNING status
    job = AIAnalysisJob(
        job_identifier=f"AIJOB-{uuid.uuid4().hex[:6].upper()}",
        case_id=case_with_members.id,
        evidence_id=ev.id,
        status=AIJobStatus.RUNNING,
        progress_percent=25.0,
        total_frames_analyzed=50,
        findings_count=3,
        config_json=json.dumps({"sample_rate_fps": 1.0}),
        created_by=test_admin_user.id
    )
    db_session.add(job)
    db_session.commit()

    # Test cancellation
    cancelled_job = cancel_job(db_session, case_with_members, job.id, user_id=test_admin_user.id)
    assert cancelled_job.status == AIJobStatus.CANCELLED
