"""Execution plane abstraction

Revision ID: e093ad7b8be7
Revises: 012_archive_slot_availability
Create Date: 2026-07-29 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'e093ad7b8be7'
down_revision = '012_archive_slot_availability'
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # 1. Add provider_health to Proxy
    if 'proxies' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('proxies')]
        if 'provider_health' not in columns:
            op.add_column('proxies', sa.Column('provider_health', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
            
    # 2. Add provider_health to PortalAccount (portal_accounts)
    if 'portal_accounts' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('portal_accounts')]
        if 'provider_health' not in columns:
            op.add_column('portal_accounts', sa.Column('provider_health', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
            
    # 3. Add supported_providers to WorkerNode
    if 'worker_nodes' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('worker_nodes')]
        if 'supported_providers' not in columns:
            op.add_column('worker_nodes', sa.Column('supported_providers', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
            
    # 4. Add provider to MonitorConfig
    if 'monitor_configs' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('monitor_configs')]
        if 'provider' not in columns:
            op.add_column('monitor_configs', sa.Column('provider', sa.String(length=50), nullable=True))

def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if 'monitor_configs' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('monitor_configs')]
        if 'provider' in columns:
            op.drop_column('monitor_configs', 'provider')
            
    if 'worker_nodes' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('worker_nodes')]
        if 'supported_providers' in columns:
            op.drop_column('worker_nodes', 'supported_providers')
            
    if 'portal_accounts' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('portal_accounts')]
        if 'provider_health' in columns:
            op.drop_column('portal_accounts', 'provider_health')
            
    if 'proxies' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('proxies')]
        if 'provider_health' in columns:
            op.drop_column('proxies', 'provider_health')
