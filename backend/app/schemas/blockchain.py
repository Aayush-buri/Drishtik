from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict

class BlockchainHealthResponse(BaseModel):
    available: bool
    status: str
    network: str
    peer_endpoint: Optional[str] = None
    channel: Optional[str] = None
    chaincode: Optional[str] = None
    msp_id: Optional[str] = None
    current_block: Optional[int] = None
    total_anchors: Optional[int] = None
    message: str

    model_config = ConfigDict(from_attributes=True)

class CustodyEventResponse(BaseModel):
    id: int
    event_identifier: str
    case_id: int
    evidence_id: int
    action: str
    actor_id: int
    actor_username: str
    timestamp: datetime
    sha256: str
    previous_event_reference: Optional[str] = None
    blockchain_tx_id: Optional[str] = None
    blockchain_status: str
    blockchain_anchored_at: Optional[datetime] = None
    blockchain_block_number: Optional[int] = None
    verification_status: str
    verification_notes: Optional[str] = None
    last_verified_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class BlockchainAnchorResponse(BaseModel):
    anchor_identifier: str
    event_type: str
    transaction_id: Optional[str] = None
    block_number: Optional[int] = None
    status: str
    timestamp: datetime
    metadata_hash: str

    model_config = ConfigDict(from_attributes=True)

class EvidenceBlockchainStatusResponse(BaseModel):
    evidence_identifier: str
    sha256: Optional[str] = None
    md5: Optional[str] = None
    integrity_status: str
    blockchain_status: str
    transaction_id: Optional[str] = None
    anchored_at: Optional[str] = None
    service_status: str
    anchors: List[BlockchainAnchorResponse] = []
    custody_events: List[Dict[str, Any]] = []

    model_config = ConfigDict(from_attributes=True)

class BlockchainVerificationResponse(BaseModel):
    evidence_identifier: str
    overall_status: str  # "VERIFIED", "MISMATCH", "UNAVAILABLE"
    current_sha256: str
    recorded_sha256: str
    anchored_sha256: Optional[str] = None
    transaction_id: Optional[str] = None
    block_number: Optional[int] = None
    blockchain_status: str
    reason: str
    verified_at: str

    model_config = ConfigDict(from_attributes=True)
