"""add user preferences

Revision ID: 005_add_user_preferences
Revises: 004_add_issued_at
Create Date: 2026-07-18 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_add_user_preferences'
down_revision = '004_add_issued_at'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add preferences column as JSONB with default empty dict
    op.add_column('users', sa.Column('preferences', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    
    # Update existing rows to have an empty dict
    op.execute("UPDATE users SET preferences = '{}'::jsonb WHERE preferences IS NULL")
    
def downgrade() -> None:
    op.drop_column('users', 'preferences')
