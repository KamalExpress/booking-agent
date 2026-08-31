# System Architecture: SaaS MCP Server Integration (Alamia TOS)

## 1. Purpose
The Model Context Protocol (MCP) Server integration exposes specific, secure control-plane functions directly to external AI Agents (such as Antigravity). By leveraging MCP, AI developers and autonomous agents can query live worker logs, inspect database states, trigger test workflows, and troubleshoot live environments in real time without writing throwaway API scripts or executing raw database queries.

## 2. Technical Architecture
- **Framework:** `fastmcp` (via the official `mcp` Python SDK)
- **Transport Layer:** Server-Sent Events (SSE)
- **Mount Point:** Mounted inside the Cloud SaaS FastAPI application at `/mcp`
- **Endpoints:**
  - `GET /mcp/sse` (Event Stream)
  - `POST /mcp/messages` (Message Transport)
- **Code Location:** `ttttt/cloud-saas/app/mcp_server.py` mounted in `ttttt/cloud-saas/app/main.py`
- **Dedicated Branch:** `feature/alamia-tos-mcp`
- **Endpoints:**
  - Staging: `https://keagent-staging.alamiaconnect.com/mcp/sse`
  - Local Dev: `http://localhost:8000/mcp/sse`

---

## 3. Currently Available MCP Tools

### `get_workers()`
- **Description:** Returns a real-time list of all registered headless workers in the database, including their hostnames, status, and capability flags (`can_scrape`, `can_book`).
- **Use Case:** Instantly verify if scrapers and bookers are connected and registered before initiating tests.

### `create_mock_worker(worker_id: str, can_scrape: bool, can_book: bool)`
- **Description:** Registers a mock worker node in the database.
- **Use Case:** Dry-run testing the `SchedulerService`, lease assignment pipeline, and `auto_dispatch_queue` when physical workers are offline.

### `fetch_agent_monitor_logs()`
- **Description:** Streams raw stdout/stderr terminal logs from worker containers (`worker_logs/*.log`) alongside the last 100 `EventLog` telemetry records.
- **Use Case:** Real-time debugging of live slot drops, WAF challenges, OTP flows, and worker crashes.

---

## 4. Antigravity Agent Configuration
To connect Antigravity to the Alamia TOS MCP server, configure the MCP settings (in the agent configuration or MCP config):

```json
{
  "mcpServers": {
    "alamia-tos-saas": {
      "serverUrl": "https://keagent-staging.alamiaconnect.com/mcp/sse"
    }
  }
}
```

---

## 5. Security & Isolation Constraints
- **Staging Only Baseline:** The MCP server is developed on `feature/alamia-tos-mcp` and tested on Staging.
- **Authentication:** Before promoting to production, API-Key / Bearer token authentication middleware must be enforced over `/mcp`.
- **Database Safety:** All MCP tool functions must use transient, scoped `SessionLocal()` sessions wrapped in `try ... finally: db.close()` to prevent database connection leakage.
