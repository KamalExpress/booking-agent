#!/bin/bash
set -e

# Change to the application directory
cd /app/app

echo "Verifying Python dependencies..."
if ! python -c "import mcp" 2>/dev/null; then
    echo "MCP library missing from container. Installing requirements..."
    pip install --no-cache-dir -r /app/requirements.txt || pip install --no-cache-dir mcp || true
fi

echo "Ensuring Base tables exist before migrations..."
python -c "
from sqlalchemy import create_engine
from models import Base
import os
engine = create_engine(os.environ['DATABASE_URL'])
Base.metadata.create_all(bind=engine)
"

echo "Applying Alembic Migrations..."
python -c "
from sqlalchemy import create_engine, inspect
import os, sys, subprocess
engine = create_engine(os.environ['DATABASE_URL'])
inspector = inspect(engine)
if not inspector.has_table('alembic_version'):
    print('No alembic_version found. Stamping database at head since Base.metadata.create_all created all tables.')
    subprocess.run([sys.executable, '-m', 'alembic', 'stamp', 'head'])
else:
    # Self-healing: if alembic is stamped but migrations were skipped, force rollback stamp
    if inspector.has_table('leases'):
        cols = [c['name'] for c in inspector.get_columns('leases')]
        if 'lease_version' not in cols:
            print('Database is missing Sprint 10 columns. Forcing stamp to 001_baseline to re-run migrations.')
            subprocess.run([sys.executable, '-m', 'alembic', 'stamp', '001_baseline'])
"

# Run alembic upgrade head; if a revision cannot be located (e.g. branch downgrade), self-heal by stamping to head
if ! python -m alembic upgrade head; then
    echo "Alembic upgrade head failed (likely due to branch divergence or missing historic revision). Auto-stamping to head..."
    python -m alembic stamp head
    echo "Re-running alembic upgrade head after stamp..."
    python -m alembic upgrade head || true
fi

echo "Seeding default database records..."
python init_db.py

echo "Starting FastAPI Server..."
cd /app
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
