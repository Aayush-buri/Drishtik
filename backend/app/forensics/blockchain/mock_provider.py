import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from app.forensics.blockchain.provider import BlockchainProvider, AnchorResult, VerificationResult

class MockBlockchainProvider(BlockchainProvider):
    """
    Deterministic in-memory Hyperledger Fabric provider for testing and validation.
    Allows testing anchor creation, custody sequencing, verification, tampering detection,
    and offline failover without running a physical Hyperledger Fabric docker network.
    """

    def __init__(
        self,
        channel_name: str = "cctvchannel",
        chaincode_name: str = "evidence_anchor",
        simulate_offline: bool = False
    ):
        self.channel_name = channel_name
        self.chaincode_name = chaincode_name
        self.simulate_offline = simulate_offline
        self.ledger: Dict[str, Dict[str, Any]] = {}
        self.custody_ledger: Dict[str, Dict[str, Any]] = {}
        self.transactions: Dict[str, Dict[str, Any]] = {}
        self.current_block: int = 100

    def _compute_metadata_hash(self, metadata: Dict[str, Any]) -> str:
        canonical = json.dumps(metadata, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    def health_check(self) -> Dict[str, Any]:
        if self.simulate_offline:
            return {
                "available": False,
                "status": "UNAVAILABLE",
                "network": "Hyperledger Fabric (Mock)",
                "channel": self.channel_name,
                "chaincode": self.chaincode_name,
                "message": "Blockchain service unavailable. Local SHA-256 integrity and audit logging remain active."
            }
        return {
            "available": True,
            "status": "ONLINE",
            "network": "Hyperledger Fabric (Mock)",
            "channel": self.channel_name,
            "chaincode": self.chaincode_name,
            "current_block": self.current_block,
            "total_anchors": len(self.ledger),
            "message": "Simulated Hyperledger Fabric ledger operational."
        }

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
        meta_hash = self._compute_metadata_hash(metadata)

        if self.simulate_offline:
            return AnchorResult(
                success=False,
                transaction_id=None,
                block_number=None,
                timestamp=timestamp,
                status="UNAVAILABLE",
                channel=self.channel_name,
                chaincode=self.chaincode_name,
                metadata_hash=meta_hash,
                error_message="Blockchain service unavailable. Local SHA-256 integrity preserved."
            )

        self.current_block += 1
        tx_id = f"tx_{hashlib.sha256(f'{evidence_identifier}_{sha256}_{self.current_block}'.encode('utf-8')).hexdigest()}"

        record = {
            "anchor_id": f"ANCH-{evidence_identifier}",
            "case_id": case_identifier,
            "case_identifier": case_identifier,
            "evidence_id": evidence_identifier,
            "evidence_identifier": evidence_identifier,
            "sha256": sha256,
            "event_type": event_type,
            "actor": actor,
            "timestamp": timestamp.isoformat(),
            "source": source,
            "metadata_hash": meta_hash,
            "transaction_id": tx_id,
            "block_number": self.current_block,
            "metadata": metadata
        }

        self.ledger[evidence_identifier] = record
        self.transactions[tx_id] = record

        return AnchorResult(
            success=True,
            transaction_id=tx_id,
            block_number=self.current_block,
            timestamp=timestamp,
            status="ANCHORED",
            channel=self.channel_name,
            chaincode=self.chaincode_name,
            metadata_hash=meta_hash,
            payload=record
        )

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
        meta_hash = self._compute_metadata_hash(metadata)

        if self.simulate_offline:
            return AnchorResult(
                success=False,
                transaction_id=None,
                block_number=None,
                timestamp=timestamp,
                status="UNAVAILABLE",
                channel=self.channel_name,
                chaincode=self.chaincode_name,
                metadata_hash=meta_hash,
                error_message="Blockchain service unavailable. Local SHA-256 integrity preserved."
            )

        self.current_block += 1
        tx_id = f"tx_{hashlib.sha256(f'{event_identifier}_{sha256}_{previous_event_reference}_{self.current_block}'.encode('utf-8')).hexdigest()}"

        record = {
            "event_identifier": event_identifier,
            "case_id": case_identifier,
            "case_identifier": case_identifier,
            "evidence_id": evidence_identifier,
            "evidence_identifier": evidence_identifier,
            "action": action,
            "actor": actor,
            "timestamp": timestamp.isoformat(),
            "sha256": sha256,
            "previous_event_reference": previous_event_reference,
            "metadata_hash": meta_hash,
            "transaction_id": tx_id,
            "block_number": self.current_block
        }

        self.custody_ledger[event_identifier] = record
        self.transactions[tx_id] = record
        self.ledger[evidence_identifier] = record

        return AnchorResult(
            success=True,
            transaction_id=tx_id,
            block_number=self.current_block,
            timestamp=timestamp,
            status="ANCHORED",
            channel=self.channel_name,
            chaincode=self.chaincode_name,
            metadata_hash=meta_hash,
            payload=record
        )

    def verify_anchor(
        self,
        case_identifier: str,
        evidence_identifier: str,
        expected_sha256: str
    ) -> VerificationResult:
        if self.simulate_offline:
            return VerificationResult(
                verified=False,
                status="UNAVAILABLE",
                current_sha256=expected_sha256,
                recorded_sha256=expected_sha256,
                anchored_sha256=None,
                transaction_id=None,
                block_number=None,
                timestamp=None,
                reason="Blockchain service unavailable. Unable to query Hyperledger Fabric ledger."
            )

        record = self.ledger.get(evidence_identifier)
        if not record:
            return VerificationResult(
                verified=False,
                status="NOT_FOUND",
                current_sha256=expected_sha256,
                recorded_sha256=expected_sha256,
                anchored_sha256=None,
                transaction_id=None,
                block_number=None,
                timestamp=None,
                reason="No blockchain anchor record found for this evidence identifier."
            )

        anchored_sha = record["sha256"]
        if anchored_sha.lower() == expected_sha256.lower():
            return VerificationResult(
                verified=True,
                status="VERIFIED",
                current_sha256=expected_sha256,
                recorded_sha256=expected_sha256,
                anchored_sha256=anchored_sha,
                transaction_id=record["transaction_id"],
                block_number=record["block_number"],
                timestamp=datetime.fromisoformat(record["timestamp"]),
                reason="Current evidence SHA-256 matches both Drishtik recorded hash and blockchain anchor."
            )
        else:
            return VerificationResult(
                verified=False,
                status="MISMATCH",
                current_sha256=expected_sha256,
                recorded_sha256=expected_sha256,
                anchored_sha256=anchored_sha,
                transaction_id=record["transaction_id"],
                block_number=record["block_number"],
                timestamp=datetime.fromisoformat(record["timestamp"]),
                reason=f"Integrity mismatch: Expected SHA-256 '{expected_sha256}' differs from blockchain anchored hash '{anchored_sha}'."
            )

    def get_transaction(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        return self.transactions.get(transaction_id)
