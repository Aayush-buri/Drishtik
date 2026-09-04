import enum
from sqlalchemy import Column, Integer, BigInteger, String, Enum, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class AcquisitionMethod(str, enum.Enum):
    FILE_COPY = "FILE_COPY"
    DIRECTORY_COPY = "DIRECTORY_COPY"
    DISK_IMAGE = "DISK_IMAGE"
    EXPORTED_VIDEO = "EXPORTED_VIDEO"
    LOGICAL_ACQUISITION = "LOGICAL_ACQUISITION"
    OTHER = "OTHER"

class AcquisitionStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class Acquisition(Base):
    __tablename__ = "acquisitions"

    id = Column(Integer, primary_key=True, index=True)
    acquisition_identifier = Column(String(32), unique=True, index=True, nullable=False)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)

    acquisition_method = Column(Enum(AcquisitionMethod), default=AcquisitionMethod.FILE_COPY, nullable=False)
    source_path = Column(String(500), nullable=False)
    destination_reference = Column(String(500), nullable=False)

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    status = Column(Enum(AcquisitionStatus), default=AcquisitionStatus.PENDING, nullable=False, index=True)
    progress = Column(Integer, default=0, nullable=False)

    operator_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    source_sha256 = Column(String(64), nullable=True)
    destination_sha256 = Column(String(64), nullable=True)
    source_md5 = Column(String(32), nullable=True)
    destination_md5 = Column(String(32), nullable=True)

    size_bytes = Column(BigInteger, nullable=True)
    notes = Column(String(2000), nullable=True)
    error_message = Column(String(2000), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    case = relationship("Case", backref="acquisitions")
    device = relationship("Device", back_populates="acquisitions")
    operator = relationship("User", foreign_keys=[operator_id])
    evidence = relationship("Evidence", back_populates="acquisition")
