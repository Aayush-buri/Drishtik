"""add_recovery_and_ai_models

Revision ID: e3f7a1b2c456
Revises: d2e6f0a12345
Create Date: 2026-09-05 09:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3f7a1b2c456'
down_revision: Union[str, Sequence[str], None] = 'd2e6f0a12345'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. recovery_scan_jobs
    op.create_table(
        'recovery_scan_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scan_identifier', sa.String(length=32), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('source_evidence_id', sa.Integer(), nullable=True),
        sa.Column('source_acquisition_id', sa.Integer(), nullable=True),
        sa.Column('source_device_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('bytes_scanned', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('candidates_found', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['source_acquisition_id'], ['acquisitions.id']),
        sa.ForeignKeyConstraint(['source_device_id'], ['devices.id']),
        sa.ForeignKeyConstraint(['source_evidence_id'], ['evidence.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recovery_scan_jobs_case_id'), 'recovery_scan_jobs', ['case_id'], unique=False)
    op.create_index(op.f('ix_recovery_scan_jobs_id'), 'recovery_scan_jobs', ['id'], unique=False)
    op.create_index(op.f('ix_recovery_scan_jobs_scan_identifier'), 'recovery_scan_jobs', ['scan_identifier'], unique=True)
    op.create_index(op.f('ix_recovery_scan_jobs_source_evidence_id'), 'recovery_scan_jobs', ['source_evidence_id'], unique=False)

    # 2. recovery_candidates
    op.create_table(
        'recovery_candidates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('candidate_identifier', sa.String(length=32), nullable=False),
        sa.Column('scan_job_id', sa.Integer(), nullable=True),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('source_evidence_id', sa.Integer(), nullable=True),
        sa.Column('source_acquisition_id', sa.Integer(), nullable=True),
        sa.Column('source_device_id', sa.Integer(), nullable=True),
        sa.Column('source_offset', sa.BigInteger(), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('detected_format', sa.String(length=64), nullable=False),
        sa.Column('vendor', sa.String(length=64), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('validation_details', sa.Text(), nullable=True),
        sa.Column('recovered_evidence_id', sa.Integer(), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recovered_evidence_id'], ['evidence.id']),
        sa.ForeignKeyConstraint(['scan_job_id'], ['recovery_scan_jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_acquisition_id'], ['acquisitions.id']),
        sa.ForeignKeyConstraint(['source_device_id'], ['devices.id']),
        sa.ForeignKeyConstraint(['source_evidence_id'], ['evidence.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recovery_candidates_candidate_identifier'), 'recovery_candidates', ['candidate_identifier'], unique=True)
    op.create_index(op.f('ix_recovery_candidates_case_id'), 'recovery_candidates', ['case_id'], unique=False)
    op.create_index(op.f('ix_recovery_candidates_id'), 'recovery_candidates', ['id'], unique=False)
    op.create_index(op.f('ix_recovery_candidates_recovered_evidence_id'), 'recovery_candidates', ['recovered_evidence_id'], unique=False)
    op.create_index(op.f('ix_recovery_candidates_scan_job_id'), 'recovery_candidates', ['scan_job_id'], unique=False)
    op.create_index(op.f('ix_recovery_candidates_source_evidence_id'), 'recovery_candidates', ['source_evidence_id'], unique=False)

    # 3. ai_analysis_jobs
    op.create_table(
        'ai_analysis_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_identifier', sa.String(length=32), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('evidence_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('progress_percent', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_frames_analyzed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('findings_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('config_json', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['evidence_id'], ['evidence.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_analysis_jobs_case_id'), 'ai_analysis_jobs', ['case_id'], unique=False)
    op.create_index(op.f('ix_ai_analysis_jobs_evidence_id'), 'ai_analysis_jobs', ['evidence_id'], unique=False)
    op.create_index(op.f('ix_ai_analysis_jobs_id'), 'ai_analysis_jobs', ['id'], unique=False)
    op.create_index(op.f('ix_ai_analysis_jobs_job_identifier'), 'ai_analysis_jobs', ['job_identifier'], unique=True)

    # 4. ai_findings
    op.create_table(
        'ai_findings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('finding_identifier', sa.String(length=32), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('evidence_id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=True),
        sa.Column('channel', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('media_time', sa.Float(), nullable=False),
        sa.Column('source_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('normalized_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('object_class', sa.String(length=64), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('bounding_box', sa.Text(), nullable=True),
        sa.Column('frame_number', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('model_name', sa.String(length=64), nullable=False, server_default='YOLOv8n'),
        sa.Column('model_version', sa.String(length=32), nullable=False, server_default='8.4.140'),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id']),
        sa.ForeignKeyConstraint(['evidence_id'], ['evidence.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['job_id'], ['ai_analysis_jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_findings_case_id'), 'ai_findings', ['case_id'], unique=False)
    op.create_index(op.f('ix_ai_findings_device_id'), 'ai_findings', ['device_id'], unique=False)
    op.create_index(op.f('ix_ai_findings_evidence_id'), 'ai_findings', ['evidence_id'], unique=False)
    op.create_index(op.f('ix_ai_findings_finding_identifier'), 'ai_findings', ['finding_identifier'], unique=True)
    op.create_index(op.f('ix_ai_findings_id'), 'ai_findings', ['id'], unique=False)
    op.create_index(op.f('ix_ai_findings_job_id'), 'ai_findings', ['job_id'], unique=False)
    op.create_index(op.f('ix_ai_findings_object_class'), 'ai_findings', ['object_class'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('ai_findings')
    op.drop_table('ai_analysis_jobs')
    op.drop_table('recovery_candidates')
    op.drop_table('recovery_scan_jobs')
