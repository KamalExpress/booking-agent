"""Add confirmation fields to booking_tasks

Revision ID: 015_booking_confirmation_fields
Revises: 014_portal_account_phone
Create Date: 2026-08-28 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '015_booking_confirmation_fields'
down_revision = '014_portal_account_phone'
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if 'booking_tasks' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('booking_tasks')]
        if 'reference_number' not in columns:
            op.add_column('booking_tasks', sa.Column('reference_number', sa.String(), nullable=True))
        if 'confirmation_payload' not in columns:
            op.add_column('booking_tasks', sa.Column('confirmation_payload', JSONB, nullable=True))
        if 'confirmation_screenshot' not in columns:
            op.add_column('booking_tasks', sa.Column('confirmation_screenshot', sa.String(), nullable=True))

def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if 'booking_tasks' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('booking_tasks')]
        if 'confirmation_screenshot' in columns:
            op.drop_column('booking_tasks', 'confirmation_screenshot')
        if 'confirmation_payload' in columns:
            op.drop_column('booking_tasks', 'confirmation_payload')
        if 'reference_number' in columns:
            op.drop_column('booking_tasks', 'reference_number')
