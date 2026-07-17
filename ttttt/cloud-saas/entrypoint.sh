#!/bin/bash
set -e

# Change to the application directory
cd /app/app

echo "Waiting for Postgres to be ready..."
# Since Alembic will crash if the DB is completely unreachable, we rely on docker-compose depends_on,
# but adding a small delay or retry logic here is helpful if needed. 

echo "Seeding default database records..."
# Run the seeding logic (init_db.py now only contains data seeding and Base.metadata.create_all for fresh DBs)
python init_db.py

echo "Applying Alembic Migrations..."
# If this is a fresh database, create_all() above created the tables. 
# We run `alembic stamp head` so Alembic knows the database is already up-to-date with the baseline.
# If this is an existing database, stamp does nothing dangerous if already stamped, 
# and upgrade head applies any subsequent migrations.
# Wait, stamp head will mark it as fully migrated even if it's missing columns!
# Let's just run upgrade head. If tables were just created by init_db.py, they are fully up to date.
# But Alembic still needs to mark its revision in the database.
# Actually, the safest approach for a system combining create_all and Alembic is:
# Check if alembic_version table exists. If not, stamp it.
python -c "
from sqlalchemy import create_engine, inspect
import os
engine = create_engine(os.environ['DATABASE_URL'])
if not inspect(engine).has_table('alembic_version'):
    print('Fresh database detected. Stamping Alembic head.')
    import subprocess
    subprocess.run(['alembic', 'stamp', 'head'])
"

alembic upgrade head

echo "Starting FastAPI Server..."
cd /app
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
