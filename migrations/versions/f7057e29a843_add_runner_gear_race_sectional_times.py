"""add_runner_gear_race_sectional_times

Revision ID: f7057e29a843
Revises: 9873688e6277
Create Date: 2026-02-23 17:16:18.719545

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f7057e29a843'
down_revision: Union[str, Sequence[str], None] = '9873688e6277'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("runner", sa.Column("gear", sa.VARCHAR(64), nullable=True))
    op.add_column("race", sa.Column("sectional_times_str", sa.VARCHAR(128), nullable=True))


def downgrade() -> None:
    op.drop_column("runner", "gear")
    op.drop_column("race", "sectional_times_str")
