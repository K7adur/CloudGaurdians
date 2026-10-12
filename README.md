# CloudGuardians

## Cloud-Based Disaster Recovery and Automated Failover Simulator

### 1. Project Overview

CloudGuardians is a Docker-based disaster recovery simulation demonstrating health monitoring, automatic failover, failback, and application-level database replication between two application regions.

The project uses two Flask applications, two PostgreSQL databases, and a gateway that routes requests to the active region.

**Note:** This is a local Docker simulation. The two regions are not geographically separate cloud deployments.

### 2. Architecture

- **Region 1:** Primary Flask application and PostgreSQL database.
- **Region 2:** Secondary Flask application and PostgreSQL database.
- **Gateway:** Routes requests and monitors primary-region health.
- **Docker Compose:** Runs the applications, databases, networks, and gateway.

### 3. Technologies Used

- Python and Flask
- PostgreSQL
- Docker and Docker Compose
- Terraform
- PowerShell

### 4. Main Features

1. Health checks for both application regions.
2. Automatic failover when the primary region becomes unavailable.
3. Automatic failback after primary-region recovery.
4. Gateway status monitoring.
5. Application-level replication of writes when both regions are reachable.
6. Separate PostgreSQL databases with persistent Docker volumes.

### 5. Prerequisites

- Docker Desktop
- Docker Compose
- Terraform (for the Terraform workflow)
- Windows PowerShell

### 6. Run the Project

Open PowerShell in the project directory.

Build and start the containers:

```powershell
docker compose -f Docker-compose.yml up --build -d
```

Check running containers:

```powershell
docker ps
```

Stop the containers:

```powershell
docker compose -f Docker-compose.yml down
```

### 7. Endpoints

| Endpoint | Purpose |
|---|---|
| `http://localhost:8080/` | Gateway |
| `http://localhost:8080/status` | Active region and monitoring status |
| `http://localhost:8080/write` | Submit a write through the gateway |
| `http://localhost:5001/health` | Primary health check |
| `http://localhost:5002/health` | Secondary health check |
| `http://localhost:5001/data` | Primary database records |
| `http://localhost:5002/data` | Secondary database records |

### 8. Testing

**Health checks**

```powershell
Invoke-RestMethod http://localhost:5001/health
Invoke-RestMethod http://localhost:5002/health
```

Both endpoints should report healthy when their applications and databases are available.

**Failover test**

```powershell
docker stop region1-primary
Start-Sleep -Seconds 10
Invoke-RestMethod http://localhost:8080/status | Format-List
```

The gateway should switch to the secondary region after detecting primary failure.

**Failback test**

```powershell
docker start region1-primary
Start-Sleep -Seconds 10
Invoke-RestMethod http://localhost:8080/status | Format-List
```

The gateway should return to the primary region after successful recovery checks.

**Replication test**

```powershell
Invoke-RestMethod `
  -Uri http://localhost:8080/write `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"message":"Replication verification"}' |
  ConvertTo-Json -Depth 5
```

When both regions are reachable, the expected result is `saved_and_replicated`.

Verify records in both databases:

```powershell
Invoke-RestMethod http://localhost:5001/data
Invoke-RestMethod http://localhost:5002/data
```

### 9. Observed Results

The project has previously demonstrated:

- Successful health checks for both application regions.
- Gateway failover from primary to secondary.
- Gateway failback after primary recovery.
- Application-level replication of writes to both databases when both regions are reachable.

An earlier end-to-end failover test measured approximately 25.96 seconds. This is an observed local test result, not a production recovery-time guarantee.

### 10. Limitations

- The project runs locally in Docker rather than in geographically separate cloud regions.
- Native PostgreSQL streaming replication is not configured.
- Replication may fail if the other region is unavailable during a write.
- Missed records are not automatically reconciled after recovery.
- The prototype does not provide production-grade security or cloud monitoring.

### 11. Future Improvements

- Provision real cloud infrastructure using Terraform.
- Deploy applications across separate cloud regions.
- Implement replication retries and reconciliation.
- Add monitoring, alerting, authentication, and secure configuration.
- Measure recovery time and data loss under repeatable failure scenarios.

### 12. Conclusion

CloudGuardians demonstrates disaster recovery concepts through health monitoring, automated failover, failback, and application-level replication in a local Docker environment. It provides a foundation for future deployment on cloud infrastructure.