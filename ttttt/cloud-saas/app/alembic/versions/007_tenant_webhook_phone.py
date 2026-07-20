"""tenant webhook phone

Revision ID: 007_tenant_webhook_phone
Revises: 006_level_1_foundation
Create Date: 2026-07-20 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '007_tenant_webhook_phone'
down_revision = '006_level_1_foundation'
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn.engine)
    
    if 'tenants' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('tenants')]
        if 'webhook_url' not in columns:
            op.add_column('tenants', sa.Column('webhook_url', sa.String(), nullable=True))
        if 'phone_number' not in columns:
            op.add_column('tenants', sa.Column('phone_number', sa.String(), nullable=True))

def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn.engine)
    
    if 'tenants' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('tenants')]
        if 'webhook_url' in columns:
            op.drop_column('tenants', 'webhook_url')
        if 'phone_number' in columns:
            op.drop_column('tenants', 'phone_number')
