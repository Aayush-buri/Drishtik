"""Forensic Video Analysis API Endpoints.

Provides REST endpoints for:
- Unified Video Representation across CCTV sources
- Multi-camera synchronized tracks
- Derived frame export
- Timeline event markers (CRUD)
- Investigator notes (CRUD)
- Timestamp calibration / normalization
- User analysis session state
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.case import CaseMember
from app.models.evidence import Evidence
from app.dependencies.auth import (
    require_case_member,
    require_case_investigator_or_admin,
)
from app.schemas.video_analysis import (
    UnifiedVideoResponse,
    CameraTrackResponse,
    FrameExportRequest,
    FrameExportResponse,
    TimelineEventCreate,
    TimelineEventResponse,
    AnalysisNoteCreate,
    AnalysisNoteResponse,
    TimestampCalibrationCreate,
    TimestampCalibrationResponse,
    VideoAnalysisSessionCreate,
    VideoAnalysisSessionResponse,
)
from app.services import video_analysis_service

router = APIRouter()


def _get_evidence_or_404(db: Session, case_id: int, evidence_id: int) -> Evidence:
    evidence = db.query(Evidence).filter(
        Evidence.case_id == case_id,
        Evidence.id == evidence_id,
        Evidence.is_deleted == False
    ).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found or has been removed")
    return evidence


@router.get("/{case_identifier}/evidence/{evidence_id}/unified-video", response_model=UnifiedVideoResponse)
def get_unified_video_endpoint(
    case_identifier: str,
    evidence_id: int,
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db)
):
    evidence = _get_evidence_or_404(db, member.case.id, evidence_id)
    return video_analysis_service.get_unified_video_representation(
        db, member.case, evidence, member.user_id
    )


@router.get("/{case_identifier}/evidence/{evidence_id}/multi-camera-tracks", response_model=List[CameraTrackResponse])
def get_multi_camera_tracks_endpoint(
    case_identifier: str,
    evidence_id: int,
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db)
):
    evidence = _get_evidence_or_404(db, member.case.id, evidence_id)
    return video_analysis_service.get_multi_camera_tracks(
        db, member.case, evidence
    )


@router.post("/{case_identifier}/evidence/{evidence_id}/export-frame", response_model=FrameExportResponse)
def export_frame_endpoint(
    case_identifier: str,
    evidence_id: int,
    request: FrameExportRequest,
    member: CaseMember = Depends(require_case_investigator_or_admin),
    db: Session = Depends(get_db)
):
    evidence = _get_evidence_or_404(db, member.case.id, evidence_id)
    return video_analysis_service.export_frame(
        db, member.case, evidence, request, member.user_id
    )


@router.get("/{case_identifier}/evidence/{evidence_id}/timeline-events", response_model=List[TimelineEventResponse])
def list_timeline_events_endpoint(
    case_identifier: str,
    evidence_id: int,
    q: Optional[str] = Query(None, description="Search query across event title/description/type"),
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db)
):
    evidence = _get_evidence_or_404(db, member.case.id, evidence_id)
    return video_analysis_service.list_timeline_events(
        db, member.case, evidence, search_query=q
    )


@router.post("/{case_identifier}/evidence/{evidence_id}/timeline-events", response_model=TimelineEventResponse)
def create_timeline_event_endpoint(
    case_identifier: str,
    evidence_id: int,
    request: TimelineEventCreate,
    member: CaseMember = Depends(require_case_investigator_or_admin),
    db: Session = Depends(get_db)
):
    evidence = _get_evidence_or_404(db, member.case.id, evidence_id)
    return video_analysis_service.create_timeline_event(
        db, member.case, evidence, request, member.user_id
    )


@router.delete("/{case_identifier}/timeline-events/{event_id}")
def delete_timeline_event_endpoint(
    case_identifier: str,
    event_id: int,
    member: CaseMember = Depends(require_case_investigator_or_admin),
    db: Session = Depends(get_db)
):
    return video_analysis_service.delete_timeline_event(
        db, member.case, event_id, member.user_id
    )


@router.get("/{case_identifier}/evidence/{evidence_id}/analysis-notes", response_model=List[AnalysisNoteResponse])
def list_analysis_notes_endpoint(
    case_identifier: str,
    evidence_id: int,
    q: Optional[str] = Query(None, description="Search query across note text"),
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db)
):
    evidence = _get_evidence_or_404(db, member.case.id, evidence_id)
    return video_analysis_service.list_analysis_notes(
        db, member.case, evidence, search_query=q
    )


@router.post("/{case_identifier}/evidence/{evidence_id}/analysis-notes", response_model=AnalysisNoteResponse)
def create_analysis_note_endpoint(
    case_identifier: str,
    evidence_id: int,
    request: AnalysisNoteCreate,
    member: CaseMember = Depends(require_case_investigator_or_admin),
    db: Session = Depends(get_db)
):
    evidence = _get_evidence_or_404(db, member.case.id, evidence_id)
    return video_analysis_service.create_analysis_note(
        db, member.case, evidence, request, member.user_id
    )


@router.delete("/{case_identifier}/analysis-notes/{note_id}")
def delete_analysis_note_endpoint(
    case_identifier: str,
    note_id: int,
    member: CaseMember = Depends(require_case_investigator_or_admin),
    db: Session = Depends(get_db)
):
    return video_analysis_service.delete_analysis_note(
        db, member.case, note_id, member.user_id
    )


@router.get("/{case_identifier}/evidence/{evidence_id}/calibration", response_model=Optional[TimestampCalibrationResponse])
def get_calibration_endpoint(
    case_identifier: str,
    evidence_id: int,
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db)
):
    evidence = _get_evidence_or_404(db, member.case.id, evidence_id)
    return video_analysis_service.get_calibration(
        db, member.case, evidence
    )


@router.post("/{case_identifier}/evidence/{evidence_id}/calibration", response_model=TimestampCalibrationResponse)
def set_calibration_endpoint(
    case_identifier: str,
    evidence_id: int,
    request: TimestampCalibrationCreate,
    member: CaseMember = Depends(require_case_investigator_or_admin),
    db: Session = Depends(get_db)
):
    evidence = _get_evidence_or_404(db, member.case.id, evidence_id)
    return video_analysis_service.set_calibration(
        db, member.case, evidence, request, member.user_id
    )


@router.post("/{case_identifier}/evidence/{evidence_id}/sessions", response_model=VideoAnalysisSessionResponse)
def save_session_endpoint(
    case_identifier: str,
    evidence_id: int,
    request: VideoAnalysisSessionCreate,
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db)
):
    evidence = _get_evidence_or_404(db, member.case.id, evidence_id)
    return video_analysis_service.save_analysis_session(
        db, member.case, evidence, request, member.user_id
    )
