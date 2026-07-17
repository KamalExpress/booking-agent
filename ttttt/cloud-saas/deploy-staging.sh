#!/bin/bash
set -e

echo "Starting Staging Database..."
docker-compose -f docker-compose.staging.yml up -d postgres_staging

echo "Waiting for PostgreSQL to become ready..."
sleep 5

echo "Applying Alembic Migrations..."
# Run alembic from within a temporary container connected to the staging network
# We mount the current app directory so it has access to alembic.ini and the scripts
docker run --rm \
  --network sam-agent-platform_staging \
  -v $(pwd)/app:/app \
  -w /app \
  -e DATABASE_URL=postgresql://postgres:postgres_staging_password@postgres_staging:5432/booking_saas_staging \
  python:3.10-slim \
  bash -c "pip install alembic psycopg2-binary sqlalchemy && alembic upgrade head"

echo "Rebuilding and starting Staging SaaS..."
docker-compose -f docker-compose.staging.yml up -d --build cloud-saas-staging

echo "Deployment complete! Staging is running on port 9743."
