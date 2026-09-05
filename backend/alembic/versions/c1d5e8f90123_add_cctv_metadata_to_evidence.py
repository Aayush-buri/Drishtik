"""add_cctv_metadata_to_evidence

Revision ID: c1d5e8f90123
Revises: b1c4e7f89012
Create Date: 2026-09-04 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d5e8f90123'
down_revision: Union[str, Sequence[str], None] = 'b1c4e7f89012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('evidence', schema=None) as batch_op:
        batch_op.add_column(sa.Column('vendor', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('proprietary_format', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('channel_index', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('start_time_osd', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('end_time_osd', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('is_natively_playable', sa.Boolean(), server_default=sa.true(), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('evidence', schema=None) as batch_op:
        batch_op.drop_column('is_natively_playable')
        batch_op.drop_column('end_time_osd')
        batch_op.drop_column('start_time_osd')
        batch_op.drop_column('channel_index')
        batch_op.drop_column('proprietary_format')
        batch_op.drop_column('vendor')
