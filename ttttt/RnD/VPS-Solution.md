# VPS Solution Architecture (Cloud Agent)

This document outlines the architectural transition from a Local Desktop Windows GUI to a Headless Cloud-Hosted PWA (Progressive Web App) deployment using Docker.

## 1. Architectural Overview

The "Kamal Express Appointment Monitor" will now run continuously on a cloud VPS. The system is divided into two primary containers:
1. **Cloud Agent Container:** A Python FastAPI server that wraps the existing Playwright scraping engine. It exposes a REST API and serves the PWA frontend.
2. **Cloudflare Tunnel Container:** An existing `cloudflared` container (part of the `wp-dev-env` stack) securely exposes the internal FastAPI server to the public internet via `https://silver-stable.samwebdevs.dpdns.org`.

## 2. Docker & Portainer Stack

To deploy the Cloud Agent effortlessly via Portainer, we use a `docker-compose.yml` file.

### Base Image
Because the system relies heavily on Playwright to bypass Cloudflare Captchas, we cannot use a standard lightweight Alpine Linux image. We must use the official **Microsoft Playwright Docker Image** (e.g., `mcr.microsoft.com/playwright/python:v1.44.0-jammy`). This image comes pre-installed with all necessary system dependencies (X11, fonts, libnss) required to launch Chromium in headless mode.

### Networking
The Cloud Agent container must join the existing Docker network (`wp-dev-env`) where the Cloudflare tunnel (`wp_stable`) resides.
In the Portainer stack, we define the external network:
```yaml
networks:
  wp-dev-env:
    external: true
```
This allows the Cloudflare tunnel to route traffic directly to the `cloud-agent` container on port 8000.

## 3. The Backend (FastAPI)

We will wrap the core Python logic (`OperatorAgent`, `SlotMonitorEngine`) in a FastAPI application.
- **State Management:** The `config_manager.py` will continue to read/write JSON files mapped to a persistent Docker Volume (`/app/data`), ensuring settings and accounts survive container restarts.
- **Lifecycle:** The `SlotMonitorEngine` thread will be started during FastAPI's `startup` event and cleanly stopped during the `shutdown` event.
- **REST API:** FastAPI will expose endpoints like `GET /api/status`, `POST /api/settings`, and `POST /api/accounts` for the frontend PWA to consume.

## 4. The Frontend (PWA)

FastAPI will serve a static folder containing a Progressive Web App (HTML/CSS/JS).
- The web interface will mirror the Desktop GUI (Dashboard, Accounts, Settings).
- Staff members will visit `https://silver-stable.samwebdevs.dpdns.org` on their phones and tap **"Add to Home Screen"**.
- We will integrate the **Web Push API**, generating VAPID keys so the Python backend can blast native push notifications directly to iOS and Android devices whenever a slot is found.

## 5. Development & Deployment Workflow

1. **Local Development:** We run the Portainer Stack locally using Docker Desktop. We test the API and PWA at `localhost:8000`.
2. **CF Tunnel Testing:** Once running locally, we map the local CF tunnel to the container to verify external access.
3. **VPS Deployment:** We copy the `docker-compose.yml` into the VPS Portainer, spin up the stack, and the agent runs 24/7.
