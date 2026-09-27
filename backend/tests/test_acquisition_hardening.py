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
