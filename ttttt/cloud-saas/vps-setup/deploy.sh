#!/bin/bash
set -e

# Navigate to the root directory of the repository
cd "$(dirname "$0")/.."

echo "================================================"
echo " Kamal Express SaaS - Production Deployment"
echo "================================================"

# Zero-config setup: All keys are hardcoded securely in docker-compose.prod.yml

echo "1. Pulling latest code from GitHub..."
git pull origin main

echo "2. Rebuilding Docker Image for Production..."
docker compose -f vps-setup/docker-compose.prod.yml build

echo "3. Starting Production Stack in detached mode..."
docker compose -f vps-setup/docker-compose.prod.yml up -d

echo "4. Cleaning up dangling images to save disk space..."
docker image prune -f

echo "================================================"
echo " Deployment Successful!"
echo " The SaaS app is now running and bound to localhost:8743."
echo " Ensure your Cloudflare Tunnel is routing traffic to localhost:8743."
echo "================================================"
