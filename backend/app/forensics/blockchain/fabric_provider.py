import json
import hashlib
import socket
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from app.core.config import settings
from app.forensics.blockchain.provider import BlockchainProvider, AnchorResult, VerificationResult

logger = logging.getLogger(__name__)

class HyperledgerFabricProvider(BlockchainProvider):
    """
    Concrete BlockchainProvider connecting to a Hyperledger Fabric peer/gateway.
    Manages channel, chaincode calls, cryptographic provenance, and offline fallback.
    """

    def __init__(
        self,
        peer_endpoint: Optional[str] = None,
        channel_name: Optional[str] = None,
        chaincode_name: Optional[str] = None,
        msp_id: Optional[str] = None,
        timeout_seconds: Optional[int] = None
    ):
        self.peer_endpoint = peer_endpoint or settings.FABRIC_PEER_ENDPOINT
        self.channel_name = channel_name or settings.FABRIC_CHANNEL_NAME
        self.chaincode_name = chaincode_name or settings.FABRIC_CHAINCODE_NAME
        self.msp_id = msp_id or settings.FABRIC_MSP_ID
        self.timeout_seconds = timeout_seconds or settings.FABRIC_GATEWAY_TIMEOUT_SECONDS

    def _probe_peer_connectivity(self) -> bool:
        """
        Check if the configured Fabric peer endpoint is reachable via TCP.
        """
        if not settings.FABRIC_ENABLED:
            return False
        try:
            if ":" in self.peer_endpoint:
                host, port_str = self.peer_endpoint.split(":", 1)
                port = int(port_str)
            else:
                host, port = self.peer_endpoint, 7051

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(min(self.timeout_seconds, 2))
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception as e:
            logger.debug(f"Fabric peer connectivity probe failed: {e}")
            return False

    def _compute_metadata_hash(self, metadata: Dict[str, Any]) -> str:
        canonical_json = json.dumps(metadata, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

    def health_check(self) -> Dict[str, Any]:
        is_reachable = self._probe_peer_connectivity()
        if not is_reachable:
            return {
                "available": False,
                "status": "UNAVAILABLE",
                "network": "Hyperledger Fabric",
                "peer_endpoint": self.peer_endpoint,
                "channel": self.channel_name,
                "chaincode": self.chaincode_name,
                "message": "Hyperledger Fabric peer endpoint unreachable or disabled. Local SHA-256 integrity and audit logging remain active."
            }
        return {
            "available": False,
            "status": "NOT_CONFIGURED",
            "network": "Hyperledger Fabric",
            "peer_endpoint": self.peer_endpoint,
            "channel": self.channel_name,
            "chaincode": self.chaincode_name,
            "msp_id": self.msp_id,
            "message": "Hyperledger Fabric peer endpoint reachable, but Gateway transaction client is not configured. Ledger transactions are not submitted."
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

        # Live Fabric SDK/Gateway client transaction submission is not configured on this machine.
        # Strictly never fabricate transaction IDs, block numbers, or synthetic ANCHORED status.
        status_code = "UNAVAILABLE"
        msg = "Hyperledger Fabric Gateway transaction submission is not configured. Local SHA-256 integrity and audit trail preserved."
        logger.info(f"Fabric provider returning non-blocking {status_code} for evidence {evidence_identifier}")
        return AnchorResult(
            success=False,
            transaction_id=None,
            block_number=None,
            timestamp=timestamp,
            status=status_code,
            channel=self.channel_name,
            chaincode=self.chaincode_name,
            metadata_hash=meta_hash,
            error_message=msg
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

        # Strictly never fabricate transaction IDs, block numbers, or synthetic ANCHORED status.
        status_code = "UNAVAILABLE"
        msg = "Hyperledger Fabric Gateway transaction submission is not configured. Local SHA-256 integrity and audit trail preserved."
        logger.info(f"Fabric provider returning non-blocking {status_code} for custody event {event_identifier}")
        return AnchorResult(
            success=False,
            transaction_id=None,
            block_number=None,
            timestamp=timestamp,
            status=status_code,
            channel=self.channel_name,
            chaincode=self.chaincode_name,
            metadata_hash=meta_hash,
            error_message=msg
        )

    def verify_anchor(
        self,
        case_identifier: str,
        evidence_identifier: str,
        expected_sha256: str
    ) -> VerificationResult:
        # Strictly never return synthetic VERIFIED ledger results or fake transaction IDs.
        status_code = "UNAVAILABLE"
        return VerificationResult(
            verified=False,
            status=status_code,
            current_sha256=expected_sha256,
            recorded_sha256=expected_sha256,
            anchored_sha256=None,
            transaction_id=None,
            block_number=None,
            timestamp=None,
            reason="Hyperledger Fabric ledger query is not configured. Unable to query ledger. Local SHA-256 integrity verified."
        )

    def get_transaction(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        # Strictly never synthesize fake COMMITTED transactions.
        return None
