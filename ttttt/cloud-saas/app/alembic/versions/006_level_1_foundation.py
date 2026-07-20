"""level 1 foundation

Revision ID: 006_level_1_foundation
Revises: 005_add_user_preferences
Create Date: 2026-07-20 10:25:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006_level_1_foundation'
down_revision = '005_add_user_preferences'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Create Applicants
    op.create_table('applicants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('surname', sa.String(), nullable=False),
        sa.Column('firstname', sa.String(), nullable=False),
        sa.Column('dateofbirth', sa.String(), nullable=False),
        sa.Column('gender', sa.String(), nullable=False),
        sa.Column('nationality', sa.String(), nullable=False),
        sa.Column('passportnumber', sa.String(), nullable=False),
        sa.Column('passport_expiry', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('phone_prefix', sa.String(), nullable=False),
        sa.Column('phone_number', sa.String(), nullable=False),
        sa.Column('provider_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_applicants_tenant_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_applicants_id'), 'applicants', ['id'], unique=False)

    # 2. Create WaitlistQueue
    op.create_table('waitlist_queue',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('applicant_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(), nullable=True),
        sa.Column('visa_center', sa.String(), nullable=False),
        sa.Column('appointment_type', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['applicant_id'], ['applicants.id'], name='fk_waitlist_queue_applicant_id', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_waitlist_queue_tenant_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_waitlist_queue_id'), 'waitlist_queue', ['id'], unique=False)

    # 3. Create InboxMessage
    op.create_table('inbox_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('severity', sa.String(), nullable=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('body', sa.String(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_inbox_messages_tenant_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inbox_messages_id'), 'inbox_messages', ['id'], unique=False)

    # 4. Modify BookingTask
    op.add_column('booking_tasks', sa.Column('applicant_id', sa.Integer(), nullable=True))
    op.add_column('booking_tasks', sa.Column('otp_code', sa.String(), nullable=True))
    op.create_foreign_key('fk_booking_tasks_applicant_id', 'booking_tasks', 'applicants', ['applicant_id'], ['id'], ondelete='SET NULL')

    # 5. Modify PortalAccount
    op.add_column('portal_accounts', sa.Column('tenant_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_portal_accounts_tenant_id', 'portal_accounts', 'tenants', ['tenant_id'], ['id'], ondelete='SET NULL')

    # 6. Modify Proxy
    op.add_column('proxies', sa.Column('tenant_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_proxies_tenant_id', 'proxies', 'tenants', ['tenant_id'], ['id'], ondelete='SET NULL')

def downgrade() -> None:
    op.drop_constraint('fk_proxies_tenant_id', 'proxies', type_='foreignkey')
    op.drop_column('proxies', 'tenant_id')

    op.drop_constraint('fk_portal_accounts_tenant_id', 'portal_accounts', type_='foreignkey')
    op.drop_column('portal_accounts', 'tenant_id')

    op.drop_constraint('fk_booking_tasks_applicant_id', 'booking_tasks', type_='foreignkey')
    op.drop_column('booking_tasks', 'otp_code')
    op.drop_column('booking_tasks', 'applicant_id')

    op.drop_index(op.f('ix_inbox_messages_id'), table_name='inbox_messages')
    op.drop_table('inbox_messages')

    op.drop_index(op.f('ix_waitlist_queue_id'), table_name='waitlist_queue')
    op.drop_table('waitlist_queue')

    op.drop_index(op.f('ix_applicants_id'), table_name='applicants')
    op.drop_table('applicants')
