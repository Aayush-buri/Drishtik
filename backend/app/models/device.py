import enum
from sqlalchemy import Column, Integer, String, Enum, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class DeviceType(str, enum.Enum):
    DVR = "DVR"
    NVR = "NVR"
    INTERNAL_HDD = "INTERNAL_HDD"
    EXTERNAL_STORAGE = "EXTERNAL_STORAGE"
    DISK_IMAGE = "DISK_IMAGE"
    OTHER = "OTHER"

class DeviceStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ACQUIRED = "ACQUIRED"
    ARCHIVED = "ARCHIVED"

class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_identifier = Column(String(32), unique=True, index=True, nullable=False)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)

    device_type = Column(Enum(DeviceType), default=DeviceType.DVR, nullable=False)
    manufacturer = Column(String(100), default="Unknown", nullable=True)
    model = Column(String(100), nullable=True)
    serial_number = Column(String(100), nullable=True)
    firmware_version = Column(String(100), nullable=True)

    ip_address = Column(String(100), nullable=True)
    mac_address = Column(String(100), nullable=True)

    storage_capacity = Column(String(50), nullable=True)
    channel_count = Column(Integer, nullable=True)

    location = Column(String(255), nullable=True)
    notes = Column(String(2000), nullable=True)
    source_root = Column(String(500), nullable=True)

    status = Column(Enum(DeviceStatus), default=DeviceStatus.ACTIVE, nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    case = relationship("Case", backref="devices")
    creator = relationship("User", foreign_keys=[created_by])
    acquisitions = relationship("Acquisition", back_populates="device", cascade="all, delete-orphan")
