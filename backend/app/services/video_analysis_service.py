"""Forensic Video Analysis Service.

Provides:
- Unified Video Representation across standard and proprietary CCTV sources
- Playback source resolution (Original vs Derived Inspection Proxy)
- Frame-by-frame extraction and DERIVED frame artifact creation
- Forensic timeline event markers and investigator notes
- Dual media time vs CCTV timestamp tracking and calibration/normalization
- Multi-camera synchronization tracks and alignment
- Strict forensic immutability and audit logging
"""
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.evidence import Evidence, EvidenceStatus, IntegrityStatus, ProcessingStatus
from app.models.device import Device
from app.models.acquisition import Acquisition
from app.models.audit import AuditLog
from app.models.video_analysis import (
    TimelineEvent,
    TimelineEventType,
    AnalysisNote,
    TimestampCalibration,
    VideoAnalysisSession,
)
from app.schemas.video_analysis import (
    TimelineEventCreate,
    TimelineEventResponse,
    AnalysisNoteCreate,
    AnalysisNoteResponse,
    TimestampCalibrationCreate,
    TimestampCalibrationResponse,
    FrameExportRequest,
    FrameExportResponse,
    CameraTrackResponse,
    UnifiedVideoResponse,
    VideoAnalysisSessionCreate,
    VideoAnalysisSessionResponse,
)
from app.services.evidence_service import compute_file_hashes, get_case_evidence_dir
from app.services.video_processing import extract_frame_image
from app.forensics.vendor_adapter import get_best_adapter_for_file

logger = logging.getLogger(__name__)


def get_unified_video_representation(
    db: Session, case: Case, evidence: Evidence, user_id: int
) -> UnifiedVideoResponse:
    """Builds a normalized, vendor-agnostic representation of video evidence for forensic analysis."""
    if evidence.case_id != case.id:
        raise HTTPException(status_code=403, detail="Evidence does not belong to specified case")
    if evidence.is_deleted:
        raise HTTPException(status_code=404, detail="Evidence has been removed")

    # 1. Device and Acquisition Provenance
    device_ident = None
    if evidence.device_id:
        dev = db.query(Device).filter(Device.id == evidence.device_id).first()
        if dev:
            device_ident = dev.device_identifier

    acq_ident = None
    if evidence.acquisition_id:
        acq = db.query(Acquisition).filter(Acquisition.id == evidence.acquisition_id).first()
        if acq:
            acq_ident = acq.acquisition_identifier

    # 2. Determine Playback Source
    browser_playable = False
    proxy_available = False
    playback_source = None
    parent_evidence_ident = None
    is_inspection_proxy = False

    if evidence.is_natively_playable and evidence.media_type == "Video":
        browser_playable = True
        playback_source = f"/api/v1/cases/{case.case_identifier}/evidence/{evidence.id}/stream"
        if evidence.evidence_status == EvidenceStatus.DERIVED:
            is_inspection_proxy = (evidence.derived_operation == "PROPRIETARY_TRANSMUX_PROXY")
            if evidence.parent_evidence_id:
                parent = db.query(Evidence).filter(Evidence.id == evidence.parent_evidence_id).first()
                if parent:
                    parent_evidence_ident = parent.evidence_identifier
    else:
        # Check if an active derived inspection proxy already exists for this proprietary evidence
        existing_proxy = db.query(Evidence).filter(
            Evidence.parent_evidence_id == evidence.id,
            Evidence.derived_operation == "PROPRIETARY_TRANSMUX_PROXY",
            Evidence.is_deleted == False
        ).first()

        if existing_proxy and Path(existing_proxy.storage_path).exists():
            browser_playable = True
            proxy_available = True
            playback_source = f"/api/v1/cases/{case.case_identifier}/evidence/{existing_proxy.id}/stream"
            is_inspection_proxy = True
            parent_evidence_ident = evidence.evidence_identifier
        else:
            # Check if adapter can generate a proxy
            src_path = Path(evidence.storage_path)
            if src_path.exists():
                adapter = get_best_adapter_for_file(src_path)
                proxy_available = adapter.can_transmux(src_path)

    # 3. Calibration / Normalization state
    calibration = db.query(TimestampCalibration).filter(
        TimestampCalibration.case_id == case.id,
        TimestampCalibration.evidence_id == evidence.id
    ).first()

    is_calibrated = calibration is not None
    offset_seconds = calibration.offset_seconds if calibration else 0.0
    timezone_str = calibration.time_zone if calibration else "UTC"
    calib_reason = calibration.calibration_reason if calibration else None

    # 4. Multi-Camera Tracks for the Case / Acquisition
    tracks = get_multi_camera_tracks(db, case, evidence)

    # 5. Audit Log
    try:
        audit = AuditLog(
            case_id=case.id,
            user_id=user_id,
            action="VIDEO_ANALYSIS_OPENED",
            target_identifier=evidence.evidence_identifier,
            details=json.dumps({
                "evidence_identifier": evidence.evidence_identifier,
                "browser_playable": browser_playable,
                "is_inspection_proxy": is_inspection_proxy,
                "channel_index": evidence.channel_index,
            })
        )
        db.add(audit)
        db.commit()
    except Exception as e:
        logger.warning("Could not record analysis open audit log: %s", e)

    ch_num = evidence.channel_index or 1
    return UnifiedVideoResponse(
        evidence_id=evidence.id,
        evidence_identifier=evidence.evidence_identifier,
        original_filename=evidence.original_filename,
        source_device_identifier=device_ident,
        acquisition_identifier=acq_ident,
        vendor=evidence.vendor or "Generic / Standard",
        container_format=evidence.proprietary_format or evidence.container or "Standard MP4",
        is_proprietary=not evidence.is_natively_playable,
        channel_number=ch_num,
        channel_name=f"CAM {ch_num:02d}",
        source_start_time=evidence.start_time_osd,
        source_end_time=evidence.end_time_osd,
        timezone=timezone_str,
        timestamp_confidence=1.0,
        has_discontinuous_timestamps=False,
        duration_seconds=evidence.duration_seconds,
        width=evidence.width,
        height=evidence.height,
        fps=evidence.fps or 25.0,
        video_codec=evidence.video_codec,
        audio_codec=evidence.audio_codec,
        bitrate_kbps=evidence.bitrate_kbps,
        browser_playable=browser_playable,
        proxy_available=proxy_available,
        playback_source=playback_source,
        parent_evidence_identifier=parent_evidence_ident,
        is_inspection_proxy=is_inspection_proxy,
        is_calibrated=is_calibrated,
        offset_seconds=offset_seconds,
        calibration_reason=calib_reason,
        sha256=evidence.sha256,
        md5_reference=evidence.md5_reference,
        camera_tracks=tracks,
    )


def get_multi_camera_tracks(db: Session, case: Case, active_evidence: Evidence) -> List[CameraTrackResponse]:
    """Discovers and synchronizes other camera channels within the case / acquisition."""
    query = db.query(Evidence).filter(
        Evidence.case_id == case.id,
        Evidence.media_type == "Video",
        Evidence.is_deleted == False
    )

    # If active evidence belongs to an acquisition, prioritize videos in the same acquisition
    all_videos = query.order_by(Evidence.channel_index.asc(), Evidence.id.asc()).all()

    tracks: List[CameraTrackResponse] = []
    active_start = active_evidence.start_time_osd

    for vid in all_videos:
        # Determine if this video is playable (directly or via inspection proxy)
        is_playable = vid.is_natively_playable
        stream_id = vid.id

        if not is_playable:
            proxy = db.query(Evidence).filter(
                Evidence.parent_evidence_id == vid.id,
                Evidence.derived_operation == "PROPRIETARY_TRANSMUX_PROXY",
                Evidence.is_deleted == False
            ).first()
            if proxy:
                is_playable = True
                stream_id = proxy.id

        ch_num = vid.channel_index or (len(tracks) + 1)
        ch_name = f"CAM {ch_num:02d}"

        # Calculate time offset from master if timestamps are known
        offset_seconds = 0.0
        if active_start and vid.start_time_osd:
            offset_seconds = (vid.start_time_osd - active_start).total_seconds()

        tracks.append(
            CameraTrackResponse(
                channel_number=ch_num,
                channel_name=ch_name,
                evidence_id=vid.id,
                evidence_identifier=vid.evidence_identifier,
                original_filename=vid.original_filename,
                vendor=vid.vendor or "Generic",
                duration_seconds=vid.duration_seconds,
                source_start_time=vid.start_time_osd,
                source_end_time=vid.end_time_osd,
                browser_playable=is_playable,
                playback_source=f"/api/v1/cases/{case.case_identifier}/evidence/{stream_id}/stream" if is_playable else None,
                is_active=(vid.id == active_evidence.id),
                offset_from_master_seconds=offset_seconds,
            )
        )

    return tracks


def export_frame(
    db: Session,
    case: Case,
    evidence: Evidence,
    req: FrameExportRequest,
    user_id: int
) -> FrameExportResponse:
    """Extracts a still frame and creates a DERIVED evidence artifact without altering original evidence."""
    if evidence.case_id != case.id:
        raise HTTPException(status_code=403, detail="Evidence does not belong to specified case")
    if evidence.is_deleted:
        raise HTTPException(status_code=400, detail="Cannot export frame from deleted evidence")

    # Determine input video file (use proxy if original is proprietary and proxy exists)
    source_path = Path(evidence.storage_path)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Source evidence file not found on disk")

    read_path = source_path
    if not evidence.is_natively_playable:
        proxy = db.query(Evidence).filter(
            Evidence.parent_evidence_id == evidence.id,
            Evidence.derived_operation == "PROPRIETARY_TRANSMUX_PROXY",
            Evidence.is_deleted == False
        ).first()
        if proxy and Path(proxy.storage_path).exists():
            read_path = Path(proxy.storage_path)
        else:
            raise HTTPException(
                status_code=400,
                detail="Cannot export frame: Original bitstream is proprietary and no inspection proxy exists. Generate proxy first."
            )

    # Pre-hash original evidence
    orig_sha_before, _ = compute_file_hashes(source_path)

    # Destination for derived frame image
    unique_id = uuid.uuid4().hex
    derived_dir = get_case_evidence_dir(case.case_identifier, "derived")
    frame_filename = f"{unique_id}_frame.jpg"
    frame_output_path = derived_dir / frame_filename

    try:
        extract_frame_image(str(read_path.resolve()), str(frame_output_path.resolve()), req.media_time)
    except Exception as e:
        logger.error("FRAME_EXPORT failed: %s", e)
        if frame_output_path.exists():
            frame_output_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Frame extraction failed: {str(e)}")

    # Calculate cryptographic hashes of the new derived frame artifact
    frame_sha, frame_md5 = compute_file_hashes(frame_output_path)
    frame_size = frame_output_path.stat().st_size

    # STRICT IMMUTABILITY CHECK
    orig_sha_after, _ = compute_file_hashes(source_path)
    if orig_sha_after != orig_sha_before:
        if frame_output_path.exists():
            frame_output_path.unlink(missing_ok=True)
        raise RuntimeError("FATAL FORENSIC INTEGRITY VIOLATION: Original evidence was modified during frame export!")

    # Calculate frame CCTV timestamp if available
    source_frame_ts = None
    if evidence.start_time_osd:
        source_frame_ts = evidence.start_time_osd + timedelta(seconds=req.media_time)

    # Approximate frame number if not provided
    fps = evidence.fps or 25.0
    calc_frame_number = req.frame_number if req.frame_number is not None else int(round(req.media_time * fps))

    frame_ident = f"EVD-{unique_id[:6].upper()}"
    stem_name = Path(evidence.original_filename).stem

    # Create new DERIVED Evidence artifact
    db_frame = Evidence(
        case_id=case.id,
        evidence_identifier=frame_ident,
        original_filename=f"{stem_name}_frame_{calc_frame_number:06d}.jpg",
        storage_path=str(frame_output_path),
        source_type="Derived Frame Export",
        media_type="Image",
        file_extension=".jpg",
        size_bytes=frame_size,
        sha256=frame_sha,
        md5_reference=frame_md5,
        source_sha256=frame_sha,
        stored_sha256=frame_sha,
        integrity_status=IntegrityStatus.VERIFIED,
        processing_status=ProcessingStatus.COMPLETED,
        evidence_status=EvidenceStatus.DERIVED,
        parent_evidence_id=evidence.id,
        derived_operation="FRAME_EXPORT",
        derived_parameters=json.dumps({
            "media_time": req.media_time,
            "frame_number": calc_frame_number,
            "source_timestamp": source_frame_ts.isoformat() if source_frame_ts else None,
            "notes": req.notes,
        }),
        width=evidence.width,
        height=evidence.height,
        channel_index=evidence.channel_index,
        start_time_osd=source_frame_ts,
        end_time_osd=source_frame_ts,
        is_natively_playable=True,
        imported_by=user_id
    )
    db.add(db_frame)
    db.commit()
    db.refresh(db_frame)

    # Forensic audit log
    audit = AuditLog(
        case_id=case.id,
        user_id=user_id,
        action="FRAME_EXPORTED",
        target_identifier=frame_ident,
        details=json.dumps({
            "parent_evidence_id": evidence.evidence_identifier,
            "child_evidence_id": frame_ident,
            "media_time": req.media_time,
            "frame_number": calc_frame_number,
            "sha256": frame_sha,
        })
    )
    db.add(audit)
    db.commit()

    logger.info("FRAME_EXPORTED: Frame %s exported from %s at %fs", frame_ident, evidence.evidence_identifier, req.media_time)

    return FrameExportResponse(
        evidence_id=db_frame.id,
        evidence_identifier=frame_ident,
        original_filename=db_frame.original_filename,
        parent_evidence_id=evidence.id,
        parent_evidence_identifier=evidence.evidence_identifier,
        evidence_status="DERIVED",
        derived_operation="FRAME_EXPORT",
        media_type="Image",
        file_extension=".jpg",
        size_bytes=frame_size,
        sha256=frame_sha,
        md5_reference=frame_md5,
        media_time=req.media_time,
        frame_number=calc_frame_number,
        source_timestamp=source_frame_ts,
        created_at=db_frame.created_at or datetime.now(timezone.utc),
    )


# --- Timeline Events ---

def create_timeline_event(
    db: Session, case: Case, evidence: Evidence, req: TimelineEventCreate, user_id: int
) -> TimelineEventResponse:
    """Creates a forensic timeline event marker."""
    if evidence.case_id != case.id:
        raise HTTPException(status_code=403, detail="Evidence does not belong to specified case")

    # Compute source timestamp from start_time_osd + media_time if not provided
    src_ts = req.source_timestamp
    if not src_ts and evidence.start_time_osd:
        src_ts = evidence.start_time_osd + timedelta(seconds=req.media_time)

    # Compute normalized timestamp if calibration exists
    calib = db.query(TimestampCalibration).filter(
        TimestampCalibration.case_id == case.id,
        TimestampCalibration.evidence_id == evidence.id
    ).first()

    norm_ts = req.normalized_timestamp
    if not norm_ts and src_ts:
        offset = calib.offset_seconds if calib else 0.0
        norm_ts = src_ts + timedelta(seconds=offset)

    evt_ident = f"EVT-{uuid.uuid4().hex[:6].upper()}"

    event = TimelineEvent(
        event_identifier=evt_ident,
        case_id=case.id,
        evidence_id=evidence.id,
        channel_id=req.channel_id or evidence.channel_index or 1,
        media_time=req.media_time,
        source_timestamp=src_ts,
        normalized_timestamp=norm_ts,
        event_type=req.event_type,
        title=req.title,
        description=req.description,
        created_by=user_id
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    audit = AuditLog(
        case_id=case.id,
        user_id=user_id,
        action="TIMELINE_EVENT_CREATED",
        target_identifier=evt_ident,
        details=json.dumps({
            "event_identifier": evt_ident,
            "evidence_identifier": evidence.evidence_identifier,
            "event_type": req.event_type.value,
            "media_time": req.media_time,
            "title": req.title
        })
    )
    db.add(audit)
    db.commit()

    return TimelineEventResponse.model_validate(event)


def list_timeline_events(
    db: Session, case: Case, evidence: Evidence, search_query: Optional[str] = None
) -> List[TimelineEventResponse]:
    """Retrieves timeline events for evidence with optional text search filter."""
    if evidence.case_id != case.id:
        raise HTTPException(status_code=403, detail="Evidence does not belong to specified case")

    query = db.query(TimelineEvent).filter(
        TimelineEvent.case_id == case.id,
        TimelineEvent.evidence_id == evidence.id
    )

    if search_query:
        q = f"%{search_query.strip()}%"
        query = query.filter(
            (TimelineEvent.title.ilike(q)) |
            (TimelineEvent.description.ilike(q)) |
            (TimelineEvent.event_type.ilike(q))
        )

    events = query.order_by(TimelineEvent.media_time.asc()).all()
    return [TimelineEventResponse.model_validate(e) for e in events]


def delete_timeline_event(db: Session, case: Case, event_id: int, user_id: int) -> dict:
    """Deletes a timeline event marker."""
    event = db.query(TimelineEvent).filter(
        TimelineEvent.id == event_id,
        TimelineEvent.case_id == case.id
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="Timeline event not found")

    ident = event.event_identifier
    db.delete(event)
    db.commit()

    audit = AuditLog(
        case_id=case.id,
        user_id=user_id,
        action="TIMELINE_EVENT_DELETED",
        target_identifier=ident,
        details=json.dumps({"event_identifier": ident})
    )
    db.add(audit)
    db.commit()

    return {"message": "Timeline event deleted successfully", "event_identifier": ident}


# --- Investigator Notes ---

def create_analysis_note(
    db: Session, case: Case, evidence: Evidence, req: AnalysisNoteCreate, user_id: int
) -> AnalysisNoteResponse:
    """Creates an investigator note pinned to a timeline position."""
    if evidence.case_id != case.id:
        raise HTTPException(status_code=403, detail="Evidence does not belong to specified case")

    src_ts = req.source_timestamp
    if not src_ts and evidence.start_time_osd:
        src_ts = evidence.start_time_osd + timedelta(seconds=req.media_time)

    calib = db.query(TimestampCalibration).filter(
        TimestampCalibration.case_id == case.id,
        TimestampCalibration.evidence_id == evidence.id
    ).first()

    norm_ts = req.normalized_timestamp
    if not norm_ts and src_ts:
        offset = calib.offset_seconds if calib else 0.0
        norm_ts = src_ts + timedelta(seconds=offset)

    note = AnalysisNote(
        case_id=case.id,
        evidence_id=evidence.id,
        media_time=req.media_time,
        source_timestamp=src_ts,
        normalized_timestamp=norm_ts,
        note_text=req.note_text,
        created_by=user_id
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    audit = AuditLog(
        case_id=case.id,
        user_id=user_id,
        action="ANALYSIS_NOTE_CREATED",
        target_identifier=f"NOTE-{note.id}",
        details=json.dumps({
            "evidence_identifier": evidence.evidence_identifier,
            "media_time": req.media_time,
            "note_preview": req.note_text[:60]
        })
    )
    db.add(audit)
    db.commit()

    return AnalysisNoteResponse.model_validate(note)


def list_analysis_notes(
    db: Session, case: Case, evidence: Evidence, search_query: Optional[str] = None
) -> List[AnalysisNoteResponse]:
    """Retrieves investigator notes for evidence with optional search filter."""
    if evidence.case_id != case.id:
        raise HTTPException(status_code=403, detail="Evidence does not belong to specified case")

    query = db.query(AnalysisNote).filter(
        AnalysisNote.case_id == case.id,
        AnalysisNote.evidence_id == evidence.id
    )

    if search_query:
        q = f"%{search_query.strip()}%"
        query = query.filter(AnalysisNote.note_text.ilike(q))

    notes = query.order_by(AnalysisNote.media_time.asc()).all()
    return [AnalysisNoteResponse.model_validate(n) for n in notes]


def delete_analysis_note(db: Session, case: Case, note_id: int, user_id: int) -> dict:
    """Deletes an investigator note."""
    note = db.query(AnalysisNote).filter(
        AnalysisNote.id == note_id,
        AnalysisNote.case_id == case.id
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Analysis note not found")

    db.delete(note)
    db.commit()

    audit = AuditLog(
        case_id=case.id,
        user_id=user_id,
        action="ANALYSIS_NOTE_DELETED",
        target_identifier=f"NOTE-{note_id}",
        details=json.dumps({"note_id": note_id})
    )
    db.add(audit)
    db.commit()

    return {"message": "Analysis note deleted successfully", "note_id": note_id}


# --- Timestamp Calibration ---

def get_calibration(
    db: Session, case: Case, evidence: Evidence
) -> Optional[TimestampCalibrationResponse]:
    """Retrieves existing calibration parameters for evidence."""
    if evidence.case_id != case.id:
        raise HTTPException(status_code=403, detail="Evidence does not belong to specified case")

    calib = db.query(TimestampCalibration).filter(
        TimestampCalibration.case_id == case.id,
        TimestampCalibration.evidence_id == evidence.id
    ).first()

    return TimestampCalibrationResponse.model_validate(calib) if calib else None


def set_calibration(
    db: Session, case: Case, evidence: Evidence, req: TimestampCalibrationCreate, user_id: int
) -> TimestampCalibrationResponse:
    """Sets or updates clock offset calibration without altering embedded raw CCTV time."""
    if evidence.case_id != case.id:
        raise HTTPException(status_code=403, detail="Evidence does not belong to specified case")

    calib = db.query(TimestampCalibration).filter(
        TimestampCalibration.case_id == case.id,
        TimestampCalibration.evidence_id == evidence.id
    ).first()

    if calib:
        calib.offset_seconds = req.offset_seconds
        calib.time_zone = req.time_zone
        calib.calibration_reason = req.calibration_reason
        calib.calibration_method = req.calibration_method
        calib.calibrated_by = user_id
    else:
        calib = TimestampCalibration(
            case_id=case.id,
            evidence_id=evidence.id,
            offset_seconds=req.offset_seconds,
            time_zone=req.time_zone,
            calibration_reason=req.calibration_reason,
            calibration_method=req.calibration_method,
            calibrated_by=user_id
        )
        db.add(calib)

    db.commit()
    db.refresh(calib)

    audit = AuditLog(
        case_id=case.id,
        user_id=user_id,
        action="TIMESTAMP_CALIBRATION_SAVED",
        target_identifier=evidence.evidence_identifier,
        details=json.dumps({
            "evidence_identifier": evidence.evidence_identifier,
            "offset_seconds": req.offset_seconds,
            "time_zone": req.time_zone,
            "reason": req.calibration_reason
        })
    )
    db.add(audit)
    db.commit()

    return TimestampCalibrationResponse.model_validate(calib)


# --- Analysis Sessions ---

def save_analysis_session(
    db: Session, case: Case, evidence: Evidence, req: VideoAnalysisSessionCreate, user_id: int
) -> VideoAnalysisSessionResponse:
    """Saves or updates user's persistent analysis playback position and zoom state."""
    session = db.query(VideoAnalysisSession).filter(
        VideoAnalysisSession.case_id == case.id,
        VideoAnalysisSession.evidence_id == evidence.id,
        VideoAnalysisSession.user_id == user_id
    ).first()

    if session:
        session.last_media_time = req.last_media_time
        session.playback_speed = req.playback_speed
        session.timeline_zoom = req.timeline_zoom
    else:
        sess_ident = f"SES-{uuid.uuid4().hex[:6].upper()}"
        session = VideoAnalysisSession(
            session_identifier=sess_ident,
            case_id=case.id,
            evidence_id=evidence.id,
            user_id=user_id,
            last_media_time=req.last_media_time,
            playback_speed=req.playback_speed,
            timeline_zoom=req.timeline_zoom
        )
        db.add(session)

    db.commit()
    db.refresh(session)
    return VideoAnalysisSessionResponse.model_validate(session)
