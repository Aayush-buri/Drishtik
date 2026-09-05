"""Pydantic Schemas for Forensic Recovery."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class RecoveryScanRequest(BaseModel):
    source_evidence_id: int
    max_scan_bytes: Optional[int] = 20 * 1024 * 1024


class RecoveryCandidateResponse(BaseModel):
    id: int
    candidate_identifier: str
    scan_job_id: Optional[int] = None
    case_id: int
    source_evidence_id: Optional[int] = None
    source_offset: int
    size_bytes: int
    detected_format: str
    vendor: str
    confidence: float
    status: str
    validation_details: Optional[str] = None
    recovered_evidence_id: Optional[int] = None
    metadata_json: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecoveryScanResponse(BaseModel):
    id: int
    scan_identifier: str
    case_id: int
    source_evidence_id: Optional[int] = None
    status: str
    bytes_scanned: int
    total_bytes: int
    candidates_found: int
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    candidates: List[RecoveryCandidateResponse] = []

    model_config = ConfigDict(from_attributes=True)


class CandidateValidationResponse(BaseModel):
    candidate_id: int
    candidate_identifier: str
    status: str
    confidence: float
    validation_details: str


class RecoverCandidateResponse(BaseModel):
    candidate: RecoveryCandidateResponse
    recovered_evidence_id: int
    recovered_evidence_identifier: str
    original_filename: str
    sha256: str
    size_bytes: int
    evidence_status: str
