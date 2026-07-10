# Booking Agent Platform - Setup Guide

This guide provides comprehensive setup instructions for each application within the `bookingagent` project.

---

## 1. Operator Agent (`/operator-agent`)
The Operator Agent is a Python application that uses Playwright for browser automation and can be compiled into a standalone Windows executable.

### Setup Instructions
1. **Navigate to the directory**:
   ```bash
   cd operator-agent
   ```
2. **Environment Configuration**:
   - Copy `.env.example` to `.env`.
   - Fill in your actual credentials, Captcha keys, and applicant data inside the `.env` file. Do NOT commit the `.env` file.
3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
4. **Running Locally (Development)**:
   You can run the mock operator directly using Python:
   ```bash
   python demo-operator.py
   ```
   Or run multiple parallel operators using the batch script:
   ```cmd
   run_parallel.bat [NUMBER_OF_INSTANCES]
   ```
5. **Building the Executable**:
   To compile the agent into a portable Windows application, run:
   ```cmd
   build.bat
   ```
   The output will be generated inside the `dist/appt-monitor` directory.

---

## 2. Cloud SaaS Platform (`/cloud-saas`)
The Cloud SaaS application is a Dockerized service that manages the cloud backend, likely using FastAPI and PostgreSQL.

### Setup Instructions
1. **Navigate to the directory**:
   ```bash
   cd cloud-saas
   ```
2. **Environment & Keys**:
   - The application relies on VAPID keys for push notifications. Ensure `private_key.pem` and `public_key.pem` exist in this directory.
   - Database connection and Secret Keys are passed as environment variables in the Docker Compose file.
3. **Docker Network**:
   The service requires an external Docker network named `sam-agent-platform_default`. Create it if it doesn't exist:
   ```bash
   docker network create sam-agent-platform_default
   ```
4. **Build and Run**:
   Start the services using Docker Compose:
   ```bash
   docker-compose up --build -d
   ```
   The platform will be accessible on `http://localhost:8000`.

---

## 3. Booking Portal (Mock) (`/booking-portal`)
This is a mock Flask-based portal used for testing the operator agent without hitting the live production systems.

### Setup Instructions
1. **Navigate to the directory**:
   ```bash
   cd booking-portal
   ```
2. **Install Dependencies**:
   Ensure you have `flask` and `python-dotenv` installed in your environment.
   ```bash
   pip install flask python-dotenv
   ```
3. **Configuration**:
   This app reads the root `.env` file for configurations like `AVAILABLE_SLOTS`. 
4. **Run the Portal**:
   ```bash
   python mock_portal.py
   ```
   By default, this will start a local Flask development server.

---

## 4. Internal API Portal (`/internal-portal`)
This is an internal API interface built with Flask.

### Setup Instructions
1. **Navigate to the directory**:
   ```bash
   cd internal-portal
   ```
2. **Run the API**:
   ```bash
   python internal_api.py
   ```

---

## General Requirements
- **Python Version**: Ensure Python 3.9+ is installed.
- **Virtual Environment**: It is highly recommended to use the provided virtual environment (`venv`) located in the root directory. Activate it before installing dependencies or running Python scripts:
  ```cmd
  # On Windows
  venv\Scripts\activate
  ```
