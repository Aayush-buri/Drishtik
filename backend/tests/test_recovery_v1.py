import os
import uuid
import hashlib
from pathlib import Path
from sqlalchemy.orm import Session
import struct

from app.models.case import Case, CaseMember, RoleEnum
from app.models.user import User
from app.models.evidence import Evidence, EvidenceStatus
from app.models.recovery import RecoveryScanStatus, RecoveryCandidateStatus, RecoveryCandidate
from app.models.audit import AuditLog
from app.forensics.recovery.engine import RecoveryEngine
from app.services.recovery_service import start_recovery_scan, recover_candidate, validate_candidate

# Ensure tests run
def test_a_dhav_single_valid_frame(tmp_path):
    engine = RecoveryEngine()
    fpath = tmp_path / "1.raw"
    header = b"DHAV" + b"\xFD\x00\x00\x00" + b"\x64\x00\x00\x00" + b"\x00" * 12
    payload = b"\x55" * 100
    fpath.write_bytes(header + payload)

    cands = engine.scan_candidates(fpath)
    assert len(cands) == 1
    assert cands[0].length_bytes == 124
    assert cands[0].metadata["structural_status"] == "VALID"
    assert cands[0].metadata["frame_count"] == 1

def test_a_dhav_multiple_contiguous(tmp_path):
    engine = RecoveryEngine()
    fpath = tmp_path / "2.raw"
    h1 = b"DHAV" + b"\xFD\x00\x00\x00" + struct.pack("<I", 100) + b"\x00" * 12
    h2 = b"DHAV" + b"\xFD\x00\x01\x00" + struct.pack("<I", 200) + b"\x00" * 12 # seq=1

    fpath.write_bytes(h1 + b"A"*100 + h2 + b"B"*200)

    cands = engine.scan_candidates(fpath)
    assert len(cands) == 1
    assert cands[0].length_bytes == 24 + 100 + 24 + 200
    assert cands[0].metadata["frame_count"] == 2
    assert cands[0].metadata["last_sequence"] == 1

def test_a_dhav_sequence_discontinuity(tmp_path):
    engine = RecoveryEngine()
    fpath = tmp_path / "4.raw"
    h1 = b"DHAV" + b"\xFD\x00\x00\x00" + struct.pack("<I", 100) + b"\x00" * 12
    h2 = b"DHAV" + b"\xFD\x00\x05\x00" + struct.pack("<I", 200) + b"\x00" * 12 # seq=5! Jump!

    fpath.write_bytes(h1 + b"A"*100 + h2 + b"B"*200)

    cands = engine.scan_candidates(fpath)
    # Should split into two candidates because of sequence jump
    assert len(cands) == 2
    assert cands[0].length_bytes == 124
    assert cands[1].length_bytes == 224

def test_a_dhav_channel_inconsistency(tmp_path):
    engine = RecoveryEngine()
    fpath = tmp_path / "5.raw"
    h1 = b"DHAV" + b"\xFD\x00\x00\x00" + struct.pack("<I", 100) + b"\x00" * 12
    h2 = b"DHAV" + b"\xFD\x01\x01\x00" + struct.pack("<I", 100) + b"\x00" * 12 # ch=2
    fpath.write_bytes(h1 + b"A"*100 + h2 + b"B"*100)

    cands = engine.scan_candidates(fpath)
    assert len(cands) == 2

def test_a_dhav_truncated(tmp_path):
    engine = RecoveryEngine()
    fpath = tmp_path / "6.raw"
    h1 = b"DHAV" + b"\xFD\x00\x00\x00" + struct.pack("<I", 100) + b"\x00" * 12
    fpath.write_bytes(h1 + b"A"*50)

    cands = engine.scan_candidates(fpath)
    assert len(cands) == 1
    assert cands[0].metadata["structural_status"] == "PARTIAL"
    assert cands[0].length_bytes == 24 + 50

def test_a_dhav_malformed_header(tmp_path):
    engine = RecoveryEngine()
    fpath = tmp_path / "7.raw"
    # payload size 0 is malformed
    h1 = b"DHAV" + b"\xFD\x00\x00\x00" + struct.pack("<I", 0) + b"\x00" * 12
    fpath.write_bytes(h1)

    cands = engine.scan_candidates(fpath)
    assert len(cands) == 0

def test_b_hikvision_mpeg_ps(tmp_path):
    engine = RecoveryEngine()
    fpath = tmp_path / "10.raw"
    # Pack header (14 bytes)
    pack = b"\x00\x00\x01\xba" + b"\x44\x00\x04\x00\x04\x01\x01\x89\xc3\xf8"
    # PES header
    pes = b"\x00\x00\x01\xe0" + struct.pack(">H", 10) + b"A"*10
    fpath.write_bytes(pack + pes)

    cands = engine.scan_candidates(fpath)
    assert len(cands) == 1
    assert cands[0].length_bytes == 14 + 6 + 10
    assert cands[0].metadata["structural_status"] == "VALID"

def test_b_hikvision_truncated_pes(tmp_path):
    engine = RecoveryEngine()
    fpath = tmp_path / "12.raw"
    pack = b"\x00\x00\x01\xba" + b"\x44\x00\x04\x00\x04\x01\x01\x89\xc3\xf8"
    pes = b"\x00\x00\x01\xe0" + struct.pack(">H", 100) + b"A"*10 # Declares 100, only has 10
    fpath.write_bytes(pack + pes)

    cands = engine.scan_candidates(fpath)
    assert len(cands) == 1
    assert cands[0].length_bytes == 14 + 6 + 10
    assert cands[0].metadata["structural_status"] == "PARTIAL"

def test_c_mp4_boxes(tmp_path):
    engine = RecoveryEngine()
    fpath = tmp_path / "14.raw"
    # ftyp 32 bytes
    ftyp = struct.pack(">I", 32) + b"ftypisom" + struct.pack(">I", 1) + b"isommp41" + b"\x00"*8
    moov = struct.pack(">I", 16) + b"moov" + b"\x00"*8
    mdat = struct.pack(">I", 24) + b"mdat" + b"\x00"*16
    fpath.write_bytes(ftyp + moov + mdat)

    cands = engine.scan_candidates(fpath)
    assert len(cands) == 1
    assert cands[0].length_bytes == 32 + 16 + 24
    assert cands[0].metadata["has_moov"] is True
    assert cands[0].metadata["has_mdat"] is True

def test_c_mp4_malformed_box(tmp_path):
    engine = RecoveryEngine()
    fpath = tmp_path / "15.raw"
    ftyp = struct.pack(">I", 32) + b"ftypisom" + struct.pack(">I", 1) + b"isommp41" + b"\x00"*8
    moov = struct.pack(">I", 4) + b"moov" # length 4 is malformed/too short for anything but just box header? wait, 8 is min
    fpath.write_bytes(ftyp + moov)

    cands = engine.scan_candidates(fpath)
    assert len(cands) == 1
    assert cands[0].metadata["structural_status"] == "PARTIAL"
    assert cands[0].length_bytes == 32 # Only parsed ftyp

def test_d_extraction(tmp_path):
    engine = RecoveryEngine()
    fpath = tmp_path / "17.raw"
    fpath.write_bytes(b"A"*1000)
    out = tmp_path / "out.raw"
    extracted = engine.extract_candidate_bytes(fpath, 100, 200, out)
    assert extracted == 200
    assert len(out.read_bytes()) == 200

    # test 18: EOF boundary is respected
    extracted = engine.extract_candidate_bytes(fpath, 900, 500, out)
    assert extracted == 100

def test_e_service_corrupted(db_session: Session, tmp_path):
    case = Case(case_identifier="CASE-TEST-1", name="Test", created_by=1)
    db_session.add(case)
    db_session.commit()

    cand = RecoveryCandidate(
        candidate_identifier="REC-TEST1",
        case_id=case.id,
        source_evidence_id=1,
        source_offset=0,
        size_bytes=10,
        detected_format="DHAV", vendor="Dahua",
        status=RecoveryCandidateStatus.CORRUPTED
    )
    db_session.add(cand)
    db_session.commit()

    try:
        recover_candidate(db_session, case, cand.id, 1)
        assert False, "Should refuse corrupted"
    except Exception as e:
        assert "Cannot recover structurally corrupted candidates" in str(e)

# --- HIKV Structural Tests ---

def test_hikv_test_a_dynamic_length(tmp_path):
    """Test A: HIKV followed by valid MPEG-PS structure with arbitrary wrapper length."""
    engine = RecoveryEngine()
    fpath = tmp_path / "hikv_a.raw"

    # 20 byte wrapper (4 for HIKV + 16 random)
    wrapper = b"HIKV" + b"\xAA" * 16
    # 14 byte pack + 0 stuffing + 6 byte PES header + 10 byte payload = 30 bytes
    pack = b"\x00\x00\x01\xba" + b"\x44\x00\x04\x00\x04\x01\x01\x89\xc3\xf8"
    pes = b"\x00\x00\x01\xe0" + b"\x00\x0a" + b"\x55" * 10

    fpath.write_bytes(wrapper + pack + pes)

    cands = engine.scan_candidates(fpath)
    assert len(cands) == 1
    c = cands[0]

    # Assert candidate starts at HIKV and is EXACTLY 50 bytes
    assert c.offset_bytes == 0
    assert c.length_bytes == 50
    assert c.length_bytes != 32
    assert c.metadata["structural_status"] == "VALID"
    assert c.metadata.get("wrapper_extent_known") is False
    assert c.metadata["mpeg_ps_structural_length"] == 30

def test_hikv_test_b_insufficient_bytes(tmp_path):
    """Test B: HIKV followed by random bytes, no valid MPEG-PS."""
    engine = RecoveryEngine()
    fpath = tmp_path / "hikv_b.raw"

    wrapper = b"HIKV" + b"\xAA" * 12
    fpath.write_bytes(wrapper)

    cands = engine.scan_candidates(fpath)
    assert len(cands) == 1
    c = cands[0]

    assert c.offset_bytes == 0
    assert c.length_bytes == 16
    assert c.metadata["structural_status"] == "PARTIAL"
    assert c.metadata.get("wrapper_extent_known") is False
    assert "mpeg_ps_structural_length" not in c.metadata

def test_hikv_test_c_multiple_wrappers(tmp_path):
    """Test C: Two different synthetic wrapper lengths to prove lengths differ."""
    engine = RecoveryEngine()

    # Pack: 14 + PES: 6+10 = 30 bytes
    pack = b"\x00\x00\x01\xba" + b"\x44\x00\x04\x00\x04\x01\x01\x89\xc3\xf8"
    pes = b"\x00\x00\x01\xe0" + b"\x00\x0a" + b"\x55" * 10

    # Case 1: 20-byte wrapper
    fpath1 = tmp_path / "hikv_c1.raw"
    fpath1.write_bytes(b"HIKV" + b"\xAA" * 16 + pack + pes)

    # Case 2: 37-byte wrapper
    fpath2 = tmp_path / "hikv_c2.raw"
    fpath2.write_bytes(b"HIKV" + b"\xBB" * 33 + pack + pes)

    cands1 = engine.scan_candidates(fpath1)
    cands2 = engine.scan_candidates(fpath2)

    assert cands1[0].length_bytes == 20 + 30
    assert cands2[0].length_bytes == 37 + 30
    assert cands1[0].length_bytes != cands2[0].length_bytes

# --- Scan Bound Enforcement Tests ---

def test_max_bytes_enforcement(tmp_path):
    """Ensure a strategy does not structurally consume bytes beyond max_bytes."""
    engine = RecoveryEngine()
    fpath = tmp_path / "scan_limit.raw"

    # Total file is 200 bytes.
    # Single DHAV frame: 24 byte header + 100 byte payload = 124 bytes
    header = b"DHAV" + b"\xFD\x00\x00\x00" + b"\x64\x00\x00\x00" + b"\x00" * 12
    payload = b"\x55" * 100
    padding = b"\x00" * 76
    fpath.write_bytes(header + payload + padding)

    # Set max_bytes to 50 bytes (which falls midway through the frame)
    cands = engine.scan_candidates(fpath, max_bytes=50)

    assert len(cands) == 1
    c = cands[0]
    assert c.length_bytes == 50
    assert c.metadata["structural_status"] == "PARTIAL"
    assert c.metadata.get("scan_limit_truncated") is True

def test_max_bytes_physical_bound(tmp_path, monkeypatch):
    """Ensure that the recovery engine physically stops reading at max_bytes limit."""
    engine = RecoveryEngine()
    fpath = tmp_path / "physical_limit.raw"

    # Create file much larger than limit
    fpath.write_bytes(b"\x55" * (2 * 1024 * 1024))

    import builtins
    original_open = builtins.open

    all_reads = []
    max_read_single_call = 0

    class SpiedFile:
        def __init__(self, f):
            self.f = f
            self.bytes_read = 0
            all_reads.append(self)

        def read(self, size=-1):
            nonlocal max_read_single_call
            res = self.f.read(size)
            self.bytes_read += len(res)
            if size != -1 and size > max_read_single_call:
                max_read_single_call = size
            return res

        def __getattr__(self, attr):
            return getattr(self.f, attr)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.f.close()

    def mocked_open(*args, **kwargs):
        if str(args[0]) == str(fpath):
            return SpiedFile(original_open(*args, **kwargs))
        return original_open(*args, **kwargs)

    monkeypatch.setattr(builtins, 'open', mocked_open)

    # Set limit to 50 bytes
    cands = engine.scan_candidates(fpath, max_bytes=50)

    # Ensure no individual reader read more than 50 bytes
    for sf in all_reads:
        assert sf.bytes_read <= 50
    assert max_read_single_call <= 50
