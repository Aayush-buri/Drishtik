"""AI Video Analysis Service.

Provides:
- Real YOLOv8 object detection (Person, Vehicle, Object)
- Real OpenCV background-subtraction motion detection
- Controlled frame sampling and confidence scoring
- Synchronization with Step 12 TimelineEvent markers
- Derived AI frame export with cryptographic hashes
- Immutability assurance and audit logging
"""
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid

import cv2
import numpy as np
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.evidence import Evidence, EvidenceStatus, IntegrityStatus, ProcessingStatus
from app.models.video_analysis import TimelineEvent, TimelineEventType, TimestampCalibration
from app.models.audit import AuditLog
from app.models.ai_analysis import (
    AIAnalysisJob,
    AIJobStatus,
    AIFinding,
)
from app.services.evidence_service import compute_file_hashes
from app.services.video_processing import extract_frame_image

logger = logging.getLogger(__name__)

# Lazy-loaded YOLO model cache
_yolo_model = None


def get_yolo_model():
    """Lazily loads YOLOv8 model instance."""
    global _yolo_model
    if _yolo_model is None:
        try:
            from ultralytics import YOLO
            _yolo_model = YOLO("yolov8n.pt")
            logger.info("Loaded YOLOv8n object detection model successfully")
        except Exception as e:
            logger.warning("Failed to load YOLOv8n model: %s", str(e))
            _yolo_model = None
    return _yolo_model


def _resolve_playable_path(db: Session, evidence: Evidence) -> Path:
    """Resolves local filepath for video playback / analysis (original or derived proxy)."""
    target = evidence
    if not evidence.is_natively_playable:
        proxy = db.query(Evidence).filter(
            Evidence.parent_evidence_id == evidence.id,
            Evidence.derived_operation == "PROPRIETARY_TRANSMUX_PROXY",
            Evidence.is_deleted == False
        ).first()
        if proxy:
            target = proxy

    path = Path(target.storage_path)
    if not path.is_file():
        path = Path.cwd() / target.storage_path
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Playable video file not found on disk: {target.storage_path}")
    return path


def start_ai_analysis_job(
    db: Session,
    case: Case,
    evidence: Evidence,
    user_id: int,
    sample_rate_fps: float = 1.0,
    confidence_threshold: float = 0.35,
    detect_objects: bool = True,
    detect_motion: bool = True,
) -> Tuple[AIAnalysisJob, List[AIFinding]]:
    """Runs AI analysis (YOLO object detection + OpenCV motion detection) on video evidence."""
    if evidence.case_id != case.id:
        raise HTTPException(status_code=403, detail="Evidence does not belong to specified case")
    if evidence.is_deleted:
        raise HTTPException(status_code=404, detail="Evidence has been deleted")

    video_path = _resolve_playable_path(db, evidence)

    # 1. Create Job record
    job_ident = f"AIJOB-{uuid.uuid4().hex[:6].upper()}"
    config_dict = {
        "sample_rate_fps": sample_rate_fps,
        "confidence_threshold": confidence_threshold,
        "detect_objects": detect_objects,
        "detect_motion": detect_motion,
    }
    job = AIAnalysisJob(
        job_identifier=job_ident,
        case_id=case.id,
        evidence_id=evidence.id,
        status=AIJobStatus.RUNNING,
        progress_percent=0.0,
        total_frames_analyzed=0,
        findings_count=0,
        config_json=json.dumps(config_dict),
        started_at=datetime.now(timezone.utc),
        created_by=user_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Forensic audit log
    audit_start = AuditLog(
        case_id=case.id,
        user_id=user_id,
        action="AI_ANALYSIS_STARTED",
        target_identifier=job_ident,
        details=json.dumps({
            "job_identifier": job_ident,
            "evidence_identifier": evidence.evidence_identifier,
            "config": config_dict,
        }),
    )
    db.add(audit_start)
    db.commit()

    # 2. Check calibration for normalized timestamps
    calib = db.query(TimestampCalibration).filter(
        TimestampCalibration.case_id == case.id,
        TimestampCalibration.evidence_id == evidence.id
    ).first()
    calib_offset = calib.offset_seconds if calib else 0.0

    # 3. Open video stream
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        job.status = AIJobStatus.FAILED
        job.error_message = "Failed to open video file for decoding"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=500, detail="OpenCV failed to open video stream")

    fps = cap.get(cv2.CAP_PROP_FPS) or evidence.fps or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    frame_step = max(1, int(round(fps / max(0.1, sample_rate_fps))))

    findings: List[AIFinding] = []
    fgbg = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=25, detectShadows=False) if detect_motion else None
    model = get_yolo_model() if detect_objects else None

    # Class mappings
    vehicle_classes = {"car", "truck", "bus", "motorcycle", "bicycle"}

    try:
        frame_idx = 0
        analyzed_count = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_step == 0:
                analyzed_count += 1
                media_time = frame_idx / fps
                h, w = frame.shape[:2]

                # Compute CCTV timestamps
                src_ts = None
                norm_ts = None
                if evidence.start_time_osd:
                    src_ts = evidence.start_time_osd + timedelta(seconds=media_time)
                    norm_ts = src_ts + timedelta(seconds=calib_offset)

                # A. YOLO Object Detection
                if model is not None:
                    try:
                        results = model.predict(frame, conf=confidence_threshold, verbose=False)
                        for r in results:
                            for box in r.boxes:
                                cls_id = int(box.cls[0])
                                cls_name = model.names.get(cls_id, f"Class_{cls_id}")
                                conf = float(box.conf[0])
                                xyxy = box.xyxy[0].tolist()  # [x1, y1, x2, y2]

                                # Normalize bbox
                                norm_bbox = {
                                    "x": round(xyxy[0] / w, 4),
                                    "y": round(xyxy[1] / h, 4),
                                    "w": round((xyxy[2] - xyxy[0]) / w, 4),
                                    "h": round((xyxy[3] - xyxy[1]) / h, 4),
                                }

                                # Generalize class for forensic categorisation
                                target_class = cls_name.capitalize()
                                if cls_name.lower() == "person":
                                    category = "Person"
                                elif cls_name.lower() in vehicle_classes:
                                    category = "Vehicle"
                                else:
                                    category = "Object"

                                f_ident = f"AIF-{uuid.uuid4().hex[:6].upper()}"
                                finding = AIFinding(
                                    finding_identifier=f_ident,
                                    job_id=job.id,
                                    case_id=case.id,
                                    evidence_id=evidence.id,
                                    device_id=evidence.device_id,
                                    channel=evidence.channel_index or 1,
                                    media_time=round(media_time, 3),
                                    source_timestamp=src_ts,
                                    normalized_timestamp=norm_ts,
                                    object_class=target_class,
                                    confidence=round(conf, 4),
                                    bounding_box=json.dumps(norm_bbox),
                                    frame_number=frame_idx,
                                    model_name="YOLOv8n",
                                    model_version="8.4.140",
                                    created_by=user_id,
                                )
                                db.add(finding)
                                findings.append(finding)

                                # Create timeline event marker on timeline
                                evt_type = TimelineEventType.PERSON if category == "Person" else (
                                    TimelineEventType.VEHICLE if category == "Vehicle" else TimelineEventType.OBJECT
                                )
                                timeline_evt = TimelineEvent(
                                    event_identifier=f"EVT-AI-{uuid.uuid4().hex[:5].upper()}",
                                    case_id=case.id,
                                    evidence_id=evidence.id,
                                    channel_id=evidence.channel_index or 1,
                                    media_time=round(media_time, 3),
                                    source_timestamp=src_ts,
                                    normalized_timestamp=norm_ts,
                                    event_type=evt_type,
                                    title=f"AI: {target_class} ({int(conf * 100)}%)",
                                    description=f"Automated detection by YOLOv8n (confidence: {conf:.2f}) at frame {frame_idx}",
                                    created_by=user_id,
                                )
                                db.add(timeline_evt)

                    except Exception as yolo_err:
                        logger.warning("YOLO detection error at frame %d: %s", frame_idx, str(yolo_err))

                # B. OpenCV Motion Detection
                if fgbg is not None and frame_idx > 0:
                    try:
                        fgmask = fgbg.apply(frame)
                        # Threshold & find contours
                        _, thresh = cv2.threshold(fgmask, 200, 255, cv2.THRESH_BINARY)
                        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                        # Check for significant motion
                        significant_contours = [c for c in contours if cv2.contourArea(c) > 600]
                        if significant_contours:
                            # Largest moving contour
                            c = max(significant_contours, key=cv2.contourArea)
                            x, y, cw, ch = cv2.boundingRect(c)
                            motion_conf = min(0.99, max(0.40, cv2.contourArea(c) / (w * h * 0.15)))

                            norm_bbox = {
                                "x": round(x / w, 4),
                                "y": round(y / h, 4),
                                "w": round(cw / w, 4),
                                "h": round(ch / h, 4),
                            }

                            f_ident = f"AIF-{uuid.uuid4().hex[:6].upper()}"
                            finding = AIFinding(
                                finding_identifier=f_ident,
                                job_id=job.id,
                                case_id=case.id,
                                evidence_id=evidence.id,
                                device_id=evidence.device_id,
                                channel=evidence.channel_index or 1,
                                media_time=round(media_time, 3),
                                source_timestamp=src_ts,
                                normalized_timestamp=norm_ts,
                                object_class="Motion",
                                confidence=round(motion_conf, 4),
                                bounding_box=json.dumps(norm_bbox),
                                frame_number=frame_idx,
                                model_name="OpenCV-MOG2",
                                model_version="5.0.0",
                                created_by=user_id,
                            )
                            db.add(finding)
                            findings.append(finding)

                            # Timeline marker for motion
                            timeline_evt = TimelineEvent(
                                event_identifier=f"EVT-MOT-{uuid.uuid4().hex[:5].upper()}",
                                case_id=case.id,
                                evidence_id=evidence.id,
                                channel_id=evidence.channel_index or 1,
                                media_time=round(media_time, 3),
                                source_timestamp=src_ts,
                                normalized_timestamp=norm_ts,
                                event_type=TimelineEventType.MOTION,
                                title=f"AI: Motion Detected ({int(motion_conf * 100)}%)",
                                description=f"OpenCV background subtraction motion contour at frame {frame_idx}",
                                created_by=user_id,
                            )
                            db.add(timeline_evt)

                    except Exception as motion_err:
                        logger.warning("Motion detection error at frame %d: %s", frame_idx, str(motion_err))

            frame_idx += 1

        cap.release()

        # Update Job
        job.status = AIJobStatus.COMPLETED
        job.progress_percent = 100.0
        job.total_frames_analyzed = analyzed_count
        job.findings_count = len(findings)
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        # Audit log completion
        audit_end = AuditLog(
            case_id=case.id,
            user_id=user_id,
            action="AI_ANALYSIS_COMPLETED",
            target_identifier=job_ident,
            details=json.dumps({
                "job_identifier": job_ident,
                "evidence_identifier": evidence.evidence_identifier,
                "total_frames_analyzed": analyzed_count,
                "findings_count": len(findings),
            }),
        )
        db.add(audit_end)
        db.commit()

        logger.info("AI Analysis completed for %s: %d findings", evidence.evidence_identifier, len(findings))
        return job, findings

    except Exception as e:
        cap.release()
        job.status = AIJobStatus.FAILED
        job.error_message = str(e)
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        audit_fail = AuditLog(
            case_id=case.id,
            user_id=user_id,
            action="AI_ANALYSIS_FAILED",
            target_identifier=job_ident,
            details=json.dumps({"error": str(e)}),
        )
        db.add(audit_fail)
        db.commit()

        logger.error("AI Analysis failed for %s: %s", evidence.evidence_identifier, str(e))
        raise HTTPException(status_code=500, detail=f"AI Analysis failed: {str(e)}")


def list_ai_findings(
    db: Session,
    case: Case,
    evidence_id: int,
    object_class: Optional[str] = None,
    min_confidence: Optional[float] = None,
    channel: Optional[int] = None,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
) -> List[AIFinding]:
    """Queries AI findings with filtering options."""
    query = db.query(AIFinding).filter(
        AIFinding.case_id == case.id,
        AIFinding.evidence_id == evidence_id
    )
    if object_class:
        query = query.filter(AIFinding.object_class.ilike(f"%{object_class.strip()}%"))
    if min_confidence is not None:
        query = query.filter(AIFinding.confidence >= min_confidence)
    if channel is not None:
        query = query.filter(AIFinding.channel == channel)
    if start_time is not None:
        query = query.filter(AIFinding.media_time >= start_time)
    if end_time is not None:
        query = query.filter(AIFinding.media_time <= end_time)

    return query.order_by(AIFinding.media_time.asc()).all()


def export_ai_frame(
    db: Session,
    case: Case,
    finding_id: int,
    user_id: int,
) -> Tuple[AIFinding, Evidence]:
    """Exports the exact video frame of an AI finding as a new DERIVED Evidence artifact."""
    finding = db.query(AIFinding).filter(
        AIFinding.id == finding_id,
        AIFinding.case_id == case.id
    ).first()
    if not finding:
        raise HTTPException(status_code=404, detail="AI finding not found")

    evidence = db.query(Evidence).filter(Evidence.id == finding.evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Parent evidence not found")

    video_path = _resolve_playable_path(db, evidence)

    # Frame output destination
    derived_dir = Path("data") / "case_data" / case.case_identifier / "evidence" / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)
    frame_ident = f"EVD-{uuid.uuid4().hex[:6].upper()}"
    filename = f"ai_{finding.object_class.lower()}_{finding.finding_identifier}_{frame_ident}.jpg"
    out_path = derived_dir / filename

    # Extract frame
    extract_frame_image(str(video_path), str(out_path), float(finding.media_time))
    if not out_path.is_file() or out_path.stat().st_size == 0:
        raise HTTPException(status_code=500, detail="Failed to extract frame image from video")

    frame_sha, frame_md5 = compute_file_hashes(out_path)
    frame_size = out_path.stat().st_size

    # Create new DERIVED evidence artifact
    derived_ev = Evidence(
        case_id=case.id,
        evidence_identifier=frame_ident,
        original_filename=filename,
        storage_path=str(out_path),
        source_type="AI_FINDING_FRAME",
        media_type="Image",
        file_extension=".jpg",
        size_bytes=frame_size,
        sha256=frame_sha,
        md5_reference=frame_md5,
        stored_sha256=frame_sha,
        integrity_status=IntegrityStatus.VERIFIED,
        processing_status=ProcessingStatus.COMPLETED,
        evidence_status=EvidenceStatus.DERIVED,
        parent_evidence_id=evidence.id,
        device_id=finding.device_id or evidence.device_id,
        channel_index=finding.channel,
        derived_operation="AI_FRAME_EXPORT",
        derived_parameters=json.dumps({
            "finding_identifier": finding.finding_identifier,
            "object_class": finding.object_class,
            "confidence": finding.confidence,
            "media_time": finding.media_time,
            "frame_number": finding.frame_number,
        }),
        is_natively_playable=True,
        imported_by=user_id,
    )
    db.add(derived_ev)
    db.commit()
    db.refresh(derived_ev)

    # Audit log
    audit = AuditLog(
        case_id=case.id,
        user_id=user_id,
        action="AI_FRAME_EXPORTED",
        target_identifier=frame_ident,
        details=json.dumps({
            "derived_evidence_identifier": frame_ident,
            "parent_evidence_identifier": evidence.evidence_identifier,
            "finding_identifier": finding.finding_identifier,
            "object_class": finding.object_class,
            "media_time": finding.media_time,
            "sha256": frame_sha,
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
            evidence=derived_ev,
            action="AI_FRAME_EXPORTED",
            user_id=user_id,
            username=uname,
            audit_log_id=audit.id,
            metadata={
                "parent_evidence": evidence.evidence_identifier,
                "finding_identifier": finding.finding_identifier,
                "object_class": finding.object_class,
                "media_time": finding.media_time
            }
        )
    except Exception as e:
        logger.warning("Failed to anchor AI frame export on blockchain: %s", e)

    logger.info("AI_FRAME_EXPORTED: Frame %s exported from finding %s", frame_ident, finding.finding_identifier)
    return finding, derived_ev


def cancel_job(
    db: Session,
    case: Case,
    job_id: int,
    user_id: int,
) -> AIAnalysisJob:
    """Cancels a queued or running AI analysis job."""
    job = db.query(AIAnalysisJob).filter(
        AIAnalysisJob.id == job_id,
        AIAnalysisJob.case_id == case.id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="AI job not found")

    job.status = AIJobStatus.CANCELLED
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)

    audit = AuditLog(
        case_id=case.id,
        user_id=user_id,
        action="AI_ANALYSIS_CANCELLED",
        target_identifier=job.job_identifier,
        details=json.dumps({"job_identifier": job.job_identifier}),
    )
    db.add(audit)
    db.commit()
    return job


def list_ai_jobs(
    db: Session,
    case: Case,
    evidence_id: Optional[int] = None,
) -> List[AIAnalysisJob]:
    """Lists AI analysis jobs for a case / evidence."""
    query = db.query(AIAnalysisJob).filter(AIAnalysisJob.case_id == case.id)
    if evidence_id:
        query = query.filter(AIAnalysisJob.evidence_id == evidence_id)
    return query.order_by(AIAnalysisJob.created_at.desc()).all()


def sync_finding_to_timeline(
    db: Session,
    case: Case,
    finding: AIFinding,
) -> TimelineEvent:
    """Creates a Step 12 TimelineEvent corresponding to an AI finding."""
    cat = finding.object_class.lower()
    if cat == "person":
        evt_type = TimelineEventType.PERSON
    elif cat in ("car", "truck", "bus", "motorcycle", "vehicle"):
        evt_type = TimelineEventType.VEHICLE
    elif cat == "motion":
        evt_type = TimelineEventType.MOTION
    else:
        evt_type = TimelineEventType.OBJECT

    timeline_evt = TimelineEvent(
        event_identifier=f"EVT-AI-{uuid.uuid4().hex[:5].upper()}",
        case_id=case.id,
        evidence_id=finding.evidence_id,
        channel_id=finding.channel,
        media_time=round(finding.media_time, 3),
        source_timestamp=finding.source_timestamp,
        normalized_timestamp=finding.normalized_timestamp,
        event_type=evt_type,
        title=f"AI: {finding.object_class.capitalize()} ({int(finding.confidence * 100)}%)",
        description=f"Detection by {finding.model_name} (confidence: {finding.confidence:.2f}) at frame {finding.frame_number}",
        created_by=finding.created_by,
    )
    db.add(timeline_evt)
    db.commit()
    db.refresh(timeline_evt)
    return timeline_evt


