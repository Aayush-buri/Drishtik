"""Forensic Recovery Models.

Stores recovery scan jobs and carved candidate streams detected in raw
disk/storage images without modifying the source image.
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


class RecoveryCandidateStatus(str, enum.Enum):
    DETECTED = "DETECTED"
    VALIDATED = "VALIDATED"
    RECOVERED = "RECOVERED"
    REJECTED = "REJECTED"
    CORRUPTED = "CORRUPTED"
    PARTIAL = "PARTIAL"


class RecoveryScanStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RecoveryScanJob(Base):
    __tablename__ = "recovery_scan_jobs"

    id = Column(Integer, primary_key=True, index=True)
    scan_identifier = Column(String(32), unique=True, index=True, nullable=False)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    source_evidence_id = Column(Integer, ForeignKey("evidence.id"), nullable=True, index=True)
    source_acquisition_id = Column(Integer, ForeignKey("acquisitions.id"), nullable=True, index=True)
    source_device_id = Column(Integer, ForeignKey("devices.id"), nullable=True, index=True)

    status = Column(SqlEnum(RecoveryScanStatus), default=RecoveryScanStatus.QUEUED, nullable=False)
    bytes_scanned = Column(BigInteger, default=0, nullable=False)
    total_bytes = Column(BigInteger, default=0, nullable=False)
    candidates_found = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    case = relationship("Case")
    source_evidence = relationship("Evidence", foreign_keys=[source_evidence_id])
    candidates = relationship("RecoveryCandidate", back_populates="scan_job", cascade="all, delete-orphan")


class RecoveryCandidate(Base):
    __tablename__ = "recovery_candidates"

    id = Column(Integer, primary_key=True, index=True)
    candidate_identifier = Column(String(32), unique=True, index=True, nullable=False)
    scan_job_id = Column(Integer, ForeignKey("recovery_scan_jobs.id"), nullable=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    source_evidence_id = Column(Integer, ForeignKey("evidence.id"), nullable=True, index=True)
    source_acquisition_id = Column(Integer, ForeignKey("acquisitions.id"), nullable=True, index=True)
    source_device_id = Column(Integer, ForeignKey("devices.id"), nullable=True, index=True)

    source_offset = Column(BigInteger, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    detected_format = Column(String(64), nullable=False)
    vendor = Column(String(64), nullable=False)
    confidence = Column(Float, nullable=False, default=0.0)

    status = Column(SqlEnum(RecoveryCandidateStatus), default=RecoveryCandidateStatus.DETECTED, nullable=False)
    validation_details = Column(Text, nullable=True)
    recovered_evidence_id = Column(Integer, ForeignKey("evidence.id"), nullable=True, index=True)
    metadata_json = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    case = relationship("Case")
    scan_job = relationship("RecoveryScanJob", back_populates="candidates")
    source_evidence = relationship("Evidence", foreign_keys=[source_evidence_id])
    recovered_evidence = relationship("Evidence", foreign_keys=[recovered_evidence_id])
