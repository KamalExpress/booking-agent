"""Baseline

Revision ID: 001_baseline
Revises: 
Create Date: 2026-07-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_baseline'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This is a baseline migration. The tables are assumed to have been created
    # either by earlier versions of init_db.py (in Production) or by 
    # Base.metadata.create_all() (in fresh deployments).
    pass


def downgrade() -> None:
    pass
