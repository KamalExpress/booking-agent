# Kamal Express - Test Procedures

## End-to-End Worker Automation Test

This procedure verifies that the distributed worker node correctly registers with the SaaS orchestrator, pulls assignments, and executes the Playwright automation flow locally.

### 1. Prerequisites
- The SaaS orchestrator must be running and deployed (e.g., via Portainer).
- The operator-agent worker environment must be configured with `venv2` containing Playwright dependencies.

### 2. Start the Worker Node
1. Open PowerShell or Command Prompt on the physical execution machine.
2. Navigate to the agent directory:
   ```bash
   cd d:\AI\bookingbot\bookingagent\ttttt\operator-agent
   ```
3. Run the worker GUI:
   ```bash
   venv2\Scripts\python.exe gui.py
   ```
4. Once the GUI opens, click **Start Monitoring**.
5. Log into the SaaS Dashboard and verify that the worker appears under the **Workers** tab with a status of **🟢 Online**.

### 3. Create a Scraper Account
1. Open the SaaS UI and navigate to the **Accounts** tab.
2. Click **+ Add Account**.
3. Provide the VFS Global Username (Email) and Password. Optionally provide a proxy string.
4. Click **Save Account**.

### 4. Dispatch an Assignment
1. Navigate to the **Assignments** tab in the SaaS UI.
2. Click **+ New Assignment**.
3. Select the Scraper Account you just created from the dropdown menu.
4. Set the Target Start Date and Target End Date.
5. Provide the Visa Center ID (e.g., `138`).
6. Click **Create**.
7. The assignment will immediately appear in the table with a status of **Idle**.

### 5. Verify Execution
1. Within 30 seconds of creating the assignment, the local worker node will send an API request to poll for new tasks.
2. The assignment status in the SaaS Dashboard will automatically update to **Leased**, and the `Leased To` column will display your worker's ID.
3. On the local machine running the worker, a Chromium browser will launch, navigate to VFS Global, solve the captcha using CapSolver, and execute the login/scraping sequence.
4. You can monitor live stream logs of this execution on the SaaS UI under the **Event Logs** tab.
