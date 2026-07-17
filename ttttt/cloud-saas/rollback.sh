#!/bin/bash
set -e

echo "Rolling back Alembic Migration by 1 revision..."

docker run --rm \
  --network sam-agent-platform_staging \
  -v $(pwd)/app:/app \
  -w /app \
  -e DATABASE_URL=postgresql://postgres:postgres_staging_password@postgres_staging:5432/booking_saas_staging \
  python:3.10-slim \
  bash -c "pip install alembic psycopg2-binary sqlalchemy && alembic downgrade -1"

echo "Restarting Staging SaaS..."
docker-compose -f docker-compose.staging.yml restart cloud-saas-staging

echo "Rollback complete!"
