import enum
from sqlalchemy import Column, Integer, String, BigInteger, Float, Boolean, Enum, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class IntegrityStatus(str, enum.Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    MISMATCH = "MISMATCH"

class ProcessingStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class EvidenceStatus(str, enum.Enum):
    ORIGINAL = "ORIGINAL"
    DERIVED = "DERIVED"
    RECOVERED = "RECOVERED"
    PARTIAL = "PARTIAL"

class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    evidence_identifier = Column(String, unique=True, index=True, nullable=False)
    original_filename = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)
    source_type = Column(String, nullable=False)
    media_type = Column(String, nullable=False)
    file_extension = Column(String, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    
    sha256 = Column(String, nullable=True)
    md5_reference = Column(String, nullable=True)
    source_sha256 = Column(String, nullable=True)
    stored_sha256 = Column(String, nullable=True)
    
    integrity_status = Column(Enum(IntegrityStatus), default=IntegrityStatus.UNVERIFIED, nullable=False)
    processing_status = Column(Enum(ProcessingStatus), default=ProcessingStatus.PENDING, nullable=False)
    evidence_status = Column(Enum(EvidenceStatus), default=EvidenceStatus.ORIGINAL, nullable=False)
    
    # Blockchain Integrity Anchoring
    blockchain_status = Column(String(32), default="NOT_ANCHORED", nullable=False)
    blockchain_tx_id = Column(String(128), nullable=True, index=True)
    blockchain_anchored_at = Column(DateTime(timezone=True), nullable=True)
    
    # Lineage & Derivation
    parent_evidence_id = Column(Integer, ForeignKey("evidence.id"), nullable=True, index=True)
    derived_operation = Column(String, nullable=True)
    derived_parameters = Column(String, nullable=True)

    # Device & Forensic Acquisition Provenance
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True, index=True)
    acquisition_id = Column(Integer, ForeignKey("acquisitions.id"), nullable=True, index=True)

    # Technical Media Metadata
    duration_seconds = Column(Float, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    fps = Column(Float, nullable=True)
    video_codec = Column(String, nullable=True)
    audio_codec = Column(String, nullable=True)
    container = Column(String, nullable=True)
    bitrate_kbps = Column(Integer, nullable=True)

    # Vendor & CCTV Container Metadata
    vendor = Column(String(100), nullable=True)
    proprietary_format = Column(String(50), nullable=True)
    channel_index = Column(Integer, nullable=True)
    start_time_osd = Column(DateTime(timezone=True), nullable=True)
    end_time_osd = Column(DateTime(timezone=True), nullable=True)
    is_natively_playable = Column(Boolean, default=True, nullable=False)

    # Soft Delete / Retention
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    deletion_reason = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    imported_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    case = relationship("Case", backref="evidence")
    importer = relationship("User", foreign_keys=[imported_by])
    parent = relationship("Evidence", remote_side=[id], backref="children")
    deleter = relationship("User", foreign_keys=[deleted_by])
    device = relationship("Device", backref="evidence")
    acquisition = relationship("Acquisition", back_populates="evidence")
