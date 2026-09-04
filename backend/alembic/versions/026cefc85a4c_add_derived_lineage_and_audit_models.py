"""add_derived_lineage_and_audit_models

Revision ID: 026cefc85a4c
Revises: 7f9678462c77
Create Date: 2026-09-04 09:09:16.224871

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '026cefc85a4c'
down_revision: Union[str, Sequence[str], None] = '7f9678462c77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('target_identifier', sa.String(length=100), nullable=True),
        sa.Column('details', sa.String(length=2000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_case_id'), 'audit_logs', ['case_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)
    op.create_index(op.f('ix_audit_logs_target_identifier'), 'audit_logs', ['target_identifier'], unique=False)

    with op.batch_alter_table('evidence', schema=None) as batch_op:
        batch_op.add_column(sa.Column('parent_evidence_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('derived_operation', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('derived_parameters', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('duration_seconds', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('width', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('height', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('fps', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('video_codec', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('audio_codec', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('container', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('bitrate_kbps', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('deleted_by', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('deletion_reason', sa.String(), nullable=True))
        batch_op.create_index(op.f('ix_evidence_is_deleted'), ['is_deleted'], unique=False)
        batch_op.create_index(op.f('ix_evidence_parent_evidence_id'), ['parent_evidence_id'], unique=False)
        batch_op.create_foreign_key('fk_evidence_parent_id', 'evidence', ['parent_evidence_id'], ['id'])
        batch_op.create_foreign_key('fk_evidence_deleted_by', 'users', ['deleted_by'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('evidence', schema=None) as batch_op:
        batch_op.drop_constraint('fk_evidence_deleted_by', type_='foreignkey')
        batch_op.drop_constraint('fk_evidence_parent_id', type_='foreignkey')
        batch_op.drop_index(op.f('ix_evidence_parent_evidence_id'))
        batch_op.drop_index(op.f('ix_evidence_is_deleted'))
        batch_op.drop_column('deletion_reason')
        batch_op.drop_column('deleted_by')
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('is_deleted')
        batch_op.drop_column('bitrate_kbps')
        batch_op.drop_column('container')
        batch_op.drop_column('audio_codec')
        batch_op.drop_column('video_codec')
        batch_op.drop_column('fps')
        batch_op.drop_column('height')
        batch_op.drop_column('width')
        batch_op.drop_column('duration_seconds')
        batch_op.drop_column('derived_parameters')
        batch_op.drop_column('derived_operation')
        batch_op.drop_column('parent_evidence_id')

    op.drop_index(op.f('ix_audit_logs_target_identifier'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_case_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_action'), table_name='audit_logs')
    op.drop_table('audit_logs')
