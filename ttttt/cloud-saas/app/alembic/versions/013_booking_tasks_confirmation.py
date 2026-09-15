"""add reference_number and confirmation_payload to booking_tasks

Revision ID: 013_booking_tasks_confirmation
Revises: 012_archive_slot_availability
Create Date: 2026-09-15 14:55:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '013_booking_tasks_confirmation'
down_revision = '012_archive_slot_availability'
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'booking_tasks' in tables:
        columns = [c['name'] for c in inspector.get_columns('booking_tasks')]
        if 'reference_number' not in columns:
            op.add_column('booking_tasks', sa.Column('reference_number', sa.String(), nullable=True))
        if 'confirmation_payload' not in columns:
            op.add_column('booking_tasks', sa.Column('confirmation_payload', JSONB(), nullable=True))

def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'booking_tasks' in tables:
        columns = [c['name'] for c in inspector.get_columns('booking_tasks')]
        if 'confirmation_payload' in columns:
            op.drop_column('booking_tasks', 'confirmation_payload')
        if 'reference_number' in columns:
            op.drop_column('booking_tasks', 'reference_number')
