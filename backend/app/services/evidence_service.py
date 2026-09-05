import os
import uuid
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session

import logging
from app.models.case import Case
from app.models.evidence import Evidence, IntegrityStatus, ProcessingStatus, EvidenceStatus
from app.models.audit import AuditLog
from app.schemas.evidence import (
    CompareResponse, CompareItem, HexPreviewResponse, HexPreviewRow, FormatAnalysisResponse
)
from app.services.video_processing import process_derived_video, extract_video_metadata
from app.forensics.signatures.signature_probe import probe_file
from app.forensics.vendor_adapter import get_best_adapter_for_file, get_ffmpeg_executable

logger = logging.getLogger(__name__)

CHUNK_SIZE = 8192

def get_case_evidence_dir(case_identifier: str, subfolder: str = "original") -> Path:
    data_dir = Path("data") / "case_data" / case_identifier / "evidence" / subfolder
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir

def compute_file_hashes(file_path: Path | str) -> tuple[str, str]:
    """Computes SHA-256 and MD5 hashes of a file."""
    sha256_hash = hashlib.sha256()
    md5_hash = hashlib.md5()
    with open(file_path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            sha256_hash.update(chunk)
            md5_hash.update(chunk)
    return sha256_hash.hexdigest(), md5_hash.hexdigest()

async def import_evidence(db: Session, case: Case, file: UploadFile, user_id: int) -> Evidence:
    sha256_hash = hashlib.sha256()
    md5_hash = hashlib.md5()
    
    original_filename = file.filename or "unknown"
    ext = os.path.splitext(original_filename)[1].lower()
    
    unique_id = uuid.uuid4().hex
    safe_filename = f"{unique_id}{ext}"
    
    storage_dir = get_case_evidence_dir(case.case_identifier, "original")
    storage_path = storage_dir / safe_filename
    
    size_bytes = 0
    with open(storage_path, "wb") as out_file:
        while chunk := await file.read(CHUNK_SIZE):
            sha256_hash.update(chunk)
            md5_hash.update(chunk)
            out_file.write(chunk)
            size_bytes += len(chunk)
            
    source_sha = sha256_hash.hexdigest()
    md5_ref = md5_hash.hexdigest()
    
    duplicate = db.query(Evidence).filter(
        Evidence.case_id == case.id, 
        Evidence.sha256 == source_sha,
        Evidence.is_deleted == False
    ).first()
    if duplicate:
        storage_path.unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail="Matching evidence content already exists in this case.")

    stored_sha = source_sha
    integrity_status = IntegrityStatus.VERIFIED
    evidence_identifier = f"EVD-{unique_id[:6].upper()}"
    
    # Binary magic-byte probe strictly overrides extension
    probe_result = probe_file(storage_path)

    if probe_result.vendor in ("Dahua", "Hikvision") or probe_result.format_name in (
        "Dahua DAV", "Hikvision HIKV", "Hikvision HIKB", "Hikvision HIKT",
        "Hikvision MPEG-PS", "Standard MP4", "Standard MKV", "Standard AVI",
        "Raw H.264 Elementary Stream", "Raw H.265 Elementary Stream"
    ):
        media_type = 'Video'
    elif ext in ['.mp4', '.avi', '.mkv', '.dav', '.mov']:
        media_type = 'Video'
    elif ext in ['.jpg', '.jpeg', '.png', '.bmp']:
        media_type = 'Image'
    else:
        media_type = 'Other'

    # Technical and CCTV vendor metadata extraction
    meta = {}
    if media_type == 'Video':
        try:
            meta = extract_video_metadata(str(storage_path))
        except Exception:
            pass

    # Extract vendor-specific CCTV metadata (e.g., Dahua OSD timestamps and channel)
    adapter = get_best_adapter_for_file(storage_path)
    cctv_meta = {}
    try:
        cctv_meta = adapter.get_metadata(storage_path)
    except Exception as e:
        logger.warning("Could not extract CCTV metadata for %s: %s", evidence_identifier, e)

    start_time_osd = None
    if cctv_meta.get("start_time_osd"):
        try:
            start_time_osd = datetime.fromisoformat(cctv_meta["start_time_osd"])
        except Exception:
            pass

    end_time_osd = None
    if cctv_meta.get("end_time_osd"):
        try:
            end_time_osd = datetime.fromisoformat(cctv_meta["end_time_osd"])
        except Exception:
            pass

    channel_index = cctv_meta.get("channel_index")
    resolved_vendor = adapter.vendor_name if adapter.vendor_name != "Generic" else probe_result.vendor
    resolved_format = cctv_meta.get("format") or probe_result.format_name

    logger.info("FORMAT_DETECTED: Detected %s format (%s) for %s", resolved_vendor, resolved_format, evidence_identifier)
        
    db_evidence = Evidence(
        case_id=case.id,
        evidence_identifier=evidence_identifier,
        original_filename=original_filename,
        storage_path=str(storage_path),
        source_type="Imported File",
        media_type=media_type,
        file_extension=ext,
        size_bytes=size_bytes,
        sha256=source_sha,
        md5_reference=md5_ref,
        source_sha256=source_sha,
        stored_sha256=stored_sha,
        integrity_status=integrity_status,
        processing_status=ProcessingStatus.COMPLETED,
        evidence_status=EvidenceStatus.ORIGINAL,
        duration_seconds=meta.get("duration_seconds"),
        width=meta.get("width"),
        height=meta.get("height"),
        fps=meta.get("fps"),
        video_codec=meta.get("video_codec"),
        audio_codec=meta.get("audio_codec"),
        container=meta.get("container") or resolved_format,
        bitrate_kbps=meta.get("bitrate_kbps"),
        vendor=resolved_vendor,
        proprietary_format=resolved_format,
        channel_index=channel_index,
        start_time_osd=start_time_osd,
        end_time_osd=end_time_osd,
        is_natively_playable=probe_result.is_natively_playable,
        imported_by=user_id
    )
    
    db.add(db_evidence)
    db.commit()
    db.refresh(db_evidence)

    # Audit log
    audit = AuditLog(
        case_id=case.id,
        user_id=user_id,
        action="EVIDENCE_IMPORTED",
        target_identifier=evidence_identifier,
        details=json.dumps({
            "evidence_identifier": evidence_identifier,
            "filename": original_filename,
            "size_bytes": size_bytes,
            "sha256": source_sha,
            "media_type": media_type
        })
    )
    db.add(audit)
    db.commit()

    try:
        from app.services.blockchain_service import blockchain_service
        user_record = db.query(User).filter_by(id=user_id).first()
        uname = user_record.username if user_record else "System"
        blockchain_service.record_custody_and_anchor(
            db=db,
            case=case,
            evidence=db_evidence,
            action="EVIDENCE_IMPORTED",
            user_id=user_id,
            username=uname,
            audit_log_id=audit.id,
            metadata={"filename": original_filename, "size_bytes": size_bytes}
        )
    except Exception as e:
        logger.warning("Failed to anchor imported evidence on blockchain: %s", e)
    
    return db_evidence

def verify_integrity(db: Session, evidence: Evidence) -> dict:
    storage_path = Path(evidence.storage_path)
    
    if not storage_path.exists():
        evidence.integrity_status = IntegrityStatus.MISMATCH
        db.commit()
        return {
            "evidence_identifier": evidence.evidence_identifier,
            "expected_sha256": evidence.sha256,
            "actual_sha256": "FILE_MISSING",
            "result": "FILE_CONTENT_DIFFERS",
            "verified_at": datetime.now(timezone.utc)
        }
        
    actual_sha, _ = compute_file_hashes(storage_path)
    
    if actual_sha == evidence.sha256:
        result = "IDENTICAL_FILE_CONTENT"
        evidence.integrity_status = IntegrityStatus.VERIFIED
    else:
        result = "FILE_CONTENT_DIFFERS"
        evidence.integrity_status = IntegrityStatus.MISMATCH
        
    evidence.stored_sha256 = actual_sha
    db.commit()
    
    return {
        "evidence_identifier": evidence.evidence_identifier,
        "expected_sha256": evidence.sha256,
        "actual_sha256": actual_sha,
        "result": result,
        "verified_at": datetime.now(timezone.utc)
    }

def compare_evidence(db: Session, evidence_list: list[Evidence]) -> CompareResponse:
    if not evidence_list:
        raise HTTPException(status_code=400, detail="No evidence provided for comparison")
        
    items = []
    first_hash = evidence_list[0].sha256
    identical = True
    
    for ev in evidence_list:
        if ev.sha256 != first_hash:
            identical = False
            
        items.append(CompareItem(
            evidence_id=ev.id,
            file_name=ev.original_filename,
            sha256=ev.sha256,
            md5_reference=ev.md5_reference,
            size_bytes=ev.size_bytes
        ))
        
    result_str = "IDENTICAL_FILE_CONTENT" if identical else "FILE_CONTENT_DIFFERS"
    return CompareResponse(items=items, result=result_str)

def derive_evidence(
    db: Session,
    case: Case,
    parent_evidence: Evidence,
    user_id: int,
    operation: str,
    start_time: float = None,
    end_time: float = None,
    crop: dict = None
) -> Evidence:
    """
    Forensic video derivation (TRIM, CROP, TRIM_AND_CROP).
    THE ORIGINAL EVIDENCE FILE IS NEVER MODIFIED.
    """
    if operation not in ("TRIM", "CROP", "TRIM_AND_CROP"):
        raise HTTPException(status_code=400, detail=f"Invalid derivation operation: {operation}")
        
    if parent_evidence.media_type != "Video":
        raise HTTPException(status_code=400, detail="Derivation is currently supported only for video evidence")
        
    parent_path = Path(parent_evidence.storage_path)
    if not parent_path.exists():
        raise HTTPException(status_code=404, detail="Parent evidence source file is missing from disk")

    # Step 1: Pre-hashing verification of the original evidence
    orig_sha_before, _ = compute_file_hashes(parent_path)

    # Step 2: Determine output naming
    base_name, _ = os.path.splitext(parent_evidence.original_filename)
    unique_id = uuid.uuid4().hex
    safe_filename = f"{unique_id}.mp4"
    derived_dir = get_case_evidence_dir(case.case_identifier, "derived")
    output_path = derived_dir / safe_filename

    # Construct clean forensic display name
    params_record = {}
    name_parts = [base_name]

    if operation in ("TRIM", "TRIM_AND_CROP"):
        if start_time is None or end_time is None or start_time < 0 or end_time <= start_time:
            raise HTTPException(status_code=400, detail="Invalid trim parameters: start must be >= 0 and < end")
        s_m, s_s = divmod(int(start_time), 60)
        e_m, e_s = divmod(int(end_time), 60)
        name_parts.append(f"trim_{s_m:02d}-{s_s:02d}_to_{e_m:02d}-{e_s:02d}")
        params_record["start_time"] = start_time
        params_record["end_time"] = end_time

    if operation in ("CROP", "TRIM_AND_CROP"):
        if not crop or not crop.get("width") or not crop.get("height"):
            raise HTTPException(status_code=400, detail="Invalid crop parameters: width and height are required")
        w = int(crop["width"])
        h = int(crop["height"])
        x = int(crop.get("x", 0))
        y = int(crop.get("y", 0))
        if w <= 0 or h <= 0 or x < 0 or y < 0:
            raise HTTPException(status_code=400, detail="Crop dimensions must be positive non-negative values")
        name_parts.append(f"crop_{w}x{h}")
        params_record["crop"] = {"x": x, "y": y, "width": w, "height": h}

    display_filename = "_".join(name_parts) + ".mp4"

    # Step 3: Run processing
    try:
        process_derived_video(
            input_path=str(parent_path),
            output_path=str(output_path),
            operation=operation,
            start_time=start_time,
            end_time=end_time,
            crop=crop
        )
    except Exception as e:
        if output_path.exists():
            output_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to process derived video: {str(e)}")

    # Step 4: Calculate hashes of the derived output
    derived_sha, derived_md5 = compute_file_hashes(output_path)
    derived_size = os.path.getsize(output_path)

    # Step 5: Critical Forensic Check: verify original has NOT been modified
    orig_sha_after, _ = compute_file_hashes(parent_path)
    if orig_sha_after != orig_sha_before:
        if output_path.exists():
            output_path.unlink(missing_ok=True)
        raise RuntimeError("FATAL FORENSIC INTEGRITY VIOLATION: Original evidence file was modified during derivation!")

    # Step 6: Extract metadata from derived output
    derived_meta = {}
    try:
        derived_meta = extract_video_metadata(str(output_path))
    except Exception:
        pass

    evidence_identifier = f"EVD-{unique_id[:6].upper()}"

    db_derived = Evidence(
        case_id=case.id,
        evidence_identifier=evidence_identifier,
        original_filename=display_filename,
        storage_path=str(output_path),
        source_type="Derived Clip",
        media_type="Video",
        file_extension=".mp4",
        size_bytes=derived_size,
        sha256=derived_sha,
        md5_reference=derived_md5,
        source_sha256=derived_sha,
        stored_sha256=derived_sha,
        integrity_status=IntegrityStatus.VERIFIED,
        processing_status=ProcessingStatus.COMPLETED,
        evidence_status=EvidenceStatus.DERIVED,
        parent_evidence_id=parent_evidence.id,
        derived_operation=operation,
        derived_parameters=json.dumps(params_record),
        duration_seconds=derived_meta.get("duration_seconds"),
        width=derived_meta.get("width"),
        height=derived_meta.get("height"),
        fps=derived_meta.get("fps"),
        video_codec=derived_meta.get("video_codec"),
        audio_codec=derived_meta.get("audio_codec"),
        container=derived_meta.get("container"),
        bitrate_kbps=derived_meta.get("bitrate_kbps"),
        imported_by=user_id
    )

    db.add(db_derived)
    db.commit()
    db.refresh(db_derived)

    # Step 7: Forensic Audit Log
    audit = AuditLog(
        case_id=case.id,
        user_id=user_id,
        action="EVIDENCE_DERIVED",
        target_identifier=evidence_identifier,
        details=json.dumps({
            "parent_id": parent_evidence.evidence_identifier,
            "child_id": evidence_identifier,
            "operation": operation,
            "parameters": params_record,
            "parent_filename": parent_evidence.original_filename,
            "derived_filename": display_filename,
            "sha256": derived_sha
        })
    )
    db.add(audit)
    db.commit()

    try:
        from app.services.blockchain_service import blockchain_service
        user_record = db.query(User).filter_by(id=user_id).first()
        uname = user_record.username if user_record else "System"
        blockchain_service.record_custody_and_anchor(
            db=db,
            case=case,
            evidence=db_derived,
            action="EVIDENCE_DERIVED",
            user_id=user_id,
            username=uname,
            audit_log_id=audit.id,
            metadata={"parent_id": parent_evidence.evidence_identifier, "operation": operation}
        )
    except Exception as e:
        logger.warning("Failed to anchor derived evidence on blockchain: %s", e)

    return db_derived

def soft_delete_evidence(
    db: Session,
    case: Case,
    evidence_ids: list[int],
    user_id: int,
    reason: str = None
) -> list[Evidence]:
    """
    Soft-deletes / removes evidence items from active case.
    Preserves records, files, lineage, and generates audit logs.
    """
    if not evidence_ids:
        raise HTTPException(status_code=400, detail="No evidence items specified for deletion")

    targets = db.query(Evidence).filter(
        Evidence.case_id == case.id,
        Evidence.id.in_(evidence_ids),
        Evidence.is_deleted == False
    ).all()

    if not targets:
        raise HTTPException(status_code=404, detail="None of the specified evidence items were found or they are already removed")

    now = datetime.now(timezone.utc)
    deleted_items = []

    for ev in targets:
        ev.is_deleted = True
        ev.deleted_at = now
        ev.deleted_by = user_id
        ev.deletion_reason = reason or "Removed by case administrator"
        deleted_items.append(ev)

        # Count active children for forensic audit log
        active_children = db.query(Evidence).filter(
            Evidence.parent_evidence_id == ev.id,
            Evidence.is_deleted == False
        ).count()

        audit = AuditLog(
            case_id=case.id,
            user_id=user_id,
            action="EVIDENCE_DELETED",
            target_identifier=ev.evidence_identifier,
            details=json.dumps({
                "evidence_identifier": ev.evidence_identifier,
                "filename": ev.original_filename,
                "reason": ev.deletion_reason,
                "active_derived_children": active_children,
                "status": ev.evidence_status
            })
        )
        db.add(audit)

    db.commit()
    return deleted_items


def generate_inspection_proxy(
    db: Session,
    case: Case,
    evidence: Evidence,
    user_id: int
) -> Evidence:
    """Generate a web inspection proxy (DERIVED Evidence) for proprietary CCTV files.

    If the proprietary container contains a usable standard video payload and safe
    transmuxing is supported, creates a DERIVED evidence record without modifying
    the original evidence.
    If transmuxing is unsupported, raises HTTPException without faking playback.
    """
    if evidence.case_id != case.id:
        raise HTTPException(status_code=403, detail="Evidence does not belong to specified case")

    if evidence.is_deleted:
        raise HTTPException(status_code=400, detail="Cannot generate proxy for deleted evidence")

    # Check if active inspection proxy already exists for this evidence
    existing_proxy = db.query(Evidence).filter(
        Evidence.parent_evidence_id == evidence.id,
        Evidence.derived_operation == "PROPRIETARY_TRANSMUX_PROXY",
        Evidence.is_deleted == False
    ).first()
    if existing_proxy:
        return existing_proxy

    source_path = Path(evidence.storage_path)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Source evidence file is missing from disk")

    adapter = get_best_adapter_for_file(source_path)
    logger.info("VENDOR_SELECTED: Best adapter %s selected for %s", adapter.vendor_name, evidence.evidence_identifier)

    if not adapter.can_transmux(source_path):
        logger.warning("DECODER_UNAVAILABLE: Transmux unavailable for %s (%s)", adapter.vendor_name, evidence.evidence_identifier)
        raise HTTPException(
            status_code=400,
            detail=(
                f"Web inspection proxy unavailable for {adapter.vendor_name} "
                f"({evidence.proprietary_format or 'proprietary format'}). "
                "Full proprietary decoder/transmuxer is not currently available. "
                "Original bitstream must be analyzed with native vendor tools."
            )
        )

    logger.info("PARSER_STARTED: Parsing %s container for %s", adapter.vendor_name, evidence.evidence_identifier)
    logger.info("PARSER_COMPLETED: Finished parsing container for %s", evidence.evidence_identifier)
    logger.info("DECODER_SELECTED: Selected decoder/transmuxer for %s", adapter.vendor_name)
    logger.info("PROXY_STARTED: Generating web proxy for %s", evidence.evidence_identifier)

    # Pre-hash original evidence
    orig_sha_before, _ = compute_file_hashes(source_path)

    # Destination derived proxy path
    unique_id = uuid.uuid4().hex
    derived_dir = get_case_evidence_dir(case.case_identifier, "derived")
    output_path = derived_dir / f"{unique_id}_proxy.mp4"

    try:
        adapter.transmux_to_proxy(source_path, output_path)
    except Exception as e:
        logger.error("PROXY_FAILED: Failed to generate proxy for %s: %s", evidence.evidence_identifier, e)
        if output_path.exists():
            output_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate proxy: {str(e)}")

    # Calculate hashes of derived proxy
    derived_sha, derived_md5 = compute_file_hashes(output_path)
    derived_size = output_path.stat().st_size

    # Verify original evidence was NOT modified
    orig_sha_after, _ = compute_file_hashes(source_path)
    if orig_sha_after != orig_sha_before:
        if output_path.exists():
            output_path.unlink(missing_ok=True)
        raise RuntimeError("FATAL FORENSIC INTEGRITY VIOLATION: Original evidence was modified during proxy generation!")

    # Extract metadata from derived proxy
    meta = {}
    try:
        meta = extract_video_metadata(str(output_path))
    except Exception:
        pass

    proxy_identifier = f"EVD-{unique_id[:6].upper()}"
    stem_name = Path(evidence.original_filename).stem

    db_derived = Evidence(
        case_id=case.id,
        evidence_identifier=proxy_identifier,
        original_filename=f"{stem_name}_proxy.mp4",
        storage_path=str(output_path),
        source_type="Derived Inspection Proxy",
        media_type="Video",
        file_extension=".mp4",
        size_bytes=derived_size,
        sha256=derived_sha,
        md5_reference=derived_md5,
        source_sha256=derived_sha,
        stored_sha256=derived_sha,
        integrity_status=IntegrityStatus.VERIFIED,
        processing_status=ProcessingStatus.COMPLETED,
        evidence_status=EvidenceStatus.DERIVED,
        parent_evidence_id=evidence.id,
        derived_operation="PROPRIETARY_TRANSMUX_PROXY",
        derived_parameters=json.dumps({
            "source_vendor": adapter.vendor_name,
            "source_format": evidence.proprietary_format,
            "source_identifier": evidence.evidence_identifier,
            "channel_index": evidence.channel_index,
            "start_time_osd": evidence.start_time_osd.isoformat() if evidence.start_time_osd else None,
            "end_time_osd": evidence.end_time_osd.isoformat() if evidence.end_time_osd else None,
        }),
        duration_seconds=meta.get("duration_seconds") or evidence.duration_seconds,
        width=meta.get("width") or evidence.width,
        height=meta.get("height") or evidence.height,
        fps=meta.get("fps") or evidence.fps,
        video_codec=meta.get("video_codec") or "h264",
        audio_codec=meta.get("audio_codec"),
        container="Standard MP4 (Proxy)",
        bitrate_kbps=meta.get("bitrate_kbps") or evidence.bitrate_kbps,
        vendor="Generic",
        proprietary_format="Standard MP4 (Proxy)",
        channel_index=evidence.channel_index,
        start_time_osd=evidence.start_time_osd,
        end_time_osd=evidence.end_time_osd,
        is_natively_playable=True,
        imported_by=user_id
    )

    db.add(db_derived)
    db.commit()
    db.refresh(db_derived)

    # Forensic audit log
    audit = AuditLog(
        case_id=case.id,
        user_id=user_id,
        action="EVIDENCE_DERIVED_PROXY",
        target_identifier=proxy_identifier,
        details=json.dumps({
            "parent_id": evidence.evidence_identifier,
            "child_id": proxy_identifier,
            "operation": "PROPRIETARY_TRANSMUX_PROXY",
            "source_vendor": adapter.vendor_name,
            "source_format": evidence.proprietary_format,
            "sha256": derived_sha
        })
    )
    db.add(audit)
    db.commit()

    logger.info("PROXY_COMPLETED: Proxy %s generated for parent %s", proxy_identifier, evidence.evidence_identifier)
    return db_derived


def get_format_analysis(db: Session, case: Case, evidence: Evidence) -> FormatAnalysisResponse:
    """Analyze proprietary or standard evidence format and return honest capabilities."""
    if evidence.case_id != case.id:
        raise HTTPException(status_code=403, detail="Evidence does not belong to specified case")

    source_path = Path(evidence.storage_path)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Evidence file missing on disk")

    probe = probe_file(source_path)
    adapter = get_best_adapter_for_file(source_path)
    meta = adapter.get_metadata(source_path)

    parser_avail = meta.get("parser_status") == "Available" or probe.vendor == "Generic"
    can_transmux = adapter.can_transmux(source_path)
    decoder_avail = can_transmux or (probe.vendor == "Generic" and probe.is_natively_playable)
    proxy_avail = can_transmux

    # Diagnostic status classification
    if probe.format_name == "Unknown / Unrecognized":
        status_str = "UNKNOWN FORMAT"
    elif probe.is_proprietary and not parser_avail:
        status_str = "UNSUPPORTED PROPRIETARY FORMAT"
    elif probe.is_proprietary and parser_avail and not decoder_avail:
        status_str = "DECODER UNAVAILABLE"
    elif not probe.is_proprietary and not decoder_avail:
        status_str = "CORRUPTED BITSTREAM"
    else:
        status_str = "SUPPORTED"

    return FormatAnalysisResponse(
        evidence_id=evidence.id,
        evidence_identifier=evidence.evidence_identifier,
        vendor=adapter.vendor_name if adapter.vendor_name != "Generic" else probe.vendor,
        format=meta.get("format") or probe.format_name,
        signature=probe.magic_hex,
        confidence=probe.confidence,
        native_playback=probe.is_natively_playable,
        parser_available=parser_avail,
        decoder_available=decoder_avail,
        proxy_available=proxy_avail,
        status=status_str,
        metadata=meta
    )


def get_hex_preview(evidence: Evidence, max_bytes: int = 512) -> HexPreviewResponse:
    """Safely reads the first up to 512 bytes of authorized evidence and returns offset, hex, and ASCII rows."""
    path = Path(evidence.storage_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Evidence file is missing on disk")

    try:
        with open(path, "rb") as f:
            data = f.read(min(max_bytes, 4096))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read evidence header: {str(e)}")

    rows = []
    for i in range(0, len(data), 16):
        chunk = data[i : i + 16]
        offset_str = f"{i:08X}"
        hex_str = " ".join(f"{b:02X}" for b in chunk)
        ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
        rows.append(HexPreviewRow(
            offset=offset_str,
            hex_bytes=hex_str,
            ascii_text=ascii_str
        ))

    return HexPreviewResponse(
        evidence_id=evidence.id,
        evidence_identifier=evidence.evidence_identifier,
        total_bytes_inspected=len(data),
        rows=rows
    )

