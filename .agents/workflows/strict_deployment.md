# Strict Deployment Workflow

**Description:** Workflow for deploying changes, particularly enforcing the separation between staging, scalable-arch, and production environments to prevent accidental deployments.

## 1. Verify Deployment Context
- Identify the current branch and the intended target environment.
- **CRITICAL:** The `feature/scalable-arch` branch MUST ONLY be deployed to `scalearch.alamiaconnect.com`. It must never be deployed to staging or production.

## 2. Scalable Architecture Deployment Rules
- Deploy the `feature/scalable-arch` branch using an isolated deployment script (e.g., configuring Portainer or Docker Compose for `scalearch.alamiaconnect.com`).
- **Verification Gate:** The scalable architecture must be verified with AT LEAST TWO different portals.
- **Merge Gate:** Once verified, wait for strict explicit approval from the USER before merging `feature/scalable-arch` into `staging`.

## 3. Staging Deployment Rules
- Any changes affecting the execution plane (auto-booking code, workers, portal interaction) MUST be strictly kept on `staging` first.
- Deploy to staging using `npm run deploy:staging` in the `devops-agent` directory (which uses Portainer CDP).
- **Verification Gate:** The staging deployment must pass End-to-End (E2E) testing and manual verification.

## 4. Production Deployment Rules
- NEVER push or merge into production (`feature/prod` or `main`) unless 100% confidence has been established via staging verification.
- Stop and explicitly ask the user for "Production Merge Approval" before performing any git pushes to the production branch.

## 5. Execution
- Do not execute any deployment commands until you have explicitly confirmed the target environment matches these rules.
