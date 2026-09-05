import enum
from sqlalchemy import Column, Integer, String, BigInteger, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class BlockchainAnchorStatus(str, enum.Enum):
    ANCHORED = "ANCHORED"
    PENDING = "PENDING"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"

class CustodyVerificationStatus(str, enum.Enum):
    VERIFIED = "VERIFIED"
    MISMATCH = "MISMATCH"
    UNVERIFIED = "UNVERIFIED"

class CustodyEvent(Base):
    __tablename__ = "custody_events"

    id = Column(Integer, primary_key=True, index=True)
    event_identifier = Column(String(32), unique=True, index=True, nullable=False)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    audit_log_id = Column(Integer, ForeignKey("audit_logs.id", ondelete="SET NULL"), nullable=True, index=True)

    action = Column(String(64), nullable=False, index=True)  # e.g. EVIDENCE_IMPORTED, EVIDENCE_DERIVED, etc.
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    actor_username = Column(String(100), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    sha256 = Column(String(64), nullable=False)
    previous_event_reference = Column(String(64), nullable=True)  # hash/identifier of previous event in custody chain

    # Blockchain Anchor Linkage
    blockchain_tx_id = Column(String(128), nullable=True, index=True)
    blockchain_status = Column(String(32), default="NOT_ANCHORED", nullable=False)  # ANCHORED, NOT_ANCHORED, UNAVAILABLE, FAILED
    blockchain_anchored_at = Column(DateTime(timezone=True), nullable=True)
    blockchain_block_number = Column(BigInteger, nullable=True)
    metadata_hash = Column(String(64), nullable=True)

    # Verification State
    verification_status = Column(String(32), default="UNVERIFIED", nullable=False)  # VERIFIED, MISMATCH, UNVERIFIED
    verification_notes = Column(Text, nullable=True)
    last_verified_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    case = relationship("Case", backref="custody_events")
    evidence = relationship("Evidence", backref="custody_events")
    actor = relationship("User", foreign_keys=[actor_id])
    audit_log = relationship("AuditLog", foreign_keys=[audit_log_id])

class BlockchainAnchor(Base):
    __tablename__ = "blockchain_anchors"

    id = Column(Integer, primary_key=True, index=True)
    anchor_identifier = Column(String(32), unique=True, index=True, nullable=False)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id", ondelete="CASCADE"), nullable=False, index=True)
    custody_event_id = Column(Integer, ForeignKey("custody_events.id", ondelete="SET NULL"), nullable=True, index=True)

    sha256 = Column(String(64), nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    actor = Column(String(100), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    source = Column(String(128), nullable=False)
    metadata_hash = Column(String(64), nullable=False)

    transaction_id = Column(String(128), unique=True, index=True, nullable=True)
    block_number = Column(BigInteger, nullable=True)
    channel_name = Column(String(64), nullable=True)
    chaincode_name = Column(String(64), nullable=True)
    status = Column(String(32), nullable=False, default="PENDING")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    case = relationship("Case", backref="blockchain_anchors")
    evidence = relationship("Evidence", backref="blockchain_anchors")
    custody_event = relationship("CustodyEvent", backref="anchors", foreign_keys=[custody_event_id])
