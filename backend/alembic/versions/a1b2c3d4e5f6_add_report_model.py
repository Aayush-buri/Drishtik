"""add_report_model

Revision ID: a1b2c3d4e5f6
Revises: f4a8b9c0d123
Create Date: 2026-09-05 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f4a8b9c0d123'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('report_identifier', sa.String(length=32), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('report_type', sa.String(length=32), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='GENERATED'),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('generated_by', sa.Integer(), nullable=False),
        sa.Column('format', sa.String(length=16), nullable=False, server_default='PDF'),
        sa.Column('file_size', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('storage_path', sa.String(length=512), nullable=True),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('examiner_notes', sa.Text(), nullable=True),
        sa.Column('data_payload', sa.JSON(), nullable=True),
        sa.Column('blockchain_status', sa.String(length=32), nullable=False, server_default='UNAVAILABLE'),
        sa.Column('blockchain_tx_id', sa.String(length=128), nullable=True),
        sa.Column('blockchain_anchored_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['generated_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reports_id'), 'reports', ['id'], unique=False)
    op.create_index(op.f('ix_reports_report_identifier'), 'reports', ['report_identifier'], unique=True)
    op.create_index(op.f('ix_reports_case_id'), 'reports', ['case_id'], unique=False)
    op.create_index(op.f('ix_reports_report_type'), 'reports', ['report_type'], unique=False)
    op.create_index(op.f('ix_reports_sha256'), 'reports', ['sha256'], unique=False)
    op.create_index(op.f('ix_reports_blockchain_tx_id'), 'reports', ['blockchain_tx_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_reports_blockchain_tx_id'), table_name='reports')
    op.drop_index(op.f('ix_reports_sha256'), table_name='reports')
    op.drop_index(op.f('ix_reports_report_type'), table_name='reports')
    op.drop_index(op.f('ix_reports_case_id'), table_name='reports')
    op.drop_index(op.f('ix_reports_report_identifier'), table_name='reports')
    op.drop_index(op.f('ix_reports_id'), table_name='reports')
    op.drop_table('reports')
