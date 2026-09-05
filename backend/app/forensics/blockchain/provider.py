from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

@dataclass
class AnchorResult:
    success: bool
    transaction_id: Optional[str]
    block_number: Optional[int]
    timestamp: datetime
    status: str  # "ANCHORED", "UNAVAILABLE", "FAILED"
    channel: str
    chaincode: str
    metadata_hash: str
    error_message: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None

@dataclass
class VerificationResult:
    verified: bool
    status: str  # "VERIFIED", "MISMATCH", "UNAVAILABLE", "NOT_FOUND"
    current_sha256: str
    recorded_sha256: str
    anchored_sha256: Optional[str]
    transaction_id: Optional[str]
    block_number: Optional[int]
    timestamp: Optional[datetime]
    reason: str

class BlockchainProvider(ABC):
    """
    Abstract interface for blockchain integrity anchoring and chain-of-custody verification.
    Decouples Drishtik forensic business logic from specific ledger implementations.
    """

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Check connectivity and readiness of the underlying blockchain network.
        Must return a dictionary containing 'available': bool, 'status': str, 'network': str.
        """
        pass

    @abstractmethod
    def anchor_evidence(
        self,
        case_identifier: str,
        evidence_identifier: str,
        sha256: str,
        event_type: str,
        actor: str,
        timestamp: datetime,
        source: str,
        metadata: Dict[str, Any]
    ) -> AnchorResult:
        """
        Anchor an evidence SHA-256 hash and associated provenance onto the blockchain ledger.
        """
        pass

    @abstractmethod
    def anchor_custody_event(
        self,
        case_identifier: str,
        evidence_identifier: str,
        event_identifier: str,
        action: str,
        actor: str,
        timestamp: datetime,
        sha256: str,
        previous_event_reference: Optional[str],
        metadata: Dict[str, Any]
    ) -> AnchorResult:
        """
        Anchor a chain-of-custody event linking back to the previous custody event reference.
        """
        pass

    @abstractmethod
    def verify_anchor(
        self,
        case_identifier: str,
        evidence_identifier: str,
        expected_sha256: str
    ) -> VerificationResult:
        """
        Query the immutable ledger and verify whether the anchored SHA-256 matches the expected hash.
        """
        pass

    @abstractmethod
    def get_transaction(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve raw transaction details and block envelope from the ledger by transaction ID.
        """
        pass
