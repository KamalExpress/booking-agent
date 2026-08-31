# System Architecture: SaaS MCP Server Integration (Alamia TOS)

## Purpose
The Model Context Protocol (MCP) Server integration exposes specific, secure control-plane functions directly to external AI Agents (such as Antigravity). By leveraging MCP, AI developers and automated agents can query live worker logs, manipulate staging environments, and construct complex workflows without needing to write throwaway API scripts or query the database manually.

## Architecture
- **Framework:** `fastmcp` (via the official `mcp` Python SDK)
- **Transport Layer:** Server-Sent Events (SSE)
- **Mount Point:** Mounted inside the main FastAPI application at `/mcp`
- **Endpoints:**
  - `GET /mcp/sse` (Event Stream)
  - `POST /mcp/messages` (Message Transport)

## Deployed Environments
- **Dedicated Branch:** `feature/alamia-tos-mcp`
- **Example Public URL (Staging):** `https://keagent-staging.alamiaconnect.com/mcp/sse`

## Available MCP Tools

### 1. `get_workers()`
- **Description:** Returns a real-time list of all registered headless workers in the database, including their capabilities (e.g., `can_scrape`, `can_book`).
- **Use Case:** An AI agent troubleshooting task assignment issues can instantly verify if a capable worker is registered.

### 2. `create_mock_worker(worker_id: str, can_scrape: bool, can_book: bool)`
- **Description:** Instantiates a mock worker node in the database.
- **Use Case:** Used for dry-run testing the `SchedulerService` or `auto_dispatch_queue` logic when no physical workers are currently connected.

### 3. `fetch_agent_monitor_logs()`
- **Description:** Streams the raw stdout/stderr terminal logs from the headless worker containers (located in `worker_logs/*.log`) alongside the last 100 `EventLog` telemetry records.
- **Use Case:** End-to-End monitoring of WAF challenges, OTP flows, and slot detection during live sprint validations.

## How to Configure Your AI Agent (Antigravity)
To grant an AI agent access to these tools, add the following configuration to the agent's MCP setup (e.g., `~/.gemini/config/mcp_config.json`):

```json
{
  "mcpServers": {
    "alamia-tos-saas": {
      "serverUrl": "https://keagent-staging.alamiaconnect.com/mcp/sse"
    }
  }
}
```

Once configured and connected, the agent's internal system prompt will dynamically inherit the tools above, enabling natural language instructions like:
> *"Check the logs to see why the worker crashed."*
> *"Spawn a dummy booker worker for our next test."*

## Security & Scalability Constraints
- **Authentication:** Currently, the SSE mount relies on network-level isolation or basic endpoint obfuscation. Do NOT merge this to `feature/prod` without adding API-Key authentication middleware over the `/mcp` router.
- **Database Locks:** The MCP tools use transient short-lived `SessionLocal()` sessions. Ensure tools handle exceptions properly to prevent dangling DB transactions.

---
*Last Reviewed: Sprint 12 | Owner: Knowledge Manager | Context: Alamia TOS MCP Integration*
