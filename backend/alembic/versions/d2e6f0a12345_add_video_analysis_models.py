"""add_video_analysis_models

Revision ID: d2e6f0a12345
Revises: c1d5e8f90123
Create Date: 2026-09-05 08:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2e6f0a12345'
down_revision: Union[str, Sequence[str], None] = 'c1d5e8f90123'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'timeline_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_identifier', sa.String(length=32), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('evidence_id', sa.Integer(), nullable=False),
        sa.Column('channel_id', sa.Integer(), nullable=True),
        sa.Column('media_time', sa.Float(), nullable=False),
        sa.Column('source_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('normalized_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['evidence_id'], ['evidence.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_timeline_events_case_id'), 'timeline_events', ['case_id'], unique=False)
    op.create_index(op.f('ix_timeline_events_event_identifier'), 'timeline_events', ['event_identifier'], unique=True)
    op.create_index(op.f('ix_timeline_events_event_type'), 'timeline_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_timeline_events_evidence_id'), 'timeline_events', ['evidence_id'], unique=False)
    op.create_index(op.f('ix_timeline_events_id'), 'timeline_events', ['id'], unique=False)

    op.create_table(
        'analysis_notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('evidence_id', sa.Integer(), nullable=False),
        sa.Column('media_time', sa.Float(), nullable=False),
        sa.Column('source_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('normalized_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('note_text', sa.Text(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['evidence_id'], ['evidence.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_analysis_notes_case_id'), 'analysis_notes', ['case_id'], unique=False)
    op.create_index(op.f('ix_analysis_notes_evidence_id'), 'analysis_notes', ['evidence_id'], unique=False)
    op.create_index(op.f('ix_analysis_notes_id'), 'analysis_notes', ['id'], unique=False)

    op.create_table(
        'timestamp_calibrations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('evidence_id', sa.Integer(), nullable=False),
        sa.Column('offset_seconds', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('time_zone', sa.String(length=50), nullable=False, server_default='UTC'),
        sa.Column('calibration_reason', sa.Text(), nullable=True),
        sa.Column('calibration_method', sa.String(length=100), nullable=False, server_default='MANUAL_CALIBRATION'),
        sa.Column('calibrated_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['calibrated_by'], ['users.id']),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['evidence_id'], ['evidence.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_timestamp_calibrations_case_id'), 'timestamp_calibrations', ['case_id'], unique=False)
    op.create_index(op.f('ix_timestamp_calibrations_evidence_id'), 'timestamp_calibrations', ['evidence_id'], unique=True)
    op.create_index(op.f('ix_timestamp_calibrations_id'), 'timestamp_calibrations', ['id'], unique=False)

    op.create_table(
        'video_analysis_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_identifier', sa.String(length=32), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('evidence_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('last_media_time', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('playback_speed', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('timeline_zoom', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['evidence_id'], ['evidence.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_video_analysis_sessions_case_id'), 'video_analysis_sessions', ['case_id'], unique=False)
    op.create_index(op.f('ix_video_analysis_sessions_evidence_id'), 'video_analysis_sessions', ['evidence_id'], unique=False)
    op.create_index(op.f('ix_video_analysis_sessions_id'), 'video_analysis_sessions', ['id'], unique=False)
    op.create_index(op.f('ix_video_analysis_sessions_session_identifier'), 'video_analysis_sessions', ['session_identifier'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('video_analysis_sessions')
    op.drop_table('timestamp_calibrations')
    op.drop_table('analysis_notes')
    op.drop_table('timeline_events')
