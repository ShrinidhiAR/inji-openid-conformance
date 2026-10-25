# MOSIP Inji OpenID Conformance Automation

Automated local execution and CI/CD pipeline integration for MOSIP Inji Certify (OpenID4VCI) and Verify (OpenID4VP) components using the official OpenID Foundation Conformance Suite.

## Prerequisites
* Docker Desktop (with WSL2 Mirrored Mode enabled)
* Python 3.14+ with `requests`

## Quick Start

1. **Start the Conformance Suite & MongoDB:**
   ```powershell
   docker compose -f docker/docker-compose.yml up -d
   ```

2. **Run Certify (Issuer) Conformance Tests:**
   ```powershell
   python scripts/conformance_runner.py --component certify
   ```

3. **Output Artifact:**
   Test results are automatically exported to `conformance-results.json` for integration into TestNG / ExtentReports test rigs.
