"""add slot_availability status and last_checked_at columns

Revision ID: 009_slot_availability_status
Revises: 008_tenant_inbox_fields
Create Date: 2026-07-28 13:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = '009_slot_availability_status'
down_revision = '008_tenant_inbox_fields'
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn.engine)
    
    if 'slot_availability' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('slot_availability')]
        if 'status' not in columns:
            op.add_column('slot_availability', sa.Column('status', sa.String(), nullable=False, server_default='AVAILABLE'))
        if 'last_checked_at' not in columns:
            op.add_column('slot_availability', sa.Column('last_checked_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')))

def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn.engine)
    
    if 'slot_availability' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('slot_availability')]
        if 'status' in columns:
            op.drop_column('slot_availability', 'status')
        if 'last_checked_at' in columns:
            op.drop_column('slot_availability', 'last_checked_at')
