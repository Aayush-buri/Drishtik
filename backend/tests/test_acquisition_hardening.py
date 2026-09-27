import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import hashlib

from app.forensics.acquisition.hashing import calculate_file_hashes
from app.forensics.acquisition.file_copy import FileCopyAdapter
from app.forensics.acquisition.directory_copy import DirectoryCopyAdapter
from app.forensics.acquisition.disk_image import DiskImageAdapter, DiskImageInspectionStatus, DiskImageInspectionResult
from app.forensics.acquisition.network_stream import NetworkStreamAdapter, NetworkConnectionInfo, NetworkDeviceTarget
from app.forensics.acquisition.base import AcquisitionResult
from app.models.acquisition import AcquisitionMethod

def test_hashing_helper(tmp_path: Path):
    test_file = tmp_path / "test.bin"
    data = b"0" * 200000
    test_file.write_bytes(data)

    sha256, md5, size = calculate_file_hashes(test_file, chunk_size=65536)

    assert size == 200000
    assert sha256 == hashlib.sha256(data).hexdigest()
    assert md5 == hashlib.md5(data).hexdigest()

def test_file_copy_adapter(tmp_path: Path):
    src = tmp_path / "src.bin"
    src.write_bytes(b"hello")

    adapter = FileCopyAdapter(src)
    dest_dir = tmp_path / "dest"
    result = adapter.acquire(dest_dir)

    assert result.method == "FILE_COPY"
    assert result.acquired_size_bytes == 5
    assert result.size_bytes == 5
    assert result.verified is True
    assert result.sector_size is None

def test_directory_copy_adapter(tmp_path: Path):
    src_dir = tmp_path / "src_dir"
    src_dir.mkdir()
    (src_dir / "f1.txt").write_text("one")
    (src_dir / "f2.txt").write_text("two")

    adapter = DirectoryCopyAdapter(src_dir)
    dest_dir = tmp_path / "dest_dir"
    result = adapter.acquire(dest_dir)

    assert result.method == "DIRECTORY_COPY"
    assert result.item_count == 2
    assert result.verified is True

def test_raw_image_metadata(tmp_path: Path):
    src = tmp_path / "image.dd"
    src.write_bytes(b"123")

    adapter = DiskImageAdapter(src)
    dest_dir = tmp_path / "dest"
    result = adapter.acquire(dest_dir)

    assert result.method == "RAW_IMAGE"
    assert result.sector_size is None

def test_e01_unavailable(tmp_path: Path):
    src = tmp_path / "image.e01"
    src.write_bytes(b"123")

    adapter = DiskImageAdapter(src)
    adapter.inspect_image = MagicMock(return_value=DiskImageInspectionResult(
        status=DiskImageInspectionStatus.DETECTED_BUT_UNAVAILABLE,
        message="libewf not installed"
    ))
    dest_dir = tmp_path / "dest"
    result = adapter.acquire(dest_dir)

    assert result.method == "E01_IMAGE"
    assert result.error_message == "libewf not installed"
    assert result.sector_size is None

def test_network_live_pull_adapter(tmp_path: Path):
    dest_dir = tmp_path / "dest"



    with patch('subprocess.Popen') as mock_popen, patch('app.forensics.acquisition.network_stream.get_ffmpeg_executable') as mock_ffmpeg:
        mock_ffmpeg.return_value = "ffmpeg"
        mock_proc = MagicMock()
        mock_proc.stdout.read.side_effect = [b"dummy", b""]
        mock_proc.poll.return_value = 0
        mock_proc.stderr.read.return_value = b""
        mock_popen.return_value = mock_proc
        target = NetworkDeviceTarget(ip_address="1.1.1.1", rtsp_port=554, channel=1, username="user", password="pwd", device_label="test")
        adapter = NetworkStreamAdapter(target)
        adapter._connection_info = NetworkConnectionInfo("rtsp://dummy", "user", "pwd")
        result = adapter.acquire(dest_dir)
        assert result.method == "NETWORK_LIVE_PULL"
        assert result.source_sha256 is None
        assert result.source_md5 is None
        assert result.destination_sha256 is not None
        assert result.acquired_size_bytes == 5
        assert result.notes == "non-transcoding RTSP live acquisition; byte-for-byte source comparison not applicable"
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.services.acquisition_service import execute_acquisition
from app.models.acquisition import AcquisitionMethod, AcquisitionStatus
from app.models.case import Case
from app.models.device import Device
from app.models.audit import AuditLog

def test_service_level_partial_metadata(tmp_path: Path, db_session):
    # Case and Device setup
    case = Case(case_identifier="CASE-TEST", name="Test Case", created_by=1)
    db_session.add(case)
    db_session.commit()
    device = Device(device_identifier="DEV-TEST", manufacturer="Test", status="ACTIVE", case_id=case.id, created_by=1)
    db_session.add(device)
    db_session.commit()

    staging_dir = Path("data/case_data") / case.case_identifier / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    src_file = staging_dir / "src.bin"
    src_file.write_bytes(b"123")

    with patch('app.services.acquisition_service.get_acquisition_adapter') as mock_get_adapter:
        mock_adapter = MagicMock()
        mock_adapter.acquire.return_value = MagicMock(
            verified=False,
            error_message="Hash mismatch, partial transfer",
            source_sha256="abc",
            destination_sha256="def",
            source_md5="123",
            destination_md5="456",
            size_bytes=1000,
            acquired_size_bytes=3,
            method="FILE_COPY",
            tool_version="Test Tool",
            notes="partial",
            vendor="v1",
            device_model="m1",
            source_filesystem="ext4",
            source_type="FILE",
            sector_size=None,
            destination_path=Path("data/case_data/CASE-TEST/acq/dest.bin")
        )
        mock_get_adapter.return_value = mock_adapter

        acq = execute_acquisition(db_session, case, device, AcquisitionMethod.FILE_COPY, str(src_file), 1)

        # Assertions
        assert acq.status == AcquisitionStatus.FAILED
        assert acq.acquired_size_bytes == 3
        assert acq.source_sha256 == "abc"
        assert acq.destination_sha256 == "def"
        assert acq.method_str() == "FILE_COPY" if hasattr(acq, 'method_str') else acq.acquisition_method.value == "FILE_COPY"
        assert acq.tool_version == "Test Tool"
        assert "partial" in acq.notes
        assert acq.error_message == "Hash mismatch, partial transfer"
        assert acq.vendor == "v1"

        # Check Audit Log
        audit = db_session.query(AuditLog).filter_by(action="ACQUISITION_FAILED").first()
        assert audit is not None
        assert "abc" in audit.details
        assert "def" in audit.details

def test_service_level_e01_unavailable(tmp_path: Path, db_session):
    # E01 detected but unavailable test
    case = Case(case_identifier="CASE-TEST2", name="Test Case 2", created_by=1)
    db_session.add(case)
    db_session.commit()
    device = Device(device_identifier="DEV-TEST2", manufacturer="Test", status="ACTIVE", case_id=case.id, created_by=1)
    db_session.add(device)
    db_session.commit()

    staging_dir = Path("data/case_data") / case.case_identifier / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    src_file = staging_dir / "image.e01"
    src_file.write_bytes(b"123")

    with patch('app.services.acquisition_service.get_acquisition_adapter') as mock_get_adapter:
        from app.forensics.acquisition.disk_image import DiskImageAdapter, DiskImageInspectionStatus, DiskImageInspectionResult, DiskImageInfo
        mock_adapter = MagicMock(spec=DiskImageAdapter)
        mock_adapter.inspect_image.return_value = DiskImageInspectionResult(
            status=DiskImageInspectionStatus.DETECTED_BUT_UNAVAILABLE,
            info=DiskImageInfo(image_format="E01", size_bytes=3, sector_size=None, is_supported=True, details="missing"),
            message="libewf not installed"
        )
        mock_adapter.acquire.return_value = MagicMock(
            verified=True, # The copy succeeds, but it has an error_message
            error_message="libewf not installed",
            method="E01_IMAGE",
            source_type="IMAGE",
            sector_size=None,
            destination_path=Path("data/case_data/CASE-TEST2/acq/image.e01"),
            size_bytes=3,
            acquired_size_bytes=3,
            tool_version="pyewf fallback",
            notes=None,
            vendor=None,
            device_model=None,
            source_filesystem=None,
            source_sha256=None,
            destination_sha256=None,
            source_md5=None,
            destination_md5=None
        )
        mock_get_adapter.return_value = mock_adapter

        acq = execute_acquisition(db_session, case, device, AcquisitionMethod.E01_IMAGE, str(src_file), 1)

        assert acq.status == AcquisitionStatus.FAILED
        assert acq.acquisition_method.value == "E01_IMAGE"
        assert acq.source_type == "IMAGE"
        assert acq.sector_size is None
        assert acq.tool_version == "pyewf fallback"
        assert "libewf not installed" in acq.error_message
