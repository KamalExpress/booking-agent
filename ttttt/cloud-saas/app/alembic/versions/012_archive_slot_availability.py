"""add is_archived, archived_at, archived_by_id columns to slot_availability

Revision ID: 012_archive_slot_availability
Revises: 011_archive_workers_accounts
Create Date: 2026-07-28 14:50:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '012_archive_slot_availability'
down_revision = '011_archive_workers_accounts'
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'slot_availability' in tables:
        columns = [c['name'] for c in inspector.get_columns('slot_availability')]
        if 'is_archived' not in columns:
            op.add_column('slot_availability', sa.Column('is_archived', sa.Boolean(), nullable=False, server_default='false'))
        if 'archived_at' not in columns:
            op.add_column('slot_availability', sa.Column('archived_at', sa.DateTime(), nullable=True))
        if 'archived_by_id' not in columns:
            op.add_column('slot_availability', sa.Column('archived_by_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))

def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'slot_availability' in tables:
        columns = [c['name'] for c in inspector.get_columns('slot_availability')]
        if 'archived_by_id' in columns:
            op.drop_column('slot_availability', 'archived_by_id')
        if 'archived_at' in columns:
            op.drop_column('slot_availability', 'archived_at')
        if 'is_archived' in columns:
            op.drop_column('slot_availability', 'is_archived')
