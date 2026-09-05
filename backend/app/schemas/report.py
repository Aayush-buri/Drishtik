from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict


class ReportCreateRequest(BaseModel):
    report_type: str  # CASE_SUMMARY, EVIDENCE_REPORT, VIDEO_SUMMARY, RECOVERY_REPORT, AI_REPORT, CHAIN_OF_CUSTODY
    examiner_notes: Optional[str] = None
    format: Optional[str] = "PDF"  # PDF, HTML, JSON


class ReportSummaryResponse(BaseModel):
    id: int
    report_identifier: str
    case_id: int
    report_type: str
    title: str
    status: str
    created_at: datetime
    generated_at: datetime
    created_by: int
    format: str
    file_size: int
    sha256: str
    blockchain_status: str
    blockchain_tx_id: Optional[str] = None
    blockchain_anchored_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ReportDetailResponse(ReportSummaryResponse):
    examiner_notes: Optional[str] = None
    storage_path: Optional[str] = None
    data_payload: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class ReportIntegrityVerifyResponse(BaseModel):
    report_identifier: str
    overall_status: str
    current_sha256: str
    recorded_sha256: str
    format: str
    file_size: int
    reason: str
    verified_at: str
    blockchain_status: str
    blockchain_tx_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
