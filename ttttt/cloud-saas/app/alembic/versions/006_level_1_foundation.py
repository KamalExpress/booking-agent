"""level 1 foundation

Revision ID: 006_level_1_foundation
Revises: 005_add_user_preferences
Create Date: 2026-07-20 10:25:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '006_level_1_foundation'
down_revision = '005_add_user_preferences'
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn.engine)
    tables = inspector.get_table_names()

    # 1. Create Applicants
    if 'applicants' not in tables:
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
    if 'waitlist_queue' not in tables:
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
    if 'inbox_messages' not in tables:
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
    if 'booking_tasks' in tables:
        columns = [c['name'] for c in inspector.get_columns('booking_tasks')]
        if 'applicant_id' not in columns:
            op.add_column('booking_tasks', sa.Column('applicant_id', sa.Integer(), nullable=True))
            op.create_foreign_key('fk_booking_tasks_applicant_id', 'booking_tasks', 'applicants', ['applicant_id'], ['id'], ondelete='SET NULL')
        if 'otp_code' not in columns:
            op.add_column('booking_tasks', sa.Column('otp_code', sa.String(), nullable=True))

    # 5. Modify PortalAccount
    if 'portal_accounts' in tables:
        columns = [c['name'] for c in inspector.get_columns('portal_accounts')]
        if 'tenant_id' not in columns:
            op.add_column('portal_accounts', sa.Column('tenant_id', sa.Integer(), nullable=True))
            op.create_foreign_key('fk_portal_accounts_tenant_id', 'portal_accounts', 'tenants', ['tenant_id'], ['id'], ondelete='SET NULL')

    # 6. Modify Proxy
    if 'proxies' in tables:
        columns = [c['name'] for c in inspector.get_columns('proxies')]
        if 'tenant_id' not in columns:
            op.add_column('proxies', sa.Column('tenant_id', sa.Integer(), nullable=True))
            op.create_foreign_key('fk_proxies_tenant_id', 'proxies', 'tenants', ['tenant_id'], ['id'], ondelete='SET NULL')

def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn.engine)
    
    if 'proxies' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('proxies')]
        if 'tenant_id' in columns:
            op.drop_constraint('fk_proxies_tenant_id', 'proxies', type_='foreignkey')
            op.drop_column('proxies', 'tenant_id')

    if 'portal_accounts' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('portal_accounts')]
        if 'tenant_id' in columns:
            op.drop_constraint('fk_portal_accounts_tenant_id', 'portal_accounts', type_='foreignkey')
            op.drop_column('portal_accounts', 'tenant_id')

    if 'booking_tasks' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('booking_tasks')]
        if 'applicant_id' in columns:
            op.drop_constraint('fk_booking_tasks_applicant_id', 'booking_tasks', type_='foreignkey')
            op.drop_column('booking_tasks', 'applicant_id')
        if 'otp_code' in columns:
            op.drop_column('booking_tasks', 'otp_code')

    tables = inspector.get_table_names()
    if 'inbox_messages' in tables:
        op.drop_index(op.f('ix_inbox_messages_id'), table_name='inbox_messages')
        op.drop_table('inbox_messages')

    if 'waitlist_queue' in tables:
        op.drop_index(op.f('ix_waitlist_queue_id'), table_name='waitlist_queue')
        op.drop_table('waitlist_queue')

    if 'applicants' in tables:
        op.drop_index(op.f('ix_applicants_id'), table_name='applicants')
        op.drop_table('applicants')
