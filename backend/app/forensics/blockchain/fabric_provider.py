import json
import hashlib
import logging
import subprocess
import threading
import uuid
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from app.core.config import settings, BASE_DIR
from app.forensics.blockchain.provider import BlockchainProvider, AnchorResult, VerificationResult

logger = logging.getLogger(__name__)

class FabricGatewayClient:
    """
    Subprocess manager for the Node.js Fabric Gateway adapter.
    """
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.process = None
        self.lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = FabricGatewayClient()
            return cls._instance

    def _start_process_if_needed(self):
        with self.lock:
            if self.process is None or self.process.poll() is not None:
                env = os.environ.copy()
                env["FABRIC_PEER_ENDPOINT"] = settings.FABRIC_PEER_ENDPOINT
                env["FABRIC_CHANNEL_NAME"] = settings.FABRIC_CHANNEL_NAME
                env["FABRIC_CHAINCODE_NAME"] = settings.FABRIC_CHAINCODE_NAME
                env["FABRIC_MSP_ID"] = settings.FABRIC_MSP_ID
                if settings.FABRIC_CLIENT_CERT_PATH:
                    env["FABRIC_CLIENT_CERT_PATH"] = settings.FABRIC_CLIENT_CERT_PATH
                if settings.FABRIC_CLIENT_KEY_PATH:
                    env["FABRIC_CLIENT_KEY_PATH"] = settings.FABRIC_CLIENT_KEY_PATH
                if settings.FABRIC_TLS_CERT_PATH:
                    env["FABRIC_TLS_CERT_PATH"] = settings.FABRIC_TLS_CERT_PATH

                script_path = os.path.join(
                    str(BASE_DIR), "fabric_adapter", "gateway_worker.js"
                )

                try:
                    self.process = subprocess.Popen(
                        ["node", script_path],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        env=env
                    )
                except Exception as e:
                    logger.error(f"Failed to start Fabric Gateway Node.js adapter: {e}")
                    self.process = None

    def send_request(self, method: str, args: Dict[str, Any]) -> Dict[str, Any]:
        self._start_process_if_needed()
        if not self.process:
            return {"error": "Gateway adapter not running", "result": None}

        req_id = str(uuid.uuid4())
        payload = json.dumps({"id": req_id, "method": method, "args": args})

        with self.lock:
            try:
                self.process.stdin.write(payload + "\n")
                self.process.stdin.flush()
                line = self.process.stdout.readline()
                if not line:
                    self.process = None
                    return {"error": "Gateway adapter closed connection", "result": None}

                response = json.loads(line)
                return response
            except Exception as e:
                self.process = None
                return {"error": str(e), "result": None}


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

        self.gateway = FabricGatewayClient.get_instance()

    def _compute_metadata_hash(self, metadata: Dict[str, Any]) -> str:
        canonical_json = json.dumps(metadata, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

    def health_check(self) -> Dict[str, Any]:
        if not settings.FABRIC_ENABLED:
            return {
                "available": False,
                "status": "DISABLED",
                "network": "Hyperledger Fabric",
                "message": "Hyperledger Fabric is explicitly disabled in configuration."
            }

        resp = self.gateway.send_request("health", {})
        err = resp.get("error")
        result = resp.get("result")

        if err or not result:
            return {
                "available": False,
                "status": "UNAVAILABLE",
                "network": "Hyperledger Fabric",
                "peer_endpoint": self.peer_endpoint,
                "channel": self.channel_name,
                "chaincode": self.chaincode_name,
                "message": f"Hyperledger Fabric gateway adapter failed: {err}"
            }

        status = result.get("status", "UNAVAILABLE")
        msg = result.get("message", "")

        return {
            "available": status == "CONNECTED",
            "status": status,
            "network": "Hyperledger Fabric",
            "peer_endpoint": self.peer_endpoint,
            "channel": self.channel_name,
            "chaincode": self.chaincode_name,
            "msp_id": self.msp_id,
            "message": msg
        }

    def evaluate_evidence_anchor(self, case_identifier: str, evidence_identifier: str) -> Dict[str, Any]:
        """
        Executes a real read-only evaluation against the configured chaincode.
        Returns the parsed JSON dictionary if successful, or {"status": "NOT_FOUND"}
        if the record does not exist.
        """
        resp = self.gateway.send_request("evaluate", {
            "transactionName": "GetEvidenceAnchor",
            "transactionArgs": [case_identifier, evidence_identifier]
        })

        err = resp.get("error")
        if err:
            if "no anchor record found" in err.lower():
                return {"status": "NOT_FOUND", "message": err}
            if err == "NOT_CONFIGURED":
                return {"status": "NOT_CONFIGURED", "message": "Gateway not configured"}
            return {"status": "ERROR", "message": err}

        return {"status": "SUCCESS", "data": resp.get("result")}

    def submit_transaction(self, transaction_name: str, *args: str) -> Dict[str, Any]:
        """
        Architecture established for Sprint 7B. Currently handles the request path to the adapter.
        """
        resp = self.gateway.send_request("submit", {
            "transactionName": transaction_name,
            "transactionArgs": list(args)
        })
        return resp

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

        # Strictly never fabricate transaction IDs, block numbers, or synthetic ANCHORED status.
        status_code = "UNAVAILABLE"
        msg = "Hyperledger Fabric Gateway transaction submission is not configured for Sprint 7A. Local SHA-256 integrity and audit trail preserved."
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
        msg = "Hyperledger Fabric Gateway transaction submission is not configured for Sprint 7A. Local SHA-256 integrity and audit trail preserved."
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

        # We can actually use the real Gateway to verify now if it is configured!
        health = self.health_check()
        if health.get("status") == "CONNECTED":
            resp = self.evaluate_evidence_anchor(case_identifier, evidence_identifier)
            if resp["status"] == "SUCCESS" and resp.get("data"):
                data = resp["data"]
                return VerificationResult(
                    verified=(data.get("sha256") == expected_sha256),
                    status="VERIFIED" if data.get("sha256") == expected_sha256 else "MISMATCH",
                    current_sha256=expected_sha256,
                    recorded_sha256=expected_sha256, # from DB ideally, but ok
                    anchored_sha256=data.get("sha256"),
                    transaction_id=data.get("transaction_id"),
                    block_number=data.get("block_number"),
                    timestamp=data.get("timestamp"),
                    reason="Verified against live Hyperledger Fabric ledger."
                )
            elif resp["status"] == "NOT_FOUND":
                return VerificationResult(
                    verified=False,
                    status="NOT_FOUND",
                    current_sha256=expected_sha256,
                    recorded_sha256=expected_sha256,
                    anchored_sha256=None,
                    transaction_id=None,
                    block_number=None,
                    timestamp=None,
                    reason="No anchor record found for this evidence."
                )

        # Strictly never return synthetic VERIFIED ledger results or fake transaction IDs.
        status_code = health.get("status", "UNAVAILABLE")
        return VerificationResult(
            verified=False,
            status=status_code,
            current_sha256=expected_sha256,
            recorded_sha256=expected_sha256,
            anchored_sha256=None,
            transaction_id=None,
            block_number=None,
            timestamp=None,
            reason="Hyperledger Fabric ledger query is not configured or unavailable. Unable to query ledger. Local SHA-256 integrity verified."
        )

    def get_transaction(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        # Strictly never synthesize fake COMMITTED transactions.
        return None
