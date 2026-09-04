import pytest
import io
import hashlib
from pathlib import Path
from sqlalchemy.orm import Session

from app.models.case import Case, CaseMember, RoleEnum
from app.models.user import User
from app.models.device import Device, DeviceType, DeviceStatus
from app.models.acquisition import Acquisition, AcquisitionMethod, AcquisitionStatus
from app.models.evidence import Evidence
from app.models.audit import AuditLog
from app.core.security import get_password_hash
from app.forensics.acquisition.file_copy import FileCopyAdapter
from app.forensics.acquisition.directory_copy import DirectoryCopyAdapter
from app.forensics.acquisition.disk_image import DiskImageAdapter

@pytest.fixture
def device_test_users(db_session: Session):
    u_admin = User(username="dev_admin", display_name="Device Admin", password_hash=get_password_hash("pass"), is_active=True)
    u_inv = User(username="dev_inv", display_name="Device Investigator", password_hash=get_password_hash("pass"), is_active=True)
    u_view = User(username="dev_view", display_name="Device Viewer", password_hash=get_password_hash("pass"), is_active=True)
    u_other = User(username="dev_other", display_name="Other Case User", password_hash=get_password_hash("pass"), is_active=True)
    db_session.add_all([u_admin, u_inv, u_view, u_other])
    db_session.commit()
    return {"admin": u_admin, "inv": u_inv, "view": u_view, "other": u_other}

@pytest.fixture
def device_test_case(db_session: Session, device_test_users):
    c = Case(case_identifier="CASE-DEVTEST1", name="Forensic Device Case", created_by=device_test_users["admin"].id)
    db_session.add(c)
    db_session.commit()

    m1 = CaseMember(case_id=c.id, user_id=device_test_users["admin"].id, role=RoleEnum.ADMIN)
    m2 = CaseMember(case_id=c.id, user_id=device_test_users["inv"].id, role=RoleEnum.INVESTIGATOR)
    m3 = CaseMember(case_id=c.id, user_id=device_test_users["view"].id, role=RoleEnum.VIEWER)
    db_session.add_all([m1, m2, m3])
    db_session.commit()
    return c

async def get_token(async_client, username: str, password: str = "pass"):
    res = await async_client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]

@pytest.mark.asyncio
async def test_device_rbac_and_crud(async_client, device_test_case, device_test_users):
    admin_token = await get_token(async_client, "dev_admin")
    inv_token = await get_token(async_client, "dev_inv")
    view_token = await get_token(async_client, "dev_view")
    other_token = await get_token(async_client, "dev_other")
    case_id = device_test_case.case_identifier

    # 1. Admin creates device
    dev1_res = await async_client.post(
        f"/api/v1/cases/{case_id}/devices",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "device_type": "DVR",
            "manufacturer": "CP Plus",
            "model": "CP-UVR-0801E1-V3",
            "serial_number": "CP12345678",
            "firmware_version": "v3.2.1",
            "channel_count": 8,
            "storage_capacity": "1 TB",
            "location": "Control Room Rack A"
        }
    )
    assert dev1_res.status_code == 200, dev1_res.text
    dev1 = dev1_res.json()
    assert dev1["device_identifier"].startswith("DEV-")
    assert dev1["manufacturer"] == "CP Plus"
    assert dev1["status"] == "ACTIVE"
    dev1_id = dev1["device_identifier"]

    # 2. Investigator creates device
    dev2_res = await async_client.post(
        f"/api/v1/cases/{case_id}/devices",
        headers={"Authorization": f"Bearer {inv_token}"},
        json={
            "device_type": "NVR",
            "manufacturer": "Hikvision",
            "model": "DS-7616NI-K2",
            "channel_count": 16,
            "storage_capacity": "4 TB"
        }
    )
    assert dev2_res.status_code == 200, dev2_res.text
    dev2 = dev2_res.json()
    assert dev2["manufacturer"] == "Hikvision"

    # 3. Viewer attempts to create device -> 403
    view_create = await async_client.post(
        f"/api/v1/cases/{case_id}/devices",
        headers={"Authorization": f"Bearer {view_token}"},
        json={"device_type": "INTERNAL_HDD"}
    )
    assert view_create.status_code == 403

    # Viewer can read devices and details
    list_res = await async_client.get(
        f"/api/v1/cases/{case_id}/devices",
        headers={"Authorization": f"Bearer {view_token}"}
    )
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 2

    get_res = await async_client.get(
        f"/api/v1/cases/{case_id}/devices/{dev1_id}",
        headers={"Authorization": f"Bearer {view_token}"}
    )
    assert get_res.status_code == 200
    assert get_res.json()["device_identifier"] == dev1_id

    # 4. Unauthorized cross-case access is rejected
    cross_res = await async_client.get(
        f"/api/v1/cases/{case_id}/devices",
        headers={"Authorization": f"Bearer {other_token}"}
    )
    assert cross_res.status_code == 403

    # 5. Device update
    update_res = await async_client.put(
        f"/api/v1/cases/{case_id}/devices/{dev1_id}",
        headers={"Authorization": f"Bearer {inv_token}"},
        json={"notes": "Inspected and tagged by forensic team"}
    )
    assert update_res.status_code == 200
    assert update_res.json()["notes"] == "Inspected and tagged by forensic team"

    # Viewer cannot update
    view_update = await async_client.put(
        f"/api/v1/cases/{case_id}/devices/{dev1_id}",
        headers={"Authorization": f"Bearer {view_token}"},
        json={"notes": "Viewer attempt"}
    )
    assert view_update.status_code == 403

    # 6. Device archive: Investigator cannot archive -> 403
    arch_inv = await async_client.post(
        f"/api/v1/cases/{case_id}/devices/{dev1_id}/archive",
        headers={"Authorization": f"Bearer {inv_token}"}
    )
    assert arch_inv.status_code == 403

    # Admin archives dev2 (no acquisitions attached)
    arch_ok = await async_client.post(
        f"/api/v1/cases/{case_id}/devices/{dev2['device_identifier']}/archive",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert arch_ok.status_code == 200
    assert arch_ok.json()["status"] == "ARCHIVED"

@pytest.mark.asyncio
async def test_forensic_acquisition_and_evidence_creation(async_client, device_test_case, device_test_users, tmp_path):
    admin_token = await get_token(async_client, "dev_admin")
    inv_token = await get_token(async_client, "dev_inv")
    case_id = device_test_case.case_identifier

    # Register Device
    dev_res = await async_client.post(
        f"/api/v1/cases/{case_id}/devices",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "device_type": "DVR",
            "manufacturer": "Dahua Technology",
            "model": "DHI-XVR5108HS-4KL-I3",
            "channel_count": 8
        }
    )
    assert dev_res.status_code == 200
    dev_id = dev_res.json()["device_identifier"]

    # Create dummy forensic source file
    source_content = b"FORENSIC_EVIDENCE_SOURCE_BITSTREAM_DATA_TEST_12345"
    source_file = tmp_path / "camera_feed_ch01.mp4"
    source_file.write_bytes(source_content)

    src_sha256 = hashlib.sha256(source_content).hexdigest()
    src_md5 = hashlib.md5(source_content).hexdigest()
    source_stat_before = source_file.stat()

    # Perform Acquisition via file upload
    with open(source_file, "rb") as f:
        acq_res = await async_client.post(
            f"/api/v1/cases/{case_id}/devices/{dev_id}/acquisitions",
            headers={"Authorization": f"Bearer {inv_token}"},
            data={"method": "FILE_COPY", "notes": "Channel 1 direct bitstream copy"},
            files={"file": ("camera_feed_ch01.mp4", f, "video/mp4")}
        )

    assert acq_res.status_code == 200, acq_res.text
    acq_data = acq_res.json()
    assert acq_data["acquisition_identifier"].startswith("ACQ-")
    assert acq_data["status"] == "COMPLETED"
    assert acq_data["progress"] == 100
    assert acq_data["source_sha256"] == src_sha256
    assert acq_data["destination_sha256"] == src_sha256
    assert acq_data["source_md5"] == src_md5
    assert acq_data["destination_md5"] == src_md5
    acq_id = acq_data["acquisition_identifier"]

    # Verify source file was completely untouched
    source_stat_after = source_file.stat()
    assert source_stat_before.st_size == source_stat_after.st_size
    assert source_stat_before.st_mtime == source_stat_after.st_mtime

    # Verify device status updated to ACQUIRED
    dev_check = await async_client.get(
        f"/api/v1/cases/{case_id}/devices/{dev_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert dev_check.json()["status"] == "ACQUIRED"
    assert dev_check.json()["acquisitions_count"] == 1

    # Verify archive warning when acquisitions exist
    arch_warn = await async_client.post(
        f"/api/v1/cases/{case_id}/devices/{dev_id}/archive",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"confirm_with_acquisitions": False}
    )
    assert arch_warn.status_code == 400
    assert "associated forensic acquisition" in arch_warn.json()["detail"]["message"]

    # Archive succeeds when confirmed
    arch_ok = await async_client.post(
        f"/api/v1/cases/{case_id}/devices/{dev_id}/archive",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"confirm_with_acquisitions": True, "reason": "Investigation complete"}
    )
    assert arch_ok.status_code == 200
    assert arch_ok.json()["status"] == "ARCHIVED"

    # Cannot start acquisition on archived device
    acq_archived = await async_client.post(
        f"/api/v1/cases/{case_id}/devices/{dev_id}/acquisitions",
        headers={"Authorization": f"Bearer {inv_token}"},
        data={"method": "FILE_COPY", "source_path": str(source_file)}
    )
    assert acq_archived.status_code == 400

    # Create Evidence from Acquisition
    ev_res = await async_client.post(
        f"/api/v1/cases/{case_id}/acquisitions/{acq_id}/create-evidence",
        headers={"Authorization": f"Bearer {inv_token}"},
        json={"custom_name": "Lobby Camera 01 (Acquired)"}
    )
    assert ev_res.status_code == 200, ev_res.text
    ev_data = ev_res.json()
    assert ev_data["evidence_identifier"].startswith("EVD-")
    assert ev_data["source_type"] == "Acquired"
    assert ev_data["sha256"] == src_sha256
    assert ev_data["md5_reference"] == src_md5
    assert ev_data["device_identifier"] == dev_id
    assert ev_data["acquisition_identifier"] == acq_id
    assert ev_data["acquisition_method"] == "FILE_COPY"

    # Inspect evidence endpoint returns relational provenance
    ev_inspect = await async_client.get(
        f"/api/v1/cases/{case_id}/evidence/{ev_data['id']}",
        headers={"Authorization": f"Bearer {inv_token}"}
    )
    assert ev_inspect.status_code == 200
    insp_data = ev_inspect.json()
    assert insp_data["device_identifier"] == dev_id
    assert insp_data["device_manufacturer"] == "Dahua Technology"
    assert insp_data["acquisition_identifier"] == acq_id

    # Verify audit trail contains all expected actions
    audit_res = await async_client.get(
        f"/api/v1/cases/{case_id}/audit-logs",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert audit_res.status_code == 200
    actions = [a["action"] for a in audit_res.json()]
    assert "DEVICE_CREATED" in actions
    assert "DEVICE_ARCHIVED" in actions
    assert "ACQUISITION_STARTED" in actions
    assert "ACQUISITION_COMPLETED" in actions
    assert "EVIDENCE_CREATED_FROM_ACQUISITION" in actions

@pytest.mark.asyncio
async def test_directory_and_disk_image_adapters(tmp_path: Path):
    # 1. Test DirectoryCopyAdapter
    src_dir = tmp_path / "dvr_export_dir"
    src_dir.mkdir()
    f1 = src_dir / "ch1_001.mp4"
    f2 = src_dir / "ch2_001.mp4"
    f1.write_bytes(b"VIDEO_CH1_STREAM_DATA")
    f2.write_bytes(b"VIDEO_CH2_STREAM_DATA")

    dir_adapter = DirectoryCopyAdapter(src_dir)
    assert dir_adapter.validate_source() is True
    assert dir_adapter.estimate_size() == len(b"VIDEO_CH1_STREAM_DATA") + len(b"VIDEO_CH2_STREAM_DATA")

    dst_dir = tmp_path / "acq_dst_dir"
    res = dir_adapter.acquire(dst_dir)
    assert res.verified is True
    assert res.item_count == 2
    assert res.source_sha256 == res.destination_sha256
    assert (dst_dir / "acquisition_manifest.json").exists()

    # 2. Test DiskImageAdapter
    disk_file = tmp_path / "forensic_source.dd"
    disk_file.write_bytes(b"FORENSIC_RAW_BITSTREAM_DISK_BLOCKS" * 100)
    disk_adapter = DiskImageAdapter(disk_file)
    assert disk_adapter.validate_source() is True

    disk_dst = tmp_path / "disk_dst"
    disk_res = disk_adapter.acquire(disk_dst)
    assert disk_res.verified is True
    assert disk_res.source_sha256 == disk_res.destination_sha256

@pytest.mark.asyncio
async def test_regression_case_bde2cdfe_device_registration(async_client, db_session: Session):
    # Setup test user as admin
    user = User(
        username="reg_admin",
        display_name="Regression Admin",
        password_hash=get_password_hash("pass"),
        is_active=True
    )
    db_session.add(user)
    db_session.commit()

    # Create Case specifically with CASE-BDE2CDFE
    case = Case(
        case_identifier="CASE-BDE2CDFE",
        name="Bank CCTV Test Regression",
        created_by=user.id
    )
    db_session.add(case)
    db_session.commit()

    member = CaseMember(case_id=case.id, user_id=user.id, role=RoleEnum.ADMIN)
    db_session.add(member)
    db_session.commit()

    token = await get_token(async_client, "reg_admin")

    # 1. Register device using public human-readable case identifier: CASE-BDE2CDFE
    # Testing exact payload described by the user
    payload = {
        "device_type": "EXTERNAL_STORAGE",
        "manufacturer": "Unknown",
        "model": "unknown",
        "serial_number": "unknown",
        "firmware_version": "not available",
        "storage_capacity": "64GB",
        "location": "personal",
        "notes": "USB drive physically intact, no visible damage."
    }

    res = await async_client.post(
        f"/api/v1/cases/CASE-BDE2CDFE/devices",
        headers={"Authorization": f"Bearer {token}"},
        json=payload
    )
    assert res.status_code == 200, res.text
    created_device = res.json()
    assert created_device["device_identifier"].startswith("DEV-")
    assert created_device["device_type"] == "EXTERNAL_STORAGE"
    assert created_device["storage_capacity"] == "64GB"
    assert created_device["manufacturer"] == "Unknown"
    assert created_device["status"] == "ACTIVE"
    dev_ident = created_device["device_identifier"]

    # Verify database relationship: Device.case_id == case.id
    db_dev = db_session.query(Device).filter(Device.device_identifier == dev_ident).first()
    assert db_dev is not None
    assert db_dev.case_id == case.id

    # 2. Fetch devices list for CASE-BDE2CDFE and verify device is returned
    list_res = await async_client.get(
        f"/api/v1/cases/CASE-BDE2CDFE/devices",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert list_res.status_code == 200
    devices = list_res.json()
    assert any(d["device_identifier"] == dev_ident for d in devices)

    # 3. Verify that numeric internal ID (case.id) ALSO successfully resolves the case
    # to guarantee compatibility with routes using numeric caseId
    num_res = await async_client.get(
        f"/api/v1/cases/{case.id}/devices",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert num_res.status_code == 200
    num_devices = num_res.json()
    assert any(d["device_identifier"] == dev_ident for d in num_devices)

    # 4. Also register device via numeric ID endpoint to ensure full bidirectional resolution
    payload2 = {
        "device_type": "EXTERNAL_STORAGE",
        "manufacturer": "SanDisk",
        "storage_capacity": "32GB"
    }
    num_post = await async_client.post(
        f"/api/v1/cases/{case.id}/devices",
        headers={"Authorization": f"Bearer {token}"},
        json=payload2
    )
    assert num_post.status_code == 200
    dev2 = num_post.json()
    assert dev2["case_id"] == case.id

@pytest.mark.asyncio
async def test_controlled_source_acquisition_and_boundary_checks(async_client, device_test_case, device_test_users, tmp_path):
    admin_token = await get_token(async_client, "dev_admin")
    inv_token = await get_token(async_client, "dev_inv")
    case_id = device_test_case.case_identifier

    # Setup a mock connected USB / source device directory
    mock_usb = tmp_path / "mock_usb_drive"
    mock_usb.mkdir()
    (mock_usb / "dvr_recordings").mkdir()
    
    # Place valid evidence clips inside mock USB
    clip1 = mock_usb / "dvr_recordings" / "cam01_footage.mp4"
    clip1_bytes = b"MOCK_USB_CCTV_STREAM_DATA_CAM01_VERIFIED"
    clip1.write_bytes(clip1_bytes)
    clip1_sha256 = hashlib.sha256(clip1_bytes).hexdigest()
    clip1_md5 = hashlib.md5(clip1_bytes).hexdigest()
    clip1_stat_before = clip1.stat()

    # Place an unauthorized file outside the mock USB
    outside_dir = tmp_path / "unauthorized_laptop_folder"
    outside_dir.mkdir()
    outside_file = outside_dir / "confidential_personal_doc.pdf"
    outside_file.write_bytes(b"UNAUTHORIZED_LAPTOP_FILE")

    # 1. Register device WITH controlled source_root
    reg_res = await async_client.post(
        f"/api/v1/cases/{case_id}/devices",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "device_type": "EXTERNAL_STORAGE",
            "manufacturer": "Kingston",
            "model": "DataTraveler Exodia",
            "storage_capacity": "64GB",
            "location": "Physical Seizure Locker B",
            "source_root": str(mock_usb),
            "notes": "Seized USB drive connected at mock workstation mount"
        }
    )
    assert reg_res.status_code == 200, reg_res.text
    dev_data = reg_res.json()
    dev_id = dev_data["device_identifier"]
    assert dev_data["source_root"] == str(mock_usb)
    assert dev_data["is_connected"] is True
    assert dev_data["connection_status"] == "CONNECTED"

    # 2. Status endpoint confirms connection
    status_res = await async_client.get(
        f"/api/v1/cases/{case_id}/devices/{dev_id}/status",
        headers={"Authorization": f"Bearer {inv_token}"}
    )
    assert status_res.status_code == 200
    assert status_res.json()["is_connected"] is True
    assert status_res.json()["connection_status"] == "CONNECTED"

    # 3. Constrained source browser lists files inside source_root
    browse_res = await async_client.get(
        f"/api/v1/cases/{case_id}/devices/{dev_id}/browse",
        headers={"Authorization": f"Bearer {inv_token}"}
    )
    assert browse_res.status_code == 200
    browse_items = browse_res.json()
    assert len(browse_items) >= 1
    assert any(item["name"] == "dvr_recordings" and item["is_dir"] is True for item in browse_items)

    # Subfolder browsing
    browse_sub = await async_client.get(
        f"/api/v1/cases/{case_id}/devices/{dev_id}/browse?subpath=dvr_recordings",
        headers={"Authorization": f"Bearer {inv_token}"}
    )
    assert browse_sub.status_code == 200
    sub_items = browse_sub.json()
    assert any(item["name"] == "cam01_footage.mp4" and item["is_dir"] is False for item in sub_items)

    # 4. Path outside source_root is rejected (arbitrary laptop path)
    acq_outside = await async_client.post(
        f"/api/v1/cases/{case_id}/devices/{dev_id}/acquisitions",
        headers={"Authorization": f"Bearer {inv_token}"},
        data={"method": "FILE_COPY", "source_path": str(outside_file)}
    )
    assert acq_outside.status_code == 400
    assert "outside the registered device" in acq_outside.json()["detail"].lower()

    # 5. Path traversal (../) is rejected
    acq_traversal = await async_client.post(
        f"/api/v1/cases/{case_id}/devices/{dev_id}/acquisitions",
        headers={"Authorization": f"Bearer {inv_token}"},
        data={"method": "FILE_COPY", "source_path": "dvr_recordings/../../unauthorized_laptop_folder/confidential_personal_doc.pdf"}
    )
    assert acq_traversal.status_code == 400
    assert "outside the registered device" in acq_traversal.json()["detail"].lower()

    # 6. Disconnected / unavailable source device blocks acquisition
    disc_dev_res = await async_client.post(
        f"/api/v1/cases/{case_id}/devices",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "device_type": "EXTERNAL_STORAGE",
            "manufacturer": "SanDisk",
            "source_root": "Z:\\non_existent_unmounted_usb_drive"
        }
    )
    assert disc_dev_res.status_code == 200
    disc_dev = disc_dev_res.json()
    assert disc_dev["is_connected"] is False
    assert disc_dev["connection_status"] == "DISCONNECTED"

    # Acquisition on disconnected device fails
    acq_disc = await async_client.post(
        f"/api/v1/cases/{case_id}/devices/{disc_dev['device_identifier']}/acquisitions",
        headers={"Authorization": f"Bearer {inv_token}"},
        data={"method": "FILE_COPY", "source_path": "any_file.mp4"}
    )
    assert acq_disc.status_code == 400
    assert "not connected or inaccessible" in acq_disc.json()["detail"].lower()

    # 7. Valid acquisition inside connected source_root succeeds
    acq_ok = await async_client.post(
        f"/api/v1/cases/{case_id}/devices/{dev_id}/acquisitions",
        headers={"Authorization": f"Bearer {inv_token}"},
        data={
            "method": "FILE_COPY",
            "source_path": "dvr_recordings/cam01_footage.mp4",
            "notes": "Forensically sound acquisition from verified mount"
        }
    )
    assert acq_ok.status_code == 200, acq_ok.text
    acq_res_data = acq_ok.json()
    assert acq_res_data["status"] == "COMPLETED"
    assert acq_res_data["source_sha256"] == clip1_sha256
    assert acq_res_data["destination_sha256"] == clip1_sha256
    assert acq_res_data["source_md5"] == clip1_md5
    assert acq_res_data["destination_md5"] == clip1_md5
    assert acq_res_data["size_bytes"] == len(clip1_bytes)

    # 8. Source file remained untouched
    clip1_stat_after = clip1.stat()
    assert clip1_stat_before.st_size == clip1_stat_after.st_size
    assert clip1_stat_before.st_mtime == clip1_stat_after.st_mtime


