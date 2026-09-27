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
    assert result.info.sector_size is None

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

import json
from unittest.mock import patch, MagicMock
from app.models.acquisition import AcquisitionMethod, AcquisitionStatus
from app.services.acquisition_service import execute_acquisition
from app.models.case import Case
from app.models.device import Device
from app.models.audit import AuditLog
from app.forensics.recovery.engine import DiskImageInfo

def test_integration_disk_image_supported(tmp_path: Path, db_session):
    # Setup mock case and device
    case = Case(case_identifier="CASE-TEST", name="Test Case", created_by=1)
    db_session.add(case)
    db_session.commit()
    device = Device(device_identifier="DEV-TEST", manufacturer="Test", status="ACTIVE", case_id=case.id, created_by=1)
    db_session.add(device)
    db_session.commit()

    # Fake staging dir so execute_acquisition bypasses physical device check
    staging_dir = Path("data") / "case_data" / case.case_identifier / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    staged_file = staging_dir / "test_integration.raw"
    staged_file.write_bytes(b"12345678")

    with patch("app.services.acquisition_service.get_acquisition_adapter") as mock_get_adapter:
        mock_adapter = MagicMock(spec=DiskImageAdapter)
        mock_adapter.inspect_image.return_value = MagicMock(
            status=DiskImageInspectionStatus.SUPPORTED,
            info=DiskImageInfo(image_format="Raw", size_bytes=8, sector_size=512),
            message="Looks good"
        )
        mock_adapter.acquire.return_value = MagicMock(
            verified=True,
            source_sha256="abc",
            destination_sha256="abc",
            source_md5="123",
            destination_md5="123",
            size_bytes=8,
            destination_path=Path("data") / "case_data" / case.case_identifier / "acq" / "dest.raw", method=AcquisitionMethod.DISK_IMAGE, sector_size=512, acquired_size_bytes=8, tool_version="Test", vendor=None, device_model=None, source_filesystem=None, source_type="IMAGE"
        )
        mock_get_adapter.return_value = mock_adapter

        acq = execute_acquisition(
            db=db_session,
            case=case,
            device=device,
            method=AcquisitionMethod.DISK_IMAGE,
            source_path_input=str(staged_file),
            user_id=1
        )

        assert acq.status == AcquisitionStatus.COMPLETED
        # Check notes
        assert "Disk Image Inspection: SUPPORTED" in acq.notes

        # Check audit log
        audit = db_session.query(AuditLog).filter_by(action="ACQUISITION_DISK_INSPECTED").first()
        assert audit is not None
        details = json.loads(audit.details)
        assert details["status"] == "SUPPORTED"
        assert details["format"] == "Raw"

        # Cleanup
        staged_file.unlink()

def test_integration_disk_image_invalid(tmp_path: Path, db_session):
    case = Case(case_identifier="CASE-TEST2", name="Test Case 2", created_by=1)
    db_session.add(case)
    db_session.commit()
    device = Device(device_identifier="DEV-TEST2", manufacturer="Test", status="ACTIVE", case_id=case.id, created_by=1)
    db_session.add(device)
    db_session.commit()

    staging_dir = Path("data") / "case_data" / case.case_identifier / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    staged_file = staging_dir / "bad.e01"
    staged_file.write_bytes(b"junk")

    with patch("app.services.acquisition_service.get_acquisition_adapter") as mock_get_adapter:
        mock_adapter = MagicMock(spec=DiskImageAdapter)
        mock_adapter.inspect_image.return_value = MagicMock(
            status=DiskImageInspectionStatus.INVALID_OR_UNREADABLE,
            info=None,
            message="No EVF signature found"
        )
        mock_get_adapter.return_value = mock_adapter

        acq = execute_acquisition(
            db=db_session,
            case=case,
            device=device,
            method=AcquisitionMethod.DISK_IMAGE,
            source_path_input=str(staged_file),
            user_id=1
        )

        # The exception is caught by execute_acquisition and marks it as FAILED
        assert acq.status == AcquisitionStatus.FAILED
        assert "INVALID_OR_UNREADABLE" in acq.error_message
        assert "No EVF signature found" in acq.error_message

        # Should not have an inspection audit event (it aborted before db_commit)
        audit = db_session.query(AuditLog).filter_by(action="ACQUISITION_DISK_INSPECTED").first()
        assert audit is None

        staged_file.unlink()
