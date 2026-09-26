"""Add drift_scale and reference_timestamp to timestamp_calibrations

Revision ID: ade18d7dcf88
Revises: a1b2c3d4e5f6
Create Date: 2026-09-26 22:20:13.810015

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ade18d7dcf88'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('timestamp_calibrations', sa.Column('drift_scale', sa.Float(), nullable=False, server_default='1.0'))
    op.add_column('timestamp_calibrations', sa.Column('reference_timestamp', sa.DateTime(timezone=True), nullable=True))

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('timestamp_calibrations', 'reference_timestamp')
    op.drop_column('timestamp_calibrations', 'drift_scale')



