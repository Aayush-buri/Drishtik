from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from app.models.device import DeviceType, DeviceStatus
from app.schemas.acquisition import AcquisitionResponse

class DeviceBase(BaseModel):
    device_type: DeviceType
    manufacturer: Optional[str] = "Unknown"
    model: Optional[str] = None
    serial_number: Optional[str] = None
    firmware_version: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    storage_capacity: Optional[str] = None
    channel_count: Optional[int] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    source_root: Optional[str] = None

class DeviceCreate(DeviceBase):
    pass

class DeviceUpdate(BaseModel):
    device_type: Optional[DeviceType] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    firmware_version: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    storage_capacity: Optional[str] = None
    channel_count: Optional[int] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    source_root: Optional[str] = None
    status: Optional[DeviceStatus] = None

class DeviceArchiveRequest(BaseModel):
    confirm_with_acquisitions: bool = False
    reason: Optional[str] = None

class DeviceResponse(DeviceBase):
    id: int
    device_identifier: str
    case_id: int
    status: DeviceStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: int
    acquisitions_count: int = 0
    latest_acquisition_date: Optional[datetime] = None
    latest_acquisition_status: Optional[str] = None
    is_connected: bool = False
    connection_status: str = "DISCONNECTED"

    model_config = ConfigDict(from_attributes=True)

class DeviceDetailResponse(DeviceResponse):
    acquisitions: List[AcquisitionResponse] = []

class DeviceBrowseItem(BaseModel):
    name: str
    path: str
    is_dir: bool
    size_bytes: Optional[int] = None
    modified_at: Optional[str] = None
