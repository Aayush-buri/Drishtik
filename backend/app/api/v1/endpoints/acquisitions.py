import os
import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.case import CaseMember
from app.models.acquisition import Acquisition, AcquisitionMethod
from app.schemas.acquisition import AcquisitionResponse, CreateEvidenceFromAcquisitionRequest
from app.schemas.evidence import EvidenceResponse
from app.dependencies.auth import require_case_member, require_case_investigator_or_admin
from app.services import device_service, acquisition_service
from app.api.v1.endpoints.evidence import _populate_evidence_fields

router = APIRouter()

@router.post("/{case_identifier}/devices/{device_identifier}/acquisitions", response_model=AcquisitionResponse)
async def start_acquisition_endpoint(
    case_identifier: str,
    device_identifier: str,
    method: AcquisitionMethod = Form(AcquisitionMethod.FILE_COPY),
    source_path: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    member: CaseMember = Depends(require_case_investigator_or_admin),
    db: Session = Depends(get_db)
):
    device = device_service.get_device_by_identifier(db, member.case.id, device_identifier)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {device_identifier} not found in this case.")

    # Determine source path
    staging_file_to_clean = None
    if file and file.filename:
        # Save uploaded file to safe acquisition staging buffer
        staging_dir = Path("data") / "case_data" / member.case.case_identifier / "staging"
        staging_dir.mkdir(parents=True, exist_ok=True)
        staging_path = staging_dir / file.filename

        with open(staging_path, "wb") as buffer:
            while chunk := await file.read(65536):
                buffer.write(chunk)
        actual_source_path = str(staging_path)
    elif source_path is not None:
        actual_source_path = source_path
    else:
        raise HTTPException(status_code=400, detail="Must provide either an uploaded file or a valid source_path.")

    try:
        acq = acquisition_service.execute_acquisition(
            db=db,
            case=member.case,
            device=device,
            method=method,
            source_path_input=actual_source_path,
            user_id=member.user_id,
            notes=notes
        )
        return AcquisitionResponse.model_validate(acq)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Acquisition execution failed: {str(e)}")

@router.get("/{case_identifier}/devices/{device_identifier}/acquisitions", response_model=List[AcquisitionResponse])
def list_device_acquisitions_endpoint(
    case_identifier: str,
    device_identifier: str,
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db)
):
    device = device_service.get_device_by_identifier(db, member.case.id, device_identifier)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {device_identifier} not found in this case.")

    acquisitions = acquisition_service.get_acquisitions_for_device(db, device.id)
    return [AcquisitionResponse.model_validate(a) for a in acquisitions]

@router.get("/{case_identifier}/acquisitions/{acquisition_identifier}", response_model=AcquisitionResponse)
def get_acquisition_endpoint(
    case_identifier: str,
    acquisition_identifier: str,
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db)
):
    acq = acquisition_service.get_acquisition_by_identifier(db, member.case.id, acquisition_identifier)
    if not acq:
        raise HTTPException(status_code=404, detail=f"Acquisition {acquisition_identifier} not found in this case.")

    return AcquisitionResponse.model_validate(acq)

@router.post("/{case_identifier}/acquisitions/{acquisition_identifier}/create-evidence", response_model=EvidenceResponse)
def create_evidence_from_acquisition_endpoint(
    case_identifier: str,
    acquisition_identifier: str,
    payload: Optional[CreateEvidenceFromAcquisitionRequest] = None,
    member: CaseMember = Depends(require_case_investigator_or_admin),
    db: Session = Depends(get_db)
):
    acq = acquisition_service.get_acquisition_by_identifier(db, member.case.id, acquisition_identifier)
    if not acq:
        raise HTTPException(status_code=404, detail=f"Acquisition {acquisition_identifier} not found in this case.")

    custom_name = payload.custom_name if payload else None
    try:
        evidence = acquisition_service.create_evidence_from_acquisition(
            db, member.case, acq, member.user_id, custom_name
        )
        return _populate_evidence_fields(evidence, db)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create evidence from acquisition: {str(e)}")
