"""add_hk33_tables

Revision ID: b1c2d3e4f5a6
Revises: afca63e32d55
Create Date: 2026-01-17 18:10:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "afca63e32d55"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create hkjc_odds and offshore_market tables for HK33 data."""
    # Create hkjc_odds table
    op.create_table(
        "hkjc_odds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("race_id", sa.Integer(), nullable=False),
        sa.Column("runner_id", sa.Integer(), nullable=False),
        sa.Column("horse_id", sa.Integer(), nullable=False),
        sa.Column("bet_type", sa.VARCHAR(length=16), nullable=False),
        sa.Column("odds_value", sa.DECIMAL(precision=8, scale=2), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("source_url", sa.TEXT(), nullable=True),
        sa.Column("scraped_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["horse_id"], ["horse.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["race_id"], ["race.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["runner_id"], ["runner.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("runner_id", "bet_type", "recorded_at", name="uq_hkjc_odds_runner_type_time"),
    )
    op.create_index("idx_hkjc_odds_horse", "hkjc_odds", ["horse_id"], unique=False)
    op.create_index("idx_hkjc_odds_race", "hkjc_odds", ["race_id"], unique=False)
    op.create_index("idx_hkjc_odds_race_time", "hkjc_odds", ["race_id", "recorded_at"], unique=False)
    op.create_index("idx_hkjc_odds_race_type", "hkjc_odds", ["race_id", "bet_type"], unique=False)
    op.create_index("idx_hkjc_odds_runner", "hkjc_odds", ["runner_id"], unique=False)

    # Create offshore_market table
    op.create_table(
        "offshore_market",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("race_id", sa.Integer(), nullable=False),
        sa.Column("runner_id", sa.Integer(), nullable=False),
        sa.Column("horse_id", sa.Integer(), nullable=False),
        sa.Column("market_type", sa.VARCHAR(length=16), nullable=False),
        sa.Column("price", sa.DECIMAL(precision=8, scale=2), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("source_url", sa.TEXT(), nullable=True),
        sa.Column("scraped_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["horse_id"], ["horse.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["race_id"], ["race.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["runner_id"], ["runner.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("runner_id", "market_type", "recorded_at", name="uq_offshore_market_runner_type_time"),
    )
    op.create_index("idx_offshore_market_horse", "offshore_market", ["horse_id"], unique=False)
    op.create_index("idx_offshore_market_race", "offshore_market", ["race_id"], unique=False)
    op.create_index("idx_offshore_market_race_time", "offshore_market", ["race_id", "recorded_at"], unique=False)
    op.create_index("idx_offshore_market_race_type", "offshore_market", ["race_id", "market_type"], unique=False)
    op.create_index("idx_offshore_market_runner", "offshore_market", ["runner_id"], unique=False)


def downgrade() -> None:
    """Drop hkjc_odds and offshore_market tables."""
    op.drop_index("idx_offshore_market_runner", table_name="offshore_market")
    op.drop_index("idx_offshore_market_race_type", table_name="offshore_market")
    op.drop_index("idx_offshore_market_race_time", table_name="offshore_market")
    op.drop_index("idx_offshore_market_race", table_name="offshore_market")
    op.drop_index("idx_offshore_market_horse", table_name="offshore_market")
    op.drop_table("offshore_market")

    op.drop_index("idx_hkjc_odds_runner", table_name="hkjc_odds")
    op.drop_index("idx_hkjc_odds_race_type", table_name="hkjc_odds")
    op.drop_index("idx_hkjc_odds_race_time", table_name="hkjc_odds")
    op.drop_index("idx_hkjc_odds_race", table_name="hkjc_odds")
    op.drop_index("idx_hkjc_odds_horse", table_name="hkjc_odds")
    op.drop_table("hkjc_odds")
