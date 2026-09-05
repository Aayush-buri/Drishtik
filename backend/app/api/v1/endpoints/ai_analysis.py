"""AI Video Analysis API Endpoints.

Provides endpoints to:
- Run YOLO object detection and OpenCV motion analysis on video evidence
- Filter and search AI findings by object class, confidence, and timestamps
- Export AI finding frames as new derived evidence artifacts
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.case import CaseMember
from app.models.evidence import Evidence
from app.models.ai_analysis import AIAnalysisJob, AIFinding
from app.dependencies.auth import (
    require_case_member,
    require_case_investigator_or_admin,
)
from app.schemas.ai_analysis import (
    AIAnalysisJobCreate,
    AIAnalysisJobResponse,
    AIFindingResponse,
    AIFrameExportResponse,
)
from app.services import ai_service

router = APIRouter()


def _get_evidence_or_404(db: Session, case_id: int, evidence_id: int) -> Evidence:
    evidence = db.query(Evidence).filter(
        Evidence.case_id == case_id,
        Evidence.id == evidence_id,
        Evidence.is_deleted == False
    ).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found or has been deleted")
    return evidence


@router.post("/{case_identifier}/evidence/{evidence_id}/ai/jobs", response_model=AIAnalysisJobResponse)
def start_ai_job_endpoint(
    case_identifier: str,
    evidence_id: int,
    request: AIAnalysisJobCreate,
    member: CaseMember = Depends(require_case_investigator_or_admin),
    db: Session = Depends(get_db),
):
    evidence = _get_evidence_or_404(db, member.case.id, evidence_id)
    job, findings = ai_service.start_ai_analysis_job(
        db,
        member.case,
        evidence,
        member.user_id,
        sample_rate_fps=request.sample_rate_fps or 1.0,
        confidence_threshold=request.confidence_threshold or 0.35,
        detect_objects=request.detect_objects if request.detect_objects is not None else True,
        detect_motion=request.detect_motion if request.detect_motion is not None else True,
    )
    res = AIAnalysisJobResponse.model_validate(job)
    res.findings = [AIFindingResponse.model_validate(f) for f in findings]
    return res


@router.get("/{case_identifier}/evidence/{evidence_id}/ai/jobs/{job_id}", response_model=AIAnalysisJobResponse)
def get_ai_job_endpoint(
    case_identifier: str,
    evidence_id: int,
    job_id: int,
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db),
):
    evidence = _get_evidence_or_404(db, member.case.id, evidence_id)
    job = db.query(AIAnalysisJob).filter(
        AIAnalysisJob.id == job_id,
        AIAnalysisJob.case_id == member.case.id,
        AIAnalysisJob.evidence_id == evidence.id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="AI analysis job not found")

    findings = db.query(AIFinding).filter(AIFinding.job_id == job.id).all()
    res = AIAnalysisJobResponse.model_validate(job)
    res.findings = [AIFindingResponse.model_validate(f) for f in findings]
    return res


@router.get("/{case_identifier}/evidence/{evidence_id}/ai/findings", response_model=List[AIFindingResponse])
def list_ai_findings_endpoint(
    case_identifier: str,
    evidence_id: int,
    object_class: Optional[str] = Query(None, description="Filter by object class (Person, Vehicle, Motion, etc.)"),
    min_confidence: Optional[float] = Query(None, description="Minimum model confidence (0.0 to 1.0)"),
    channel: Optional[int] = Query(None, description="Camera channel filter"),
    start_time: Optional[float] = Query(None, description="Minimum media time in seconds"),
    end_time: Optional[float] = Query(None, description="Maximum media time in seconds"),
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db),
):
    evidence = _get_evidence_or_404(db, member.case.id, evidence_id)
    findings = ai_service.list_ai_findings(
        db,
        member.case,
        evidence.id,
        object_class=object_class,
        min_confidence=min_confidence,
        channel=channel,
        start_time=start_time,
        end_time=end_time,
    )
    return [AIFindingResponse.model_validate(f) for f in findings]


@router.post("/{case_identifier}/evidence/{evidence_id}/ai/findings/{finding_id}/export-frame", response_model=AIFrameExportResponse)
def export_ai_frame_endpoint(
    case_identifier: str,
    evidence_id: int,
    finding_id: int,
    member: CaseMember = Depends(require_case_investigator_or_admin),
    db: Session = Depends(get_db),
):
    _get_evidence_or_404(db, member.case.id, evidence_id)
    finding, derived_ev = ai_service.export_ai_frame(
        db, member.case, finding_id, member.user_id
    )
    return AIFrameExportResponse(
        evidence_id=derived_ev.id,
        evidence_identifier=derived_ev.evidence_identifier,
        original_filename=derived_ev.original_filename,
        parent_evidence_id=finding.evidence_id,
        parent_evidence_identifier=derived_ev.parent.evidence_identifier if derived_ev.parent else "",
        evidence_status=derived_ev.evidence_status.value,
        derived_operation=derived_ev.derived_operation or "AI_FRAME_EXPORT",
        media_type=derived_ev.media_type,
        file_extension=derived_ev.file_extension,
        size_bytes=derived_ev.size_bytes,
        sha256=derived_ev.sha256 or "",
        md5_reference=derived_ev.md5_reference,
        media_time=finding.media_time,
        finding_identifier=finding.finding_identifier,
        created_at=derived_ev.created_at,
    )
