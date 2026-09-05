import enum
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class ReportType(str, enum.Enum):
    CASE_SUMMARY = "CASE_SUMMARY"
    EVIDENCE_REPORT = "EVIDENCE_REPORT"
    VIDEO_SUMMARY = "VIDEO_SUMMARY"
    RECOVERY_REPORT = "RECOVERY_REPORT"
    AI_REPORT = "AI_REPORT"
    CHAIN_OF_CUSTODY = "CHAIN_OF_CUSTODY"


class ReportStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"
    FINAL = "FINAL"


class ReportFormat(str, enum.Enum):
    PDF = "PDF"
    HTML = "HTML"
    JSON = "JSON"


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    report_identifier = Column(String(32), unique=True, index=True, nullable=False)  # e.g. RPT-XXXXXX
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)

    report_type = Column(String(32), nullable=False, index=True)  # CASE_SUMMARY, EVIDENCE_REPORT, etc.
    title = Column(String(255), nullable=False)
    status = Column(String(32), default=ReportStatus.GENERATED.value, nullable=False)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    generated_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    format = Column(String(16), default="PDF", nullable=False)  # PDF, HTML, JSON
    file_size = Column(Integer, default=0, nullable=False)
    storage_path = Column(String(512), nullable=True)

    # Forensic Integrity Hash
    sha256 = Column(String(64), nullable=False, index=True)

    # Examiner Notes & Forensic Findings (No AI conclusions)
    examiner_notes = Column(Text, nullable=True)

    # Structured Canonical JSON Payload
    data_payload = Column(JSON, nullable=True)

    # Blockchain Status & Transaction Reference
    blockchain_status = Column(String(32), default="UNAVAILABLE", nullable=False)
    blockchain_tx_id = Column(String(128), nullable=True, index=True)
    blockchain_anchored_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    case = relationship("Case", backref="reports")
    creator = relationship("User", foreign_keys=[created_by])
    generator = relationship("User", foreign_keys=[generated_by])
