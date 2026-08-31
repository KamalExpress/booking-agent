"""Add otp_challenges table and has_ai_copilot to tenants

Revision ID: 016_otp_challenges
Revises: 015_booking_confirmation_fields
Create Date: 2026-08-31 17:35:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '016_otp_challenges'
down_revision = '015_booking_confirmation_fields'
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    # 1. Add has_ai_copilot to tenants
    if 'tenants' in tables:
        columns = [c['name'] for c in inspector.get_columns('tenants')]
        if 'has_ai_copilot' not in columns:
            op.add_column('tenants', sa.Column('has_ai_copilot', sa.Boolean(), server_default=sa.text('true'), nullable=True))

    # 2. Create otp_challenges table
    if 'otp_challenges' not in tables:
        op.create_table(
            'otp_challenges',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('challenge_id', sa.String(), unique=True, index=True, nullable=False),
            sa.Column('booking_task_id', sa.Integer(), sa.ForeignKey('booking_tasks.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id', ondelete='SET NULL'), nullable=True),
            sa.Column('applicant_name', sa.String(), nullable=True),
            sa.Column('visa_center', sa.String(), nullable=True),
            sa.Column('appointment_type', sa.String(), nullable=True),
            sa.Column('status', sa.String(), server_default='PENDING', index=True),
            sa.Column('otp_code', sa.String(), nullable=True),
            sa.Column('expires_in_seconds', sa.Integer(), server_default='300'),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('submitted_at', sa.DateTime(), nullable=True),
            sa.Column('consumed_at', sa.DateTime(), nullable=True),
            sa.Column('submitted_by', sa.String(), nullable=True),
            sa.Column('attempt_count', sa.Integer(), server_default='0')
        )

def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'otp_challenges' in tables:
        op.drop_table('otp_challenges')
        
    if 'tenants' in tables:
        columns = [c['name'] for c in inspector.get_columns('tenants')]
        if 'has_ai_copilot' in columns:
            op.drop_column('tenants', 'has_ai_copilot')
