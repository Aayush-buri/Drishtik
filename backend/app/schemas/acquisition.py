from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.acquisition import AcquisitionMethod, AcquisitionStatus

class AcquisitionCreate(BaseModel):
    acquisition_method: AcquisitionMethod = AcquisitionMethod.FILE_COPY
    source_path: Optional[str] = None
    notes: Optional[str] = None

class AcquisitionResponse(BaseModel):
    id: int
    acquisition_identifier: str
    case_id: int
    device_id: int
    device_identifier: Optional[str] = None
    device_name: Optional[str] = None
    acquisition_method: AcquisitionMethod
    source_path: str
    destination_reference: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: AcquisitionStatus
    progress: int
    operator_id: int
    operator_name: Optional[str] = None
    source_sha256: Optional[str] = None
    destination_sha256: Optional[str] = None
    source_md5: Optional[str] = None
    destination_md5: Optional[str] = None
    size_bytes: Optional[int] = None
    notes: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    has_evidence: bool = False
    evidence_identifier: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class CreateEvidenceFromAcquisitionRequest(BaseModel):
    custom_name: Optional[str] = None
    notes: Optional[str] = None
