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

## 4. Bearer Authentication & Antigravity Agent Configuration

The FastMCP server and `/api/admin/agent-monitor-logs` endpoint are protected by **`MCPAuthMiddleware`**:
- **Environment Variable:** Set `MCP_API_KEY=<secret_key>` in Cloud SaaS `.env` or Portainer stack environment.
- **Header Authentication:** Pass `Authorization: Bearer <secret_key>` on all requests.
- **Query Parameter Fallback:** Alternatively, pass `?api_key=<secret_key>` or `?token=<secret_key>` in the SSE connection URL (ideal for web clients or MCP clients without custom header support).
- **Open Dev Mode:** If `MCP_API_KEY` is unset or empty in the environment, the server operates in open mode for local development.

### Antigravity / MCP Client Configuration Example:

```json
{
  "mcpServers": {
    "alamia-tos-saas": {
      "serverUrl": "https://keagent-staging.alamiaconnect.com/mcp/sse",
      "headers": {
        "Authorization": "Bearer YOUR_MCP_API_KEY"
      }
    }
  }
}
```

Or using query parameter URL:
```json
{
  "mcpServers": {
    "alamia-tos-saas": {
      "serverUrl": "https://keagent-staging.alamiaconnect.com/mcp/sse?api_key=YOUR_MCP_API_KEY"
    }
  }
}
```

---

## 5. Security & Isolation Constraints
- **Staging-First Validation:** The MCP server is developed on `feature/alamia-tos-mcp` and verified on `feature/staging-july2026`.
- **Protected Endpoints:** Both `/mcp` (`GET /mcp/sse`, `POST /mcp/messages`) and `/api/admin/agent-monitor-logs` enforce `MCPAuthMiddleware`.
- **Database Safety:** All MCP tool functions use transient, scoped `SessionLocal()` sessions wrapped in `try ... finally: db.close()` with defensive `getattr()` checks for schema-divergence resilience.
