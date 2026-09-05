"""Forensic Recovery Endpoints.

Provides endpoints to:
- Probe disk images / raw bitstreams
- Launch carving scans for Dahua, Hikvision, and MP4 structures
- Validate detected candidate stream fragments
- Carve immutable RECOVERED evidence artifacts
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.case import CaseMember
from app.models.recovery import RecoveryCandidate, RecoveryScanJob
from app.dependencies.auth import (
    require_case_member,
    require_case_investigator_or_admin,
)
from app.schemas.recovery import (
    RecoveryScanRequest,
    RecoveryScanResponse,
    RecoveryCandidateResponse,
    CandidateValidationResponse,
    RecoverCandidateResponse,
)
from app.services import recovery_service

router = APIRouter()


@router.post("/{case_identifier}/recovery/scans", response_model=RecoveryScanResponse)
def start_scan_endpoint(
    case_identifier: str,
    request: RecoveryScanRequest,
    member: CaseMember = Depends(require_case_investigator_or_admin),
    db: Session = Depends(get_db),
):
    scan_job, candidates = recovery_service.start_recovery_scan(
        db, member.case, request.source_evidence_id, member.user_id, max_bytes=request.max_scan_bytes or (20 * 1024 * 1024)
    )
    res = RecoveryScanResponse.model_validate(scan_job)
    res.candidates = [RecoveryCandidateResponse.model_validate(c) for c in candidates]
    return res


@router.get("/{case_identifier}/recovery/scans/{scan_id}", response_model=RecoveryScanResponse)
def get_scan_endpoint(
    case_identifier: str,
    scan_id: int,
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db),
):
    scan_job = db.query(RecoveryScanJob).filter(
        RecoveryScanJob.id == scan_id,
        RecoveryScanJob.case_id == member.case.id
    ).first()
    if not scan_job:
        raise HTTPException(status_code=404, detail="Recovery scan job not found")

    candidates = db.query(RecoveryCandidate).filter(
        RecoveryCandidate.scan_job_id == scan_job.id
    ).all()

    res = RecoveryScanResponse.model_validate(scan_job)
    res.candidates = [RecoveryCandidateResponse.model_validate(c) for c in candidates]
    return res


@router.get("/{case_identifier}/recovery/candidates", response_model=List[RecoveryCandidateResponse])
def list_candidates_endpoint(
    case_identifier: str,
    source_evidence_id: Optional[int] = Query(None),
    scan_job_id: Optional[int] = Query(None),
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db),
):
    candidates = recovery_service.list_recovery_candidates(
        db, member.case, source_evidence_id=source_evidence_id, scan_job_id=scan_job_id
    )
    return [RecoveryCandidateResponse.model_validate(c) for c in candidates]


@router.post("/{case_identifier}/recovery/candidates/{candidate_id}/validate", response_model=CandidateValidationResponse)
def validate_candidate_endpoint(
    case_identifier: str,
    candidate_id: int,
    member: CaseMember = Depends(require_case_investigator_or_admin),
    db: Session = Depends(get_db),
):
    cand = recovery_service.validate_candidate(db, member.case, candidate_id, member.user_id)
    return CandidateValidationResponse(
        candidate_id=cand.id,
        candidate_identifier=cand.candidate_identifier,
        status=cand.status.value,
        confidence=cand.confidence,
        validation_details=cand.validation_details or "",
    )


@router.post("/{case_identifier}/recovery/candidates/{candidate_id}/recover", response_model=RecoverCandidateResponse)
def recover_candidate_endpoint(
    case_identifier: str,
    candidate_id: int,
    member: CaseMember = Depends(require_case_investigator_or_admin),
    db: Session = Depends(get_db),
):
    cand, recovered_ev = recovery_service.recover_candidate(
        db, member.case, candidate_id, member.user_id
    )
    return RecoverCandidateResponse(
        candidate=RecoveryCandidateResponse.model_validate(cand),
        recovered_evidence_id=recovered_ev.id,
        recovered_evidence_identifier=recovered_ev.evidence_identifier,
        original_filename=recovered_ev.original_filename,
        sha256=recovered_ev.sha256 or "",
        size_bytes=recovered_ev.size_bytes,
        evidence_status=recovered_ev.evidence_status.value,
    )
