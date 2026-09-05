"""Comprehensive tests for Step 10: Format Signature Identification, Vendor Adapters,
Unsupported Format Handling, and Derived Inspection Proxy Foundation.
"""
import io
import os
import tempfile
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.case import Case, CaseMember, RoleEnum
from app.models.evidence import Evidence, EvidenceStatus, IntegrityStatus
from app.models.user import User
from app.core.security import get_password_hash
from app.forensics.signatures.signature_probe import (
    SignatureProbeResult,
    probe_bytes,
    probe_file,
)
from app.forensics.vendor_adapter import (
    GenericVendorAdapter,
    get_best_adapter_for_file,
    get_vendor_adapter,
    register_vendor_adapter,
)
from app.services.evidence_service import (
    compute_file_hashes,
    generate_inspection_proxy,
    get_hex_preview,
)


# Test fixtures
@pytest.fixture
def test_user(db_session: Session):
    user = User(
        username=f"forensic_expert_{uuid.uuid4().hex[:6]}",
        password_hash=get_password_hash("forensicPass123"),
        display_name="Forensic Analyst"
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def other_user(db_session: Session):
    user = User(
        username=f"unauthorized_{uuid.uuid4().hex[:6]}",
        password_hash=get_password_hash("pass123"),
        display_name="External User"
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_case(db_session: Session, test_user: User):
    case = Case(
        case_identifier=f"CASE-{uuid.uuid4().hex[:6].upper()}",
        name="CCTV Forensic Investigation Case",
        created_by=test_user.id
    )
    db_session.add(case)
    db_session.commit()
    member = CaseMember(case_id=case.id, user_id=test_user.id, role=RoleEnum.ADMIN)
    db_session.add(member)
    db_session.commit()
    return case


@pytest.fixture
def second_case(db_session: Session, other_user: User):
    case = Case(
        case_identifier=f"CASE-{uuid.uuid4().hex[:6].upper()}",
        name="Separate Unrelated Case",
        created_by=other_user.id
    )
    db_session.add(case)
    db_session.commit()
    member = CaseMember(case_id=case.id, user_id=other_user.id, role=RoleEnum.INVESTIGATOR)
    db_session.add(member)
    db_session.commit()
    return case


# --- Tests 1 to 8: Binary Signature Probe Engine ---

def test_1_dhav_detected_correctly():
    """1. DHAV magic bytes are detected correctly as Dahua DAV."""
    data = b"DHAV\x01\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x00"
    result = probe_bytes(data, filename="evidence.dav")
    assert result.vendor == "Dahua"
    assert result.format_name == "Dahua DAV"
    assert result.is_proprietary is True
    assert result.is_natively_playable is False
    assert result.confidence == 0.98
    assert result.recommended_action == "TRANSMUX_PROXY"
    assert result.magic_hex == "44484156"


def test_2_dhav_detected_even_if_extension_is_mp4():
    """2. DHAV is detected even if the file is renamed to .mp4 (extension independence)."""
    data = b"DHAV\x00\x00\x00\x00randomstreamcontent"
    result = probe_bytes(data, filename="tampered_extension.mp4")
    assert result.vendor == "Dahua"
    assert result.format_name == "Dahua DAV"
    assert result.is_natively_playable is False
    assert result.is_proprietary is True


def test_3_hikv_detected():
    """3. HIKV signature detected correctly as Hikvision Video Container."""
    data = b"HIKV\x00\x01\x02\x03\x04\x05\x06\x07"
    result = probe_bytes(data, filename="hik_camera.mp4")
    assert result.vendor == "Hikvision"
    assert result.format_name == "Hikvision HIKV"
    assert result.is_proprietary is True
    assert result.is_natively_playable is False
    assert result.confidence == 0.98


def test_4_hikb_detected():
    """4. HIKB signature detected correctly as Hikvision Backup Block Container."""
    data = b"HIKB\x00\x00\x00\x01\x00\x00\x00\x00"
    result = probe_bytes(data, filename="backup.bin")
    assert result.vendor == "Hikvision"
    assert result.format_name == "Hikvision HIKB"
    assert result.is_proprietary is True
    assert result.is_natively_playable is False
    assert result.confidence == 0.98


def test_5_mp4_detected():
    """5. Standard ISO/IEC MP4 container detected via ftyp box."""
    data = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2mp41"
    result = probe_bytes(data, filename="standard.mp4")
    assert result.vendor == "Generic"
    assert result.format_name == "Standard MP4"
    assert result.is_proprietary is False
    assert result.is_natively_playable is True
    assert result.confidence == 0.99
    assert result.recommended_action == "NATIVE_PLAYBACK"


def test_6_mkv_detected():
    """6. MKV / WebM container detected via EBML header (1A 45 DF A3)."""
    data = b"\x1a\x45\xdf\xa3\x93B\x86\x81\x01B\xf7\x81\x01"
    result = probe_bytes(data, filename="recording.mkv")
    assert result.vendor == "Generic"
    assert result.format_name == "Standard MKV"
    assert result.is_proprietary is False
    assert result.is_natively_playable is True
    assert result.confidence == 0.98


def test_7_avi_detected():
    """7. Standard AVI container detected via RIFF....AVI ."""
    data = b"RIFF\x24\x00\x00\x00AVI LIST\x18\x00\x00\x00hdrlavih"
    result = probe_bytes(data, filename="traffic.avi")
    assert result.vendor == "Generic"
    assert result.format_name == "Standard AVI"
    assert result.is_proprietary is False
    assert result.is_natively_playable is False
    assert result.confidence == 0.98


def test_8_unknown_binary_returns_unknown_proprietary():
    """8. Unrecognized binary stream returns UNKNOWN_PROPRIETARY with 0.0 confidence."""
    data = b"\xde\xad\xbe\xef\xca\xfe\xba\xbe\x01\x02\x03\x04\x05"
    result = probe_bytes(data, filename="unrecognized.dat")
    assert result.vendor == "Unknown"
    assert result.format_name == "Unknown Proprietary Format"
    assert result.is_proprietary is True
    assert result.is_natively_playable is False
    assert result.confidence == 0.0
    assert result.recommended_action == "RAW_EXPORT / CARVE_STREAM"


def test_9_extension_and_signature_conflict_handled_correctly():
    """9. Binary signature wins over filename extension when they conflict."""
    # Unknown bytes named .mp4 must NOT be treated as MP4
    fake_mp4 = b"\x11\x22\x33\x44\x55\x66\x77\x88\x99\xaa\xbb\xcc"
    result = probe_bytes(fake_mp4, filename="fake_video.mp4")
    assert result.vendor == "Unknown"
    assert result.is_natively_playable is False
    assert result.confidence == 0.0

    # Dahua DAV named .avi must be treated as Dahua DAV
    dav_as_avi = b"DHAV\x00\x01\x02\x03\x04\x05"
    result_dav = probe_bytes(dav_as_avi, filename="fake_avi.avi")
    assert result_dav.vendor == "Dahua"
    assert result_dav.format_name == "Dahua DAV"


# --- Tests 10 to 12: Vendor Adapter Registry Resolution ---

def test_10_generic_adapter_selected_for_standard_video(tmp_path: Path):
    """10. Generic adapter is selected for standard MP4 files."""
    mp4_file = tmp_path / "camera_clip.mp4"
    mp4_file.write_bytes(b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2mp41" + b"\x00" * 100)

    adapter = get_best_adapter_for_file(mp4_file)
    assert adapter.vendor_name == "Generic"
    meta = adapter.get_metadata(mp4_file)
    assert meta["vendor"] == "Generic"
    assert meta["is_natively_playable"] is True


def test_11_dahua_adapter_selected_for_dhav(tmp_path: Path):
    """11. Dahua adapter is selected for DHAV file even with .mp4 extension."""
    dhav_file = tmp_path / "dahua_camera.mp4"
    dhav_file.write_bytes(b"DHAV\x01\x02\x03\x04\x05\x06\x07\x08" + b"\x00" * 100)

    adapter = get_best_adapter_for_file(dhav_file)
    assert adapter.vendor_name == "Dahua"
    meta = adapter.get_metadata(dhav_file)
    assert meta["vendor"] == "Dahua"
    assert meta["decoder_status"] == "Not currently available"
    assert meta["is_natively_playable"] is False


def test_12_hikvision_adapter_selected_for_hikv_and_hikb(tmp_path: Path):
    """12. Hikvision adapter is selected for HIKV and HIKB files."""
    hikv_file = tmp_path / "hik_stream.hik"
    hikv_file.write_bytes(b"HIKV\x00\x00\x01\x00" + b"\x00" * 50)
    adapter_v = get_best_adapter_for_file(hikv_file)
    assert adapter_v.vendor_name == "Hikvision"

    hikb_file = tmp_path / "hik_backup.bin"
    hikb_file.write_bytes(b"HIKB\x00\x00\x01\x00" + b"\x00" * 50)
    adapter_b = get_best_adapter_for_file(hikb_file)
    assert adapter_b.vendor_name == "Hikvision"


import subprocess
import imageio_ffmpeg
from app.api.v1.endpoints.evidence import get_current_user_flexible

def generate_tiny_test_video() -> bytes:
    """Generate a valid 1-second tiny MP4 video using imageio_ffmpeg for genuine transmux testing."""
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    tmp_name = f"tmp_{uuid.uuid4().hex}.mp4"
    subprocess.run([
        exe, "-f", "lavfi", "-i", "testsrc=duration=1:size=160x120:rate=10",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", tmp_name
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with open(tmp_name, "rb") as f:
        data = f.read()
    if os.path.exists(tmp_name):
        os.remove(tmp_name)
    return data


# --- Tests 13 to 16: Evidence Ingestion, Hash Preservation, and Lineage ---

def test_13_and_14_original_evidence_hash_and_bytes_unchanged(
    test_case: Case, test_user: User, override_get_db, db_session: Session
):
    """13 & 14. Original evidence hash and bytes remain strictly untouched."""
    client = TestClient(app)
    from app.dependencies.auth import require_case_investigator_or_admin, get_current_user

    app.dependency_overrides[require_case_investigator_or_admin] = lambda: db_session.query(CaseMember).first()
    app.dependency_overrides[get_current_user] = lambda: test_user

    # Ingest proprietary Dahua evidence
    dahua_bytes = b"DHAV\x00\x01\x02\x03" + b"FORENSIC_RAW_PAYLOAD_" + uuid.uuid4().hex.encode()
    response = client.post(
        f"/api/v1/cases/{test_case.case_identifier}/evidence",
        files={"file": ("channel01.dav", io.BytesIO(dahua_bytes), "application/octet-stream")}
    )
    assert response.status_code == 200
    data = response.json()
    evidence_id = data["id"]
    orig_sha256 = data["sha256"]
    orig_md5 = data["md5_reference"]

    # Verify vendor normalization
    assert data["vendor"] == "Dahua"
    assert data["proprietary_format"] == "Dahua DAV"
    assert data["is_natively_playable"] is False
    assert data["evidence_status"] == "ORIGINAL"

    # Query DB record directly
    evidence = db_session.query(Evidence).filter(Evidence.id == evidence_id).first()
    storage_path = Path(evidence.storage_path)
    assert storage_path.exists()
    assert storage_path.read_bytes() == dahua_bytes

    sha_after, md5_after = compute_file_hashes(storage_path)
    assert sha_after == orig_sha256
    assert md5_after == orig_md5

    app.dependency_overrides = {}


def test_15_derived_proxy_has_parent_linkage_and_new_hash(
    test_case: Case, test_user: User, override_get_db, db_session: Session
):
    """15. Derived proxy, when genuinely supported, has parent evidence, DERIVED status, and new hash."""
    # Generate a real valid tiny MP4 video
    real_video_bytes = generate_tiny_test_video()

    test_vault = Path("data") / "case_data" / test_case.case_identifier / "evidence" / "original"
    test_vault.mkdir(parents=True, exist_ok=True)
    raw_source = test_vault / f"{uuid.uuid4().hex}.mp4"
    raw_source.write_bytes(real_video_bytes)

    sha256, md5 = compute_file_hashes(raw_source)

    orig_evidence = Evidence(
        case_id=test_case.id,
        evidence_identifier=f"EVD-{uuid.uuid4().hex[:6].upper()}",
        original_filename="standard_source.mp4",
        storage_path=str(raw_source),
        source_type="Imported File",
        media_type="Video",
        file_extension=".mp4",
        size_bytes=len(real_video_bytes),
        sha256=sha256,
        md5_reference=md5,
        source_sha256=sha256,
        stored_sha256=sha256,
        integrity_status=IntegrityStatus.VERIFIED,
        evidence_status=EvidenceStatus.ORIGINAL,
        vendor="Generic",
        proprietary_format="Standard MP4",
        is_natively_playable=True,
        imported_by=test_user.id
    )
    db_session.add(orig_evidence)
    db_session.commit()
    db_session.refresh(orig_evidence)

    # Generate inspection proxy
    proxy = generate_inspection_proxy(db_session, test_case, orig_evidence, test_user.id)

    assert proxy.id != orig_evidence.id
    assert proxy.parent_evidence_id == orig_evidence.id
    assert proxy.evidence_status == EvidenceStatus.DERIVED
    assert proxy.derived_operation == "PROPRIETARY_TRANSMUX_PROXY"
    assert proxy.is_natively_playable is True
    assert proxy.storage_path != orig_evidence.storage_path
    assert Path(proxy.storage_path).exists()
    assert Path(orig_evidence.storage_path).read_bytes() == real_video_bytes  # Original untouched


def test_16_unsupported_proprietary_file_does_not_fake_playback(
    test_case: Case, test_user: User, override_get_db, db_session: Session
):
    """16. Unsupported proprietary format returns clean HTTP 400 error without fake playback."""
    client = TestClient(app)
    from app.dependencies.auth import require_case_investigator_or_admin, get_current_user

    app.dependency_overrides[require_case_investigator_or_admin] = lambda: db_session.query(CaseMember).first()
    app.dependency_overrides[get_current_user] = lambda: test_user

    # Import raw Dahua DAV evidence
    dahua_bytes = b"DHAV\x00\x00\x00\x00PROPRIETARY_RAW_STREAM_" + uuid.uuid4().hex.encode()
    res = client.post(
        f"/api/v1/cases/{test_case.case_identifier}/evidence",
        files={"file": ("nvr_channel2.dav", io.BytesIO(dahua_bytes), "application/octet-stream")}
    )
    assert res.status_code == 200
    ev_id = res.json()["id"]

    # Attempt to generate proxy on proprietary Dahua container without fake decoding
    proxy_res = client.post(
        f"/api/v1/cases/{test_case.case_identifier}/evidence/{ev_id}/generate-proxy"
    )
    assert proxy_res.status_code == 400
    error_detail = proxy_res.json()["detail"]
    assert "Web inspection proxy unavailable" in error_detail
    assert "Dahua" in error_detail

    app.dependency_overrides = {}


# --- Tests 17 to 19: Hex Preview, Original Download, and Authorization Boundaries ---

def test_17_hex_preview_only_accesses_authorized_evidence(
    test_case: Case, second_case: Case, test_user: User, other_user: User, override_get_db, db_session: Session
):
    """17. Hex header preview operates safely on first 512 bytes and enforces authorization."""
    client = TestClient(app)
    from app.dependencies.auth import require_case_member, get_current_user

    # Create evidence in test_case
    vault_dir = Path("data") / "case_data" / test_case.case_identifier / "evidence" / "original"
    vault_dir.mkdir(parents=True, exist_ok=True)
    file_path = vault_dir / f"{uuid.uuid4().hex}.bin"
    header_data = b"DHAV" + bytes(range(64))
    file_path.write_bytes(header_data)

    evidence = Evidence(
        case_id=test_case.id,
        evidence_identifier=f"EVD-{uuid.uuid4().hex[:6].upper()}",
        original_filename="firmware_dump.bin",
        storage_path=str(file_path),
        source_type="Imported File",
        media_type="Video",
        file_extension=".bin",
        size_bytes=len(header_data),
        sha256="dummy_sha",
        md5_reference="dummy_md5",
        integrity_status=IntegrityStatus.VERIFIED,
        evidence_status=EvidenceStatus.ORIGINAL,
        vendor="Dahua",
        proprietary_format="Dahua DAV",
        is_natively_playable=False,
        imported_by=test_user.id
    )
    db_session.add(evidence)
    db_session.commit()

    # Authorized member access
    app.dependency_overrides[require_case_member] = lambda: db_session.query(CaseMember).filter(
        CaseMember.case_id == test_case.id, CaseMember.user_id == test_user.id
    ).first()

    res = client.get(f"/api/v1/cases/{test_case.case_identifier}/evidence/{evidence.id}/hex-preview")
    assert res.status_code == 200
    preview = res.json()
    assert preview["evidence_id"] == evidence.id
    assert preview["total_bytes_inspected"] == len(header_data)
    assert len(preview["rows"]) > 0
    assert preview["rows"][0]["offset"] == "00000000"
    assert "44 48 41 56" in preview["rows"][0]["hex_bytes"]
    assert "DHAV" in preview["rows"][0]["ascii_text"]

    # Unauthorized access (trying to access evidence through second_case)
    app.dependency_overrides[require_case_member] = lambda: db_session.query(CaseMember).filter(
        CaseMember.case_id == second_case.id, CaseMember.user_id == other_user.id
    ).first()

    res_unauth = client.get(f"/api/v1/cases/{second_case.case_identifier}/evidence/{evidence.id}/hex-preview")
    assert res_unauth.status_code == 404

    app.dependency_overrides = {}


def test_18_original_download_only_accesses_authorized_evidence(
    test_case: Case, test_user: User, other_user: User, override_get_db, db_session: Session
):
    """18. Original download delivers exact byte stream to authorized case members."""
    client = TestClient(app)

    vault_dir = Path("data") / "case_data" / test_case.case_identifier / "evidence" / "original"
    vault_dir.mkdir(parents=True, exist_ok=True)
    file_path = vault_dir / f"{uuid.uuid4().hex}.dav"
    original_raw_bytes = b"DHAV\x00\x01\x02\x03\x04FORENSIC_EVIDENCE_EXACT_BITSTREAM"
    file_path.write_bytes(original_raw_bytes)

    evidence = Evidence(
        case_id=test_case.id,
        evidence_identifier=f"EVD-{uuid.uuid4().hex[:6].upper()}",
        original_filename="surveillance_exact.dav",
        storage_path=str(file_path),
        source_type="Imported File",
        media_type="Video",
        file_extension=".dav",
        size_bytes=len(original_raw_bytes),
        sha256="exact_sha",
        integrity_status=IntegrityStatus.VERIFIED,
        evidence_status=EvidenceStatus.ORIGINAL,
        imported_by=test_user.id
    )
    db_session.add(evidence)
    db_session.commit()

    # Authorized user downloads original
    app.dependency_overrides[get_current_user_flexible] = lambda: test_user
    res = client.get(
        f"/api/v1/cases/{test_case.case_identifier}/evidence/{evidence.id}/download-original",
        headers={"Authorization": "Bearer fake_token"}
    )
    assert res.status_code == 200
    assert res.content == original_raw_bytes
    assert "surveillance_exact.dav" in res.headers.get("content-disposition", "")

    # Unauthorized user (not member of test_case)
    app.dependency_overrides[get_current_user_flexible] = lambda: other_user
    res_forbidden = client.get(
        f"/api/v1/cases/{test_case.case_identifier}/evidence/{evidence.id}/download-original",
        headers={"Authorization": "Bearer fake_token"}
    )
    assert res_forbidden.status_code == 403

    app.dependency_overrides = {}


def test_19_cross_case_evidence_access_rejected(
    test_case: Case, second_case: Case, test_user: User, override_get_db, db_session: Session
):
    """19. Cross-case evidence lookup is strictly rejected."""
    client = TestClient(app)
    from app.dependencies.auth import require_case_member


    # Evidence belongs to test_case
    vault_dir = Path("data") / "case_data" / test_case.case_identifier / "evidence" / "original"
    vault_dir.mkdir(parents=True, exist_ok=True)
    file_path = vault_dir / f"{uuid.uuid4().hex}.mp4"
    file_path.write_bytes(b"content")

    evidence = Evidence(
        case_id=test_case.id,
        evidence_identifier=f"EVD-{uuid.uuid4().hex[:6].upper()}",
        original_filename="sample.mp4",
        storage_path=str(file_path),
        source_type="Imported File",
        media_type="Video",
        file_extension=".mp4",
        size_bytes=7,
        integrity_status=IntegrityStatus.VERIFIED,
        evidence_status=EvidenceStatus.ORIGINAL,
        imported_by=test_user.id
    )
    db_session.add(evidence)
    db_session.commit()

    # Attempting to fetch evidence.id via second_case URL must fail with 404
    app.dependency_overrides[require_case_member] = lambda: db_session.query(CaseMember).filter(
        CaseMember.case_id == second_case.id
    ).first()

    res = client.get(f"/api/v1/cases/{second_case.case_identifier}/evidence/{evidence.id}")
    assert res.status_code == 404

    app.dependency_overrides = {}
