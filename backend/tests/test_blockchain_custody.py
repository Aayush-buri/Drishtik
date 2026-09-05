import pytest
import io
import os
import uuid
import hashlib
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.config import settings
from app.models.case import Case, CaseMember, RoleEnum
from app.models.user import User
from app.models.evidence import Evidence, IntegrityStatus, EvidenceStatus
from app.models.blockchain import CustodyEvent, BlockchainAnchor, BlockchainAnchorStatus, CustodyVerificationStatus
from app.models.audit import AuditLog
from app.core.security import get_password_hash
from app.forensics.blockchain.provider import BlockchainProvider, AnchorResult, VerificationResult
from app.forensics.blockchain.fabric_provider import HyperledgerFabricProvider
from app.forensics.blockchain.mock_provider import MockBlockchainProvider
from app.forensics.blockchain import set_blockchain_provider, get_blockchain_provider
from app.services.blockchain_service import (
    record_custody_and_anchor,
    verify_blockchain_integrity,
    list_case_custody_events,
    get_evidence_blockchain_status,
    get_blockchain_health,
)


@pytest.fixture
def test_user(db_session: Session):
    user = User(
        username=f"bc_examiner_{uuid.uuid4().hex[:6]}",
        password_hash=get_password_hash("password123"),
        display_name="Forensic Blockchain Examiner",
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def viewer_user(db_session: Session):
    user = User(
        username=f"bc_viewer_{uuid.uuid4().hex[:6]}",
        password_hash=get_password_hash("password123"),
        display_name="Forensic Viewer",
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_case(db_session: Session, test_user: User, viewer_user: User):
    case = Case(
        case_identifier=f"CASE-BC-{uuid.uuid4().hex[:6]}",
        name="Blockchain Forensic Test Case",
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
def mock_provider():
    mock = MockBlockchainProvider()
    set_blockchain_provider(mock)
    yield mock
    set_blockchain_provider(None)


# ==============================================================================
# 1. BlockchainProvider interface compliance
# ==============================================================================
def test_blockchain_provider_interface():
    """Verify BlockchainProvider is an ABC and requires all core methods."""
    with pytest.raises(TypeError):
        BlockchainProvider()  # Cannot instantiate abstract class

    mock = MockBlockchainProvider()
    assert isinstance(mock, BlockchainProvider)
    assert hasattr(mock, "anchor_evidence")
    assert hasattr(mock, "anchor_custody_event")
    assert hasattr(mock, "verify_anchor")
    assert hasattr(mock, "get_transaction")
    assert hasattr(mock, "health_check")


# ==============================================================================
# 2. Fabric provider initialization & health check
# ==============================================================================
def test_fabric_provider_initialization_and_health():
    """Verify HyperledgerFabricProvider initializes cleanly and handles offline peer without crashing."""
    fabric = HyperledgerFabricProvider()
    assert fabric.channel_name == settings.FABRIC_CHANNEL_NAME
    assert fabric.chaincode_name == settings.FABRIC_CHAINCODE_NAME

    health = fabric.health_check()
    assert health["available"] is False
    assert health["status"] == "UNAVAILABLE"
    assert "Hyperledger Fabric" in health["network"]


# ==============================================================================
# 3. Anchor creation & schema validation
# ==============================================================================
def test_anchor_creation_and_schema_validation(test_case: Case, test_user: User, db_session: Session, mock_provider: MockBlockchainProvider):
    """Verify CustodyEvent and BlockchainAnchor models validate fields and relationships."""
    test_content = b"forensic sample video data 001"
    sha256_hash = hashlib.sha256(test_content).hexdigest()

    evidence = Evidence(
        case_id=test_case.id,
        evidence_identifier=f"EVID-{uuid.uuid4().hex[:6]}",
        original_filename="sample_cctv.mp4",
        storage_path="/tmp/fake_path.mp4",
        source_type="Imported",
        size_bytes=len(test_content),
        sha256=sha256_hash,
        file_extension="mp4",
        media_type="Video",
        imported_by=test_user.id,
        evidence_status=EvidenceStatus.ORIGINAL,
        integrity_status=IntegrityStatus.VERIFIED,
    )
    db_session.add(evidence)
    db_session.commit()

    custody_ev = record_custody_and_anchor(
        db=db_session,
        case=test_case,
        evidence=evidence,
        action="EVIDENCE_IMPORTED",
        user_id=test_user.id,
        username=test_user.username,
        metadata={"filename": evidence.original_filename},
    )

    assert custody_ev is not None
    assert custody_ev.evidence_id == evidence.id
    assert custody_ev.case_id == test_case.id
    assert custody_ev.action == "EVIDENCE_IMPORTED"
    assert custody_ev.actor_username == test_user.username
    assert custody_ev.sha256 == sha256_hash
    assert custody_ev.blockchain_status == BlockchainAnchorStatus.ANCHORED

    anchor = db_session.query(BlockchainAnchor).filter(BlockchainAnchor.evidence_id == evidence.id).first()
    assert anchor is not None
    assert anchor.sha256 == sha256_hash
    assert anchor.transaction_id.lower().startswith("tx")
    assert anchor.block_number is not None


# ==============================================================================
# 4. Evidence SHA-256 anchoring
# ==============================================================================
def test_evidence_sha256_anchoring(test_case: Case, test_user: User, db_session: Session, mock_provider: MockBlockchainProvider):
    """Verify evidence SHA-256 is correctly anchored to blockchain."""
    test_bytes = b"real-cctv-stream-bytes"
    expected_sha = hashlib.sha256(test_bytes).hexdigest()

    evidence = Evidence(
        case_id=test_case.id,
        evidence_identifier=f"EVID-{uuid.uuid4().hex[:6]}",
        original_filename="dahua_ch1.mp4",
        storage_path="/tmp/dahua_ch1.mp4",
        source_type="Imported",
        size_bytes=len(test_bytes),
        sha256=expected_sha,
        file_extension="mp4",
        media_type="Video",
        imported_by=test_user.id,
        evidence_status=EvidenceStatus.ORIGINAL,
        integrity_status=IntegrityStatus.VERIFIED,
    )
    db_session.add(evidence)
    db_session.commit()

    record_custody_and_anchor(
        db=db_session,
        case=test_case,
        evidence=evidence,
        action="EVIDENCE_IMPORTED",
        user_id=test_user.id,
        username=test_user.username,
    )

    db_session.refresh(evidence)
    assert evidence.blockchain_status == BlockchainAnchorStatus.ANCHORED
    assert evidence.blockchain_tx_id is not None
    assert evidence.blockchain_anchored_at is not None

    tx_data = mock_provider.get_transaction(evidence.blockchain_tx_id)
    assert tx_data is not None
    assert tx_data["sha256"] == expected_sha
    assert tx_data["case_identifier"] == test_case.case_identifier


# ==============================================================================
# 5. Custody event anchoring lineage
# ==============================================================================
def test_custody_event_anchoring_lineage(test_case: Case, test_user: User, db_session: Session, mock_provider: MockBlockchainProvider):
    """Verify contiguous previous_event_reference chain across multiple events."""
    evidence = Evidence(
        case_id=test_case.id,
        evidence_identifier=f"EVID-{uuid.uuid4().hex[:6]}",
        original_filename="cctv_feed.mp4",
        storage_path="/tmp/cctv_feed.mp4",
        source_type="Imported",
        size_bytes=1000,
        sha256=hashlib.sha256(b"stream1").hexdigest(),
        file_extension="mp4",
        media_type="Video",
        imported_by=test_user.id,
        evidence_status=EvidenceStatus.ORIGINAL,
        integrity_status=IntegrityStatus.VERIFIED,
    )
    db_session.add(evidence)
    db_session.commit()

    # Event 1: Import (Genesis event for this evidence)
    ev1 = record_custody_and_anchor(
        db=db_session,
        case=test_case,
        evidence=evidence,
        action="EVIDENCE_IMPORTED",
        user_id=test_user.id,
        username=test_user.username,
    )
    assert ev1.previous_event_reference is None

    # Event 2: Acquisition / Verification
    ev2 = record_custody_and_anchor(
        db=db_session,
        case=test_case,
        evidence=evidence,
        action="ACQUISITION_COMPLETED",
        user_id=test_user.id,
        username=test_user.username,
    )
    assert ev2.previous_event_reference == ev1.event_identifier

    # Event 3: Integrity verification
    ev3 = record_custody_and_anchor(
        db=db_session,
        case=test_case,
        evidence=evidence,
        action="INTEGRITY_VERIFIED",
        user_id=test_user.id,
        username=test_user.username,
    )
    assert ev3.previous_event_reference == ev2.event_identifier


# ==============================================================================
# 6. Transaction ID persistence
# ==============================================================================
def test_transaction_id_persistence(test_case: Case, test_user: User, db_session: Session, mock_provider: MockBlockchainProvider):
    """Verify transaction IDs are saved, indexed, and retrievable."""
    evidence = Evidence(
        case_id=test_case.id,
        evidence_identifier=f"EVID-{uuid.uuid4().hex[:6]}",
        original_filename="persist_test.mp4",
        storage_path="/tmp/persist_test.mp4",
        source_type="Imported",
        size_bytes=500,
        sha256=hashlib.sha256(b"persist").hexdigest(),
        file_extension="mp4",
        media_type="Video",
        imported_by=test_user.id,
        evidence_status=EvidenceStatus.ORIGINAL,
        integrity_status=IntegrityStatus.VERIFIED,
    )
    db_session.add(evidence)
    db_session.commit()

    custody_ev = record_custody_and_anchor(
        db=db_session,
        case=test_case,
        evidence=evidence,
        action="EVIDENCE_IMPORTED",
        user_id=test_user.id,
        username=test_user.username,
    )

    found_anchor = db_session.query(BlockchainAnchor).filter(BlockchainAnchor.evidence_id == evidence.id).first()
    assert found_anchor is not None
    assert found_anchor.transaction_id == custody_ev.blockchain_tx_id

    status = get_evidence_blockchain_status(db=db_session, case=test_case, evidence=evidence)
    assert status["transaction_id"] == custody_ev.blockchain_tx_id
    assert len(status["anchors"]) >= 1


# ==============================================================================
# 7. Verification success (3-point check)
# ==============================================================================
def test_verification_success(test_case: Case, test_user: User, db_session: Session, mock_provider: MockBlockchainProvider, tmp_path):
    """Verify 3-point check succeeds when disk == database == blockchain."""
    real_file = tmp_path / "authentic_video.mp4"
    file_bytes = b"unaltered original cctv video data"
    real_file.write_bytes(file_bytes)
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()

    evidence = Evidence(
        case_id=test_case.id,
        evidence_identifier=f"EVID-{uuid.uuid4().hex[:6]}",
        original_filename="authentic_video.mp4",
        storage_path=str(real_file),
        source_type="Imported",
        size_bytes=len(file_bytes),
        sha256=sha256_hash,
        file_extension="mp4",
        media_type="Video",
        imported_by=test_user.id,
        evidence_status=EvidenceStatus.ORIGINAL,
        integrity_status=IntegrityStatus.VERIFIED,
    )
    db_session.add(evidence)
    db_session.commit()

    record_custody_and_anchor(
        db=db_session,
        case=test_case,
        evidence=evidence,
        action="EVIDENCE_IMPORTED",
        user_id=test_user.id,
        username=test_user.username,
    )

    res = verify_blockchain_integrity(
        db=db_session,
        case=test_case,
        evidence=evidence,
        user_id=test_user.id,
        username=test_user.username,
    )

    assert res["overall_status"] == "VERIFIED"
    assert res["current_sha256"] == sha256_hash
    assert res["recorded_sha256"] == sha256_hash
    assert res["anchored_sha256"] == sha256_hash
    assert "Cryptographic 3-point verification passed" in res["reason"]


# ==============================================================================
# 8. Verification mismatch (Tampering detection)
# ==============================================================================
def test_verification_mismatch_detection(test_case: Case, test_user: User, db_session: Session, mock_provider: MockBlockchainProvider, tmp_path):
    """Verify mismatch is detected if disk content is altered after blockchain anchor."""
    real_file = tmp_path / "tamper_target.mp4"
    file_bytes = b"original forensic footage"
    real_file.write_bytes(file_bytes)
    original_sha = hashlib.sha256(file_bytes).hexdigest()

    evidence = Evidence(
        case_id=test_case.id,
        evidence_identifier=f"EVID-{uuid.uuid4().hex[:6]}",
        original_filename="tamper_target.mp4",
        storage_path=str(real_file),
        source_type="Imported",
        size_bytes=len(file_bytes),
        sha256=original_sha,
        file_extension="mp4",
        media_type="Video",
        imported_by=test_user.id,
        evidence_status=EvidenceStatus.ORIGINAL,
        integrity_status=IntegrityStatus.VERIFIED,
    )
    db_session.add(evidence)
    db_session.commit()

    record_custody_and_anchor(
        db=db_session,
        case=test_case,
        evidence=evidence,
        action="EVIDENCE_IMPORTED",
        user_id=test_user.id,
        username=test_user.username,
    )

    # Tamper with the file on disk!
    real_file.write_bytes(b"tampered footage with edited frames")

    res = verify_blockchain_integrity(
        db=db_session,
        case=test_case,
        evidence=evidence,
        user_id=test_user.id,
        username=test_user.username,
    )

    assert res["overall_status"] == "MISMATCH"
    assert res["current_sha256"] != original_sha
    assert res["anchored_sha256"] == original_sha
    assert "Current file SHA-256" in res["reason"]


# ==============================================================================
# 9. Fabric unavailable behavior (Non-blocking fallback)
# ==============================================================================
def test_fabric_unavailable_graceful_degradation(test_case: Case, test_user: User, db_session: Session, mock_provider: MockBlockchainProvider):
    """Verify operations proceed normally when blockchain is offline without raising unhandled exceptions."""
    mock_provider.simulate_offline = True

    evidence = Evidence(
        case_id=test_case.id,
        evidence_identifier=f"EVID-{uuid.uuid4().hex[:6]}",
        original_filename="offline_test.mp4",
        storage_path="/tmp/offline_test.mp4",
        source_type="Imported",
        size_bytes=800,
        sha256=hashlib.sha256(b"offline_data").hexdigest(),
        file_extension="mp4",
        media_type="Video",
        imported_by=test_user.id,
        evidence_status=EvidenceStatus.ORIGINAL,
        integrity_status=IntegrityStatus.VERIFIED,
    )
    db_session.add(evidence)
    db_session.commit()

    custody_ev = record_custody_and_anchor(
        db=db_session,
        case=test_case,
        evidence=evidence,
        action="EVIDENCE_IMPORTED",
        user_id=test_user.id,
        username=test_user.username,
    )

    assert custody_ev.blockchain_status == BlockchainAnchorStatus.UNAVAILABLE
    assert custody_ev.blockchain_tx_id is None
    assert evidence.blockchain_status == BlockchainAnchorStatus.UNAVAILABLE
    assert custody_ev.sha256 == evidence.sha256

    mock_provider.simulate_offline = False


# ==============================================================================
# 10. Authorization & Case Isolation
# ==============================================================================
def test_blockchain_authorization_and_case_isolation(test_case: Case, test_user: User, viewer_user: User, db_session: Session, mock_provider: MockBlockchainProvider):
    """Verify role authorization for blockchain operations."""
    client = TestClient(app)
    from app.dependencies.auth import get_current_user
    from app.db.database import get_db

    app.dependency_overrides[get_db] = lambda: db_session

    evidence = Evidence(
        case_id=test_case.id,
        evidence_identifier=f"EVID-{uuid.uuid4().hex[:6]}",
        original_filename="auth_test.mp4",
        storage_path="/tmp/auth_test.mp4",
        source_type="Imported",
        size_bytes=100,
        sha256=hashlib.sha256(b"auth_check").hexdigest(),
        file_extension="mp4",
        media_type="Video",
        imported_by=test_user.id,
        evidence_status=EvidenceStatus.ORIGINAL,
        integrity_status=IntegrityStatus.VERIFIED,
    )
    db_session.add(evidence)
    db_session.commit()

    # 1. Viewer CAN query health & custody events (read-only)
    app.dependency_overrides[get_current_user] = lambda: viewer_user
    health_resp = client.get(f"/api/v1/cases/{test_case.case_identifier}/blockchain/health")
    assert health_resp.status_code == 200

    custody_resp = client.get(f"/api/v1/cases/{test_case.case_identifier}/blockchain/custody-events")
    assert custody_resp.status_code == 200

    # 2. Viewer CANNOT trigger anchoring (requires Investigator or Admin)
    anchor_resp = client.post(f"/api/v1/cases/{test_case.case_identifier}/evidence/{evidence.id}/blockchain/anchor")
    assert anchor_resp.status_code == 403

    # 3. Admin CAN trigger anchoring
    app.dependency_overrides[get_current_user] = lambda: test_user
    admin_anchor_resp = client.post(f"/api/v1/cases/{test_case.case_identifier}/evidence/{evidence.id}/blockchain/anchor")
    assert admin_anchor_resp.status_code == 200

    app.dependency_overrides.clear()


# ==============================================================================
# 11. Audit logging for blockchain operations
# ==============================================================================
def test_audit_logging_blockchain_events(test_case: Case, test_user: User, db_session: Session, mock_provider: MockBlockchainProvider, tmp_path):
    """Verify blockchain events produce proper audit trail entries."""
    real_file = tmp_path / "audit_test.mp4"
    real_file.write_bytes(b"audit test footage")
    sha = hashlib.sha256(b"audit test footage").hexdigest()

    evidence = Evidence(
        case_id=test_case.id,
        evidence_identifier=f"EVID-{uuid.uuid4().hex[:6]}",
        original_filename="audit_test.mp4",
        storage_path=str(real_file),
        source_type="Imported",
        size_bytes=len(b"audit test footage"),
        sha256=sha,
        file_extension="mp4",
        media_type="Video",
        imported_by=test_user.id,
        evidence_status=EvidenceStatus.ORIGINAL,
        integrity_status=IntegrityStatus.VERIFIED,
    )
    db_session.add(evidence)
    db_session.commit()

    record_custody_and_anchor(
        db=db_session,
        case=test_case,
        evidence=evidence,
        action="EVIDENCE_IMPORTED",
        user_id=test_user.id,
        username=test_user.username,
    )

    verify_blockchain_integrity(
        db=db_session,
        case=test_case,
        evidence=evidence,
        user_id=test_user.id,
        username=test_user.username,
    )

    anchor_logs = db_session.query(AuditLog).filter(
        AuditLog.case_id == test_case.id,
        AuditLog.action.in_(["BLOCKCHAIN_ANCHOR_COMPLETED", "BLOCKCHAIN_INTEGRITY_VERIFIED"])
    ).all()

    actions = [l.action for l in anchor_logs]
    assert "BLOCKCHAIN_ANCHOR_COMPLETED" in actions
    assert "BLOCKCHAIN_INTEGRITY_VERIFIED" in actions


# ==============================================================================
# 12. Original evidence immutability
# ==============================================================================
def test_original_evidence_immutability(test_case: Case, test_user: User, db_session: Session, mock_provider: MockBlockchainProvider, tmp_path):
    """Verify blockchain operations NEVER alter evidence binary files or original SHA-256."""
    test_video = tmp_path / "immutability_sample.mp4"
    exact_bytes = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42forensic-data"
    test_video.write_bytes(exact_bytes)
    original_sha = hashlib.sha256(exact_bytes).hexdigest()

    evidence = Evidence(
        case_id=test_case.id,
        evidence_identifier=f"EVID-{uuid.uuid4().hex[:6]}",
        original_filename="immutability_sample.mp4",
        storage_path=str(test_video),
        source_type="Imported",
        size_bytes=len(exact_bytes),
        sha256=original_sha,
        file_extension="mp4",
        media_type="Video",
        imported_by=test_user.id,
        evidence_status=EvidenceStatus.ORIGINAL,
        integrity_status=IntegrityStatus.VERIFIED,
    )
    db_session.add(evidence)
    db_session.commit()

    record_custody_and_anchor(
        db=db_session,
        case=test_case,
        evidence=evidence,
        action="EVIDENCE_IMPORTED",
        user_id=test_user.id,
        username=test_user.username,
    )

    verify_blockchain_integrity(db=db_session, case=test_case, evidence=evidence, user_id=test_user.id, username=test_user.username)
    verify_blockchain_integrity(db=db_session, case=test_case, evidence=evidence, user_id=test_user.id, username=test_user.username)

    post_bytes = test_video.read_bytes()
    assert post_bytes == exact_bytes
    assert hashlib.sha256(post_bytes).hexdigest() == original_sha


# ==============================================================================
# 13. Derived evidence lineage anchoring
# ==============================================================================
def test_derived_evidence_lineage_anchoring(test_case: Case, test_user: User, db_session: Session, mock_provider: MockBlockchainProvider):
    """Verify EVIDENCE_DERIVED triggers custody recording and blockchain anchor."""
    parent = Evidence(
        case_id=test_case.id,
        evidence_identifier=f"EVID-{uuid.uuid4().hex[:6]}",
        original_filename="parent_stream.mp4",
        storage_path="/tmp/parent_stream.mp4",
        source_type="Imported",
        size_bytes=5000,
        sha256=hashlib.sha256(b"parent").hexdigest(),
        file_extension="mp4",
        media_type="Video",
        imported_by=test_user.id,
        evidence_status=EvidenceStatus.ORIGINAL,
        integrity_status=IntegrityStatus.VERIFIED,
    )
    db_session.add(parent)
    db_session.commit()

    derived = Evidence(
        case_id=test_case.id,
        evidence_identifier=f"EVID-{uuid.uuid4().hex[:6]}",
        original_filename="derived_clip.mp4",
        storage_path="/tmp/derived_clip.mp4",
        source_type="Derived",
        size_bytes=1000,
        sha256=hashlib.sha256(b"derived").hexdigest(),
        file_extension="mp4",
        media_type="Video",
        imported_by=test_user.id,
        evidence_status=EvidenceStatus.DERIVED,
        parent_evidence_id=parent.id,
        derived_operation="TRIM",
        integrity_status=IntegrityStatus.VERIFIED,
    )
    db_session.add(derived)
    db_session.commit()

    custody_ev = record_custody_and_anchor(
        db=db_session,
        case=test_case,
        evidence=derived,
        action="EVIDENCE_DERIVED",
        user_id=test_user.id,
        username=test_user.username,
        metadata={"parent_id": parent.evidence_identifier, "operation": "TRIM"},
    )

    assert custody_ev.action == "EVIDENCE_DERIVED"
    assert custody_ev.blockchain_status == BlockchainAnchorStatus.ANCHORED

    anchor = db_session.query(BlockchainAnchor).filter(BlockchainAnchor.evidence_id == derived.id).first()
    assert anchor is not None
    assert anchor.event_type == "EVIDENCE_DERIVED"


# ==============================================================================
# 14. Recovery evidence anchoring
# ==============================================================================
def test_recovery_evidence_anchoring(test_case: Case, test_user: User, db_session: Session, mock_provider: MockBlockchainProvider):
    """Verify RECOVERED_EVIDENCE_CREATED triggers custody recording and blockchain anchor."""
    recovered = Evidence(
        case_id=test_case.id,
        evidence_identifier=f"EVID-REC-{uuid.uuid4().hex[:6]}",
        original_filename="carved_sector_004.mp4",
        storage_path="/tmp/carved_sector_004.mp4",
        size_bytes=2048,
        sha256=hashlib.sha256(b"carved_video").hexdigest(),
        file_extension="mp4",
        media_type="Video",
        imported_by=test_user.id,
        evidence_status=EvidenceStatus.ORIGINAL,
        source_type="Recovered",
        integrity_status=IntegrityStatus.VERIFIED,
    )
    db_session.add(recovered)
    db_session.commit()

    custody_ev = record_custody_and_anchor(
        db=db_session,
        case=test_case,
        evidence=recovered,
        action="RECOVERED_EVIDENCE_CREATED",
        user_id=test_user.id,
        username=test_user.username,
        metadata={"offset": 1048576, "source": "disk_image.dd"},
    )

    assert custody_ev.action == "RECOVERED_EVIDENCE_CREATED"
    assert custody_ev.blockchain_status == BlockchainAnchorStatus.ANCHORED

    anchor = db_session.query(BlockchainAnchor).filter(BlockchainAnchor.evidence_id == recovered.id).first()
    assert anchor is not None
    assert anchor.event_type == "RECOVERED_EVIDENCE_CREATED"


# ==============================================================================
# 15. AI frame evidence anchoring
# ==============================================================================
def test_ai_frame_evidence_anchoring(test_case: Case, test_user: User, db_session: Session, mock_provider: MockBlockchainProvider):
    """Verify AI_FRAME_EXPORTED triggers custody recording and blockchain anchor."""
    frame_evidence = Evidence(
        case_id=test_case.id,
        evidence_identifier=f"EVID-AI-{uuid.uuid4().hex[:6]}",
        original_filename="detection_frame_042.jpg",
        storage_path="/tmp/detection_frame_042.jpg",
        size_bytes=40960,
        sha256=hashlib.sha256(b"ai_detection_jpg_bytes").hexdigest(),
        file_extension="jpg",
        media_type="Image",
        imported_by=test_user.id,
        evidence_status=EvidenceStatus.DERIVED,
        source_type="Derived",
        derived_operation="AI_FRAME_EXPORT",
        integrity_status=IntegrityStatus.VERIFIED,
    )
    db_session.add(frame_evidence)
    db_session.commit()

    custody_ev = record_custody_and_anchor(
        db=db_session,
        case=test_case,
        evidence=frame_evidence,
        action="AI_FRAME_EXPORTED",
        user_id=test_user.id,
        username=test_user.username,
        metadata={"finding_id": "FINDING-001", "class": "person", "confidence": 0.94},
    )

    assert custody_ev.action == "AI_FRAME_EXPORTED"
    assert custody_ev.blockchain_status == BlockchainAnchorStatus.ANCHORED

    anchor = db_session.query(BlockchainAnchor).filter(BlockchainAnchor.evidence_id == frame_evidence.id).first()
    assert anchor is not None
    assert anchor.event_type == "AI_FRAME_EXPORTED"
