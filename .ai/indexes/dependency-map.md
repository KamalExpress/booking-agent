# System Dependency Map

This diagram illustrates the high-level dependencies between major system components.

```mermaid
flowchart TD
    subgraph SaaS["Cloud SaaS (Control Plane)"]
        UI["Tenant / Super Admin UI"]
        API["FastAPI Worker Endpoints"]
        DB[(PostgreSQL Database)]
        Push["Web Push Notifications"]
        
        UI --> DB
        API --> DB
        DB --> Push
    end

    subgraph Worker["Headless Worker (Execution Plane)"]
        Orchestrator["Worker Main Loop"]
        Session["Session Manager (curl_cffi)"]
        Browser["Browser Trust (Playwright)"]
        Captcha["Captcha Service (CapSolver)"]
        
        Orchestrator --> Session
        Orchestrator --> Browser
        Browser --> Captcha
    end

    subgraph Targets["External Targets"]
        VFS["VFS Global / Visa Portals"]
        WAF["Imperva / Cloudflare WAF"]
        
        WAF --> VFS
    end

    %% Cross-boundary connections
    Orchestrator -- "Polls for Assignments / Reports Slots" --> API
    Session -- "Bypasses TLS Fingerprinting" --> WAF
    Browser -- "Solves JS Challenges" --> WAF

```

---
*Last Reviewed: Sprint 09 | Implementation Verified: YES | Owner: Knowledge Manager | Confidence: High*
