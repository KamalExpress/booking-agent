#!/bin/bash
set -e

# Change to the application directory
cd /app/app

echo "Waiting for Postgres to be ready..."
# Since Alembic will crash if the DB is completely unreachable, we rely on docker-compose depends_on,
# but adding a small delay or retry logic here is helpful if needed. 

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

python -m alembic upgrade head

echo "Seeding default database records..."
python init_db.py

echo "Starting FastAPI Server..."
cd /app
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
