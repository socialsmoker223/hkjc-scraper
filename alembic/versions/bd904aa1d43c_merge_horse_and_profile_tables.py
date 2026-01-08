"""merge_horse_and_profile_tables

Revision ID: bd904aa1d43c
Revises: 38e7c088ce19
Create Date: 2026-01-09 01:22:09.483132

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bd904aa1d43c'
down_revision: Union[str, Sequence[str], None] = '38e7c088ce19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Add columns to horse
    op.add_column('horse', sa.Column('origin', sa.VARCHAR(64), nullable=True))
    op.add_column('horse', sa.Column('age', sa.Integer(), nullable=True))
    op.add_column('horse', sa.Column('colour', sa.VARCHAR(32), nullable=True))
    op.add_column('horse', sa.Column('sex', sa.VARCHAR(16), nullable=True))
    op.add_column('horse', sa.Column('import_type', sa.VARCHAR(64), nullable=True))
    op.add_column('horse', sa.Column('season_prize_hkd', sa.Integer(), nullable=True))
    op.add_column('horse', sa.Column('lifetime_prize_hkd', sa.Integer(), nullable=True))
    op.add_column('horse', sa.Column('record_wins', sa.Integer(), nullable=True))
    op.add_column('horse', sa.Column('record_seconds', sa.Integer(), nullable=True))
    op.add_column('horse', sa.Column('record_thirds', sa.Integer(), nullable=True))
    op.add_column('horse', sa.Column('record_starts', sa.Integer(), nullable=True))
    op.add_column('horse', sa.Column('last10_starts', sa.Integer(), nullable=True))
    op.add_column('horse', sa.Column('current_location', sa.VARCHAR(64), nullable=True))
    op.add_column('horse', sa.Column('current_location_date', sa.Date(), nullable=True))
    op.add_column('horse', sa.Column('import_date', sa.Date(), nullable=True))
    op.add_column('horse', sa.Column('owner_name', sa.VARCHAR(128), nullable=True))
    op.add_column('horse', sa.Column('current_rating', sa.Integer(), nullable=True))
    op.add_column('horse', sa.Column('season_start_rating', sa.Integer(), nullable=True))
    op.add_column('horse', sa.Column('sire_name', sa.VARCHAR(128), nullable=True))
    op.add_column('horse', sa.Column('dam_name', sa.VARCHAR(128), nullable=True))
    op.add_column('horse', sa.Column('dam_sire_name', sa.VARCHAR(128), nullable=True))

    # 2. Data Migration
    op.execute("""
        UPDATE horse
        SET
            origin = hp.origin,
            age = hp.age,
            colour = hp.colour,
            sex = hp.sex,
            import_type = hp.import_type,
            season_prize_hkd = hp.season_prize_hkd,
            lifetime_prize_hkd = hp.lifetime_prize_hkd,
            record_wins = hp.record_wins,
            record_seconds = hp.record_seconds,
            record_thirds = hp.record_thirds,
            record_starts = hp.record_starts,
            last10_starts = hp.last10_starts,
            current_location = hp.current_location,
            current_location_date = hp.current_location_date,
            import_date = hp.import_date,
            owner_name = hp.owner_name,
            current_rating = hp.current_rating,
            season_start_rating = hp.season_start_rating,
            sire_name = hp.sire_name,
            dam_name = hp.dam_name,
            dam_sire_name = hp.dam_sire_name
        FROM horse_profile hp
        WHERE horse.id = hp.horse_id
    """)

    # 3. Drop table
    op.drop_table('horse_profile')


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Create table
    op.create_table('horse_profile',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column('horse_id', sa.Integer(), sa.ForeignKey('horse.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('origin', sa.VARCHAR(64)),
        sa.Column('age', sa.Integer()),
        sa.Column('colour', sa.VARCHAR(32)),
        sa.Column('sex', sa.VARCHAR(16)),
        sa.Column('import_type', sa.VARCHAR(64)),
        sa.Column('season_prize_hkd', sa.Integer()),
        sa.Column('lifetime_prize_hkd', sa.Integer()),
        sa.Column('record_wins', sa.Integer()),
        sa.Column('record_seconds', sa.Integer()),
        sa.Column('record_thirds', sa.Integer()),
        sa.Column('record_starts', sa.Integer()),
        sa.Column('last10_starts', sa.Integer()),
        sa.Column('current_location', sa.VARCHAR(64)),
        sa.Column('current_location_date', sa.Date()),
        sa.Column('import_date', sa.Date()),
        sa.Column('owner_name', sa.VARCHAR(128)),
        sa.Column('current_rating', sa.Integer()),
        sa.Column('season_start_rating', sa.Integer()),
        sa.Column('sire_name', sa.VARCHAR(128)),
        sa.Column('dam_name', sa.VARCHAR(128)),
        sa.Column('dam_sire_name', sa.VARCHAR(128))
    )

    # 2. Data Migration
    op.execute("""
        INSERT INTO horse_profile (
            horse_id, origin, age, colour, sex, import_type,
            season_prize_hkd, lifetime_prize_hkd,
            record_wins, record_seconds, record_thirds, record_starts,
            last10_starts,
            current_location, current_location_date, import_date,
            owner_name,
            current_rating, season_start_rating,
            sire_name, dam_name, dam_sire_name
        )
        SELECT
            id, origin, age, colour, sex, import_type,
            season_prize_hkd, lifetime_prize_hkd,
            record_wins, record_seconds, record_thirds, record_starts,
            last10_starts,
            current_location, current_location_date, import_date,
            owner_name,
            current_rating, season_start_rating,
            sire_name, dam_name, dam_sire_name
        FROM horse
        WHERE origin IS NOT NULL OR owner_name IS NOT NULL
    """)

    # 3. Drop columns
    op.drop_column('horse', 'dam_sire_name')
    op.drop_column('horse', 'dam_name')
    op.drop_column('horse', 'sire_name')
    op.drop_column('horse', 'season_start_rating')
    op.drop_column('horse', 'current_rating')
    op.drop_column('horse', 'owner_name')
    op.drop_column('horse', 'import_date')
    op.drop_column('horse', 'current_location_date')
    op.drop_column('horse', 'current_location')
    op.drop_column('horse', 'last10_starts')
    op.drop_column('horse', 'record_starts')
    op.drop_column('horse', 'record_thirds')
    op.drop_column('horse', 'record_seconds')
    op.drop_column('horse', 'record_wins')
    op.drop_column('horse', 'lifetime_prize_hkd')
    op.drop_column('horse', 'season_prize_hkd')
    op.drop_column('horse', 'import_type')
    op.drop_column('horse', 'sex')
    op.drop_column('horse', 'colour')
    op.drop_column('horse', 'age')
    op.drop_column('horse', 'origin')
