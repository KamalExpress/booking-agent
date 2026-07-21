"""tenant inbox fields

Revision ID: 008_tenant_inbox_fields
Revises: 007_tenant_webhook_phone
Create Date: 2026-07-21 16:50:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '008_tenant_inbox_fields'
down_revision = '007_tenant_webhook_phone'
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn.engine)
    
    if 'inbox_messages' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('inbox_messages')]
        if 'is_system_alert' not in columns:
            op.add_column('inbox_messages', sa.Column('is_system_alert', sa.Boolean(), nullable=True, server_default='false'))
        if 'sender_id' not in columns:
            op.add_column('inbox_messages', sa.Column('sender_id', sa.Integer(), nullable=True))
            op.create_foreign_key('fk_inbox_messages_sender_id', 'inbox_messages', 'users', ['sender_id'], ['id'])
        if 'parent_id' not in columns:
            op.add_column('inbox_messages', sa.Column('parent_id', sa.Integer(), nullable=True))
            op.create_foreign_key('fk_inbox_messages_parent_id', 'inbox_messages', 'inbox_messages', ['parent_id'], ['id'])

def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn.engine)
    
    if 'inbox_messages' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('inbox_messages')]
        if 'sender_id' in columns:
            op.drop_constraint('fk_inbox_messages_sender_id', 'inbox_messages', type_='foreignkey')
            op.drop_column('inbox_messages', 'sender_id')
        if 'parent_id' in columns:
            op.drop_constraint('fk_inbox_messages_parent_id', 'inbox_messages', type_='foreignkey')
            op.drop_column('inbox_messages', 'parent_id')
        if 'is_system_alert' in columns:
            op.drop_column('inbox_messages', 'is_system_alert')
