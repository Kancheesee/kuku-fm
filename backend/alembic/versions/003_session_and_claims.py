"""Milestone 3 session hash and atomic lease claim extensions

Revision ID: 003_session_and_claims
Revises: 002_milestone3_features
Create Date: 2026-11-08

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003_session_and_claims'
down_revision: Union[str, None] = '002_milestone3_features'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. runs: session_hash
    op.add_column('runs', sa.Column('session_hash', sa.String(64), nullable=True))
    op.create_index('ix_runs_session_hash', 'runs', ['session_hash'])

    # 2. episodes: atomic claims, lease expiry, attempt ownership
    op.add_column('episodes', sa.Column('lease_token', sa.String(64), nullable=True))
    op.add_column('episodes', sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('episodes', sa.Column('attempt_number', sa.Integer(), nullable=False, server_default='0'))
    op.create_index('ix_episodes_lease_token', 'episodes', ['lease_token'])
    op.create_index('ix_episodes_lease_expires_at', 'episodes', ['lease_expires_at'])


def downgrade() -> None:
    op.drop_index('ix_episodes_lease_expires_at', table_name='episodes')
    op.drop_index('ix_episodes_lease_token', table_name='episodes')
    op.drop_column('episodes', 'attempt_number')
    op.drop_column('episodes', 'lease_expires_at')
    op.drop_column('episodes', 'lease_token')

    op.drop_index('ix_runs_session_hash', table_name='runs')
    op.drop_column('runs', 'session_hash')
