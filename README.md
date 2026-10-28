# CloudGuardians
### Multi-Region Disaster Recovery and Failover Simulation

CloudGuardians is a Docker-based project that demonstrates core disaster recovery concepts using two application regions, separate PostgreSQL databases, a gateway/router, application-level data replication, and a web dashboard.

The project simulates a primary-region failure and recovery so that failover behavior can be observed and measured in a local development environment.

> **Deployment note:** This version is a local Docker simulation. It does not deploy resources to AWS or provide real geographic multi-region cloud infrastructure.

## Table of Contents

- [Objectives](#objectives)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Run the Project](#run-the-project)
- [Access the Services](#access-the-services)
- [Verify Health and Status](#verify-health-and-status)
- [Test Data Replication](#test-data-replication)
- [Run a Failover Test](#run-a-failover-test)
- [Frontend Dashboard](#frontend-dashboard)
- [Terraform](#terraform)
- [Monitoring and Logs](#monitoring-and-logs)
- [Troubleshooting](#troubleshooting)
- [Current Limitations](#current-limitations)

## Objectives

- Run primary and secondary application instances in Docker containers.
- Monitor application health through a gateway/router.
- Route application activity to the active region.
- Demonstrate failover when the primary application becomes unavailable.
- Demonstrate recovery when the primary application returns.
- Replicate application records between the primary and secondary databases.
- Provide a dashboard for viewing status and records and submitting writes.
- Record failover test results for review and evaluation.

## Architecture

```text
                         User / Browser
                               |
                 +---------------------------+
                 | Frontend Dashboard        |
                 | http://localhost:3000     |
                 +---------------------------+
                               |
                     Frontend API proxy
                               |
                 +---------------------------+
                 | Gateway / Router          |
                 | http://localhost:8080     |
                 +---------------------------+
                       /               \\
                      /                 \\
         +--------------------+  +--------------------+
         | Primary App        |  | Secondary App      |
         | localhost:5001     |  | localhost:5002     |
         +--------------------+  +--------------------+
                    |                     |
         +--------------------+  +--------------------+
         | Primary PostgreSQL |  | Secondary          |
         | region1-db         |  | PostgreSQL         |
         +--------------------+  +--------------------+
                    \\                     /
                     Application-level replication
```

The router checks application health and uses a failure/recovery threshold to decide when to switch regions. The configured behavior uses three consecutive failed health checks to trigger failover and three consecutive successful checks to trigger recovery/failback.

Data replication is implemented at the application level through the write/replication endpoints. It is not native PostgreSQL streaming replication.

## Technology Stack

- **Python and Flask** — application and gateway services.
- **Docker and Docker Compose** — local containerized environment.
- **PostgreSQL** — separate databases for the primary and secondary applications.
- **HTML, CSS, and JavaScript** — frontend dashboard.
- **Python HTTP server** — serves the frontend and proxies dashboard API requests to the gateway.
- **Terraform** — local orchestration through the project configuration; it does not create cloud infrastructure in this version.

## Project Structure

The main project layout is expected to resemble:

```text
CloudGuardians/
├── docker-compose.yml
├── frontend/
│   ├── server.py
│   └── static/
│       ├── index.html
│       ├── app.js
│       └── style.css
├── region1/
│   └── app/
│       └── app.py
├── region2/
│   └── app/
│       └── app.py
├── router/
│   └── app.py
├── monitoring/
│   ├── failover_test.py
│   ├── rpo_test.py
│   ├── monitor.py
│   └── logs/
├── terraform/
│   └── main.tf
└── README.md
```

File names may differ if the project has been updated. Check the actual folders in your working copy before relying on this illustrative tree.

## Prerequisites

Install and verify the following:

- Docker Desktop with the Docker engine running.
- Docker Compose (included with current Docker Desktop installations).
- Python 3.
- Terraform, if you intend to use the Terraform configuration.

Check the installations:

```powershell
docker --version
docker compose version
python --version
terraform version
```

Terraform is optional if you start the project directly with Docker Compose.

## Run the Project

Open PowerShell and change to the project directory. Update the path if your project is stored elsewhere.

```powershell
cd "C:\Users\JK\OneDrive\Documents\Keerthana\Projects\CloudGuardians"
```

Start the Docker services:

```powershell
docker compose up --build -d
```

Check container status:

```powershell
docker compose ps
```

The project has used these container names:

- `region1-primary`
- `region2-secondary`
- `cloudguardians-gateway`
- `region1-db`
- `region2-db`

If your Compose configuration uses different names, use the names shown by `docker compose ps`.

### Start the frontend

Open a **separate PowerShell window** in the project directory and run:

```powershell
python .\frontend\server.py
```

Keep this terminal open while using the dashboard. Open:

- Frontend dashboard: <http://localhost:3000>
- Gateway status: <http://localhost:8080/status>
- Primary health: <http://localhost:5001/health>
- Secondary health: <http://localhost:5002/health>

The dashboard server binds to `127.0.0.1`, so it is intended for local access on the same computer.

## Access the Services

| Service | Local URL | Purpose |
|---|---|---|
| Frontend dashboard | http://localhost:3000 | Web interface |
| Gateway status | http://localhost:8080/status | Active region and failover status |
| Primary application health | http://localhost:5001/health | Primary app health check |
| Secondary application health | http://localhost:5002/health | Secondary app health check |

The application endpoints are exposed by the local Docker setup. The gateway also provides the application API routes used by the dashboard.

## Verify Health and Status

Run these commands in PowerShell:

```powershell
Invoke-RestMethod http://localhost:5001/health
Invoke-RestMethod http://localhost:5002/health
Invoke-RestMethod http://localhost:8080/status | Format-List
```

Both application health endpoints should report healthy when both applications and their databases are available. The gateway status should identify the currently active region.

Check the dashboard's proxied status endpoint:

```powershell
Invoke-RestMethod http://localhost:3000/api/status
```

## Test Data Replication

### Write through the gateway

This test creates a database record:

```powershell
$body = @{ message = "CloudGuardians replication test" } | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://localhost:8080/write" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

A successful response should include fields such as `active_region`, `replicated_to`, and `saved_record`. When the primary is active and replication succeeds, the response should indicate replication to the secondary.

### Read records through the gateway

```powershell
Invoke-RestMethod http://localhost:8080/data
```

### Test the frontend API

The dashboard server proxies the following endpoints:

```powershell
Invoke-RestMethod http://localhost:3000/api/data
```

To submit a write through the frontend API:

```powershell
$body = @{ message = "Dashboard write test" } | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://localhost:3000/api/write" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

These write commands create real records in the local test databases. Use clearly labelled test messages.

**Replication note:** The databases use independent sequences, so the same replicated message may have different record IDs in each database. Compare the message and other relevant fields rather than assuming the IDs must match.

## Run a Failover Test

> **Warning:** This test intentionally stops the primary application container. Run it only when you are ready to interrupt the primary service.

From the project root:

```powershell
python monitoring/failover_test.py
```

The script stops the primary application, waits for secondary takeover, reports a measured recovery time, and restarts the primary application. The exact result depends on the environment and timing.

After the test, verify recovery:

```powershell
Invoke-RestMethod http://localhost:5001/health
Invoke-RestMethod http://localhost:8080/status | Format-List
```

The primary health endpoint should return to a healthy state after the container restarts. The gateway may need a short period to detect recovery and switch back.

### Understanding the recovery measurements

The failover script's elapsed recovery time and the gateway's `rto_seconds` field are separate measurements. Record each with its source and definition; do not treat them as interchangeable without checking the implementation.

## Frontend Dashboard

The frontend is made up of:

- `frontend/static/index.html` — page structure and dashboard controls.
- `frontend/static/style.css` — dashboard styling.
- `frontend/static/app.js` — client-side interactions and API requests.
- `frontend/server.py` — local HTTP server and API proxy.

The frontend API supports status and data reads and a write endpoint. The server also defines local chaos actions for stopping and starting the primary application:

- `POST /api/chaos/fail-primary`
- `POST /api/chaos/restore-primary`

These actions run Docker commands on the same machine. They require Docker to be installed and accessible to the user running the frontend server. They are destructive to the primary service while the failure test is active, so use them carefully.

The existence of an endpoint does not by itself prove that every dashboard button is connected correctly. Verify the actual browser controls before claiming that all frontend features are complete.

## Terraform

The Terraform configuration in this project is intended for local orchestration through Docker Compose. It does **not** provision AWS resources or establish real geographically separated cloud regions.

Review `terraform/main.tf` before using Terraform. Only run Terraform commands if Terraform is installed and you understand the local actions defined in the configuration.

## Monitoring and Logs

The `monitoring/` directory contains test and monitoring scripts, including:

- `failover_test.py` — automated primary-failure and recovery test.
- `rpo_test.py` — recovery-point/data-loss test, if included in the current project version.
- `monitor.py` — monitoring utility, if included in the current project version.
- `logs/` — generated test output, such as `failover_results.csv`.

Run scripts from the project root so their relative paths resolve correctly. Keep the original CSV results as evidence for project evaluation.

## Troubleshooting

### Docker services are not running

```powershell
docker compose ps
docker compose logs --tail 100
```

If the Docker engine is stopped, start Docker Desktop first.

### A local port is unavailable

Check whether another process is using the required port. Stop only the conflicting process after identifying it.

### Gateway status or API requests fail

Check the gateway logs and both application health endpoints:

```powershell
docker logs cloudguardians-gateway --tail 100
Invoke-RestMethod http://localhost:5001/health
Invoke-RestMethod http://localhost:5002/health
```

If container names differ, use the names shown by `docker compose ps`.

### Dashboard does not open

Make sure the frontend server is running in a separate terminal:

```powershell
python .\frontend\server.py
```

Then open <http://localhost:3000>. Keep the terminal open and inspect its output for errors.

### Frontend writes or chaos controls fail

First test the gateway API directly. If the gateway works but the frontend API fails, check `frontend/server.py`. If the frontend API works but a browser button does not, inspect the corresponding handler in `frontend/static/app.js` and the button in `frontend/static/index.html`.

### Primary does not recover immediately

Allow the router's configured recovery checks to complete, then inspect:

```powershell
Invoke-RestMethod http://localhost:8080/status | Format-List
```

## Current Limitations

- The project is a local simulation, not a production cloud deployment.
- The two regions are represented by local Docker services; they are not geographically isolated.
- Data replication is application-level and best-effort, rather than native PostgreSQL replication. The current design does not provide automatic retry and reconciliation for every failed replication attempt.
- Failover and recovery timings vary with health-check intervals, thresholds, Docker startup time, and test conditions.
- Local chaos actions require Docker access from the computer running the frontend server.
- Production-grade authentication, authorization, secrets management, high availability of the gateway, durable replication guarantees, and cross-region networking are outside the verified scope of this version.

## Project Status

The following behaviors have been verified during local testing:

- Primary and secondary application health endpoints respond successfully when the services are healthy.
- The gateway reports the active region and recovery status.
- Records can be written through the gateway and the frontend API.
- A successful write response has reported replication to the secondary database.
- The automated failover script has completed successfully and restarted the primary application.

Keep the latest terminal outputs and test logs with the project evidence. Re-run the tests after code changes and update this section if the implementation or results change.

---

**CloudGuardians** — a local disaster recovery simulation for demonstrating health monitoring, failover, recovery, and application-level data replication.
