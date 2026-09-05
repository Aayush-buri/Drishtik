import os
import json
import uuid
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.evidence import Evidence, IntegrityStatus
from app.models.blockchain import CustodyEvent, BlockchainAnchor, BlockchainAnchorStatus, CustodyVerificationStatus
from app.models.audit import AuditLog
from app.forensics.blockchain import get_blockchain_provider
from app.core.config import settings

logger = logging.getLogger(__name__)

class BlockchainService:
    @staticmethod
    def _generate_identifier(prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"

    @staticmethod
    def calculate_file_sha256(filepath: str) -> str:
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(65536), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def get_blockchain_health(self) -> Dict[str, Any]:
        provider = get_blockchain_provider()
        return provider.health_check()

    def record_custody_and_anchor(
        self,
        db: Session,
        case: Case,
        evidence: Evidence,
        action: str,
        user_id: int,
        username: str,
        audit_log_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> CustodyEvent:
        """
        Records a chain-of-custody event and attempts to anchor it on the blockchain ledger.
        Gracefully handles offline/unavailable blockchain states without blocking evidence workflow.
        """
        meta = metadata or {}
        provider = get_blockchain_provider()
        current_time = datetime.now(timezone.utc)

        # 1. Determine previous event reference for contiguous custody linking
        last_event = (
            db.query(CustodyEvent)
            .filter(CustodyEvent.case_id == case.id, CustodyEvent.evidence_id == evidence.id)
            .order_by(CustodyEvent.timestamp.desc())
            .first()
        )
        previous_ref = last_event.event_identifier if last_event else None

        # 2. Create local CustodyEvent record
        custody_event = CustodyEvent(
            event_identifier=self._generate_identifier("CUST"),
            case_id=case.id,
            evidence_id=evidence.id,
            audit_log_id=audit_log_id,
            action=action,
            actor_id=user_id,
            actor_username=username,
            timestamp=current_time,
            sha256=evidence.sha256 or "",
            previous_event_reference=previous_ref,
            blockchain_status="NOT_ANCHORED",
            verification_status="UNVERIFIED"
        )
        db.add(custody_event)
        db.flush()

        # 3. Log audit event: BLOCKCHAIN_ANCHOR_STARTED
        audit_start = AuditLog(
            case_id=case.id,
            user_id=user_id,
            action="BLOCKCHAIN_ANCHOR_STARTED",
            target_identifier=evidence.evidence_identifier,
            details=json.dumps({
                "custody_event_id": custody_event.event_identifier,
                "action": action,
                "sha256": evidence.sha256
            })
        )
        db.add(audit_start)
        db.flush()

        # 4. Attempt blockchain anchoring through provider
        anchor_result = provider.anchor_custody_event(
            case_identifier=case.case_identifier,
            evidence_identifier=evidence.evidence_identifier,
            event_identifier=custody_event.event_identifier,
            action=action,
            actor=username,
            timestamp=current_time,
            sha256=evidence.sha256 or "",
            previous_event_reference=previous_ref,
            metadata=meta
        )

        if anchor_result.success and anchor_result.status == "ANCHORED":
            # 5a. Successfully anchored
            custody_event.blockchain_tx_id = anchor_result.transaction_id
            custody_event.blockchain_status = "ANCHORED"
            custody_event.blockchain_anchored_at = anchor_result.timestamp
            custody_event.blockchain_block_number = anchor_result.block_number
            custody_event.metadata_hash = anchor_result.metadata_hash

            # Update evidence summary fields
            evidence.blockchain_status = "ANCHORED"
            evidence.blockchain_tx_id = anchor_result.transaction_id
            evidence.blockchain_anchored_at = anchor_result.timestamp

            # Store BlockchainAnchor record
            anchor_record = BlockchainAnchor(
                anchor_identifier=self._generate_identifier("ANCH"),
                case_id=case.id,
                evidence_id=evidence.id,
                custody_event_id=custody_event.id,
                sha256=evidence.sha256 or "",
                event_type=action,
                actor=username,
                timestamp=current_time,
                source="Drishtik Forensic Engine",
                metadata_hash=anchor_result.metadata_hash,
                transaction_id=anchor_result.transaction_id,
                block_number=anchor_result.block_number,
                channel_name=anchor_result.channel,
                chaincode_name=anchor_result.chaincode,
                status="ANCHORED"
            )
            db.add(anchor_record)

            audit_complete = AuditLog(
                case_id=case.id,
                user_id=user_id,
                action="BLOCKCHAIN_ANCHOR_COMPLETED",
                target_identifier=evidence.evidence_identifier,
                details=json.dumps({
                    "transaction_id": anchor_result.transaction_id,
                    "block_number": anchor_result.block_number,
                    "channel": anchor_result.channel,
                    "chaincode": anchor_result.chaincode
                })
            )
            db.add(audit_complete)
        else:
            # 5b. Blockchain unavailable or failed
            custody_event.blockchain_status = anchor_result.status
            if evidence.blockchain_status != "ANCHORED":
                evidence.blockchain_status = anchor_result.status

            audit_fail = AuditLog(
                case_id=case.id,
                user_id=user_id,
                action="BLOCKCHAIN_ANCHOR_FAILED",
                target_identifier=evidence.evidence_identifier,
                details=json.dumps({
                    "status": anchor_result.status,
                    "reason": anchor_result.error_message or "Blockchain endpoint unavailable. Local SHA-256 integrity preserved."
                })
            )
            db.add(audit_fail)

        db.commit()
        db.refresh(custody_event)
        return custody_event

    def verify_blockchain_integrity(
        self,
        db: Session,
        case: Case,
        evidence: Evidence,
        user_id: int,
        username: str
    ) -> Dict[str, Any]:
        """
        Performs the 3-point forensic integrity verification:
        1. Current File SHA-256 on Disk
        2. Drishtik Recorded Database SHA-256
        3. Hyperledger Fabric Anchored SHA-256
        """
        provider = get_blockchain_provider()

        # 1. Compute current hash from disk storage
        if not os.path.exists(evidence.storage_path):
            current_sha256 = "FILE_NOT_FOUND"
        else:
            current_sha256 = self.calculate_file_sha256(evidence.storage_path)

        recorded_sha256 = evidence.sha256 or ""

        # 2. Query blockchain provider for anchored hash
        verification_result = provider.verify_anchor(
            case_identifier=case.case_identifier,
            evidence_identifier=evidence.evidence_identifier,
            expected_sha256=recorded_sha256
        )

        current_time = datetime.now(timezone.utc)
        is_disk_match = (current_sha256.lower() == recorded_sha256.lower())

        if verification_result.status == "UNAVAILABLE":
            overall_status = "UNAVAILABLE"
            reason = "Blockchain service is currently unavailable. Local storage SHA-256 integrity remains " + (
                "VERIFIED" if is_disk_match else "MISMATCH"
            )
            audit_action = "BLOCKCHAIN_INTEGRITY_FAILED"
        elif not is_disk_match:
            overall_status = "MISMATCH"
            reason = f"Current file SHA-256 ('{current_sha256}') does not match recorded SHA-256 ('{recorded_sha256}')."
            audit_action = "BLOCKCHAIN_INTEGRITY_FAILED"
        elif verification_result.status == "MISMATCH":
            overall_status = "MISMATCH"
            reason = f"Recorded SHA-256 differs from blockchain anchored SHA-256 ('{verification_result.anchored_sha256}')."
            audit_action = "BLOCKCHAIN_INTEGRITY_FAILED"
        elif verification_result.status == "VERIFIED":
            overall_status = "VERIFIED"
            reason = "Cryptographic 3-point verification passed: Current disk SHA-256, Drishtik database record, and Hyperledger Fabric ledger anchor are bit-for-bit identical."
            audit_action = "BLOCKCHAIN_INTEGRITY_VERIFIED"
        else:
            overall_status = verification_result.status
            reason = verification_result.reason
            audit_action = "BLOCKCHAIN_INTEGRITY_FAILED"

        # 3. Update custody events verification status
        latest_custody = (
            db.query(CustodyEvent)
            .filter(CustodyEvent.case_id == case.id, CustodyEvent.evidence_id == evidence.id)
            .order_by(CustodyEvent.timestamp.desc())
            .first()
        )
        if latest_custody:
            latest_custody.verification_status = overall_status
            latest_custody.verification_notes = reason
            latest_custody.last_verified_at = current_time

        # 4. Audit logging
        audit_log = AuditLog(
            case_id=case.id,
            user_id=user_id,
            action=audit_action,
            target_identifier=evidence.evidence_identifier,
            details=json.dumps({
                "status": overall_status,
                "current_sha256": current_sha256,
                "recorded_sha256": recorded_sha256,
                "anchored_sha256": verification_result.anchored_sha256,
                "transaction_id": verification_result.transaction_id,
                "reason": reason
            })
        )
        db.add(audit_log)
        db.commit()

        return {
            "evidence_identifier": evidence.evidence_identifier,
            "overall_status": overall_status,
            "current_sha256": current_sha256,
            "recorded_sha256": recorded_sha256,
            "anchored_sha256": verification_result.anchored_sha256,
            "transaction_id": verification_result.transaction_id,
            "block_number": verification_result.block_number,
            "blockchain_status": evidence.blockchain_status,
            "reason": reason,
            "verified_at": current_time.isoformat()
        }

    def list_case_custody_events(self, db: Session, case: Case) -> List[CustodyEvent]:
        return (
            db.query(CustodyEvent)
            .filter(CustodyEvent.case_id == case.id)
            .order_by(CustodyEvent.timestamp.asc())
            .all()
        )

    def get_evidence_blockchain_status(self, db: Session, case: Case, evidence: Evidence) -> Dict[str, Any]:
        anchors = (
            db.query(BlockchainAnchor)
            .filter(BlockchainAnchor.case_id == case.id, BlockchainAnchor.evidence_id == evidence.id)
            .order_by(BlockchainAnchor.created_at.desc())
            .all()
        )
        custody_history = (
            db.query(CustodyEvent)
            .filter(CustodyEvent.case_id == case.id, CustodyEvent.evidence_id == evidence.id)
            .order_by(CustodyEvent.timestamp.asc())
            .all()
        )

        health = self.get_blockchain_health()

        return {
            "evidence_identifier": evidence.evidence_identifier,
            "sha256": evidence.sha256,
            "md5": evidence.md5_reference,
            "integrity_status": evidence.integrity_status.value if hasattr(evidence.integrity_status, "value") else str(evidence.integrity_status),
            "blockchain_status": evidence.blockchain_status or "NOT_ANCHORED",
            "transaction_id": evidence.blockchain_tx_id,
            "anchored_at": evidence.blockchain_anchored_at.isoformat() if evidence.blockchain_anchored_at else None,
            "service_status": health.get("status", "UNAVAILABLE"),
            "anchors": [
                {
                    "anchor_identifier": a.anchor_identifier,
                    "event_type": a.event_type,
                    "transaction_id": a.transaction_id,
                    "block_number": a.block_number,
                    "status": a.status,
                    "timestamp": a.timestamp.isoformat(),
                    "metadata_hash": a.metadata_hash
                }
                for a in anchors
            ],
            "custody_events": [
                {
                    "event_identifier": c.event_identifier,
                    "action": c.action,
                    "actor": c.actor_username,
                    "timestamp": c.timestamp.isoformat(),
                    "sha256": c.sha256,
                    "previous_reference": c.previous_event_reference,
                    "blockchain_tx_id": c.blockchain_tx_id,
                    "blockchain_status": c.blockchain_status,
                    "verification_status": c.verification_status
                }
                for c in custody_history
            ]
        }

blockchain_service = BlockchainService()

# Module-level convenience functions
record_custody_and_anchor = blockchain_service.record_custody_and_anchor
verify_blockchain_integrity = blockchain_service.verify_blockchain_integrity
list_case_custody_events = blockchain_service.list_case_custody_events
get_evidence_blockchain_status = blockchain_service.get_evidence_blockchain_status
get_blockchain_health = blockchain_service.get_blockchain_health
