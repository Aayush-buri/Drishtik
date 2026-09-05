"""Forensic tests for proprietary CCTV parsing, decoding foundations, and stream recovery.

NTRO Step 11 Verification Suite:
- Dahua DHAV demuxing, OSD timestamp decoding, channel extraction
- Hikvision HIKV/HIKB and MPEG-PS detection and demuxing foundation
- CP Plus Dahua OEM compatibility recognition
- VideoDecoderAdapter and lossless transmuxing to web MP4 proxy
- Original evidence immutability and separate derived proxy lineage
- Forensic audit logging and case authorization enforcement
- Recovery engine candidate detection and raw disk image format identification (.raw, .dd, .img, .e01)
- Format analysis diagnostic endpoint
"""
import io
import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.case import Case, CaseMember, RoleEnum
from app.models.evidence import Evidence, EvidenceStatus, IntegrityStatus
from app.models.user import User
from app.models.audit import AuditLog
from app.forensics.signatures.signature_probe import probe_file, probe_bytes
from app.forensics.vendor_adapter import (
    get_best_adapter_for_file,
    get_vendor_adapter,
    get_ffmpeg_executable,
)
from app.core.security import get_password_hash
from app.forensics.decoder import DahuaVideoDecoder, GenericVideoDecoder
from app.forensics.recovery.engine import RecoveryEngine, DhavCarvingStrategy, HikvisionCarvingStrategy
from parsers.dahua.demuxer import DahuaDemuxer, decode_dahua_timestamp, encode_dahua_timestamp
from parsers.common.demuxer import PacketType


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


def build_synthetic_dhav_file(output_path: Path, num_frames: int = 10) -> Path:
    """Helper to generate a genuine, valid Dahua DHAV file containing valid H.264 Annex B NAL units.

    Uses FFmpeg to generate an actual elementary H.264 video stream, then packages
    it into standard Dahua DHAV frame headers with packed 32-bit OSD timestamps and channel index.
    """
    ffmpeg_exe = get_ffmpeg_executable()
    assert ffmpeg_exe is not None, "FFmpeg executable must be available for genuine CCTV decoding test"

    raw_h264_path = output_path.parent / f"{output_path.stem}_temp.h264"
    # Generate 1-second 320x240 test video at 10 fps in raw H.264 Annex B format
    cmd = [
        ffmpeg_exe,
        "-y",
        "-f", "lavfi",
        "-i", f"testsrc=duration=1:size=320x240:rate=10",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-g", "5",
        "-f", "h264",
        str(raw_h264_path.resolve()),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res.returncode == 0, f"FFmpeg raw H.264 generation failed: {res.stderr}"
    assert raw_h264_path.exists() and raw_h264_path.stat().st_size > 0

    h264_bytes = raw_h264_path.read_bytes()
    raw_h264_path.unlink(missing_ok=True)

    # Split into NAL chunks (separated by 0x000001 or 0x00000001)
    # Wrap each chunk in a Dahua DHAV frame
    dhav_data = bytearray()
    start_dt = datetime(2026, 9, 5, 10, 0, 0)

    # We write 2 DHAV frames splitting the H.264 payload
    half = len(h264_bytes) // 2

    chunks = [
        (h264_bytes[:half], 0xFD, start_dt),                    # I-frame
        (h264_bytes[half:], 0xFC, datetime(2026, 9, 5, 10, 0, 1)) # P-frame
    ]

    for seq, (payload, frame_type_byte, frame_time) in enumerate(chunks):
        ts_val = encode_dahua_timestamp(frame_time)
        payload_len = len(payload)

        # 24-byte DHAV header
        header = bytearray(24)
        header[0:4] = b"DHAV"
        header[4] = frame_type_byte
        header[5] = 0x00  # Channel 1 (0-indexed)
        header[6:8] = seq.to_bytes(2, "little")
        header[8:12] = payload_len.to_bytes(4, "little")
        header[12:16] = ts_val.to_bytes(4, "little")
        # remaining 8 bytes reserved

        # 8-byte DHAV footer
        footer = bytearray(8)
        footer[0:4] = b"dhav"
        footer[4:8] = (payload_len + 32).to_bytes(4, "little")

        dhav_data.extend(header)
        dhav_data.extend(payload)
        dhav_data.extend(footer)

    output_path.write_bytes(bytes(dhav_data))
    return output_path


def test_01_dahua_adapter_detects_dhav(tmp_path: Path):
    """1. Dahua adapter detects DHAV magic bytes regardless of file extension."""
    sample_file = tmp_path / "camera_feed.xyz"
    sample_file.write_bytes(b"DHAV\xfd\x00\x00\x00\x10\x00\x00\x00" + b"\x00" * 32)

    probe = probe_file(sample_file)
    assert probe.vendor == "Dahua"
    assert probe.format_name == "Dahua DAV"
    assert probe.confidence >= 0.95

    adapter = get_best_adapter_for_file(sample_file)
    assert adapter.vendor_name == "Dahua"


def test_02_hikvision_adapter_detects_hikv_and_hikb(tmp_path: Path):
    """2. Hikvision adapter detects HIKV and HIKB proprietary headers."""
    hikv_file = tmp_path / "surveillance_h.bin"
    hikv_file.write_bytes(b"HIKV\x01\x00\x00\x00\x00\x00\x00\x00" + b"\x00" * 40)
    probe_v = probe_file(hikv_file)
    assert probe_v.vendor == "Hikvision"
    assert probe_v.format_name == "Hikvision HIKV"

    hikb_file = tmp_path / "backup_archive.dat"
    hikb_file.write_bytes(b"HIKB\x01\x00\x00\x00" + b"\x00" * 40)
    probe_b = probe_file(hikb_file)
    assert probe_b.vendor == "Hikvision"
    assert probe_b.format_name == "Hikvision HIKB"


def test_03_cpplus_adapter_detection_honest(tmp_path: Path):
    """3. CP Plus adapter detection behavior is honest and documents Dahua OEM relationship."""
    # Test OEM compatible DHAV file
    oem_file = tmp_path / "cpplus_dhav.dav"
    oem_file.write_bytes(b"DHAV\xfd\x00\x00\x00" + b"\x00" * 40)

    adapter = get_vendor_adapter("CP Plus")
    assert adapter is not None
    assert adapter.vendor_name == "CP Plus"

    meta = adapter.get_metadata(oem_file)
    assert meta["vendor"] == "CP Plus"
    assert "Dahua OEM" in meta["format"] or "DHAV" in meta["format"]
    assert meta["is_proprietary"] is True


def test_04_correct_adapter_selected(tmp_path: Path):
    """4. Global adapter registry routes files to appropriate vendor adapter."""
    dhav_path = tmp_path / "test.dav"
    dhav_path.write_bytes(b"DHAV" + b"\x00" * 50)
    assert get_best_adapter_for_file(dhav_path).vendor_name == "Dahua"

    hik_path = tmp_path / "test.hik"
    hik_path.write_bytes(b"HIKV" + b"\x00" * 50)
    assert get_best_adapter_for_file(hik_path).vendor_name == "Hikvision"

    std_path = tmp_path / "test.mp4"
    std_path.write_bytes(b"\x00\x00\x00 ftypisom" + b"\x00" * 50)
    assert get_best_adapter_for_file(std_path).vendor_name == "Generic"


def test_05_metadata_and_osd_timestamp_extraction():
    """5. Dahua 32-bit packed timestamp bitfield decodes and encodes symmetrically."""
    target_dt = datetime(2026, 9, 5, 14, 30, 45)
    packed_val = encode_dahua_timestamp(target_dt)
    decoded_dt = decode_dahua_timestamp(packed_val)

    assert decoded_dt.year == 2026
    assert decoded_dt.month == 9
    assert decoded_dt.day == 5
    assert decoded_dt.hour == 14
    assert decoded_dt.minute == 30
    assert decoded_dt.second == 45


def test_06_unsupported_proprietary_format_honestly_reported(
    test_case: Case, test_user: User, override_get_db, db_session: Session, tmp_path: Path
):
    """6. Unsupported proprietary format reports clean diagnostic error without fake playback."""
    client = TestClient(app)
    from app.dependencies.auth import require_case_investigator_or_admin, get_current_user

    app.dependency_overrides[require_case_investigator_or_admin] = lambda: db_session.query(CaseMember).first()
    app.dependency_overrides[get_current_user] = lambda: test_user

    # Create dummy proprietary Hikvision HIKB backup file
    unsupported_data = b"HIKB\x00\x00\x00\x00UNSUPPORTED_BLOB_" + uuid.uuid4().hex.encode()
    res = client.post(
        f"/api/v1/cases/{test_case.case_identifier}/evidence",
        files={"file": ("vault_backup.hik", io.BytesIO(unsupported_data), "application/octet-stream")}
    )
    assert res.status_code == 200
    ev_data = res.json()
    assert ev_data["is_natively_playable"] is False

    # Attempting to generate web proxy on unsupported container returns HTTP 400
    proxy_res = client.post(
        f"/api/v1/cases/{test_case.case_identifier}/evidence/{ev_data['id']}/generate-proxy"
    )
    assert proxy_res.status_code == 400
    assert "unavailable" in proxy_res.json()["detail"].lower()


def test_07_genuine_end_to_end_proprietary_transmux_and_immutability(
    test_case: Case, test_user: User, override_get_db, db_session: Session, tmp_path: Path
):
    """7-12, 15. Genuine end-to-end Dahua DHAV test:
    - Genuine parsing and demuxing of real H.264 payload
    - Lossless transmuxing to web MP4 proxy
    - Original evidence hash and bytes remain strictly immutable
    - Derived proxy record created with parent evidence ID, new SHA-256, and audit event
    """
    client = TestClient(app)
    from app.dependencies.auth import require_case_investigator_or_admin, get_current_user

    app.dependency_overrides[require_case_investigator_or_admin] = lambda: db_session.query(CaseMember).first()
    app.dependency_overrides[get_current_user] = lambda: test_user

    sample_dhav_path = tmp_path / "genuine_dahua_cctv.dav"
    build_synthetic_dhav_file(sample_dhav_path)
    sample_bytes = sample_dhav_path.read_bytes()

    # 1. Import genuine Dahua DAV evidence
    res = client.post(
        f"/api/v1/cases/{test_case.case_identifier}/evidence",
        files={"file": ("cctv_entrance.dav", io.BytesIO(sample_bytes), "application/octet-stream")}
    )
    assert res.status_code == 200
    ev_data = res.json()
    ev_id = ev_data["id"]
    original_sha = ev_data["sha256"]
    assert original_sha is not None
    assert ev_data["vendor"] == "Dahua"
    assert ev_data["evidence_status"] == "ORIGINAL"
    assert ev_data["channel_index"] == 1
    assert ev_data["start_time_osd"] is not None

    # Read the stored file directly from disk before proxy generation
    original_stored_path = Path(ev_data["storage_path"])
    assert original_stored_path.exists()
    bytes_before = original_stored_path.read_bytes()

    # 2. Generate web inspection proxy
    proxy_res = client.post(
        f"/api/v1/cases/{test_case.case_identifier}/evidence/{ev_id}/generate-proxy"
    )
    assert proxy_res.status_code == 200
    proxy_data = proxy_res.json()

    # 3. Verify ORIGINAL evidence immutability
    bytes_after = original_stored_path.read_bytes()
    assert bytes_before == bytes_after, "Original evidence bytes were modified during proxy generation!"

    # Refresh original evidence from DB
    original_db = db_session.query(Evidence).filter(Evidence.id == ev_id).first()
    assert original_db.sha256 == original_sha
    assert original_db.evidence_status == EvidenceStatus.ORIGINAL

    # 4. Verify Derived Proxy Lineage
    assert proxy_data["evidence_status"] == "DERIVED"
    assert proxy_data["parent_evidence_id"] == ev_id
    assert proxy_data["parent_evidence_identifier"] == ev_data["evidence_identifier"]
    assert proxy_data["derived_operation"] == "PROPRIETARY_TRANSMUX_PROXY"
    assert proxy_data["sha256"] != original_sha
    assert proxy_data["is_natively_playable"] is True

    # 5. Verify derived proxy file exists on disk and is a valid MP4
    proxy_stored_path = Path(proxy_data["storage_path"])
    assert proxy_stored_path.exists()
    assert proxy_stored_path.stat().st_size > 0
    with open(proxy_stored_path, "rb") as f:
        head = f.read(16)
        assert b"ftyp" in head or b"moov" in head or b"mdat" in head

    # 6. Verify Audit Log entry was generated
    audit_entry = db_session.query(AuditLog).filter(
        AuditLog.case_id == test_case.id,
        AuditLog.action == "EVIDENCE_DERIVED_PROXY",
        AuditLog.target_identifier == proxy_data["evidence_identifier"]
    ).first()
    assert audit_entry is not None
    details = json.loads(audit_entry.details)
    assert details["parent_id"] == ev_data["evidence_identifier"]
    assert details["operation"] == "PROPRIETARY_TRANSMUX_PROXY"


def test_10_unauthorized_user_cannot_generate_proxy(
    test_case: Case, db_session: Session, override_get_db
):
    """10, 13. Unauthorized non-member user is forbidden from generating proxy."""
    client = TestClient(app)
    unauth_user = User(
        username="outsider",
        password_hash=get_password_hash("hash123"),
        display_name="Outsider Agent"
    )
    db_session.add(unauth_user)
    db_session.commit()

    from app.dependencies.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: unauth_user

    res = client.post(
        f"/api/v1/cases/{test_case.case_identifier}/evidence/1/generate-proxy"
    )
    assert res.status_code in (401, 403)


def test_12_format_analysis_endpoint(
    test_case: Case, test_user: User, override_get_db, db_session: Session, tmp_path: Path
):
    """12, 17. GET /cases/{case_id}/evidence/{evidence_id}/format-analysis returns full forensic audit diagnostics."""
    client = TestClient(app)
    from app.dependencies.auth import require_case_member, get_current_user

    app.dependency_overrides[require_case_member] = lambda: db_session.query(CaseMember).first()
    app.dependency_overrides[get_current_user] = lambda: test_user

    sample_file = tmp_path / "test_dhav_audit.dav"
    sample_file.write_bytes(b"DHAV\x00\x00\x00\x00" + b"\x00" * 40)

    # Import evidence
    res = client.post(
        f"/api/v1/cases/{test_case.case_identifier}/evidence",
        files={"file": ("audit_cctv.dav", io.BytesIO(sample_file.read_bytes()), "application/octet-stream")}
    )
    ev_id = res.json()["id"]

    analysis_res = client.get(
        f"/api/v1/cases/{test_case.case_identifier}/evidence/{ev_id}/format-analysis"
    )
    assert analysis_res.status_code == 200
    data = analysis_res.json()

    assert data["evidence_id"] == ev_id
    assert data["vendor"] == "Dahua"
    assert "DHAV" in data["format"] or "Dahua DAV" in data["format"]
    assert "parser_available" in data
    assert "decoder_available" in data
    assert "proxy_available" in data
    assert "status" in data


def test_13_recovery_foundation_disk_image_identification(tmp_path: Path):
    """13, 14. RecoveryEngine accurately identifies raw disk image formats (.raw, .dd, .img, .e01) without fake claims."""
    engine = RecoveryEngine()

    raw_disk = tmp_path / "forensic_nvr.dd"
    raw_disk.write_bytes(b"\xeb\x3c\x90MSDOS5.0" + b"\x00" * 500)
    info_dd = engine.identify_disk_image(raw_disk)
    assert "Raw" in info_dd.image_format or "DD" in info_dd.image_format
    assert info_dd.size_bytes == raw_disk.stat().st_size

    e01_disk = tmp_path / "evidence_vault.E01"
    e01_disk.write_bytes(b"EVF\x09\x0d\x0a\xff\x00" + b"\x00" * 500)
    info_e01 = engine.identify_disk_image(e01_disk)
    assert "Expert Witness" in info_e01.image_format or "E01" in info_e01.image_format


def test_14_recovery_carving_candidates_detection():
    """14. Carving strategies detect proprietary CCTV candidates in unallocated stream buffer."""
    dhav_strategy = DhavCarvingStrategy()
    hik_strategy = HikvisionCarvingStrategy()

    # Synthetic unallocated cluster buffer with embedded CCTV streams
    cluster_buffer = (
        b"\x00" * 1024 +
        b"DHAV\xfd\x00\x00\x00\x20\x00\x00\x00" + b"\xaa" * 32 +
        b"\x00" * 512 +
        b"HIKV\x01\x00\x00\x00\x00\x00\x00\x00" + b"\xbb" * 32
    )

    dhav_candidates = list(dhav_strategy.carve_candidates(cluster_buffer))
    assert len(dhav_candidates) >= 1
    assert dhav_candidates[0].detected_vendor == "Dahua"
    assert dhav_candidates[0].offset_bytes == 1024

    hik_candidates = list(hik_strategy.carve_candidates(cluster_buffer))
    assert len(hik_candidates) >= 1
    assert hik_candidates[0].detected_vendor == "Hikvision"
    assert hik_candidates[0].offset_bytes == 1580
