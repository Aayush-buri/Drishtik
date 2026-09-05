"""AI Video Analysis Models.

Stores AI analysis jobs and detected findings (person, vehicle, object, motion)
linked to exact video timestamps, confidence scores, and bounding boxes.
"""
from datetime import datetime, timezone
import enum
from sqlalchemy import (
    Column,
    Integer,
    String,
    BigInteger,
    Float,
    Text,
    DateTime,
    ForeignKey,
    Enum as SqlEnum,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class AIJobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AIAnalysisJob(Base):
    __tablename__ = "ai_analysis_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_identifier = Column(String(32), unique=True, index=True, nullable=False)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id"), nullable=False, index=True)

    status = Column(SqlEnum(AIJobStatus), default=AIJobStatus.QUEUED, nullable=False)
    progress_percent = Column(Float, default=0.0, nullable=False)
    total_frames_analyzed = Column(Integer, default=0, nullable=False)
    findings_count = Column(Integer, default=0, nullable=False)
    config_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    case = relationship("Case")
    evidence = relationship("Evidence")
    findings = relationship("AIFinding", back_populates="job", cascade="all, delete-orphan")


class AIFinding(Base):
    __tablename__ = "ai_findings"

    id = Column(Integer, primary_key=True, index=True)
    finding_identifier = Column(String(32), unique=True, index=True, nullable=False)
    job_id = Column(Integer, ForeignKey("ai_analysis_jobs.id"), nullable=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id"), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True, index=True)

    channel = Column(Integer, default=1, nullable=False)
    media_time = Column(Float, nullable=False)
    source_timestamp = Column(DateTime(timezone=True), nullable=True)
    normalized_timestamp = Column(DateTime(timezone=True), nullable=True)

    object_class = Column(String(64), nullable=False, index=True)
    confidence = Column(Float, nullable=False)
    bounding_box = Column(Text, nullable=True)  # JSON string: {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4}
    frame_number = Column(Integer, default=0, nullable=False)

    model_name = Column(String(64), default="YOLOv8n", nullable=False)
    model_version = Column(String(32), default="8.4.140", nullable=False)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    case = relationship("Case")
    evidence = relationship("Evidence")
    job = relationship("AIAnalysisJob", back_populates="findings")
