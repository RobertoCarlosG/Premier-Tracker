"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2026-03-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'demo_users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('is_verified', sa.Boolean(), nullable=True),
        sa.Column('verification_token', sa.String(), nullable=True),
        sa.Column('access_token', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_access', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_demo_users_email'), 'demo_users', ['email'], unique=True)
    op.create_index(op.f('ix_demo_users_id'), 'demo_users', ['id'], unique=False)

    op.create_table(
        'cache_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cache_key', sa.String(), nullable=False),
        sa.Column('cache_type', sa.String(), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('hit_count', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cache_entries_cache_key'), 'cache_entries', ['cache_key'], unique=True)
    op.create_index(op.f('ix_cache_entries_cache_type'), 'cache_entries', ['cache_type'], unique=False)
    op.create_index(op.f('ix_cache_entries_expires_at'), 'cache_entries', ['expires_at'], unique=False)
    op.create_index(op.f('ix_cache_entries_id'), 'cache_entries', ['id'], unique=False)

    op.create_table(
        'api_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('endpoint', sa.String(), nullable=False),
        sa.Column('method', sa.String(), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_api_logs_created_at'), 'api_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_api_logs_id'), 'api_logs', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_api_logs_id'), table_name='api_logs')
    op.drop_index(op.f('ix_api_logs_created_at'), table_name='api_logs')
    op.drop_table('api_logs')
    
    op.drop_index(op.f('ix_cache_entries_id'), table_name='cache_entries')
    op.drop_index(op.f('ix_cache_entries_expires_at'), table_name='cache_entries')
    op.drop_index(op.f('ix_cache_entries_cache_type'), table_name='cache_entries')
    op.drop_index(op.f('ix_cache_entries_cache_key'), table_name='cache_entries')
    op.drop_table('cache_entries')
    
    op.drop_index(op.f('ix_demo_users_id'), table_name='demo_users')
    op.drop_index(op.f('ix_demo_users_email'), table_name='demo_users')
    op.drop_table('demo_users')
