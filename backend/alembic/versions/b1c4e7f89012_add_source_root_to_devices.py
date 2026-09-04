"""add_source_root_to_devices

Revision ID: b1c4e7f89012
Revises: a5c92d868d2c
Create Date: 2026-09-04 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c4e7f89012'
down_revision: Union[str, Sequence[str], None] = 'a5c92d868d2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('devices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source_root', sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('devices', schema=None) as batch_op:
        batch_op.drop_column('source_root')
