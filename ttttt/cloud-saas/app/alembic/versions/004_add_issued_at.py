"""Add issued_at to leases

Revision ID: 004_add_issued_at
Revises: 003_dual_pools
Create Date: 2026-07-18 17:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
import datetime

# revision identifiers, used by Alembic.
revision = '004_add_issued_at'
down_revision = '003_dual_pools'
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if inspector.has_table('leases'):
        lease_cols = [col['name'] for col in inspector.get_columns('leases')]
        if 'issued_at' not in lease_cols:
            op.add_column('leases', sa.Column('issued_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True))

def downgrade() -> None:
    pass
