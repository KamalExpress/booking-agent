"""Add LeaseArchive

Revision ID: 002_add_lease_archive
Revises: 001_baseline
Create Date: 2026-07-17 17:25:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = '002_add_lease_archive'
down_revision = '001_baseline'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if not inspector.has_table('lease_archives'):
        op.create_table(
            'lease_archives',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('assignment_id', sa.Integer(), nullable=False),
            sa.Column('worker_id', sa.String(), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('last_heartbeat', sa.DateTime(), nullable=True),
            sa.Column('status', sa.String(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('archived_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['assignment_id'], ['assignments.id'], ),
            sa.ForeignKeyConstraint(['worker_id'], ['worker_nodes.worker_id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_lease_archives_id'), 'lease_archives', ['id'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if inspector.has_table('lease_archives'):
        op.drop_index(op.f('ix_lease_archives_id'), table_name='lease_archives')
        op.drop_table('lease_archives')
