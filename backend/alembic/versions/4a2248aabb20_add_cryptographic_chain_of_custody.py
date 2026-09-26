"""Add cryptographic chain of custody

Revision ID: 4a2248aabb20
Revises: ade18d7dcf88
Create Date: 2026-09-26 23:34:23.131803

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import declarative_base
import json
import hashlib

# revision identifiers, used by Alembic.
revision: str = '4a2248aabb20'
down_revision: Union[str, Sequence[str], None] = 'ade18d7dcf88'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

Base = declarative_base()

class CustodyEvent(Base):
    __tablename__ = 'custody_events'
    id = sa.Column(sa.Integer, primary_key=True)
    event_identifier = sa.Column(sa.String(32))
    case_id = sa.Column(sa.Integer)
    evidence_id = sa.Column(sa.Integer)
    action = sa.Column(sa.String(64))
    actor_id = sa.Column(sa.Integer)
    actor_username = sa.Column(sa.String(100))
    timestamp = sa.Column(sa.DateTime(timezone=True))
    sha256 = sa.Column(sa.String(64))
    metadata_hash = sa.Column(sa.String(64))
    previous_event_hash = sa.Column(sa.String(64))
    chain_digest = sa.Column(sa.String(64))

def canonicalize_custody_event(payload) -> str:
    return json.dumps(payload, sort_keys=True, separators=(',', ':'))

def calculate_chain_digest(canonical_payload: str) -> str:
    return hashlib.sha256(canonical_payload.encode('utf-8')).hexdigest()

def upgrade() -> None:
    # Add columns
    op.add_column('custody_events', sa.Column('previous_event_hash', sa.String(length=64), nullable=True))
    op.add_column('custody_events', sa.Column('chain_digest', sa.String(length=64), nullable=True))

    bind = op.get_bind()
    session = Session(bind=bind)

    # Backfill
    GENESIS_CHAIN_HASH = "0" * 64
    
    events = session.query(CustodyEvent).order_by(
        CustodyEvent.case_id.asc(),
        CustodyEvent.evidence_id.asc(),
        CustodyEvent.timestamp.asc(),
        CustodyEvent.id.asc()
    ).all()
    
    current_case_id = None
    current_evidence_id = None
    expected_previous_hash = GENESIS_CHAIN_HASH
    
    for event in events:
        if event.case_id != current_case_id or event.evidence_id != current_evidence_id:
            current_case_id = event.case_id
            current_evidence_id = event.evidence_id
            expected_previous_hash = GENESIS_CHAIN_HASH
            
        # We need to construct the payload for this legacy event
        # If any required immutable field is missing, we leave it NULL
        if event.action and event.actor_id and event.actor_username and event.timestamp:
            payload = {
                "action": event.action,
                "actor_id": event.actor_id,
                "actor_username": event.actor_username,
                "case_id": event.case_id,
                "event_identifier": event.event_identifier,
                "evidence_id": event.evidence_id,
                "metadata_hash": event.metadata_hash,
                "previous_event_hash": expected_previous_hash,
                "sha256": event.sha256 or "",
                "timestamp_utc": event.timestamp.isoformat()
            }
            canonical_payload = canonicalize_custody_event(payload)
            digest = calculate_chain_digest(canonical_payload)
            
            event.previous_event_hash = expected_previous_hash
            event.chain_digest = digest
            expected_previous_hash = digest
        else:
            # Cannot safely backfill, leave NULL, which means UNVERIFIED
            expected_previous_hash = GENESIS_CHAIN_HASH # Break chain safely

    session.commit()

def downgrade() -> None:
    op.drop_column('custody_events', 'chain_digest')
    op.drop_column('custody_events', 'previous_event_hash')

