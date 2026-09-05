import os
import json
import uuid
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.case import Case
from app.models.device import Device, DeviceStatus
from app.models.acquisition import Acquisition, AcquisitionStatus, AcquisitionMethod
from app.models.evidence import Evidence, IntegrityStatus, ProcessingStatus, EvidenceStatus
from app.models.audit import AuditLog
from app.forensics.acquisition import get_acquisition_adapter
from app.forensics.device_provider import get_device_provider
from app.forensics.signatures.signature_probe import probe_file
from app.services.video_processing import extract_video_metadata


def get_case_acquisition_dir(case_identifier: str, acquisition_identifier: str) -> Path:
    vault_dir = Path("data") / "case_data" / case_identifier / "acquisitions" / acquisition_identifier
    vault_dir.mkdir(parents=True, exist_ok=True)
    return vault_dir

def generate_acquisition_identifier(db: Session) -> str:
    """Generates unique human-readable acquisition identifier ACQ-XXXXXX."""
    while True:
        ident = f"ACQ-{uuid.uuid4().hex[:6].upper()}"
        exists = db.query(Acquisition).filter(Acquisition.acquisition_identifier == ident).first()
        if not exists:
            return ident

def enrich_acquisition_metadata(acq: Acquisition, db: Session) -> Acquisition:
    """Populates operator name, device identifier, and evidence link."""
    if acq.device:
        acq.device_identifier = acq.device.device_identifier
        acq.device_name = f"{acq.device.manufacturer or ''} {acq.device.model or ''}".strip()
    if acq.operator:
        acq.operator_name = acq.operator.display_name or acq.operator.username
    
    # Check if evidence exists for this acquisition
    ev = db.query(Evidence).filter(Evidence.acquisition_id == acq.id, Evidence.is_deleted == False).first()
    if ev:
        acq.has_evidence = True
        acq.evidence_identifier = ev.evidence_identifier
    else:
        acq.has_evidence = False
        acq.evidence_identifier = None
    return acq

def execute_acquisition(
    db: Session,
    case: Case,
    device: Device,
    method: AcquisitionMethod,
    source_path_input: str,
    user_id: int,
    notes: Optional[str] = None
) -> Acquisition:
    if device.status == DeviceStatus.ARCHIVED:
        raise HTTPException(status_code=400, detail="Cannot perform acquisition on an archived device.")

    provider = get_device_provider()

    # Determine if this is an uploaded staging file
    staging_dir = (Path("data") / "case_data" / case.case_identifier / "staging").resolve()
    raw_p = Path(source_path_input)
    is_staging = False
    try:
        if raw_p.exists() and raw_p.resolve().is_relative_to(staging_dir):
            is_staging = True
    except (ValueError, AttributeError):
        pass

    if is_staging:
        src_p = raw_p.resolve()
        if not src_p.exists():
            raise HTTPException(status_code=404, detail=f"Uploaded source not found: {source_path_input}")
    else:
        # Physical source device access
        if not device.source_root or not provider.is_connected(device.source_root):
            raise HTTPException(status_code=400, detail="Source device is not connected or inaccessible.")

        try:
            src_p = provider.validate_access(device.source_root, source_path_input)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))

    acq_ident = generate_acquisition_identifier(db)
    destination_dir = get_case_acquisition_dir(case.case_identifier, acq_ident)

    # Relative reference for safe storage representation
    dest_reference = f"acquisitions/{acq_ident}/{src_p.name}"

    acquisition = Acquisition(
        acquisition_identifier=acq_ident,
        case_id=case.id,
        device_id=device.id,
        acquisition_method=method,
        source_path=str(src_p),
        destination_reference=dest_reference,
        status=AcquisitionStatus.RUNNING,
        progress=0,
        operator_id=user_id,
        notes=notes
    )
    db.add(acquisition)
    db.commit()
    db.refresh(acquisition)

    audit_start = AuditLog(
        case_id=case.id,
        user_id=user_id,
        action="ACQUISITION_STARTED",
        target_identifier=acq_ident,
        details=json.dumps({
            "acquisition_identifier": acq_ident,
            "device_identifier": device.device_identifier,
            "method": str(method.value if hasattr(method, 'value') else method),
            "source_name": src_p.name
        })
    )
    db.add(audit_start)
    db.commit()

    pre_stat = (src_p.stat().st_mtime, src_p.stat().st_size) if src_p.is_file() else None

    # Perform forensic acquisition using vendor-agnostic adapter
    try:
        adapter = get_acquisition_adapter(method, src_p)
        result = adapter.acquire(destination_dir)

        if pre_stat and src_p.exists() and src_p.is_file():
            post_stat = (src_p.stat().st_mtime, src_p.stat().st_size)
            if post_stat != pre_stat:
                raise RuntimeError("CRITICAL FORENSIC INTEGRITY VIOLATION: Source file was modified during acquisition!")

        if result.verified:
            acquisition.status = AcquisitionStatus.COMPLETED
            acquisition.progress = 100
            acquisition.source_sha256 = result.source_sha256
            acquisition.destination_sha256 = result.destination_sha256
            acquisition.source_md5 = result.source_md5
            acquisition.destination_md5 = result.destination_md5
            acquisition.size_bytes = result.size_bytes
            acquisition.destination_reference = str(result.destination_path.relative_to(Path("data") / "case_data" / case.case_identifier)).replace("\\", "/")
            acquisition.completed_at = datetime.now(timezone.utc)
            acquisition.error_message = None

            # Mark device as acquired
            if device.status == DeviceStatus.ACTIVE:
                device.status = DeviceStatus.ACQUIRED

            db.commit()

            audit_complete = AuditLog(
                case_id=case.id,
                user_id=user_id,
                action="ACQUISITION_COMPLETED",
                target_identifier=acq_ident,
                details=json.dumps({
                    "acquisition_identifier": acq_ident,
                    "device_identifier": device.device_identifier,
                    "sha256": result.destination_sha256,
                    "md5": result.destination_md5,
                    "size_bytes": result.size_bytes,
                    "verified": True
                })
            )
            db.add(audit_complete)
            db.commit()

        else:
            acquisition.status = AcquisitionStatus.FAILED
            acquisition.error_message = result.error_message or "Integrity check failed: source and destination hashes do not match."
            acquisition.source_sha256 = result.source_sha256
            acquisition.destination_sha256 = result.destination_sha256
            acquisition.source_md5 = result.source_md5
            acquisition.destination_md5 = result.destination_md5
            acquisition.completed_at = datetime.now(timezone.utc)
            db.commit()

            audit_fail = AuditLog(
                case_id=case.id,
                user_id=user_id,
                action="ACQUISITION_FAILED",
                target_identifier=acq_ident,
                details=json.dumps({
                    "acquisition_identifier": acq_ident,
                    "device_identifier": device.device_identifier,
                    "error": acquisition.error_message
                })
            )
            db.add(audit_fail)
            db.commit()

    except Exception as e:
        acquisition.status = AcquisitionStatus.FAILED
        acquisition.error_message = str(e)
        acquisition.completed_at = datetime.now(timezone.utc)
        db.commit()

        audit_fail = AuditLog(
            case_id=case.id,
            user_id=user_id,
            action="ACQUISITION_FAILED",
            target_identifier=acq_ident,
            details=json.dumps({
                "acquisition_identifier": acq_ident,
                "device_identifier": device.device_identifier,
                "error": str(e)
            })
        )
        db.add(audit_fail)
        db.commit()

    enrich_acquisition_metadata(acquisition, db)
    return acquisition

def get_acquisitions_for_device(db: Session, device_id: int) -> List[Acquisition]:
    acquisitions = db.query(Acquisition).filter(
        Acquisition.device_id == device_id
    ).order_by(Acquisition.started_at.desc()).all()
    for a in acquisitions:
        enrich_acquisition_metadata(a, db)
    return acquisitions

def get_acquisition_by_identifier(db: Session, case_id: int, acquisition_identifier: str) -> Optional[Acquisition]:
    acq = db.query(Acquisition).filter(
        Acquisition.case_id == case_id,
        Acquisition.acquisition_identifier == acquisition_identifier
    ).first()
    if acq:
        enrich_acquisition_metadata(acq, db)
    return acq

def create_evidence_from_acquisition(
    db: Session,
    case: Case,
    acquisition: Acquisition,
    user_id: int,
    custom_name: Optional[str] = None
) -> Evidence:
    if acquisition.status != AcquisitionStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Evidence can only be created from completed acquisitions.")

    # Check if evidence already exists for this acquisition
    existing_ev = db.query(Evidence).filter(
        Evidence.case_id == case.id,
        Evidence.acquisition_id == acquisition.id,
        Evidence.is_deleted == False
    ).first()
    if existing_ev:
        return existing_ev

    # Resolve destination file path
    case_data_dir = Path("data") / "case_data" / case.case_identifier
    acquired_path = case_data_dir / acquisition.destination_reference

    if not acquired_path.exists():
        raise HTTPException(status_code=404, detail="Acquired forensic data file missing from managed vault.")

    # Determine file details
    original_filename = custom_name or acquired_path.name
    ext = acquired_path.suffix.lower()
    unique_id = uuid.uuid4().hex
    evidence_ident = f"EVD-{unique_id[:6].upper()}"

    # Place safely into evidence vault (read-only copy)
    evidence_vault_dir = case_data_dir / "evidence" / "original"
    evidence_vault_dir.mkdir(parents=True, exist_ok=True)
    evidence_storage_path = evidence_vault_dir / f"{unique_id}{ext}"

    if acquired_path.is_file():
        shutil.copy2(acquired_path, evidence_storage_path)
    else:
        # Directory acquisition: zip or reference
        shutil.copytree(acquired_path, evidence_storage_path)

    # Probe file signature
    probe_result = probe_file(evidence_storage_path) if evidence_storage_path.is_file() else None

    # Determine media type
    if probe_result and (probe_result.vendor in ("Dahua", "Hikvision") or probe_result.format_name in (
        "Dahua DAV", "Hikvision HIKV", "Hikvision HIKB", "Hikvision HIKT",
        "Hikvision MPEG-PS", "Standard MP4", "Standard MKV", "Standard AVI",
        "Raw H.264 Elementary Stream", "Raw H.265 Elementary Stream"
    )):
        media_type = 'Video'
    elif ext in ['.mp4', '.avi', '.mkv', '.dav', '.mov']:
        media_type = 'Video'
    elif ext in ['.jpg', '.jpeg', '.png', '.bmp']:
        media_type = 'Image'
    elif ext in ['.raw', '.dd', '.img', '.bin', '.e01']:
        media_type = 'Disk Image'
    else:
        media_type = 'Other'

    # Extract technical video metadata if applicable
    meta = {}
    if media_type == 'Video':
        try:
            meta = extract_video_metadata(str(evidence_storage_path))
        except Exception:
            pass

    evidence = Evidence(
        case_id=case.id,
        evidence_identifier=evidence_ident,
        original_filename=original_filename,
        storage_path=str(evidence_storage_path),
        source_type="Acquired",
        media_type=media_type,
        file_extension=ext,
        size_bytes=acquisition.size_bytes or evidence_storage_path.stat().st_size,
        sha256=acquisition.destination_sha256,
        md5_reference=acquisition.destination_md5,
        source_sha256=acquisition.source_sha256,
        stored_sha256=acquisition.destination_sha256,
        integrity_status=IntegrityStatus.VERIFIED,
        processing_status=ProcessingStatus.COMPLETED,
        evidence_status=EvidenceStatus.ORIGINAL,
        device_id=acquisition.device_id,
        acquisition_id=acquisition.id,
        duration_seconds=meta.get("duration_seconds"),
        width=meta.get("width"),
        height=meta.get("height"),
        fps=meta.get("fps"),
        video_codec=meta.get("video_codec"),
        audio_codec=meta.get("audio_codec"),
        container=meta.get("container") or (probe_result.format_name if probe_result else None),
        bitrate_kbps=meta.get("bitrate_kbps"),
        vendor=probe_result.vendor if probe_result else None,
        proprietary_format=probe_result.format_name if probe_result else None,
        is_natively_playable=probe_result.is_natively_playable if probe_result else True,
        imported_by=user_id
    )

    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    audit = AuditLog(
        case_id=case.id,
        user_id=user_id,
        action="EVIDENCE_CREATED_FROM_ACQUISITION",
        target_identifier=evidence_ident,
        details=json.dumps({
            "evidence_identifier": evidence_ident,
            "acquisition_identifier": acquisition.acquisition_identifier,
            "device_identifier": acquisition.device.device_identifier if acquisition.device else None,
            "sha256": acquisition.destination_sha256,
            "original_filename": original_filename
        })
    )
    db.add(audit)
    db.commit()

    try:
        from app.services.blockchain_service import blockchain_service
        from app.models.user import User
        user_record = db.query(User).filter_by(id=user_id).first()
        uname = user_record.username if user_record else "System"
        blockchain_service.record_custody_and_anchor(
            db=db,
            case=case,
            evidence=evidence,
            action="EVIDENCE_ACQUIRED",
            user_id=user_id,
            username=uname,
            audit_log_id=audit.id,
            metadata={
                "acquisition_identifier": acquisition.acquisition_identifier,
                "original_filename": original_filename
            }
        )
    except Exception as e:
        logger.warning("Failed to anchor acquired evidence on blockchain: %s", e)

    return evidence
