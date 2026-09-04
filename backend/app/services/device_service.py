import json
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException

from app.models.case import Case
from app.models.device import Device, DeviceStatus, DeviceType
from app.models.acquisition import Acquisition
from app.models.audit import AuditLog
from app.schemas.device import DeviceCreate, DeviceUpdate
from app.forensics.device_provider import get_device_provider

def generate_device_identifier(db: Session) -> str:
    """Generates unique human-readable device identifier DEV-XXXXXX."""
    while True:
        ident = f"DEV-{uuid.uuid4().hex[:6].upper()}"
        exists = db.query(Device).filter(Device.device_identifier == ident).first()
        if not exists:
            return ident

def create_device(db: Session, case: Case, data: DeviceCreate, user_id: int) -> Device:
    ident = generate_device_identifier(db)
    
    device = Device(
        device_identifier=ident,
        case_id=case.id,
        device_type=data.device_type,
        manufacturer=data.manufacturer or "Unknown",
        model=data.model,
        serial_number=data.serial_number,
        firmware_version=data.firmware_version,
        ip_address=data.ip_address,
        mac_address=data.mac_address,
        storage_capacity=data.storage_capacity,
        channel_count=data.channel_count,
        location=data.location,
        notes=data.notes,
        source_root=data.source_root,
        status=DeviceStatus.ACTIVE,
        created_by=user_id
    )
    db.add(device)
    db.commit()
    db.refresh(device)

    audit = AuditLog(
        case_id=case.id,
        user_id=user_id,
        action="DEVICE_CREATED",
        target_identifier=ident,
        details=json.dumps({
            "device_identifier": ident,
            "device_type": str(data.device_type.value if hasattr(data.device_type, 'value') else data.device_type),
            "manufacturer": device.manufacturer,
            "model": device.model,
            "source_root": device.source_root
        })
    )
    db.add(audit)
    db.commit()

    device.acquisitions_count = 0
    device.latest_acquisition_date = None
    device.latest_acquisition_status = None
    enrich_device_metadata(device, db)
    return device

def enrich_device_metadata(device: Device, db: Session) -> Device:
    """Populates acquisitions count, connection status, and latest acquisition details."""
    acquisitions = db.query(Acquisition).filter(
        Acquisition.device_id == device.id
    ).order_by(desc(Acquisition.started_at)).all()

    device.acquisitions_count = len(acquisitions)
    if acquisitions:
        latest = acquisitions[0]
        device.latest_acquisition_date = latest.completed_at or latest.started_at
        device.latest_acquisition_status = str(latest.status.value if hasattr(latest.status, 'value') else latest.status)
    else:
        device.latest_acquisition_date = None
        device.latest_acquisition_status = None

    # Evaluate live connection status via SourceDeviceProvider without fabricating
    provider = get_device_provider()
    device.is_connected = provider.is_connected(device.source_root)
    if not device.source_root or not device.source_root.strip():
        device.connection_status = "UNCONFIGURED"
    elif device.is_connected:
        device.connection_status = "CONNECTED"
    else:
        device.connection_status = "DISCONNECTED"

    return device

def browse_device_source(device: Device, subpath: str = "") -> List[dict]:
    """Lists constrained files/folders inside the registered device's source root."""
    if not device.source_root or not device.source_root.strip():
        raise HTTPException(status_code=400, detail="Device has no registered source root.")
    
    provider = get_device_provider()
    if not provider.is_connected(device.source_root):
        raise HTTPException(status_code=400, detail="Source device is not connected or accessible.")

    try:
        return provider.list_source_contents(device.source_root, subpath)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

def get_devices(
    db: Session,
    case_id: int,
    status: Optional[str] = None,
    device_type: Optional[str] = None,
    search: Optional[str] = None
) -> List[Device]:
    query = db.query(Device).filter(Device.case_id == case_id)

    if status:
        query = query.filter(Device.status == status)
    if device_type:
        query = query.filter(Device.device_type == device_type)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Device.device_identifier.ilike(search_pattern)) |
            (Device.manufacturer.ilike(search_pattern)) |
            (Device.model.ilike(search_pattern)) |
            (Device.serial_number.ilike(search_pattern)) |
            (Device.location.ilike(search_pattern))
        )

    devices = query.order_by(desc(Device.created_at)).all()
    for d in devices:
        enrich_device_metadata(d, db)
    return devices

def get_device_by_identifier(db: Session, case_id: int, device_identifier: str) -> Optional[Device]:
    device = db.query(Device).filter(
        Device.case_id == case_id,
        Device.device_identifier == device_identifier
    ).first()
    if device:
        enrich_device_metadata(device, db)
    return device

def update_device(db: Session, device: Device, data: DeviceUpdate, user_id: int) -> Device:
    update_data = data.model_dump(exclude_unset=True)
    changed_fields = {}

    for field, val in update_data.items():
        old_val = getattr(device, field, None)
        if old_val != val:
            changed_fields[field] = {"old": str(old_val), "new": str(val)}
            setattr(device, field, val)

    db.commit()
    db.refresh(device)

    if changed_fields:
        audit = AuditLog(
            case_id=device.case_id,
            user_id=user_id,
            action="DEVICE_UPDATED",
            target_identifier=device.device_identifier,
            details=json.dumps({
                "device_identifier": device.device_identifier,
                "changes": changed_fields
            })
        )
        db.add(audit)
        db.commit()

    enrich_device_metadata(device, db)
    return device

def archive_device(
    db: Session,
    device: Device,
    user_id: int,
    confirm_with_acquisitions: bool = False,
    reason: Optional[str] = None
) -> Device:
    acquisitions_count = db.query(Acquisition).filter(Acquisition.device_id == device.id).count()
    if acquisitions_count > 0 and not confirm_with_acquisitions:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Device {device.device_identifier} has {acquisitions_count} associated forensic acquisition(s). Confirmation required.",
                "acquisitions_count": acquisitions_count,
                "requires_confirmation": True
            }
        )

    device.status = DeviceStatus.ARCHIVED
    db.commit()
    db.refresh(device)

    audit = AuditLog(
        case_id=device.case_id,
        user_id=user_id,
        action="DEVICE_ARCHIVED",
        target_identifier=device.device_identifier,
        details=json.dumps({
            "device_identifier": device.device_identifier,
            "acquisitions_count": acquisitions_count,
            "reason": reason or "Archived by Admin"
        })
    )
    db.add(audit)
    db.commit()

    enrich_device_metadata(device, db)
    return device
