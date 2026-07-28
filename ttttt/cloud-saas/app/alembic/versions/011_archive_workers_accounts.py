"""add is_archived, archived_at, archived_by_id columns to worker_nodes and portal_accounts

Revision ID: 011_archive_workers_accounts
Revises: 010_portal_account_name
Create Date: 2026-07-28 14:18:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '011_archive_workers_accounts'
down_revision = '010_portal_account_name'
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'worker_nodes' in tables:
        columns = [c['name'] for c in inspector.get_columns('worker_nodes')]
        if 'is_archived' not in columns:
            op.add_column('worker_nodes', sa.Column('is_archived', sa.Boolean(), nullable=False, server_default='false'))
        if 'archived_at' not in columns:
            op.add_column('worker_nodes', sa.Column('archived_at', sa.DateTime(), nullable=True))
        if 'archived_by_id' not in columns:
            op.add_column('worker_nodes', sa.Column('archived_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))

    if 'portal_accounts' in tables:
        columns = [c['name'] for c in inspector.get_columns('portal_accounts')]
        if 'is_archived' not in columns:
            op.add_column('portal_accounts', sa.Column('is_archived', sa.Boolean(), nullable=False, server_default='false'))
        if 'archived_at' not in columns:
            op.add_column('portal_accounts', sa.Column('archived_at', sa.DateTime(), nullable=True))
        if 'archived_by_id' not in columns:
            op.add_column('portal_accounts', sa.Column('archived_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))

def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'worker_nodes' in tables:
        columns = [c['name'] for c in inspector.get_columns('worker_nodes')]
        if 'archived_by_id' in columns:
            op.drop_column('worker_nodes', 'archived_by_id')
        if 'archived_at' in columns:
            op.drop_column('worker_nodes', 'archived_at')
        if 'is_archived' in columns:
            op.drop_column('worker_nodes', 'is_archived')

    if 'portal_accounts' in tables:
        columns = [c['name'] for c in inspector.get_columns('portal_accounts')]
        if 'archived_by_id' in columns:
            op.drop_column('portal_accounts', 'archived_by_id')
        if 'archived_at' in columns:
            op.drop_column('portal_accounts', 'archived_at')
        if 'is_archived' in columns:
            op.drop_column('portal_accounts', 'is_archived')
