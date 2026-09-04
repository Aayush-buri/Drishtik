from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.case import CaseMember
from app.models.device import Device
from app.schemas.device import (
    DeviceCreate, DeviceUpdate, DeviceResponse, DeviceDetailResponse, DeviceArchiveRequest, DeviceBrowseItem
)
from app.schemas.acquisition import AcquisitionResponse
from app.dependencies.auth import (
    require_case_member, require_case_investigator_or_admin, require_case_admin
)
from app.services import device_service, acquisition_service

router = APIRouter()

@router.post("/{case_identifier}/devices", response_model=DeviceResponse)
def create_device_endpoint(
    case_identifier: str,
    payload: DeviceCreate,
    member: CaseMember = Depends(require_case_investigator_or_admin),
    db: Session = Depends(get_db)
):
    try:
        return device_service.create_device(db, member.case, payload, member.user_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create device: {str(e)}")

@router.get("/{case_identifier}/devices", response_model=List[DeviceResponse])
def list_devices_endpoint(
    case_identifier: str,
    status: Optional[str] = Query(None),
    device_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db)
):
    return device_service.get_devices(
        db, member.case.id, status=status, device_type=device_type, search=search
    )

@router.get("/{case_identifier}/devices/{device_identifier}", response_model=DeviceDetailResponse)
def get_device_endpoint(
    case_identifier: str,
    device_identifier: str,
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db)
):
    device = device_service.get_device_by_identifier(db, member.case.id, device_identifier)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {device_identifier} not found in this case.")

    acquisitions = acquisition_service.get_acquisitions_for_device(db, device.id)
    acq_responses = [AcquisitionResponse.model_validate(a) for a in acquisitions]

    detail = DeviceDetailResponse.model_validate(device)
    detail.acquisitions = acq_responses
    return detail

@router.put("/{case_identifier}/devices/{device_identifier}", response_model=DeviceResponse)
def update_device_endpoint(
    case_identifier: str,
    device_identifier: str,
    payload: DeviceUpdate,
    member: CaseMember = Depends(require_case_investigator_or_admin),
    db: Session = Depends(get_db)
):
    device = device_service.get_device_by_identifier(db, member.case.id, device_identifier)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {device_identifier} not found in this case.")

    return device_service.update_device(db, device, payload, member.user_id)

@router.post("/{case_identifier}/devices/{device_identifier}/archive", response_model=DeviceResponse)
def archive_device_endpoint(
    case_identifier: str,
    device_identifier: str,
    payload: Optional[DeviceArchiveRequest] = None,
    member: CaseMember = Depends(require_case_admin),
    db: Session = Depends(get_db)
):
    device = device_service.get_device_by_identifier(db, member.case.id, device_identifier)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {device_identifier} not found in this case.")

    confirm = payload.confirm_with_acquisitions if payload else False
    reason = payload.reason if payload else None
    return device_service.archive_device(db, device, member.user_id, confirm, reason)

@router.get("/{case_identifier}/devices/{device_identifier}/browse", response_model=List[DeviceBrowseItem])
def browse_device_source_endpoint(
    case_identifier: str,
    device_identifier: str,
    subpath: str = Query("", description="Relative path within registered source device"),
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db)
):
    device = device_service.get_device_by_identifier(db, member.case.id, device_identifier)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {device_identifier} not found in this case.")

    return device_service.browse_device_source(device, subpath)

@router.get("/{case_identifier}/devices/{device_identifier}/status")
def get_device_status_endpoint(
    case_identifier: str,
    device_identifier: str,
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db)
):
    device = device_service.get_device_by_identifier(db, member.case.id, device_identifier)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {device_identifier} not found in this case.")

    return {
        "device_identifier": device.device_identifier,
        "source_root": device.source_root,
        "is_connected": device.is_connected,
        "connection_status": device.connection_status
    }
