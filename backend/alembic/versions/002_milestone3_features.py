"""Milestone 3 schema extensions for runs, episode analysis status, and show-wide ranking

Revision ID: 002_milestone3_features
Revises: 001_initial_schema
Create Date: 2026-11-08

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = '002_milestone3_features'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. runs extensions: browser_session_id
    op.add_column('runs', sa.Column('browser_session_id', sa.String(64), nullable=True))
    op.create_index('ix_runs_browser_session_id', 'runs', ['browser_session_id'])

    # 2. episodes extensions: per-episode status, analysis result, errors, retries, timestamp
    op.add_column('episodes', sa.Column('analysis_status', sa.String(50), nullable=False, server_default='pending'))
    op.add_column('episodes', sa.Column('analysis_result_json', JSONB().with_variant(sa.JSON(), "sqlite"), nullable=True))
    op.add_column('episodes', sa.Column('error_message', sa.Text(), nullable=True))
    op.add_column('episodes', sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('episodes', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')))
    op.create_index('ix_episodes_analysis_status', 'episodes', ['analysis_status'])

    # 3. promos extensions: show-wide ranking, title, score, question, full candidate data
    op.add_column('promos', sa.Column('show_rank', sa.Integer(), nullable=True))
    op.add_column('promos', sa.Column('editorial_title', sa.String(255), nullable=True))
    op.add_column('promos', sa.Column('overall_score', sa.Float(), nullable=True))
    op.add_column('promos', sa.Column('unresolved_question', sa.Text(), nullable=True))
    op.add_column('promos', sa.Column('candidate_data_json', JSONB().with_variant(sa.JSON(), "sqlite"), nullable=True))
    op.create_index('ix_promos_show_rank', 'promos', ['show_rank'])
    op.create_index('ix_promos_overall_score', 'promos', ['overall_score'])


def downgrade() -> None:
    op.drop_index('ix_promos_overall_score', table_name='promos')
    op.drop_index('ix_promos_show_rank', table_name='promos')
    op.drop_column('promos', 'candidate_data_json')
    op.drop_column('promos', 'unresolved_question')
    op.drop_column('promos', 'overall_score')
    op.drop_column('promos', 'editorial_title')
    op.drop_column('promos', 'show_rank')

    op.drop_index('ix_episodes_analysis_status', table_name='episodes')
    op.drop_column('episodes', 'updated_at')
    op.drop_column('episodes', 'retry_count')
    op.drop_column('episodes', 'error_message')
    op.drop_column('episodes', 'analysis_result_json')
    op.drop_column('episodes', 'analysis_status')

    op.drop_index('ix_runs_browser_session_id', table_name='runs')
    op.drop_column('runs', 'browser_session_id')

