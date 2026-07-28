"""add account_name column to portal_accounts

Revision ID: 010_portal_account_name
Revises: 009_slot_availability_status
Create Date: 2026-07-28 13:34:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = '010_portal_account_name'
down_revision = '009_slot_availability_status'
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn.engine)
    
    if 'portal_accounts' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('portal_accounts')]
        if 'account_name' not in columns:
            op.add_column('portal_accounts', sa.Column('account_name', sa.String(), nullable=True))

def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn.engine)
    
    if 'portal_accounts' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('portal_accounts')]
        if 'account_name' in columns:
            op.drop_column('portal_accounts', 'account_name')
