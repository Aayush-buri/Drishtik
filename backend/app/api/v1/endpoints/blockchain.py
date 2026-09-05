"""Blockchain and Chain-of-Custody Endpoints.

Provides endpoints to:
- Check Hyperledger Fabric network health and connectivity
- List chronological case chain-of-custody events
- Retrieve evidence-specific blockchain anchor status
- Trigger manual blockchain anchoring for evidence
- Perform 3-point cryptographic verification [ Verify Blockchain Integrity ]
"""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.case import CaseMember
from app.models.evidence import Evidence
from app.dependencies.auth import (
    require_case_member,
    require_case_investigator_or_admin,
)
from app.schemas.blockchain import (
    BlockchainHealthResponse,
    CustodyEventResponse,
    EvidenceBlockchainStatusResponse,
    BlockchainVerificationResponse,
)
from app.services.blockchain_service import blockchain_service

router = APIRouter()


@router.get("/{case_identifier}/blockchain/health", response_model=BlockchainHealthResponse)
def get_blockchain_health_endpoint(
    case_identifier: str,
    member: CaseMember = Depends(require_case_member),
):
    """Query health status of the Hyperledger Fabric blockchain network."""
    health = blockchain_service.get_blockchain_health()
    return health


@router.get("/{case_identifier}/blockchain/custody-events", response_model=List[CustodyEventResponse])
def list_custody_events_endpoint(
    case_identifier: str,
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db),
):
    """Retrieve chronological chain-of-custody events for the active case."""
    events = blockchain_service.list_case_custody_events(db, member.case)
    return events


@router.get("/{case_identifier}/evidence/{evidence_id}/blockchain", response_model=EvidenceBlockchainStatusResponse)
def get_evidence_blockchain_status_endpoint(
    case_identifier: str,
    evidence_id: int,
    member: CaseMember = Depends(require_case_member),
    db: Session = Depends(get_db),
):
    """Retrieve blockchain anchor details and custody history for specific evidence."""
    evidence = (
        db.query(Evidence)
        .filter(Evidence.id == evidence_id, Evidence.case_id == member.case.id)
        .first()
    )
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    status = blockchain_service.get_evidence_blockchain_status(db, member.case, evidence)
    return status


@router.post("/{case_identifier}/evidence/{evidence_id}/blockchain/anchor")
def anchor_evidence_endpoint(
    case_identifier: str,
    evidence_id: int,
    member: CaseMember = Depends(require_case_investigator_or_admin),
    db: Session = Depends(get_db),
):
    """Manually anchor an evidence file and create a custody event."""
    evidence = (
        db.query(Evidence)
        .filter(Evidence.id == evidence_id, Evidence.case_id == member.case.id)
        .first()
    )
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    custody_event = blockchain_service.record_custody_and_anchor(
        db=db,
        case=member.case,
        evidence=evidence,
        action="MANUAL_INTEGRITY_ANCHOR",
        user_id=member.user_id,
        username=member.user.username if member.user else "Examiner",
        metadata={"manual": True}
    )

    return {
        "status": custody_event.blockchain_status,
        "event_identifier": custody_event.event_identifier,
        "transaction_id": custody_event.blockchain_tx_id,
        "message": "Blockchain anchoring completed." if custody_event.blockchain_status == "ANCHORED" else "Blockchain service unavailable; local custody preserved."
    }


@router.post("/{case_identifier}/evidence/{evidence_id}/blockchain/verify", response_model=BlockchainVerificationResponse)
def verify_blockchain_integrity_endpoint(
    case_identifier: str,
    evidence_id: int,
    member: CaseMember = Depends(require_case_investigator_or_admin),
    db: Session = Depends(get_db),
):
    """
    Perform 3-point forensic integrity verification:
    Current File SHA-256 vs Recorded Database SHA-256 vs Hyperledger Fabric Ledger.
    """
    evidence = (
        db.query(Evidence)
        .filter(Evidence.id == evidence_id, Evidence.case_id == member.case.id)
        .first()
    )
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    result = blockchain_service.verify_blockchain_integrity(
        db=db,
        case=member.case,
        evidence=evidence,
        user_id=member.user_id,
        username=member.user.username if member.user else "Examiner"
    )
    return result
