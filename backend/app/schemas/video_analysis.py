"""Pydantic schemas for forensic video analysis, timeline events, notes,
timestamp calibration, and frame export.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict
from app.models.video_analysis import TimelineEventType


class TimelineEventCreate(BaseModel):
    media_time: float
    source_timestamp: Optional[datetime] = None
    normalized_timestamp: Optional[datetime] = None
    event_type: TimelineEventType = TimelineEventType.OBSERVATION
    title: str
    description: Optional[str] = None
    channel_id: Optional[int] = None


class TimelineEventResponse(BaseModel):
    id: int
    event_identifier: str
    case_id: int
    evidence_id: int
    channel_id: Optional[int] = None
    media_time: float
    source_timestamp: Optional[datetime] = None
    normalized_timestamp: Optional[datetime] = None
    event_type: TimelineEventType
    title: str
    description: Optional[str] = None
    created_by: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnalysisNoteCreate(BaseModel):
    media_time: float
    source_timestamp: Optional[datetime] = None
    normalized_timestamp: Optional[datetime] = None
    note_text: str


class AnalysisNoteResponse(BaseModel):
    id: int
    case_id: int
    evidence_id: int
    media_time: float
    source_timestamp: Optional[datetime] = None
    normalized_timestamp: Optional[datetime] = None
    note_text: str
    created_by: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimestampCalibrationCreate(BaseModel):
    offset_seconds: float = 0.0
    time_zone: str = "UTC"
    calibration_reason: Optional[str] = None
    calibration_method: str = "MANUAL_CALIBRATION"


class TimestampCalibrationResponse(BaseModel):
    id: int
    case_id: int
    evidence_id: int
    offset_seconds: float
    time_zone: str
    calibration_reason: Optional[str] = None
    calibration_method: str
    calibrated_by: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class FrameExportRequest(BaseModel):
    media_time: float
    frame_number: Optional[int] = None
    notes: Optional[str] = None


class FrameExportResponse(BaseModel):
    evidence_id: int
    evidence_identifier: str
    original_filename: str
    parent_evidence_id: int
    parent_evidence_identifier: str
    evidence_status: str
    derived_operation: str
    media_type: str
    file_extension: str
    size_bytes: int
    sha256: str
    md5_reference: str
    media_time: float
    frame_number: Optional[int] = None
    source_timestamp: Optional[datetime] = None
    created_at: datetime


class CameraTrackResponse(BaseModel):
    channel_number: int
    channel_name: str
    evidence_id: int
    evidence_identifier: str
    original_filename: str
    vendor: str
    duration_seconds: Optional[float] = None
    source_start_time: Optional[datetime] = None
    source_end_time: Optional[datetime] = None
    browser_playable: bool
    playback_source: Optional[str] = None
    is_active: bool = False
    offset_from_master_seconds: float = 0.0


class UnifiedVideoResponse(BaseModel):
    evidence_id: int
    evidence_identifier: str
    original_filename: str
    source_device_identifier: Optional[str] = None
    acquisition_identifier: Optional[str] = None
    vendor: str
    container_format: str
    is_proprietary: bool

    channel_number: Optional[int] = 1
    channel_name: str = "CAM 01"
    source_start_time: Optional[datetime] = None
    source_end_time: Optional[datetime] = None
    timezone: str = "UTC"
    timestamp_confidence: float = 1.0
    has_discontinuous_timestamps: bool = False

    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    bitrate_kbps: Optional[int] = None

    browser_playable: bool
    proxy_available: bool
    playback_source: Optional[str] = None
    parent_evidence_identifier: Optional[str] = None
    is_inspection_proxy: bool = False

    is_calibrated: bool = False
    offset_seconds: float = 0.0
    calibration_reason: Optional[str] = None

    sha256: Optional[str] = None
    md5_reference: Optional[str] = None

    camera_tracks: List[CameraTrackResponse] = []


class VideoAnalysisSessionCreate(BaseModel):
    last_media_time: float = 0.0
    playback_speed: float = 1.0
    timeline_zoom: float = 1.0


class VideoAnalysisSessionResponse(BaseModel):
    id: int
    session_identifier: str
    case_id: int
    evidence_id: int
    user_id: int
    last_media_time: float
    playback_speed: float
    timeline_zoom: float
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
