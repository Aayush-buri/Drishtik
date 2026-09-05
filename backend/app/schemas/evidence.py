from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from app.models.evidence import IntegrityStatus, ProcessingStatus, EvidenceStatus

class EvidenceBase(BaseModel):
    original_filename: str
    source_type: str
    media_type: str
    file_extension: str
    size_bytes: int

class EvidenceCreate(EvidenceBase):
    pass

class EvidenceResponse(EvidenceBase):
    id: int
    case_id: int
    evidence_identifier: str
    storage_path: str
    sha256: Optional[str] = None
    md5_reference: Optional[str] = None
    source_sha256: Optional[str] = None
    stored_sha256: Optional[str] = None
    integrity_status: IntegrityStatus
    processing_status: ProcessingStatus
    evidence_status: EvidenceStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    imported_by: int
    
    # Lineage
    parent_evidence_id: Optional[int] = None
    parent_evidence_identifier: Optional[str] = None
    parent_filename: Optional[str] = None
    derived_operation: Optional[str] = None
    derived_parameters: Optional[str] = None
    active_derived_children_count: Optional[int] = 0

    # Device & Acquisition Provenance
    device_id: Optional[int] = None
    device_identifier: Optional[str] = None
    device_manufacturer: Optional[str] = None
    device_model: Optional[str] = None
    acquisition_id: Optional[int] = None
    acquisition_identifier: Optional[str] = None
    acquisition_method: Optional[str] = None

    # Technical Media Metadata
    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    container: Optional[str] = None
    bitrate_kbps: Optional[int] = None

    # Vendor & CCTV Container Metadata
    vendor: Optional[str] = None
    proprietary_format: Optional[str] = None
    channel_index: Optional[int] = None
    start_time_osd: Optional[datetime] = None
    end_time_osd: Optional[datetime] = None
    is_natively_playable: bool = True

    # Soft Delete
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[int] = None
    deletion_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class HexPreviewRow(BaseModel):
    offset: str
    hex_bytes: str
    ascii_text: str


class HexPreviewResponse(BaseModel):
    evidence_id: int
    evidence_identifier: str
    total_bytes_inspected: int
    rows: List[HexPreviewRow]


class FormatAnalysisResponse(BaseModel):
    evidence_id: int
    evidence_identifier: str
    vendor: str
    format: str
    signature: Optional[str] = None
    confidence: float
    native_playback: bool
    parser_available: bool
    decoder_available: bool
    proxy_available: bool
    status: str
    metadata: dict = {}



class VerifyResponse(BaseModel):
    evidence_identifier: str
    expected_sha256: Optional[str] = None
    actual_sha256: str
    result: str
    verified_at: datetime

class CompareRequest(BaseModel):
    evidence_ids: List[int]

class CompareItem(BaseModel):
    evidence_id: int
    file_name: str
    sha256: Optional[str] = None
    md5_reference: Optional[str] = None
    size_bytes: int

class CompareResponse(BaseModel):
    items: List[CompareItem]
    result: str

class CropParameters(BaseModel):
    x: int = 0
    y: int = 0
    width: int
    height: int

class DeriveEvidenceRequest(BaseModel):
    operation: str  # "TRIM", "CROP", "TRIM_AND_CROP"
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    crop: Optional[CropParameters] = None

class BatchDeleteRequest(BaseModel):
    evidence_ids: List[int]
    reason: Optional[str] = None

class BatchDeleteResponse(BaseModel):
    message: str
    deleted_count: int
    deleted_ids: List[int]

class AuditLogResponse(BaseModel):
    id: int
    case_id: int
    user_id: int
    username: Optional[str] = None
    action: str
    target_identifier: Optional[str] = None
    details: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
