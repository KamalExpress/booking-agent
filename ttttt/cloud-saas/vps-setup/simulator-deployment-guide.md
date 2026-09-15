# GVC Consular Portal & Simulator - VPS Deployment Guide

This guide details how to deploy the standalone, hardened **GVC Consular Portal & Simulator** on a production or staging VPS (e.g., Hetzner, DigitalOcean) using Docker and Cloudflare Tunnel.

---

## 1. Architectural Topology

`
┌─────────────────────────────────────────────────────────────┐
│                      Cloudflare Edge                        │
│             (e.g., https://gvc-mock.yourdomain.com)         │
└──────────────────────────────┬──────────────────────────────┘
                               │ Cloudflare Tunnel (cloudflared)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                     VPS Host Environment                    │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │  mock-gvc-portal-standalone (Docker Container)      │   │
│   │  • Port Exposed: 127.0.0.1:8745                     │   │
│   │  • Internal Port: 5001                              │   │
│   │                                                     │   │
│   │  Components:                                        │   │
│   │  1. Human Consular Web UI (/)                       │   │
│   │  2. Simulator Admin Control Deck (/admin)           │   │
│   │  3. GVC REST API Engine (/api/v1/...)               │   │
│   │  4. TLS Fingerprint Radar & Telemetry               │   │
│   └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
`

The simulator runs as an **isolated, standalone stack** on port **8745**, ensuring **zero interference** with the live SaaS Control Plane (port 8743).

---

## 2. Deployment Option A: Portainer CE (Recommended GUI Flow)

If managing your VPS via Portainer CE:

1. Log into your **Portainer CE Dashboard**.
2. Navigate to **Stacks** → **Add Stack**.
3. Set **Name**: gvc-simulator
4. Select **Build method**: **Repository**
5. Enter Repository Details:
   - **Repository URL**: https://github.com/KamalExpress/booking-agent.git (or your repo clone URL)
   - **Repository reference**: efs/heads/feature/mock-portal-hardening (or main / your current active branch)
   - **Compose path**: 	tttt/cloud-saas/vps-setup/docker-compose-simulator.yml
   - **Automatic updates**: Disabled (or webhook-enabled for manual redeploys)
6. Click **Deploy the stack**.
7. Portainer will build the Python image, establish the bridge network, and start mock-gvc-portal-standalone.

---

## 3. Deployment Option B: SSH Command Line

If deploying directly via SSH terminal:

`ash
# 1. SSH into the VPS
ssh user@your-vps-ip

# 2. Navigate to repository directory
cd /path/to/bookingbot

# 3. Checkout the target branch
git fetch origin
git checkout feature/mock-portal-hardening
git pull origin feature/mock-portal-hardening

# 4. Run the automated deployment script
chmod +x ttttt/cloud-saas/vps-setup/deploy-simulator.sh
./ttttt/cloud-saas/vps-setup/deploy-simulator.sh
`

Or execute docker compose directly:
`ash
docker compose -f ttttt/cloud-saas/vps-setup/docker-compose-simulator.yml up -d --build
`

---

## 4. Cloudflare Tunnel Configuration

To securely route a public domain to the simulator without exposing public IP ports:

1. In the **Cloudflare Zero Trust Dashboard**, navigate to **Networks** → **Tunnels**.
2. Select your active server tunnel and click **Configure**.
3. Under the **Public Hostnames** tab, click **Add a public hostname**.
4. Fill in the hostname routing details:
   - **Subdomain**: simulator (or gvc-sim / mock-portal)
   - **Domain**: yourdomain.com
   - **Path**: *(leave empty)*
   - **Type**: HTTP
   - **URL**: localhost:8745 (or 127.0.0.1:8745)
5. Click **Save Hostname**.

> **Security Recommendation:** Add a Cloudflare Access policy on path /admin* (e.g., OTP pin or GitHub email login) to restrict simulator admin control deck access to authorized team members only.

---

## 5. Live Endpoints & Operational Verification

Once deployed and routed via Cloudflare:

| Route | Purpose | Access Persona |
| :--- | :--- | :--- |
| https://simulator.yourdomain.com/ | Authentic 5-step GVC Consular booking interface & printable appointment slips | Human consular agents / testers |
| https://simulator.yourdomain.com/admin | Date-range slot dropper, WAF challenge toggles, live confirmed bookings ledger | System Administrators |
| https://simulator.yourdomain.com/api/v1/auth/login | Real GVC JWT authentication endpoint | Booker/Scraper Workers |
| https://simulator.yourdomain.com/api/v1/periodslot/slots | Live slot matrix query endpoint (PUT) | Scrapers & Booker Swarms |
| https://simulator.yourdomain.com/sendOtpBookAppointment | SMS OTP dispatch trigger | Booking Workers |
| https://simulator.yourdomain.com/api/v1/appointments | Final booking submission & confirmation payload | Booking Workers |
| https://simulator.yourdomain.com/telemetry/fingerprints | Inspect recorded TLS fingerprints and worker personas | DevOps / Verification |

---

## 6. Pointing SaaS & Workers to the Simulator

To run scrapers or booker swarms against the deployed simulator instead of live GVC, set the environment variable:

`ash
# In .env or worker process:
BOOKING_PORTAL_URL=https://simulator.yourdomain.com
`

**Zero Code Divergence Guarantee:** All worker HTTP payloads, headers, curl_cffi TLS fingerprints, and OTP injection logic operate with 100% identical code between the live GVC portal and the simulator.

---

## 7. Useful Maintenance Commands

`ash
# View live simulator container logs:
docker logs -f mock-gvc-portal-standalone

# Restart simulator service:
docker compose -f ttttt/cloud-saas/vps-setup/docker-compose-simulator.yml restart

# Reset telemetry logs & booking ledger:
curl -X POST https://simulator.yourdomain.com/telemetry/reset
`
