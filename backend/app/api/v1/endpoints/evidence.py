from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request, Query
from sqlalchemy.orm import Session
import os

from app.db.database import get_db
from app.models.case import CaseMember, RoleEnum
from app.models.evidence import Evidence
from app.models.device import Device
from app.models.acquisition import Acquisition
from app.models.user import User
from app.models.audit import AuditLog
from app.schemas.evidence import (
    EvidenceResponse, VerifyResponse, CompareRequest, CompareResponse,
    DeriveEvidenceRequest, BatchDeleteRequest, BatchDeleteResponse, AuditLogResponse
)
from app.dependencies.auth import (
    require_case_member, require_case_investigator_or_admin, require_case_admin, get_current_user
)
from app.services import evidence_service
from app.core.streaming import range_requests_response

router = APIRouter()

def _populate_evidence_fields(evidence: Evidence, db: Session) -> Evidence:
    """Helper to populate lineage, device/acquisition provenance, and child counts on an Evidence instance."""
    if evidence.parent_evidence_id:
        parent = db.query(Evidence).filter(Evidence.id == evidence.parent_evidence_id).first()
        if parent:
            evidence.parent_evidence_identifier = parent.evidence_identifier
            evidence.parent_filename = parent.original_filename
            
    evidence.active_derived_children_count = db.query(Evidence).filter(
        Evidence.parent_evidence_id == evidence.id,
        Evidence.is_deleted == False
    ).count()

    if evidence.device_id:
        device = db.query(Device).filter(Device.id == evidence.device_id).first()
        if device:
            evidence.device_identifier = device.device_identifier
            evidence.device_manufacturer = device.manufacturer
            evidence.device_model = device.model

    if evidence.acquisition_id:
        acq = db.query(Acquisition).filter(Acquisition.id == evidence.acquisition_id).first()
        if acq:
            evidence.acquisition_identifier = acq.acquisition_identifier
            evidence.acquisition_method = str(acq.acquisition_method.value if hasattr(acq.acquisition_method, 'value') else acq.acquisition_method)
            if not getattr(evidence, 'device_identifier', None) and acq.device_id:
                dev = db.query(Device).filter(Device.id == acq.device_id).first()
                if dev:
                    evidence.device_identifier = dev.device_identifier
                    evidence.device_manufacturer = dev.manufacturer
                    evidence.device_model = dev.model

    return evidence

@router.post("/{case_identifier}/evidence", response_model=EvidenceResponse)
async def import_evidence_endpoint(
    case_identifier: str, 
    file: UploadFile = File(...), 
    member: CaseMember = Depends(require_case_investigator_or_admin),
    db: Session = Depends(get_db)
):
    try:
        evidence = await evidence_service.import_evidence(db, member.case, file, member.user_id)
        return _populate_evidence_fields(evidence, db)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import evidence: {str(e)}")

@router.get("/{case_identifier}/evidence", response_model=List[EvidenceResponse])
def list_evidence_endpoint(
    case_identifier: str, 
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db)
):
    evidence_list = db.query(Evidence).filter(
        Evidence.case_id == member.case.id,
        Evidence.is_deleted == False
    ).all()
    for ev in evidence_list:
        _populate_evidence_fields(ev, db)
    return evidence_list

@router.get("/{case_identifier}/evidence/{evidence_id}", response_model=EvidenceResponse)
def get_evidence_endpoint(
    case_identifier: str, 
    evidence_id: int,
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db)
):
    evidence = db.query(Evidence).filter(
        Evidence.case_id == member.case.id, 
        Evidence.id == evidence_id
    ).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return _populate_evidence_fields(evidence, db)

@router.post("/{case_identifier}/evidence/{evidence_id}/derive", response_model=EvidenceResponse)
def derive_evidence_endpoint(
    case_identifier: str,
    evidence_id: int,
    request: DeriveEvidenceRequest,
    member: CaseMember = Depends(require_case_investigator_or_admin),
    db: Session = Depends(get_db)
):
    parent = db.query(Evidence).filter(
        Evidence.case_id == member.case.id,
        Evidence.id == evidence_id,
        Evidence.is_deleted == False
    ).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent evidence not found or has been removed")

    crop_dict = request.crop.model_dump() if request.crop else None
    derived = evidence_service.derive_evidence(
        db=db,
        case=member.case,
        parent_evidence=parent,
        user_id=member.user_id,
        operation=request.operation,
        start_time=request.start_time,
        end_time=request.end_time,
        crop=crop_dict
    )
    return _populate_evidence_fields(derived, db)

@router.delete("/{case_identifier}/evidence/{evidence_id}")
def delete_single_evidence_endpoint(
    case_identifier: str,
    evidence_id: int,
    reason: str = None,
    admin: CaseMember = Depends(require_case_admin),
    db: Session = Depends(get_db)
):
    deleted = evidence_service.soft_delete_evidence(
        db=db,
        case=admin.case,
        evidence_ids=[evidence_id],
        user_id=admin.user_id,
        reason=reason
    )
    return {"message": "Evidence removed from active case", "deleted_id": deleted[0].id}

@router.post("/{case_identifier}/evidence/batch-delete", response_model=BatchDeleteResponse)
def batch_delete_evidence_endpoint(
    case_identifier: str,
    request: BatchDeleteRequest,
    admin: CaseMember = Depends(require_case_admin),
    db: Session = Depends(get_db)
):
    deleted = evidence_service.soft_delete_evidence(
        db=db,
        case=admin.case,
        evidence_ids=request.evidence_ids,
        user_id=admin.user_id,
        reason=request.reason
    )
    return BatchDeleteResponse(
        message=f"Successfully removed {len(deleted)} evidence items from active case",
        deleted_count=len(deleted),
        deleted_ids=[d.id for d in deleted]
    )

@router.get("/{case_identifier}/audit-logs", response_model=List[AuditLogResponse])
def list_audit_logs_endpoint(
    case_identifier: str,
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db)
):
    logs = db.query(AuditLog).filter(
        AuditLog.case_id == member.case.id
    ).order_by(AuditLog.created_at.desc()).all()
    
    response = []
    for log in logs:
        item = AuditLogResponse(
            id=log.id,
            case_id=log.case_id,
            user_id=log.user_id,
            username=log.user.username if log.user else "System",
            action=log.action,
            target_identifier=log.target_identifier,
            details=log.details,
            created_at=log.created_at
        )
        response.append(item)
    return response

@router.post("/{case_identifier}/evidence/{evidence_id}/verify", response_model=VerifyResponse)
def verify_evidence_endpoint(
    case_identifier: str,
    evidence_id: int,
    member: CaseMember = Depends(require_case_investigator_or_admin),
    db: Session = Depends(get_db)
):
    evidence = db.query(Evidence).filter(
        Evidence.case_id == member.case.id, 
        Evidence.id == evidence_id
    ).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
        
    return evidence_service.verify_integrity(db, evidence)

@router.post("/{case_identifier}/evidence/compare", response_model=CompareResponse)
def compare_evidence_endpoint(
    case_identifier: str,
    request: CompareRequest,
    member: CaseMember = Depends(require_case_investigator_or_admin),
    db: Session = Depends(get_db)
):
    evidence_list = db.query(Evidence).filter(
        Evidence.case_id == member.case.id,
        Evidence.id.in_(request.evidence_ids),
        Evidence.is_deleted == False
    ).all()
    
    if len(evidence_list) != len(request.evidence_ids):
        raise HTTPException(status_code=404, detail="One or more evidence items not found")
        
    return evidence_service.compare_evidence(db, evidence_list)

def get_current_user_from_query(
    db: Session = Depends(get_db),
    access_token: str = Query(..., description="Access token for streaming")
) -> User:
    return get_current_user(token=access_token, db=db)

def require_case_member_for_stream(
    case_identifier: str, 
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_from_query)
) -> CaseMember:
    return require_case_member(case_identifier=case_identifier, case_id=None, current_user=user, db=db)

@router.get("/{case_identifier}/evidence/{evidence_id}/stream")
def stream_evidence_endpoint(
    request: Request,
    case_identifier: str, 
    evidence_id: int,
    member: CaseMember = Depends(require_case_member_for_stream),
    db: Session = Depends(get_db)
):
    evidence = db.query(Evidence).filter(
        Evidence.case_id == member.case.id, 
        Evidence.id == evidence_id
    ).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
        
    if not os.path.exists(evidence.storage_path):
        raise HTTPException(status_code=404, detail="Evidence file is missing on disk")
        
    content_type = f"video/{evidence.file_extension.strip('.')}" if evidence.media_type == "Video" else "application/octet-stream"
    return range_requests_response(request, evidence.storage_path, content_type)
