#!/bin/bash
set -e

# Navigate to root directory
cd "$(dirname "$0")/.."

echo "================================================"
echo " Kamal Express - GVC Simulator Stack Deploy"
echo "================================================"

echo "1. Pulling latest code from GitHub..."
git pull origin feature/mock-portal-hardening

echo "2. Rebuilding GVC Simulator Image..."
docker compose -f vps-setup/docker-compose-simulator.yml build

echo "3. Starting Simulator Stack in detached mode..."
docker compose -f vps-setup/docker-compose-simulator.yml up -d

echo "================================================"
echo " GVC Simulator Successfully Deployed!"
echo " The Mock Portal is running and bound to localhost:8745 (or internal port 5001)."
echo " Route your Cloudflare Tunnel hostname to http://localhost:8745."
echo " Admin Control Center: http://localhost:8745/admin"
echo " Human Consular Portal: http://localhost:8745/"
echo "================================================"
