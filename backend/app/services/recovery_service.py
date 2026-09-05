"""Forensic Recovery Service.

Orchestrates disk image probing, signature/structure-based carving,
candidate validation, and creation of immutable RECOVERED evidence records.
"""
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.evidence import Evidence, EvidenceStatus, IntegrityStatus, ProcessingStatus
from app.models.audit import AuditLog
from app.models.recovery import (
    RecoveryCandidate,
    RecoveryCandidateStatus,
    RecoveryScanJob,
    RecoveryScanStatus,
)
from app.forensics.recovery.engine import RecoveryEngine, DiskImageInfo
from app.services.evidence_service import compute_file_hashes, get_case_evidence_dir

logger = logging.getLogger(__name__)

recovery_engine = RecoveryEngine()


def _resolve_evidence_path(evidence: Evidence) -> Path:
    """Safely resolves absolute path of an evidence file."""
    path = Path(evidence.storage_path)
    if not path.is_file():
        path = Path.cwd() / evidence.storage_path
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Source evidence file not found on disk: {evidence.storage_path}")
    return path


def start_recovery_scan(
    db: Session,
    case: Case,
    source_evidence_id: int,
    user_id: int,
    max_bytes: int = 20 * 1024 * 1024,
) -> Tuple[RecoveryScanJob, List[RecoveryCandidate]]:
    """Launches a carving scan on a source disk image or binary evidence file."""
    evidence = db.query(Evidence).filter(
        Evidence.id == source_evidence_id,
        Evidence.case_id == case.id,
        Evidence.is_deleted == False
    ).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Source evidence not found in specified case")

    image_path = _resolve_evidence_path(evidence)

    # 1. Probe image
    image_info = recovery_engine.probe_image(image_path)

    # 2. Create Scan Job
    scan_ident = f"SCAN-{uuid.uuid4().hex[:6].upper()}"
    scan_job = RecoveryScanJob(
        scan_identifier=scan_ident,
        case_id=case.id,
        source_evidence_id=evidence.id,
        source_acquisition_id=evidence.acquisition_id,
        source_device_id=evidence.device_id,
        status=RecoveryScanStatus.RUNNING,
        bytes_scanned=0,
        total_bytes=image_info.size_bytes,
        candidates_found=0,
        started_at=datetime.now(timezone.utc),
        created_by=user_id,
    )
    db.add(scan_job)
    db.commit()
    db.refresh(scan_job)

    # 3. Execute carving scan
    try:
        raw_candidates = recovery_engine.scan_candidates(image_path, max_bytes=max_bytes)
        db_candidates: List[RecoveryCandidate] = []

        for rc in raw_candidates:
            cand_ident = f"REC-{uuid.uuid4().hex[:6].upper()}"
            cand = RecoveryCandidate(
                candidate_identifier=cand_ident,
                scan_job_id=scan_job.id,
                case_id=case.id,
                source_evidence_id=evidence.id,
                source_acquisition_id=evidence.acquisition_id,
                source_device_id=evidence.device_id,
                source_offset=rc.offset_bytes,
                size_bytes=rc.length_bytes,
                detected_format=rc.format_name,
                vendor=rc.detected_vendor,
                confidence=rc.confidence,
                status=RecoveryCandidateStatus.DETECTED,
                metadata_json=json.dumps(rc.metadata),
            )
            db.add(cand)
            db_candidates.append(cand)

        scan_job.status = RecoveryScanStatus.COMPLETED
        scan_job.bytes_scanned = min(max_bytes, image_info.size_bytes)
        scan_job.candidates_found = len(db_candidates)
        scan_job.completed_at = datetime.now(timezone.utc)
        db.commit()

        # Audit log
        audit = AuditLog(
            case_id=case.id,
            user_id=user_id,
            action="RECOVERY_SCAN_STARTED",
            target_identifier=scan_ident,
            details=json.dumps({
                "scan_identifier": scan_ident,
                "source_evidence_id": evidence.evidence_identifier,
                "candidates_found": len(db_candidates),
                "image_format": image_info.image_format,
            }),
        )
        db.add(audit)
        db.commit()

        return scan_job, db_candidates

    except Exception as e:
        scan_job.status = RecoveryScanStatus.FAILED
        scan_job.error_message = str(e)
        scan_job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.error("Recovery scan %s failed: %s", scan_ident, str(e))
        raise HTTPException(status_code=500, detail=f"Recovery scan failed: {str(e)}")


def list_recovery_candidates(
    db: Session,
    case: Case,
    source_evidence_id: Optional[int] = None,
    scan_job_id: Optional[int] = None,
) -> List[RecoveryCandidate]:
    """Retrieves discovered carving candidates."""
    query = db.query(RecoveryCandidate).filter(RecoveryCandidate.case_id == case.id)
    if source_evidence_id:
        query = query.filter(RecoveryCandidate.source_evidence_id == source_evidence_id)
    if scan_job_id:
        query = query.filter(RecoveryCandidate.scan_job_id == scan_job_id)
    return query.order_by(RecoveryCandidate.source_offset.asc()).all()


def validate_candidate(
    db: Session,
    case: Case,
    candidate_id: int,
    user_id: int,
) -> RecoveryCandidate:
    """Validates structural integrity of stream candidate."""
    cand = db.query(RecoveryCandidate).filter(
        RecoveryCandidate.id == candidate_id,
        RecoveryCandidate.case_id == case.id
    ).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Recovery candidate not found")

    source_ev = db.query(Evidence).filter(Evidence.id == cand.source_evidence_id).first()
    if not source_ev:
        raise HTTPException(status_code=404, detail="Source evidence for candidate missing")

    image_path = _resolve_evidence_path(source_ev)
    val_result = recovery_engine.validate_candidate_stream(
        image_path, cand.source_offset, cand.size_bytes, cand.detected_format
    )

    status_str = val_result.get("status", "UNKNOWN")
    if status_str == "VALID":
        cand.status = RecoveryCandidateStatus.VALIDATED
    elif status_str == "PARTIAL":
        cand.status = RecoveryCandidateStatus.PARTIAL
    elif status_str == "CORRUPTED":
        cand.status = RecoveryCandidateStatus.CORRUPTED
    else:
        cand.status = RecoveryCandidateStatus.DETECTED

    cand.confidence = val_result.get("confidence", cand.confidence)
    cand.validation_details = val_result.get("details", "")
    db.commit()
    db.refresh(cand)

    audit = AuditLog(
        case_id=case.id,
        user_id=user_id,
        action="RECOVERY_CANDIDATE_VALIDATED",
        target_identifier=cand.candidate_identifier,
        details=json.dumps({
            "candidate_identifier": cand.candidate_identifier,
            "status": cand.status.value,
            "details": cand.validation_details,
            "confidence": cand.confidence,
        }),
    )
    db.add(audit)
    db.commit()

    return cand


def recover_candidate(
    db: Session,
    case: Case,
    candidate_id: int,
    user_id: int,
) -> Tuple[RecoveryCandidate, Evidence]:
    """Carves candidate bytes into an immutable RECOVERED Evidence record."""
    cand = db.query(RecoveryCandidate).filter(
        RecoveryCandidate.id == candidate_id,
        RecoveryCandidate.case_id == case.id
    ).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Recovery candidate not found")

    if cand.status == RecoveryCandidateStatus.RECOVERED and cand.recovered_evidence_id:
        existing = db.query(Evidence).filter(Evidence.id == cand.recovered_evidence_id).first()
        if existing:
            return cand, existing

    source_ev = db.query(Evidence).filter(Evidence.id == cand.source_evidence_id).first()
    if not source_ev:
        raise HTTPException(status_code=404, detail="Source evidence for candidate missing")

    image_path = _resolve_evidence_path(source_ev)

    # Determine extension
    ext = ".mp4"
    if "DHAV" in cand.detected_format or cand.vendor == "Dahua":
        ext = ".dav"
    elif "Hikvision" in cand.detected_format:
        ext = ".mp4"

    # Destination in Drishtik case storage
    rec_dir = Path("data") / "case_data" / case.case_identifier / "evidence" / "recovered"
    rec_dir.mkdir(parents=True, exist_ok=True)
    out_filename = f"recovered_{cand.candidate_identifier}{ext}"
    out_path = rec_dir / out_filename

    # Carve bytes
    carved_size = recovery_engine.extract_candidate_bytes(
        image_path, cand.source_offset, cand.size_bytes, out_path
    )
    if carved_size == 0:
        raise HTTPException(status_code=500, detail="Failed to carve bytes from source image")

    # Compute hashes on carved artifact
    sha256_hash, md5_hash = compute_file_hashes(out_path)

    ev_ident = f"EVD-R{uuid.uuid4().hex[:6].upper()}"
    recovered_ev = Evidence(
        case_id=case.id,
        evidence_identifier=ev_ident,
        original_filename=out_filename,
        storage_path=str(out_path),
        source_type="DISK_CARVED_RECOVERY",
        media_type="Video",
        file_extension=ext,
        size_bytes=carved_size,
        sha256=sha256_hash,
        md5_reference=md5_hash,
        stored_sha256=sha256_hash,
        integrity_status=IntegrityStatus.VERIFIED,
        processing_status=ProcessingStatus.COMPLETED,
        evidence_status=EvidenceStatus.RECOVERED,
        parent_evidence_id=source_ev.id,
        device_id=cand.source_device_id or source_ev.device_id,
        acquisition_id=cand.source_acquisition_id or source_ev.acquisition_id,
        derived_operation="CARVED_STREAM_RECOVERY",
        derived_parameters=json.dumps({
            "candidate_identifier": cand.candidate_identifier,
            "source_evidence_id": source_ev.id,
            "source_offset": cand.source_offset,
            "recovery_method": "SIGNATURE_CARVING",
            "detected_format": cand.detected_format,
            "vendor": cand.vendor,
        }),
        vendor=cand.vendor,
        proprietary_format=cand.detected_format,
        is_natively_playable=(ext == ".mp4"),
        imported_by=user_id,
    )
    db.add(recovered_ev)
    db.commit()
    db.refresh(recovered_ev)

    # Update candidate record
    cand.status = RecoveryCandidateStatus.RECOVERED
    cand.recovered_evidence_id = recovered_ev.id
    db.commit()
    db.refresh(cand)

    # Audit log
    audit = AuditLog(
        case_id=case.id,
        user_id=user_id,
        action="RECOVERED_EVIDENCE_CREATED",
        target_identifier=ev_ident,
        details=json.dumps({
            "recovered_evidence_identifier": ev_ident,
            "candidate_identifier": cand.candidate_identifier,
            "source_evidence_identifier": source_ev.evidence_identifier,
            "source_offset": cand.source_offset,
            "sha256": sha256_hash,
            "size_bytes": carved_size,
        }),
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
            evidence=recovered_ev,
            action="RECOVERED_EVIDENCE_CREATED",
            user_id=user_id,
            username=uname,
            audit_log_id=audit.id,
            metadata={
                "candidate_identifier": cand.candidate_identifier,
                "source_evidence": source_ev.evidence_identifier,
                "source_offset": cand.source_offset
            }
        )
    except Exception as e:
        logger.warning("Failed to anchor recovered evidence on blockchain: %s", e)

    logger.info("RECOVERED_EVIDENCE_CREATED: %s carved from %s at offset %d", ev_ident, source_ev.evidence_identifier, cand.source_offset)

    return cand, recovered_ev
