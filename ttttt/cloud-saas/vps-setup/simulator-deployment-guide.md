# GVC Consular Portal & Simulator - VPS Deployment Guide

This guide details how to deploy and expose the standalone, hardened **GVC Consular Portal & Simulator** on a production or staging VPS (e.g., Hetzner, DigitalOcean) using Docker and Cloudflare (Zero Trust Tunnel, DNS, and Access Policies).

---

## 1. Architectural Topology

`
┌───────────────────────────────────────────────────────────────────────────┐
│                           Cloudflare Edge (WAF & DNS)                     │
│                                                                           │
│   Public Domain: https://simulator.yourdomain.com                         │
│   • Public / User Path  : / (Human GVC Consular Experience)               │
│   • API Routes (Workers): /api/v1/*, /sendOtpBookAppointment              │
│   • Admin Console       : /admin (Protected via Cloudflare Access)        │
└─────────────────────────────────────┬─────────────────────────────────────┘
                                      │ Cloudflare Tunnel (cloudflared)
                                      ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                            VPS Host Environment                           │
│                                                                           │
│   ┌───────────────────────────────────────────────────────────────────┐   │
│   │  mock-gvc-portal-standalone (Docker Container)                    │   │
│   │  • Exposed Host Port : 127.0.0.1:8745                             │   │
│   │  • Internal App Port : 5001                                       │   │
│   │                                                                   │   │
│   │  Engine Components:                                               │   │
│   │  1. Human Consular Web UI (5-step booking & confirmation slip)   │   │
│   │  2. Simulator Admin Control Deck (Date Range slot drop & WAF)     │   │
│   │  3. GVC REST API Engine (/api/v1/auth/login, /periodslot/slots)   │   │
│   │  4. TLS Fingerprint Radar & Live Booking Ledger                   │   │
│   └───────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────────┘
`

The simulator runs as an **isolated, standalone stack** on host port **8745**, ensuring **zero interference** with the live SaaS Control Plane (port 8743).

---

## 2. Portainer CE Deployment (Step-by-Step)

If managing your VPS through the Portainer CE web interface:

1. Log into your **Portainer CE Dashboard**.
2. In the left sidebar, click **Stacks** $\rightarrow$ **Add stack**.
3. Configure the Stack parameters:
   - **Name**: gvc-simulator
   - **Build method**: **Repository** (Git)
4. Enter the Repository Settings:
   - **Repository URL**: https://github.com/KamalExpress/booking-agent.git
   - **Repository reference**: efs/heads/feature/mock-portal-hardening *(or eature/mock-portal-hardening)*
   - **Compose path**: 	tttt/cloud-saas/vps-setup/docker-compose-simulator.yml *(Note: 5 't's in 	tttt)*
   - **Automatic updates**: Leave disabled (or configure webhook if desired).
5. Click **Deploy the stack**.
6. Portainer will build the Python image, create ps-setup_simulator-network, and start mock-gvc-portal-standalone bound to 127.0.0.1:8745.

---

## 3. SSH Command Line Deployment (Alternative)

If deploying directly on the VPS terminal via SSH:

`ash
# 1. SSH into the VPS
ssh user@your-vps-ip

# 2. Navigate to your repository workspace
cd /path/to/bookingbot

# 3. Pull latest changes from the feature branch
git fetch origin
git checkout feature/mock-portal-hardening
git pull origin feature/mock-portal-hardening

# 4. Build and start the simulator container
docker compose -f ttttt/cloud-saas/vps-setup/docker-compose-simulator.yml up -d --build
`

---

## 4. Complete Cloudflare (CF) Configuration Instructions

### Step 4.1: Cloudflare Zero Trust Tunnel Routing (Public Hostname)

Route incoming HTTPS traffic from your domain to the simulator container on port 8745:

1. Open the [Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com/).
2. In the left sidebar, go to **Networks** $\rightarrow$ **Tunnels**.
3. Click on your active server tunnel (e.g., ps-production-tunnel) and click **Configure**.
4. Go to the **Public Hostname** tab and click **Add a public hostname**.
5. Configure the Public Hostname fields:
   - **Subdomain**: simulator *(or gvc-sim / mock-portal)*
   - **Domain**: Select your domain from the dropdown (e.g., yourdomain.com)
   - **Path**: *(Leave completely empty to route all paths)*
   - **Service Type**: HTTP
   - **URL**: localhost:8745 *(or 127.0.0.1:8745)*
6. *(Optional)* Under **Additional application settings** $\rightarrow$ **HTTP Settings**:
   - **HTTP Host Header**: *(Leave blank or set to simulator.yourdomain.com)*
   - **Connect Timeout**: 30s
7. Click **Save hostname**.

---

### Step 4.2: Cloudflare SSL/TLS & Caching Settings

1. In the main [Cloudflare Dashboard](https://dash.cloudflare.com/), select your zone/domain.
2. Go to **SSL/TLS** $\rightarrow$ **Overview**:
   - Set encryption mode to **Full** (or **Full (strict)**).
3. Go to **SSL/TLS** $\rightarrow$ **Edge Certificates**:
   - Ensure **Always Use HTTPS** is enabled.
4. Go to **Caching** $\rightarrow$ **Configuration**:
   - Ensure development mode is disabled, or create a Cache Rule to **Bypass Cache** for simulator.yourdomain.com/* so API slot responses and OTP verifications are always evaluated dynamically.

---

### Step 4.3: Cloudflare Access Policy (Protect /admin Console)

To prevent unauthorized public internet users from releasing slots, triggering WAF toggles, or clearing telemetry logs:

1. In the **Cloudflare Zero Trust Dashboard**, go to **Access** $\rightarrow$ **Applications**.
2. Click **Add an application** $\rightarrow$ select **Self-hosted**.
3. Configure the Application:
   - **Application name**: GVC Simulator Admin
   - **Session Duration**: 24 hours
   - **Application domain**: simulator.yourdomain.com
   - **Path**: /admin*
4. Click **Next** to configure the **Access Policy**:
   - **Policy name**: Admin Team Only
   - **Action**: Allow
   - **Rule Include**: Add **Emails** or **Email domain** (e.g., @kamalexpress.com or your admin email).
5. Click **Next** and then **Save application**.

> **Note:** The public booking UI (/) and API routes (/api/v1/*, /sendOtpBookAppointment) will remain publicly reachable by your scrapers/bookers, while /admin is safely protected by Cloudflare Pin/Email verification.

---

### Step 4.4: Cloudflare WAF / Bot Bypass for Automated Swarms

If your Cloudflare zone has **Bot Fight Mode** or aggressive **Super Bot Fight Mode** enabled:

1. In the Cloudflare Dashboard, go to **Security** $\rightarrow$ **WAF** $\rightarrow$ **Custom Rules**.
2. Click **Create rule**:
   - **Rule name**: Allow Simulator Automated Swarms
   - **Expression**:
     (http.host eq simulator.yourdomain.com and (http.request.uri.path starts_with /api/v1/ or http.request.uri.path eq /sendOtpBookAppointment or http.request.uri.path starts_with /telemetry/))
   - **Action**: **Skip** $\rightarrow$ Check **All remaining custom rules** and **WAF components (Managed Challenges, Bot Fight Mode)**.
3. Click **Deploy**.

This ensures your automated booker and scraper swarms (curl_cffi workers) can interact with the simulator API without being interrupted by external Cloudflare challenges.

---

## 5. Operational Verification & Testing

Once deployed and configured in Cloudflare, verify the live endpoints:

| Endpoint | Target URL | Expected Behavior |
| :--- | :--- | :--- |
| **Human Consular Portal** | https://simulator.yourdomain.com/ | Authentic GVC 5-step visa appointment wizard & downloadable appointment slip |
| **Admin Control Deck** | https://simulator.yourdomain.com/admin | Date-range slot dropper (start_date, end_date), WAF toggles, confirmed ledger |
| **Slot Matrix API** | https://simulator.yourdomain.com/api/v1/periodslot/slots (PUT) | Returns active slot JSON for Lahore/Islamabad |
| **SMS OTP Dispatch** | https://simulator.yourdomain.com/sendOtpBookAppointment (POST) | Returns {code: SUCCESS, status: OTP_SENT} |
| **Appointment Booking** | https://simulator.yourdomain.com/api/v1/appointments (POST) | Confirms booking and records reference number |
| **Telemetry Radar** | https://simulator.yourdomain.com/telemetry/fingerprints | Displays captured TLS personas, User-Agents, and headers |

---

## 6. Pointing SaaS & Booker Workers to the Simulator

To target the newly deployed simulator from your local or VPS workers:

`ash
# In your worker configuration or .env:
BOOKING_PORTAL_URL=https://simulator.yourdomain.com
`

**Zero Code Mutation:** The worker code does not need any adjustments. It will seamlessly execute authentication, slot detection, SMS OTP validation, and appointment bookings directly against the simulator.

---

## 7. Useful Operational Commands

`ash
# View real-time simulator container logs
docker logs -f mock-gvc-portal-standalone

# Restart the simulator container
docker compose -f ttttt/cloud-saas/vps-setup/docker-compose-simulator.yml restart

# Flush slots, bookings, and telemetry remotely
curl -X POST https://simulator.yourdomain.com/telemetry/reset
`
