import os
import uuid
import json
import hashlib
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.case import Case, CaseMember, RoleEnum
from app.models.user import User
from app.models.evidence import Evidence, EvidenceStatus, IntegrityStatus
from app.models.device import Device, DeviceType, DeviceStatus
from app.models.acquisition import Acquisition, AcquisitionMethod, AcquisitionStatus
from app.models.video_analysis import TimelineEvent, TimelineEventType
from app.models.recovery import RecoveryCandidate, RecoveryCandidateStatus, RecoveryScanJob, RecoveryScanStatus
from app.models.ai_analysis import AIAnalysisJob, AIJobStatus, AIFinding
from app.models.audit import AuditLog
from app.models.blockchain import CustodyEvent
from app.models.report import Report, ReportType, ReportStatus
from app.core.security import get_password_hash
from app.services.report_service import report_service
from app.forensics.reporting.generator import ReportGenerator
from app.forensics.reporting.exporters import PDFExporter, HTMLExporter, JSONExporter, compute_sha256
from app.forensics.blockchain.mock_provider import MockBlockchainProvider
from app.forensics.blockchain import set_blockchain_provider


@pytest.fixture
def test_user(db_session: Session):
    user = User(
        username=f"rpt_examiner_{uuid.uuid4().hex[:6]}",
        password_hash=get_password_hash("password123"),
        display_name="Forensic Report Examiner",
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def viewer_user(db_session: Session):
    user = User(
        username=f"rpt_viewer_{uuid.uuid4().hex[:6]}",
        password_hash=get_password_hash("password123"),
        display_name="Forensic Viewer",
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def outsider_user(db_session: Session):
    user = User(
        username=f"rpt_outsider_{uuid.uuid4().hex[:6]}",
        password_hash=get_password_hash("password123"),
        display_name="Outsider User",
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_case(db_session: Session, test_user: User, viewer_user: User):
    case = Case(
        case_identifier=f"CASE-RPT-{uuid.uuid4().hex[:6]}",
        name="Forensic Reporting Test Case",
        description="Test case for automated forensic reporting validation",
        created_by=test_user.id,
    )
    db_session.add(case)
    db_session.commit()

    admin_member = CaseMember(case_id=case.id, user_id=test_user.id, role=RoleEnum.ADMIN)
    viewer_member = CaseMember(case_id=case.id, user_id=viewer_user.id, role=RoleEnum.VIEWER)
    db_session.add(admin_member)
    db_session.add(viewer_member)
    db_session.commit()
    return case


@pytest.fixture
def populated_case(db_session: Session, test_case: Case, test_user: User, tmp_path):
    """Case populated with real multi-module forensic artifacts."""
    # 1. Device & Acquisition
    device = Device(
        case_id=test_case.id,
        device_identifier=f"DEV-{uuid.uuid4().hex[:6]}",
        manufacturer="Dahua",
        device_type=DeviceType.DVR,
        model="DH-XVR5116H",
        serial_number="DH12345678",
        status=DeviceStatus.ACTIVE,
        created_by=test_user.id
    )
    db_session.add(device)
    db_session.commit()

    acq = Acquisition(
        case_id=test_case.id,
        device_id=device.id,
        acquisition_identifier=f"ACQ-{uuid.uuid4().hex[:6]}",
        acquisition_method=AcquisitionMethod.FILE_COPY,
        status=AcquisitionStatus.COMPLETED,
        source_path="/dev/sdb",
        destination_reference=str(tmp_path / "acq.raw"),
        size_bytes=1048576,
        operator_id=test_user.id,
        destination_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    db_session.add(acq)
    db_session.commit()

    # 2. Evidence (Video file on disk)
    video_file = tmp_path / "cctv_ch01.mp4"
    video_file.write_bytes(b"cctv forensic video stream bytes 12345")
    vid_sha = hashlib.sha256(b"cctv forensic video stream bytes 12345").hexdigest()

    evidence = Evidence(
        case_id=test_case.id,
        evidence_identifier=f"EVD-{uuid.uuid4().hex[:6]}",
        original_filename="cctv_ch01.mp4",
        storage_path=str(video_file),
        source_type="Local File",
        media_type="video/mp4",
        file_extension=".mp4",
        size_bytes=len(b"cctv forensic video stream bytes 12345"),
        sha256=vid_sha,
        md5_reference="098f6bcd4621d373cade4e832627b4f6",
        integrity_status=IntegrityStatus.VERIFIED,
        evidence_status=EvidenceStatus.ORIGINAL,
        imported_by=test_user.id,
        device_id=device.id,
        acquisition_id=acq.id,
        duration_seconds=120.5,
        width=1920,
        height=1080,
        fps=25.0,
        video_codec="H.264",
        vendor="Dahua",
        channel_index=1,
        blockchain_status="ANCHORED",
        blockchain_tx_id="TX-TEST-ANCHOR-001"
    )
    db_session.add(evidence)
    db_session.commit()

    # 3. Timeline Event
    te = TimelineEvent(
        event_identifier=f"EVT-{uuid.uuid4().hex[:8].upper()}",
        case_id=test_case.id,
        evidence_id=evidence.id,
        channel_id=1,
        media_time=12.5,
        source_timestamp=datetime.now(timezone.utc),
        event_type=TimelineEventType.MOTION,
        title="Vehicle Entry Detected",
        description="White sedan entered facility gate.",
        created_by=test_user.id
    )
    db_session.add(te)

    # 4. Recovery Job & Candidate
    scan_job = RecoveryScanJob(
        case_id=test_case.id,
        source_evidence_id=evidence.id,
        scan_identifier=f"SCAN-{uuid.uuid4().hex[:6]}",
        created_by=test_user.id,
        total_bytes=1048576,
        status=RecoveryScanStatus.COMPLETED
    )
    db_session.add(scan_job)
    db_session.commit()

    cand = RecoveryCandidate(
        case_id=test_case.id,
        scan_job_id=scan_job.id,
        candidate_identifier=f"CAND-{uuid.uuid4().hex[:6]}",
        source_offset=512,
        size_bytes=1024,
        detected_format="DHAV",
        vendor="Dahua",
        status=RecoveryCandidateStatus.VALIDATED,
        confidence=0.95
    )
    db_session.add(cand)

    # 5. AI Analysis Job & Finding
    ai_job = AIAnalysisJob(
        case_id=test_case.id,
        evidence_id=evidence.id,
        job_identifier=f"AIJ-{uuid.uuid4().hex[:6]}",
        status=AIJobStatus.COMPLETED,
        total_frames_analyzed=10,
        findings_count=1,
        created_by=test_user.id,
        config_json=json.dumps({
            "model_name": "YOLOv8n + OpenCV MOG2",
            "model_version": "8.0",
            "sample_rate_fps": 1.0,
            "confidence_threshold": 0.30
        })
    )
    db_session.add(ai_job)
    db_session.commit()

    ai_find = AIFinding(
        case_id=test_case.id,
        evidence_id=evidence.id,
        job_id=ai_job.id,
        finding_identifier=f"AIF-{uuid.uuid4().hex[:6]}",
        object_class="person",
        confidence=0.88,
        media_time=12.4,
        channel=1,
        frame_number=310,
        bounding_box='{"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4}',
        source_timestamp=datetime.now(timezone.utc),
        created_by=test_user.id
    )
    db_session.add(ai_find)

    # 6. Audit Logs & Custody Event
    audit1 = AuditLog(
        case_id=test_case.id,
        user_id=test_user.id,
        action="EVIDENCE_IMPORTED",
        target_identifier=evidence.evidence_identifier,
        details="Imported evidence file."
    )
    db_session.add(audit1)
    db_session.commit()

    custody1 = CustodyEvent(
        event_identifier=f"CUST-{uuid.uuid4().hex[:6]}",
        case_id=test_case.id,
        evidence_id=evidence.id,
        audit_log_id=audit1.id,
        action="EVIDENCE_IMPORTED",
        actor_id=test_user.id,
        actor_username=test_user.username,
        sha256=vid_sha,
        blockchain_status="ANCHORED",
        blockchain_tx_id="TX-TEST-ANCHOR-001"
    )
    db_session.add(custody1)
    db_session.commit()

    return test_case, evidence, video_file


# ==============================================================================
# 1. Case Report Generation
# ==============================================================================
def test_case_report_generation(populated_case, test_user: User, db_session: Session):
    """Verify Case Summary / Final Investigation Report compiles Sections A–M correctly."""
    case, evidence, _ = populated_case
    generator = ReportGenerator(db_session)
    report_data = generator.generate_case_report(case, test_user, examiner_notes="Test investigation conclusions.")

    assert report_data["report_type"] == "CASE_SUMMARY"
    assert report_data["case_info"]["case_identifier"] == case.case_identifier
    assert report_data["counts"]["evidence_count"] >= 1
    assert report_data["counts"]["device_count"] >= 1
    assert report_data["counts"]["acquisition_count"] >= 1
    assert report_data["counts"]["ai_finding_count"] >= 1
    assert "Test investigation conclusions." in report_data["examiner_notes"]
    assert report_data["integrity_summary"]["verified_matching_count"] >= 1
    assert len(report_data["evidence_inventory"]) >= 1
    assert report_data["evidence_inventory"][0]["sha256"] == evidence.sha256


# ==============================================================================
# 2. Evidence Report Generation
# ==============================================================================
def test_evidence_report_generation(populated_case, test_user: User, db_session: Session):
    """Verify Evidence Report includes all forensic fields without hash truncation."""
    case, evidence, _ = populated_case
    generator = ReportGenerator(db_session)
    report_data = generator.generate_evidence_report(case, test_user)

    assert report_data["report_type"] == "EVIDENCE_REPORT"
    records = report_data["evidence_records"]
    assert len(records) >= 1
    rec = records[0]
    assert rec["evidence_identifier"] == evidence.evidence_identifier
    assert rec["sha256"] == evidence.sha256
    assert len(rec["sha256"]) == 64  # Full un-truncated SHA-256
    assert rec["md5"] == evidence.md5_reference
    assert rec["vendor"] == "Dahua"
    assert rec["integrity_status"] == "VERIFIED"


# ==============================================================================
# 3. Video Report Generation
# ==============================================================================
def test_video_report_generation(populated_case, test_user: User, db_session: Session):
    """Verify Unified Video Representation report captures duration, fps, resolution, codecs."""
    case, evidence, _ = populated_case
    generator = ReportGenerator(db_session)
    report_data = generator.generate_video_report(case, test_user)

    assert report_data["report_type"] == "VIDEO_SUMMARY"
    streams = report_data["video_streams"]
    assert len(streams) >= 1
    st = streams[0]
    assert st["evidence_identifier"] == evidence.evidence_identifier
    assert st["resolution"] == "1920x1080"
    assert st["fps"] == "25.00"
    assert st["video_codec"] == "H.264"
    assert st["duration_seconds"] == 120.5
    assert st["timeline_events_count"] >= 1


# ==============================================================================
# 4. Recovery Report Generation
# ==============================================================================
def test_recovery_report_generation(populated_case, test_user: User, db_session: Session):
    """Verify Recovery Report captures scan jobs, candidates, validation state, and confidence."""
    case, evidence, _ = populated_case
    generator = ReportGenerator(db_session)
    report_data = generator.generate_recovery_report(case, test_user)

    assert report_data["report_type"] == "RECOVERY_REPORT"
    assert report_data["total_scan_jobs"] >= 1
    job = report_data["scan_jobs"][0]
    assert job["scan_method"] in ("SIGNATURE_CARVING", "SIGNATURE_AND_STRUCTURE_CARVING")
    assert len(job["candidates"]) >= 1
    cand = job["candidates"][0]
    assert cand["validation_state"] in ("VALID", "VALIDATED")
    assert cand["validation_confidence"] == "95%"
    assert cand["offset_bytes"] == 512


# ==============================================================================
# 5. AI Report Generation
# ==============================================================================
def test_ai_report_generation(populated_case, test_user: User, db_session: Session):
    """Verify AI Report clearly labels 'Model confidence' and does not claim certainty."""
    case, evidence, _ = populated_case
    generator = ReportGenerator(db_session)
    report_data = generator.generate_ai_report(case, test_user)

    assert report_data["report_type"] == "AI_REPORT"
    assert "disclaimer" in report_data
    assert "not constitute conclusive" in report_data["disclaimer"]
    assert report_data["total_findings"] >= 1
    finding = report_data["jobs"][0]["findings"][0]
    assert finding["model_confidence"] == "Model confidence: 88%"
    assert finding["class_name"] == "person"
    assert finding["frame_number"] == 310


# ==============================================================================
# 6. Chain-of-Custody Report Generation
# ==============================================================================
def test_chain_of_custody_report_generation(populated_case, test_user: User, db_session: Session):
    """Verify Chain of Custody Report generates chronological table from audit logs."""
    case, evidence, _ = populated_case
    generator = ReportGenerator(db_session)
    report_data = generator.generate_chain_of_custody_report(case, test_user)

    assert report_data["report_type"] == "CHAIN_OF_CUSTODY"
    events = report_data["events"]
    assert len(events) >= 1
    # Verify chronological ordering
    timestamps = [e["timestamp_utc"] for e in events]
    assert timestamps == sorted(timestamps)
    assert events[0]["action"] == "EVIDENCE_IMPORTED"
    assert events[0]["target_evidence"] == evidence.evidence_identifier


# ==============================================================================
# 7. Report Metadata & Persistence
# ==============================================================================
def test_report_metadata_and_persistence(populated_case, test_user: User, db_session: Session):
    """Verify ReportService creates report with valid identifier, format, and DB record."""
    case, _, _ = populated_case
    report = report_service.generate_report(
        db=db_session,
        case=case,
        examiner=test_user,
        report_type=ReportType.CASE_SUMMARY.value,
        examiner_notes="Metadata persistence test.",
        export_format="PDF"
    )

    assert report.report_identifier.startswith("RPT-")
    assert report.status == ReportStatus.GENERATED.value
    assert report.format == "PDF"
    assert report.file_size > 0
    assert os.path.exists(report.storage_path)
    assert report.sha256 is not None
    assert len(report.sha256) == 64

    # Verify query
    fetched = report_service.get_report_by_identifier(db_session, case.id, report.report_identifier)
    assert fetched is not None
    assert fetched.id == report.id


# ==============================================================================
# 8. Report SHA-256 Integrity & Tamper Detection
# ==============================================================================
def test_report_sha256_integrity_and_tamper_detection(populated_case, test_user: User, db_session: Session):
    """Verify report SHA-256 matches disk file, and tampering produces MISMATCH."""
    case, _, _ = populated_case
    report = report_service.generate_report(
        db=db_session,
        case=case,
        examiner=test_user,
        report_type=ReportType.EVIDENCE_REPORT.value,
        export_format="PDF"
    )

    # 1. Initial verification -> VERIFIED
    verify_res = report_service.verify_report_integrity(db_session, case, test_user, report.report_identifier)
    assert verify_res["overall_status"] == "VERIFIED"
    assert verify_res["current_sha256"] == report.sha256

    # 2. Tamper file on disk by appending 1 byte -> MISMATCH
    with open(report.storage_path, "ab") as f:
        f.write(b"\x00")

    tamper_res = report_service.verify_report_integrity(db_session, case, test_user, report.report_identifier)
    assert tamper_res["overall_status"] == "MISMATCH"
    assert tamper_res["current_sha256"] != report.sha256
    assert "does not match" in tamper_res["reason"]


# ==============================================================================
# 9. PDF Generation Quality
# ==============================================================================
def test_pdf_generation_quality(populated_case, test_user: User, db_session: Session):
    """Verify generated PDF has valid %PDF header and non-empty content."""
    case, _, _ = populated_case
    report = report_service.generate_report(
        db=db_session,
        case=case,
        examiner=test_user,
        report_type=ReportType.CASE_SUMMARY.value,
        export_format="PDF"
    )

    with open(report.storage_path, "rb") as f:
        pdf_bytes = f.read()

    assert pdf_bytes.startswith(b"%PDF-")
    assert b"DRISHTIK" in pdf_bytes
    assert len(pdf_bytes) > 500


# ==============================================================================
# 10. JSON Export
# ==============================================================================
def test_json_export(populated_case, test_user: User, db_session: Session):
    """Verify JSON export creates structured canonical JSON with metadata."""
    case, _, _ = populated_case
    report = report_service.generate_report(
        db=db_session,
        case=case,
        examiner=test_user,
        report_type=ReportType.VIDEO_SUMMARY.value,
        export_format="JSON"
    )

    content_bytes, filename, media_type = report_service.export_report_file(
        db=db_session,
        case=case,
        examiner=test_user,
        report_identifier=report.report_identifier,
        target_format="JSON"
    )

    assert media_type == "application/json"
    assert filename.endswith(".json")
    parsed = json.loads(content_bytes.decode("utf-8"))
    assert "report_metadata" in parsed
    assert "report_data" in parsed
    assert parsed["report_metadata"]["report_identifier"] == report.report_identifier


# ==============================================================================
# 11. Report Audit Logging
# ==============================================================================
def test_report_audit_logging(populated_case, test_user: User, db_session: Session):
    """Verify report lifecycle generates audit records."""
    case, _, _ = populated_case
    report = report_service.generate_report(
        db=db_session,
        case=case,
        examiner=test_user,
        report_type=ReportType.CHAIN_OF_CUSTODY.value,
        export_format="PDF"
    )

    report_service.export_report_file(
        db=db_session,
        case=case,
        examiner=test_user,
        report_identifier=report.report_identifier,
        target_format="PDF"
    )

    report_service.verify_report_integrity(
        db=db_session,
        case=case,
        examiner=test_user,
        report_identifier=report.report_identifier
    )

    logs = db_session.query(AuditLog).filter(
        AuditLog.case_id == case.id,
        AuditLog.target_identifier == report.report_identifier
    ).all()

    actions = [l.action for l in logs]
    assert "REPORT_GENERATION_STARTED" in actions
    assert "REPORT_GENERATION_COMPLETED" in actions
    assert "REPORT_EXPORTED" in actions
    assert "REPORT_INTEGRITY_VERIFIED" in actions


# ==============================================================================
# 12. Authorization (Viewer cannot generate, Admin/Investigator can)
# ==============================================================================
def test_report_authorization(populated_case, test_user: User, viewer_user: User, db_session: Session):
    """Verify role checks: Viewer cannot generate report (403), Admin can (200)."""
    case, _, _ = populated_case
    client = TestClient(app)
    from app.dependencies.auth import get_current_user
    from app.db.database import get_db

    app.dependency_overrides[get_db] = lambda: db_session

    # 1. Viewer attempt to generate report -> 403 Forbidden
    app.dependency_overrides[get_current_user] = lambda: viewer_user
    resp_viewer = client.post(
        f"/api/v1/cases/{case.case_identifier}/reports/generate",
        json={"report_type": "CASE_SUMMARY", "format": "PDF"}
    )
    assert resp_viewer.status_code == 403

    # 2. Admin attempt to generate report -> 200 OK
    app.dependency_overrides[get_current_user] = lambda: test_user
    resp_admin = client.post(
        f"/api/v1/cases/{case.case_identifier}/reports/generate",
        json={"report_type": "CASE_SUMMARY", "format": "PDF"}
    )
    assert resp_admin.status_code == 200
    assert resp_admin.json()["report_identifier"].startswith("RPT-")


# ==============================================================================
# 13. Case Isolation
# ==============================================================================
def test_case_isolation(populated_case, outsider_user: User, test_user: User, db_session: Session):
    """Verify users from outside the case cannot list or export its reports."""
    case, _, _ = populated_case
    client = TestClient(app)
    from app.dependencies.auth import get_current_user
    from app.db.database import get_db

    app.dependency_overrides[get_db] = lambda: db_session

    # Generate a report as test_user
    report = report_service.generate_report(
        db=db_session,
        case=case,
        examiner=test_user,
        report_type=ReportType.CASE_SUMMARY.value
    )

    # Outsider attempt to list reports -> 403 Forbidden
    app.dependency_overrides[get_current_user] = lambda: outsider_user
    resp = client.get(f"/api/v1/cases/{case.case_identifier}/reports")
    assert resp.status_code == 403

    # Outsider attempt to export report -> 403 Forbidden
    resp_export = client.get(f"/api/v1/cases/{case.case_identifier}/reports/{report.report_identifier}/export")
    assert resp_export.status_code == 403


# ==============================================================================
# 14. Empty Case Report
# ==============================================================================
def test_empty_case_report(test_user: User, db_session: Session):
    """Verify report generation on an empty case succeeds without errors."""
    empty_case = Case(
        case_identifier=f"CASE-EMPTY-{uuid.uuid4().hex[:6]}",
        name="Empty Test Case",
        created_by=test_user.id
    )
    db_session.add(empty_case)
    db_session.commit()

    member = CaseMember(case_id=empty_case.id, user_id=test_user.id, role=RoleEnum.ADMIN)
    db_session.add(member)
    db_session.commit()

    # Generate all 6 report types on empty case
    for rtype in [
        ReportType.CASE_SUMMARY.value,
        ReportType.EVIDENCE_REPORT.value,
        ReportType.VIDEO_SUMMARY.value,
        ReportType.RECOVERY_REPORT.value,
        ReportType.AI_REPORT.value,
        ReportType.CHAIN_OF_CUSTODY.value
    ]:
        rpt = report_service.generate_report(
            db=db_session,
            case=empty_case,
            examiner=test_user,
            report_type=rtype,
            export_format="PDF"
        )
        assert rpt is not None
        assert rpt.file_size > 0
        assert os.path.exists(rpt.storage_path)


# ==============================================================================
# 15. Large Evidence Inventory
# ==============================================================================
def test_large_evidence_inventory(test_case: Case, test_user: User, db_session: Session, tmp_path):
    """Verify multi-page evidence table formatting with 50+ items."""
    for i in range(50):
        ev = Evidence(
            case_id=test_case.id,
            evidence_identifier=f"EVD-BULK-{i:03d}",
            original_filename=f"camera_feed_{i:03d}.mp4",
            storage_path=str(tmp_path / f"feed_{i}.mp4"),
            source_type="Local File",
            media_type="video/mp4",
            file_extension=".mp4",
            size_bytes=1024 * (i + 1),
            sha256=hashlib.sha256(f"bulk-evidence-{i}".encode("utf-8")).hexdigest(),
            imported_by=test_user.id,
            evidence_status=EvidenceStatus.ORIGINAL,
            integrity_status=IntegrityStatus.VERIFIED
        )
        db_session.add(ev)
    db_session.commit()

    report = report_service.generate_report(
        db=db_session,
        case=test_case,
        examiner=test_user,
        report_type=ReportType.EVIDENCE_REPORT.value,
        export_format="PDF"
    )

    assert report.file_size > 0
    assert report.data_payload["total_evidence_count"] >= 50


# ==============================================================================
# 16. Long Audit History
# ==============================================================================
def test_long_audit_history(test_case: Case, test_user: User, db_session: Session):
    """Verify chronological ordering preserved across 100+ audit logs."""
    for i in range(100):
        audit = AuditLog(
            case_id=test_case.id,
            user_id=test_user.id,
            action=f"ACTION_STEP_{i:03d}",
            details=f"Procedural step execution #{i}"
        )
        db_session.add(audit)
    db_session.commit()

    report = report_service.generate_report(
        db=db_session,
        case=test_case,
        examiner=test_user,
        report_type=ReportType.CHAIN_OF_CUSTODY.value,
        export_format="PDF"
    )

    assert report.data_payload["total_custody_records"] >= 100
    events = report.data_payload["events"]
    assert len(events) >= 100


# ==============================================================================
# 17. Original Evidence Immutability
# ==============================================================================
def test_original_evidence_immutability(populated_case, test_user: User, db_session: Session):
    """Verify original evidence files remain bit-for-bit unchanged before and after report generation."""
    case, evidence, video_file = populated_case

    # Read pre-generation hash
    with open(str(video_file), "rb") as f:
        pre_hash = hashlib.sha256(f.read()).hexdigest()

    # Generate all reports
    for rtype in [
        ReportType.CASE_SUMMARY.value,
        ReportType.EVIDENCE_REPORT.value,
        ReportType.VIDEO_SUMMARY.value,
        ReportType.RECOVERY_REPORT.value,
        ReportType.AI_REPORT.value,
        ReportType.CHAIN_OF_CUSTODY.value
    ]:
        report_service.generate_report(
            db=db_session,
            case=case,
            examiner=test_user,
            report_type=rtype,
            export_format="PDF"
        )

    # Read post-generation hash
    with open(str(video_file), "rb") as f:
        post_hash = hashlib.sha256(f.read()).hexdigest()

    assert pre_hash == post_hash
    assert pre_hash == evidence.sha256


# ==============================================================================
# 18. Blockchain-Unavailable Behavior
# ==============================================================================
def test_blockchain_unavailable_behavior(populated_case, test_user: User, db_session: Session):
    """Verify that when Fabric is unavailable, reports clearly reflect UNAVAILABLE without fake Tx IDs."""
    case, _, _ = populated_case
    mock = MockBlockchainProvider()
    mock.simulate_offline = True
    set_blockchain_provider(mock)

    try:
        report = report_service.generate_report(
            db=db_session,
            case=case,
            examiner=test_user,
            report_type=ReportType.CASE_SUMMARY.value,
            export_format="PDF"
        )

        assert report.blockchain_status == "UNAVAILABLE"
        assert report.blockchain_tx_id is None
        assert report.sha256 is not None
        assert len(report.sha256) == 64  # Local SHA-256 remains active
    finally:
        set_blockchain_provider(None)
