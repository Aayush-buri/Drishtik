"""Pydantic Schemas for AI Video Analysis."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class AIAnalysisJobCreate(BaseModel):
    sample_rate_fps: Optional[float] = 1.0
    confidence_threshold: Optional[float] = 0.35
    detect_objects: Optional[bool] = True
    detect_motion: Optional[bool] = True


class AIFindingResponse(BaseModel):
    id: int
    finding_identifier: str
    job_id: Optional[int] = None
    case_id: int
    evidence_id: int
    channel: int
    media_time: float
    source_timestamp: Optional[datetime] = None
    normalized_timestamp: Optional[datetime] = None
    object_class: str
    confidence: float
    bounding_box: Optional[str] = None
    frame_number: int
    model_name: str
    model_version: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AIAnalysisJobResponse(BaseModel):
    id: int
    job_identifier: str
    case_id: int
    evidence_id: int
    status: str
    progress_percent: float
    total_frames_analyzed: int
    findings_count: int
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    findings: List[AIFindingResponse] = []

    model_config = ConfigDict(from_attributes=True)


class AIFrameExportResponse(BaseModel):
    evidence_id: int
    evidence_identifier: str
    original_filename: str
    parent_evidence_id: int
    parent_evidence_identifier: str
    evidence_status: str
    derived_operation: str
    media_type: str
    file_extension: str
    size_bytes: int
    sha256: str
    md5_reference: Optional[str] = None
    media_time: float
    finding_identifier: str
    created_at: datetime
