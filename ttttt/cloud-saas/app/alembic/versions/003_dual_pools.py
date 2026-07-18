"""Dual Pools Architecture

Revision ID: 003_dual_pools
Revises: 002_add_lease_archive
Create Date: 2026-07-18 16:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = '003_dual_pools'
down_revision = '002_add_lease_archive'
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # 1. worker_nodes
    if inspector.has_table('worker_nodes'):
        columns = [col['name'] for col in inspector.get_columns('worker_nodes')]
        if 'can_scrape' not in columns:
            op.add_column('worker_nodes', sa.Column('can_scrape', sa.Boolean(), server_default='true', nullable=True))
        if 'can_book' not in columns:
            op.add_column('worker_nodes', sa.Column('can_book', sa.Boolean(), server_default='false', nullable=True))
        if 'scheduling_state' not in columns:
            op.add_column('worker_nodes', sa.Column('scheduling_state', sa.String(), server_default='IDLE', nullable=True))

    # 2. leases
    if inspector.has_table('leases'):
        lease_cols = [col['name'] for col in inspector.get_columns('leases')]
        if 'booking_task_id' not in lease_cols:
            op.add_column('leases', sa.Column('booking_task_id', sa.Integer(), nullable=True))
        if 'portal_account_id' not in lease_cols:
            op.add_column('leases', sa.Column('portal_account_id', sa.Integer(), nullable=True))
        if 'proxy_id' not in lease_cols:
            op.add_column('leases', sa.Column('proxy_id', sa.Integer(), nullable=True))
        if 'lease_version' not in lease_cols:
            op.add_column('leases', sa.Column('lease_version', sa.Integer(), server_default='1', nullable=True))
            
        # assignment_id was made nullable, we should probably ALTER COLUMN assignment_id DROP NOT NULL
        # But sqlite doesn't support alter column easily. Assuming postgresql since it's on a VPS:
        if 'assignment_id' in lease_cols:
            op.alter_column('leases', 'assignment_id', nullable=True)

    # 3. lease_archives
    if inspector.has_table('lease_archives'):
        archive_cols = [col['name'] for col in inspector.get_columns('lease_archives')]
        if 'booking_task_id' not in archive_cols:
            op.add_column('lease_archives', sa.Column('booking_task_id', sa.Integer(), nullable=True))
        if 'portal_account_id' not in archive_cols:
            op.add_column('lease_archives', sa.Column('portal_account_id', sa.Integer(), nullable=True))
        if 'proxy_id' not in archive_cols:
            op.add_column('lease_archives', sa.Column('proxy_id', sa.Integer(), nullable=True))
        if 'assignment_id' in archive_cols:
            op.alter_column('lease_archives', 'assignment_id', nullable=True)

    # 4. assignments
    if inspector.has_table('assignments'):
        assign_cols = [col['name'] for col in inspector.get_columns('assignments')]
        if 'scraper_account_id' in assign_cols:
            op.drop_column('assignments', 'scraper_account_id')
        if 'provider' not in assign_cols:
            op.add_column('assignments', sa.Column('provider', sa.String(), server_default='VFS', nullable=True))
        if 'polling_interval' not in assign_cols:
            op.add_column('assignments', sa.Column('polling_interval', sa.Integer(), server_default='300', nullable=True))
        if 'priority' not in assign_cols:
            op.add_column('assignments', sa.Column('priority', sa.Integer(), server_default='0', nullable=True))
        if 'required_labels' not in assign_cols:
            op.add_column('assignments', sa.Column('required_labels', JSONB(), server_default='{}', nullable=True))
        if 'last_checked' not in assign_cols:
            op.add_column('assignments', sa.Column('last_checked', sa.DateTime(), nullable=True))

    # 5. event_logs
    if inspector.has_table('event_logs'):
        event_cols = [col['name'] for col in inspector.get_columns('event_logs')]
        if 'payload' not in event_cols:
            op.add_column('event_logs', sa.Column('payload', JSONB(), nullable=True))

def downgrade() -> None:
    pass
