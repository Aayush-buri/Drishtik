import pytest
from pathlib import Path
import os
import time

from app.forensics.acquisition.disk_image import DiskImageAdapter, DiskImageInspectionStatus

def test_raw_image_inspection(tmp_path: Path):
    """A. Valid synthetic/raw image still works."""
    raw_file = tmp_path / "test.raw"
    raw_file.write_bytes(b"0" * 1024)

    adapter = DiskImageAdapter(raw_file)
    result = adapter.inspect_image()

    assert result.status == DiskImageInspectionStatus.SUPPORTED
    assert result.info is not None
    assert result.info.image_format == "Raw / DD Bitstream Image"
    assert result.info.size_bytes == 1024
    assert result.info.sector_size == 512

def test_e01_signature_detection_unavailable(tmp_path: Path):
    """B & C. E01 signature detection works; inspection capability unavailable.
    - must return an explicit 'detected but unavailable' type/status
    """
    e01_file = tmp_path / "test.e01"

    # Write EVF signature
    header = bytearray(512)
    header[0:3] = b"EVF"
    e01_file.write_bytes(header)

    adapter = DiskImageAdapter(e01_file)
    result = adapter.inspect_image()

    # Since pyewf is not installed in the environment, it must gracefully fallback
    assert result.status == DiskImageInspectionStatus.DETECTED_BUT_UNAVAILABLE
    assert result.info is not None
    assert result.info.image_format == "E01 (Expert Witness Format)"
    assert result.info.sector_size is None

def test_invalid_corrupt_e01(tmp_path: Path):
    """E. Invalid/corrupt E01-like input must not be reported as successfully inspected."""
    e01_file = tmp_path / "bad.e01"

    # Extension is .e01 but NO EVF signature
    e01_file.write_bytes(b"NOT_EVF_DATA_JUST_GARBAGE")

    adapter = DiskImageAdapter(e01_file)
    result = adapter.inspect_image()

    assert result.status == DiskImageInspectionStatus.INVALID_OR_UNREADABLE
    assert "missing EVF signature" in result.message

def test_source_immutability(tmp_path: Path):
    """F. Source immutability:
    - size unchanged;
    - mtime unchanged where practical.
    """
    e01_file = tmp_path / "test2.e01"
    header = bytearray(512)
    header[0:3] = b"EVF"
    e01_file.write_bytes(header)

    stat_before = e01_file.stat()

    # wait a moment to ensure mtime would be different if modified
    time.sleep(0.1)

    adapter = DiskImageAdapter(e01_file)
    adapter.inspect_image()

    stat_after = e01_file.stat()

    assert stat_before.st_size == stat_after.st_size
    assert stat_before.st_mtime == stat_after.st_mtime
