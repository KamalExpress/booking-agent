"""Add phone_number to portal_accounts

Revision ID: 014_portal_account_phone
Revises: e093ad7b8be7
Create Date: 2026-08-28 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '014_portal_account_phone'
down_revision = 'e093ad7b8be7'
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if 'portal_accounts' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('portal_accounts')]
        if 'phone_number' not in columns:
            op.add_column('portal_accounts', sa.Column('phone_number', sa.String(), nullable=True))

def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if 'portal_accounts' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('portal_accounts')]
        if 'phone_number' in columns:
            op.drop_column('portal_accounts', 'phone_number')
