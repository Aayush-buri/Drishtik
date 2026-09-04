"""add_device_and_acquisition_models

Revision ID: a5c92d868d2c
Revises: 026cefc85a4c
Create Date: 2026-09-04 09:45:24.945794

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a5c92d868d2c'
down_revision: Union[str, Sequence[str], None] = '026cefc85a4c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('devices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('device_identifier', sa.String(length=32), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('device_type', sa.Enum('DVR', 'NVR', 'INTERNAL_HDD', 'EXTERNAL_STORAGE', 'DISK_IMAGE', 'OTHER', name='devicetype'), nullable=False),
        sa.Column('manufacturer', sa.String(length=100), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('serial_number', sa.String(length=100), nullable=True),
        sa.Column('firmware_version', sa.String(length=100), nullable=True),
        sa.Column('ip_address', sa.String(length=100), nullable=True),
        sa.Column('mac_address', sa.String(length=100), nullable=True),
        sa.Column('storage_capacity', sa.String(length=50), nullable=True),
        sa.Column('channel_count', sa.Integer(), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('notes', sa.String(length=2000), nullable=True),
        sa.Column('status', sa.Enum('ACTIVE', 'INACTIVE', 'ACQUIRED', 'ARCHIVED', name='devicestatus'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_devices_case_id'), 'devices', ['case_id'], unique=False)
    op.create_index(op.f('ix_devices_device_identifier'), 'devices', ['device_identifier'], unique=True)
    op.create_index(op.f('ix_devices_id'), 'devices', ['id'], unique=False)
    op.create_index(op.f('ix_devices_status'), 'devices', ['status'], unique=False)

    op.create_table('acquisitions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('acquisition_identifier', sa.String(length=32), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=False),
        sa.Column('acquisition_method', sa.Enum('FILE_COPY', 'DIRECTORY_COPY', 'DISK_IMAGE', 'EXPORTED_VIDEO', 'LOGICAL_ACQUISITION', 'OTHER', name='acquisitionmethod'), nullable=False),
        sa.Column('source_path', sa.String(length=500), nullable=False),
        sa.Column('destination_reference', sa.String(length=500), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', name='acquisitionstatus'), nullable=False),
        sa.Column('progress', sa.Integer(), nullable=False),
        sa.Column('operator_id', sa.Integer(), nullable=False),
        sa.Column('source_sha256', sa.String(length=64), nullable=True),
        sa.Column('destination_sha256', sa.String(length=64), nullable=True),
        sa.Column('source_md5', sa.String(length=32), nullable=True),
        sa.Column('destination_md5', sa.String(length=32), nullable=True),
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('notes', sa.String(length=2000), nullable=True),
        sa.Column('error_message', sa.String(length=2000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
        sa.ForeignKeyConstraint(['operator_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_acquisitions_acquisition_identifier'), 'acquisitions', ['acquisition_identifier'], unique=True)
    op.create_index(op.f('ix_acquisitions_case_id'), 'acquisitions', ['case_id'], unique=False)
    op.create_index(op.f('ix_acquisitions_device_id'), 'acquisitions', ['device_id'], unique=False)
    op.create_index(op.f('ix_acquisitions_id'), 'acquisitions', ['id'], unique=False)
    op.create_index(op.f('ix_acquisitions_status'), 'acquisitions', ['status'], unique=False)

    with op.batch_alter_table('evidence', schema=None) as batch_op:
        batch_op.add_column(sa.Column('device_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('acquisition_id', sa.Integer(), nullable=True))
        batch_op.create_index(op.f('ix_evidence_acquisition_id'), ['acquisition_id'], unique=False)
        batch_op.create_index(op.f('ix_evidence_device_id'), ['device_id'], unique=False)
        batch_op.create_foreign_key('fk_evidence_device_id', 'devices', ['device_id'], ['id'])
        batch_op.create_foreign_key('fk_evidence_acquisition_id', 'acquisitions', ['acquisition_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('evidence', schema=None) as batch_op:
        batch_op.drop_constraint('fk_evidence_acquisition_id', type_='foreignkey')
        batch_op.drop_constraint('fk_evidence_device_id', type_='foreignkey')
        batch_op.drop_index(op.f('ix_evidence_device_id'))
        batch_op.drop_index(op.f('ix_evidence_acquisition_id'))
        batch_op.drop_column('acquisition_id')
        batch_op.drop_column('device_id')

    op.drop_index(op.f('ix_acquisitions_status'), table_name='acquisitions')
    op.drop_index(op.f('ix_acquisitions_id'), table_name='acquisitions')
    op.drop_index(op.f('ix_acquisitions_device_id'), table_name='acquisitions')
    op.drop_index(op.f('ix_acquisitions_case_id'), table_name='acquisitions')
    op.drop_index(op.f('ix_acquisitions_acquisition_identifier'), table_name='acquisitions')
    op.drop_table('acquisitions')

    op.drop_index(op.f('ix_devices_status'), table_name='devices')
    op.drop_index(op.f('ix_devices_id'), table_name='devices')
    op.drop_index(op.f('ix_devices_device_identifier'), table_name='devices')
    op.drop_index(op.f('ix_devices_case_id'), table_name='devices')
    op.drop_table('devices')
