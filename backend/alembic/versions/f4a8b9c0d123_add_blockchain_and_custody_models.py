"""add_blockchain_and_custody_models

Revision ID: f4a8b9c0d123
Revises: e3f7a1b2c456
Create Date: 2026-09-05 11:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4a8b9c0d123'
down_revision: Union[str, Sequence[str], None] = 'e3f7a1b2c456'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. custody_events
    op.create_table(
        'custody_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_identifier', sa.String(length=32), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('evidence_id', sa.Integer(), nullable=False),
        sa.Column('audit_log_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('actor_id', sa.Integer(), nullable=False),
        sa.Column('actor_username', sa.String(length=100), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('previous_event_reference', sa.String(length=64), nullable=True),
        sa.Column('blockchain_tx_id', sa.String(length=128), nullable=True),
        sa.Column('blockchain_status', sa.String(length=32), server_default='NOT_ANCHORED', nullable=False),
        sa.Column('blockchain_anchored_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('blockchain_block_number', sa.BigInteger(), nullable=True),
        sa.Column('metadata_hash', sa.String(length=64), nullable=True),
        sa.Column('verification_status', sa.String(length=32), server_default='UNVERIFIED', nullable=False),
        sa.Column('verification_notes', sa.Text(), nullable=True),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['evidence_id'], ['evidence.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id']),
        sa.ForeignKeyConstraint(['audit_log_id'], ['audit_logs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_custody_events_id'), 'custody_events', ['id'], unique=False)
    op.create_index(op.f('ix_custody_events_event_identifier'), 'custody_events', ['event_identifier'], unique=True)
    op.create_index(op.f('ix_custody_events_case_id'), 'custody_events', ['case_id'], unique=False)
    op.create_index(op.f('ix_custody_events_evidence_id'), 'custody_events', ['evidence_id'], unique=False)
    op.create_index(op.f('ix_custody_events_action'), 'custody_events', ['action'], unique=False)
    op.create_index(op.f('ix_custody_events_blockchain_tx_id'), 'custody_events', ['blockchain_tx_id'], unique=False)

    # 2. blockchain_anchors
    op.create_table(
        'blockchain_anchors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('anchor_identifier', sa.String(length=32), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('evidence_id', sa.Integer(), nullable=False),
        sa.Column('custody_event_id', sa.Integer(), nullable=True),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('actor', sa.String(length=100), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source', sa.String(length=128), nullable=False),
        sa.Column('metadata_hash', sa.String(length=64), nullable=False),
        sa.Column('transaction_id', sa.String(length=128), nullable=True),
        sa.Column('block_number', sa.BigInteger(), nullable=True),
        sa.Column('channel_name', sa.String(length=64), nullable=True),
        sa.Column('chaincode_name', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=32), server_default='PENDING', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['evidence_id'], ['evidence.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['custody_event_id'], ['custody_events.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_blockchain_anchors_id'), 'blockchain_anchors', ['id'], unique=False)
    op.create_index(op.f('ix_blockchain_anchors_anchor_identifier'), 'blockchain_anchors', ['anchor_identifier'], unique=True)
    op.create_index(op.f('ix_blockchain_anchors_case_id'), 'blockchain_anchors', ['case_id'], unique=False)
    op.create_index(op.f('ix_blockchain_anchors_evidence_id'), 'blockchain_anchors', ['evidence_id'], unique=False)
    op.create_index(op.f('ix_blockchain_anchors_sha256'), 'blockchain_anchors', ['sha256'], unique=False)
    op.create_index(op.f('ix_blockchain_anchors_transaction_id'), 'blockchain_anchors', ['transaction_id'], unique=True)

    # 3. Add columns to evidence
    with op.batch_alter_table('evidence', schema=None) as batch_op:
        batch_op.add_column(sa.Column('blockchain_status', sa.String(length=32), server_default='NOT_ANCHORED', nullable=False))
        batch_op.add_column(sa.Column('blockchain_tx_id', sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column('blockchain_anchored_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index('ix_evidence_blockchain_tx_id', ['blockchain_tx_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('evidence', schema=None) as batch_op:
        batch_op.drop_index('ix_evidence_blockchain_tx_id')
        batch_op.drop_column('blockchain_anchored_at')
        batch_op.drop_column('blockchain_tx_id')
        batch_op.drop_column('blockchain_status')

    op.drop_table('blockchain_anchors')
    op.drop_table('custody_events')
