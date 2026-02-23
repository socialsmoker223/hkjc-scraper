"""enforce_hkjc_horse_id_not_null

Revision ID: 9873688e6277
Revises: b1c2d3e4f5a6
Create Date: 2026-02-23 16:38:11.097912

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9873688e6277'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("horse", "hkjc_horse_id", nullable=False)


def downgrade() -> None:
    op.alter_column("horse", "hkjc_horse_id", nullable=True)
