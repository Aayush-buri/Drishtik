"""Database models for forensic video analysis, timeline events, investigator notes,
timestamp calibrations, and analysis sessions.
"""
import enum
from sqlalchemy import (
    Column, Integer, String, Float, ForeignKey, DateTime, Text, Enum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class TimelineEventType(str, enum.Enum):
    OBSERVATION = "Observation"
    PERSON = "Person"
    VEHICLE = "Vehicle"
    OBJECT = "Object"
    MOTION = "Motion"
    ENTRY = "Entry"
    EXIT = "Exit"
    INCIDENT = "Incident"
    OTHER = "Other"


class TimelineEvent(Base):
    """Forensic timeline event marker linked to exact media time and CCTV timestamps."""
    __tablename__ = "timeline_events"

    id = Column(Integer, primary_key=True, index=True)
    event_identifier = Column(String(32), unique=True, index=True, nullable=False)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    channel_id = Column(Integer, nullable=True)

    media_time = Column(Float, nullable=False, default=0.0)  # In seconds within video
    source_timestamp = Column(DateTime(timezone=True), nullable=True)  # Embedded CCTV OSD
    normalized_timestamp = Column(DateTime(timezone=True), nullable=True)  # Calibrated/adjusted

    event_type = Column(Enum(TimelineEventType), default=TimelineEventType.OBSERVATION, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    case = relationship("Case", backref="timeline_events")
    evidence = relationship("Evidence", backref="timeline_events")
    creator = relationship("User", foreign_keys=[created_by])


class AnalysisNote(Base):
    """Investigator note linked to a specific media playback timestamp."""
    __tablename__ = "analysis_notes"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True)

    media_time = Column(Float, nullable=False, default=0.0)
    source_timestamp = Column(DateTime(timezone=True), nullable=True)
    normalized_timestamp = Column(DateTime(timezone=True), nullable=True)

    note_text = Column(Text, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    case = relationship("Case", backref="analysis_notes")
    evidence = relationship("Evidence", backref="analysis_notes")
    creator = relationship("User", foreign_keys=[created_by])


class TimestampCalibration(Base):
    """Clock offset and timezone calibration for forensic timestamp normalization."""
    __tablename__ = "timestamp_calibrations"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    offset_seconds = Column(Float, default=0.0, nullable=False)  # e.g. +192.0 (+3m12s drift)
    time_zone = Column(String(50), default="UTC", nullable=False)
    calibration_reason = Column(Text, nullable=True)  # e.g. "Compared against verified GPS/NTP reference"
    calibration_method = Column(String(100), default="MANUAL_CALIBRATION", nullable=False)

    calibrated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    case = relationship("Case", backref="timestamp_calibrations")
    evidence = relationship("Evidence", backref="timestamp_calibration")
    calibrator = relationship("User", foreign_keys=[calibrated_by])


class VideoAnalysisSession(Base):
    """Persistent analysis session state for an evidence item."""
    __tablename__ = "video_analysis_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_identifier = Column(String(32), unique=True, index=True, nullable=False)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    last_media_time = Column(Float, default=0.0, nullable=False)
    playback_speed = Column(Float, default=1.0, nullable=False)
    timeline_zoom = Column(Float, default=1.0, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    case = relationship("Case", backref="analysis_sessions")
    evidence = relationship("Evidence", backref="analysis_sessions")
    user = relationship("User", foreign_keys=[user_id])
