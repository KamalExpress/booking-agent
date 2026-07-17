# Deployment & Compose Topology (Lesson 02)

## Context
During the Staging environment setup, an architectural drift was discovered regarding how Docker Compose stacks are structured for the Kamal Express platform.

The root `docker-compose.yml` file is barebones and only defines the SaaS container. Future agents might incorrectly assume that the workers are manually deployed elsewhere or that the system operates without them.

## The Reality
The platform is designed with a decoupled Control Plane (SaaS) and Execution Plane (Workers). 
While workers *can* be deployed on remote VPS nodes, the standard single-node deployment (used in Production and Staging) spins up all containers within the same stack.

- **Production Topology:** `ttttt/cloud-saas/vps-setup/docker-compose.prod.yml`
- **Staging Topology:** `ttttt/cloud-saas/docker-compose-staging.yml`

Both files contain:
1. `db` (Postgres)
2. `cloud-saas` (Control Plane API)
3. `operator-worker` (Headless Agent)

## The Gotcha: Environment Variables
The headless worker (`ttttt/operator-agent/headless.py`) expects the `SAAS_BASE_URL` environment variable to connect to the Control Plane. 

It **DOES NOT** use `BASE_URL`.

If an agent configures `BASE_URL` inside the docker-compose file for the worker, the worker will silently fail to connect or fallback to a default URL, resulting in an idle worker that never pulls assignments.

## Actions Taken
- `docker-compose-staging.yml` was updated to mirror `docker-compose.prod.yml`.
- `SAAS_BASE_URL` is now explicitly set for the worker.
- `project_context.md` was updated to reflect this topological truth.

---
*Last Reviewed: Sprint 09 | Owner: Knowledge Manager | Confidence: High*
