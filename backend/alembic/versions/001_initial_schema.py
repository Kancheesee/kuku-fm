"""Initial schema for runs, episodes, promos, and model calls

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-11-08

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. runs
    op.create_table(
        'runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='created'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('metadata_json', JSONB().with_variant(sa.JSON(), "sqlite"), nullable=False),
    )

    # 2. episodes
    op.create_table(
        'episodes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('internal_id', sa.String(64), nullable=False),
        sa.Column('episode_number', sa.Integer(), nullable=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=False),
        sa.Column('logline', sa.Text(), nullable=True),
        sa.Column('continuity_notes', sa.Text(), nullable=True),
        sa.Column('scenes_json', JSONB().with_variant(sa.JSON(), "sqlite"), nullable=False),
        sa.Column('events_json', JSONB().with_variant(sa.JSON(), "sqlite"), nullable=False),
        sa.Column('warnings_json', JSONB().with_variant(sa.JSON(), "sqlite"), nullable=False),
        sa.Column('parser_version', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('run_id', 'content_hash', name='uq_run_content_hash'),
    )
    op.create_index('ix_episodes_run_id', 'episodes', ['run_id'])
    op.create_index('ix_episodes_internal_id', 'episodes', ['internal_id'])
    op.create_index('ix_episodes_episode_number', 'episodes', ['episode_number'])
    op.create_index('ix_episodes_content_hash', 'episodes', ['content_hash'])

    # 3. promos
    op.create_table(
        'promos',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('episode_id', sa.String(36), sa.ForeignKey('episodes.id', ondelete='SET NULL'), nullable=True),
        sa.Column('rank', sa.Integer(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=False),
        sa.Column('hook_description', sa.Text(), nullable=False),
        sa.Column('cliffhanger_description', sa.Text(), nullable=False),
        sa.Column('why_it_works', sa.Text(), nullable=False),
        sa.Column('segments_json', JSONB().with_variant(sa.JSON(), "sqlite"), nullable=False),
        sa.Column('editorial_flags_json', JSONB().with_variant(sa.JSON(), "sqlite"), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='suggested'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_promos_run_id', 'promos', ['run_id'])
    op.create_index('ix_promos_episode_id', 'promos', ['episode_id'])
    op.create_index('ix_promos_rank', 'promos', ['rank'])

    # 4. model_calls
    op.create_table(
        'model_calls',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('runs.id', ondelete='CASCADE'), nullable=True),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('model_identifier', sa.String(100), nullable=False),
        sa.Column('prompt_version', sa.String(50), nullable=False),
        sa.Column('prompt_messages_json', JSONB().with_variant(sa.JSON(), "sqlite"), nullable=False),
        sa.Column('raw_response_text', sa.Text(), nullable=False),
        sa.Column('parsed_response_json', JSONB().with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='success'),
        sa.Column('usage_metadata_json', JSONB().with_variant(sa.JSON(), "sqlite"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_model_calls_run_id', 'model_calls', ['run_id'])


def downgrade() -> None:
    op.drop_table('model_calls')
    op.drop_table('promos')
    op.drop_table('episodes')
    op.drop_table('runs')

