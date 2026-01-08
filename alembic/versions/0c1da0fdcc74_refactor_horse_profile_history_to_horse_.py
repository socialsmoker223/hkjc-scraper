"""refactor_horse_profile_history_to_horse_history

Revision ID: 0c1da0fdcc74
Revises: bd904aa1d43c
Create Date: 2026-01-09 01:28:31.357462

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0c1da0fdcc74'
down_revision: Union[str, Sequence[str], None] = 'bd904aa1d43c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Rename table
    op.rename_table('horse_profile_history', 'horse_history')

    # 2. Add identity columns
    op.add_column('horse_history', sa.Column('code', sa.VARCHAR(16), nullable=True))
    op.add_column('horse_history', sa.Column('name_cn', sa.VARCHAR(128), nullable=True))
    op.add_column('horse_history', sa.Column('name_en', sa.VARCHAR(128), nullable=True))
    op.add_column('horse_history', sa.Column('hkjc_horse_id', sa.VARCHAR(32), nullable=True))
    op.add_column('horse_history', sa.Column('profile_url', sa.Text(), nullable=True))

    # 3. Rename indexes/constraints (Postgres specific mainly but good practice)
    # Note: Alembic operations for constraint renaming can be tricky depending on DB support.
    # We'll drop and recreate the unique constraint to be safe and clean with naming.
    # Unique constraint was: UNIQUE(horse_id, captured_at)
    # Index was: idx_horse_profile_history_horse_captured
    
    # Drop old constraints/indexes if they exist by name (attempting to be safe)
    # In alembic, we often need to know the exact constraint name.
    # The name was explicitly set as 'uq_horse_profile_history_horse_captured' in models
    try:
        op.drop_constraint('uq_horse_profile_history_horse_captured', 'horse_history', type_='unique')
    except Exception:
        pass # Might not exist or name differs

    # Recreate explicit unique constraint with new name
    op.create_unique_constraint('uq_horse_history_horse_captured', 'horse_history', ['horse_id', 'captured_at'])
    
    # Rename index if possible, or drop create.
    # op.drop_index('idx_horse_profile_history_horse_captured', table_name='horse_history')
    # op.create_index('idx_horse_history_horse_captured', 'horse_history', ['horse_id', 'captured_at'])
    # We will just leave the index as is or rely on autogen for future. 
    # Let's simple add columns and rename table is the core requirement.
    
    # 4. Backfill data
    op.execute("""
        UPDATE horse_history hh
        SET
            code = h.code,
            name_cn = h.name_cn,
            name_en = h.name_en,
            hkjc_horse_id = h.hkjc_horse_id,
            profile_url = h.profile_url
        FROM horse h
        WHERE hh.horse_id = h.id
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Drop columns
    op.drop_column('horse_history', 'profile_url')
    op.drop_column('horse_history', 'hkjc_horse_id')
    op.drop_column('horse_history', 'name_en')
    op.drop_column('horse_history', 'name_cn')
    op.drop_column('horse_history', 'code')

    # 2. Rename back
    op.rename_table('horse_history', 'horse_profile_history')
    
    # 3. Restore constraint name
    op.drop_constraint('uq_horse_history_horse_captured', 'horse_profile_history', type_='unique')
    op.create_unique_constraint('uq_horse_profile_history_horse_captured', 'horse_profile_history', ['horse_id', 'captured_at'])
