# Cloud SaaS Production Cost Breakdown

Running a cloud-based booking bot requires more infrastructure than a local desktop app because you are managing the server, database, headless browsers, and captchas on behalf of your tenants.

Here is a breakdown of the estimated monthly costs for running this SaaS MVP.

## 1. Core Infrastructure

| Item | Description | Estimated Monthly Cost |
| :--- | :--- | :--- |
| **VPS (Virtual Private Server)** | To run multiple headless Playwright browsers, you need a server with decent RAM. A minimum of 4 vCPUs and 8GB RAM is recommended. <br><br>• **Hetzner** (CPX31): ~$10/mo (Best Value)<br>• **DigitalOcean / Vultr**: ~$40 - $48/mo | $10.00 - $48.00 |
| **PostgreSQL Database** | Included in the VPS cost if you self-host it via Docker. (Alternatively, a managed database costs ~$15/mo, but is optional). | $0.00 |
| **Domain Name** | Required for SSL and Push Notifications (e.g., `apptsys.samwebdevs.com`). Costs ~$12/year. | $1.00 |

---

## 2. Bot Operations (Variable Costs)

| Item | Description | Estimated Monthly Cost |
| :--- | :--- | :--- |
| **Automated Captcha Solving** | Services like **NopeCha**, **CapSolver**, or **2Captcha** charge roughly $0.80 to $1.50 per 1,000 reCAPTCHA v2 solves.<br><br>If a bot checks slots every 5 minutes (288 times/day = ~8,640 times/month), that's roughly **$8.64 per month, per active bot**. | ~$8.64 (per active bot) |
| **Proxy Network** | Essential for SaaS. If all your tenants scrape from the same VPS IP, the target website will ban your server immediately. You need Datacenter or Residential Proxies (e.g., Webshare, IPRoyal). | $10.00 - $30.00 |

---

## 3. Optional Upgrades

| Item | Description | Estimated Monthly Cost |
| :--- | :--- | :--- |
| **Sentry / Log Management** | Cloud error tracking to know immediately when a tenant's bot crashes. | $0.00 (Free Tier) |
| **Managed DB Backups** | Automated daily database backups to an AWS S3 bucket or DigitalOcean Spaces to ensure you never lose tenant data. | ~$5.00 |

---

### Total Estimated Monthly Cost

For a basic MVP supporting a handful of tenants:
* **Bootstrapped Setup (Hetzner + Free SSL + Self-Hosted DB + 1 Bot)**: **~$30 / month**
* **Premium Setup (DigitalOcean + Managed DB + Proxies + Multiple Bots)**: **~$100+ / month**

> [!TIP]
> Because Captcha costs scale linearly with the number of tenants, you should factor the **$10/month captcha cost** into the subscription fee you charge your clients!
