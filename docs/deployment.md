# Deployment Guide

## Overview

The MFT trading bot uses a two-phase CI/CD pipeline via GitHub Actions to ensure extreme reliability and deployment speed.

**Philosophy**: "Move fast and **prove** it works"

## GitHub Actions Workflows

### Phase 1: Continuous Integration (CI) - Quality Gate

**File**: `.github/workflows/ci-quality-gate.yml`

**Triggers**: Every push or pull request to any branch

**Purpose**: Automated quality gate that answers: "Is this code safe and high-quality?"

#### What It Checks

1. **Backend Quality** (Python/FastAPI)
   - Code formatting with `black`
   - Linting with `ruff`
   - Unit and integration tests with `pytest`
   - PostgreSQL integration tests (temporary container)
   - Test coverage minimum 80%

2. **Risk-Critical Validation**
   - Scans for dangerous `float()` usage in financial code
   - Verifies risk limits are defined
   - Confirms kill switch implementation exists

3. **Frontend Quality** (React/TypeScript)
   - Linting with `eslint`
   - Unit tests with `jest`/`vitest`
   - Build verification (`npm run build`)

4. **Security Scanning**
   - Python dependency audit with `safety`
   - Node.js dependency audit with `npm audit`
   - Secret scanning with TruffleHog

**Result**: No code can be merged to `main` unless ALL checks pass.

### Phase 2: Continuous Deployment (CD) - Release Engine

**File**: `.github/workflows/cd-deploy.yml`

**Triggers**: Merge to `main` branch (or manual trigger)

**Purpose**: Automated deployment pipeline that releases verified code to staging and production

#### Deployment Stages

1. **Re-verify Quality**
   - Re-runs all CI checks (never trust a merge)
   - Ensures no last-minute issues

2. **Build Docker Images**
   - Builds production-ready containers:
     - Backend trading engine
     - FastAPI server
     - React frontend
   - Tags with version (e.g., `v1.2.5`)
   - Pushes to GitHub Container Registry

3. **Deploy to Staging**
   - Automatically deploys to staging environment
   - Runs smoke tests (health checks, API endpoints)
   - Validates in production-like environment

4. **Deploy to Production** ⚠️ MANUAL APPROVAL REQUIRED
   - Waits for manual approval from project lead
   - Deploys **exact same images** tested in staging
   - Runs production health checks
   - Sends deployment notifications

## Required GitHub Secrets

Configure these secrets in your GitHub repository settings:

### Staging Environment
```
STAGING_SSH_KEY       - SSH private key for staging VPS
STAGING_HOST          - Staging server hostname/IP
STAGING_USER          - SSH username for staging
```

### Production Environment
```
PRODUCTION_SSH_KEY    - SSH private key for production VPS
PRODUCTION_HOST       - Production server hostname/IP
PRODUCTION_USER       - SSH username for production
```

### Container Registry
```
GITHUB_TOKEN          - Automatically provided by GitHub Actions
```

### Optional (for notifications)
```
DISCORD_WEBHOOK       - Discord webhook URL for deployment notifications
SLACK_WEBHOOK         - Slack webhook URL for alerts
```

## Environment Configuration

### Staging Environment
- **URL**: `https://staging.mftbot.example.com`
- **Purpose**: Pre-production validation
- **Data**: Uses testnet exchange API
- **Configuration**: Identical to production except for API keys

### Production Environment
- **URL**: `https://mftbot.example.com`
- **Purpose**: Live trading
- **Data**: Real exchange API with real capital
- **Configuration**: Production API keys and risk limits

## Manual Approval Process

When deploying to production:

1. GitHub Actions will pause at the "Deploy to Production" job
2. A notification appears in GitHub Actions interface
3. Project lead reviews:
   - Staging deployment success
   - Smoke test results
   - Recent code changes
4. Lead clicks "Approve" or "Reject"
5. If approved, deployment proceeds to production
6. If rejected, deployment stops (no production changes)

## Deployment Checklist

### Before Approving Production Deployment

- [ ] All CI checks passed
- [ ] Staging deployment successful
- [ ] Smoke tests passed on staging
- [ ] No critical bugs reported in staging
- [ ] Code review completed and approved
- [ ] Risk-critical code changes reviewed extra carefully
- [ ] Release notes documented

### After Production Deployment

- [ ] Monitor dashboard for 15-30 minutes
- [ ] Check error logs for anomalies
- [ ] Verify WebSocket connections stable
- [ ] Confirm risk limits enforcing correctly
- [ ] Test kill switch functionality
- [ ] Validate P&L tracking accuracy
- [ ] Check trade execution logs

## Rollback Procedure

If production deployment fails or issues are discovered:

### Quick Rollback (< 5 minutes)

```bash
# SSH into production server
ssh $PRODUCTION_USER@$PRODUCTION_HOST

# Navigate to deployment directory
cd /opt/mft-bot

# Rollback to previous version
docker-compose down
docker-compose pull  # or specify previous tag
docker-compose up -d

# Verify health
curl http://localhost:8000/health
```

### Git-based Rollback

```bash
# Revert the problematic merge commit
git revert <commit-hash>

# Push to main (triggers new deployment)
git push origin main
```

## Docker Image Management

### Image Naming Convention
```
ghcr.io/USERNAME/mft:latest           - Latest main branch
ghcr.io/USERNAME/mft:v1.2.5           - Specific version
ghcr.io/USERNAME/mft:main-abc123      - Main branch with git SHA
ghcr.io/USERNAME/mft-backend:latest   - Backend only
ghcr.io/USERNAME/mft-api:latest       - API server only
ghcr.io/USERNAME/mft-frontend:latest  - Frontend only
```

### Cleanup Old Images

```bash
# List all images
docker images | grep mft

# Remove old versions (keep last 5)
docker image prune -a --filter "until=720h"
```

## Local Testing Before Push

To test changes locally before pushing:

### Backend
```bash
# Run quality checks locally
black --check engine/ api/ tests/
ruff check engine/ api/ tests/
pytest tests/ --cov=engine --cov=api -v

# Test with local PostgreSQL
docker-compose -f docker-compose.test.yml up -d
pytest tests/integration/
docker-compose -f docker-compose.test.yml down
```

### Frontend
```bash
cd ui
npm run lint
npm run test
npm run build
```

### Docker Build Test
```bash
# Test backend image builds
docker build -f Dockerfile.backend -t mft-backend:test .

# Test API image builds
docker build -f Dockerfile.api -t mft-api:test .

# Test frontend image builds
docker build -f ui/Dockerfile -t mft-frontend:test .
```

## Monitoring Deployments

### GitHub Actions Dashboard
- Navigate to: Repository → Actions → Recent workflow runs
- View logs for each job
- Download artifacts (test reports, coverage)

### Deployment Status
- Check staging: `https://staging.mftbot.example.com/health`
- Check production: `https://mftbot.example.com/health`

### Logs
```bash
# View live logs on server
ssh $PRODUCTION_USER@$PRODUCTION_HOST
docker-compose logs -f --tail=100 backend
docker-compose logs -f --tail=100 api
```

## Troubleshooting

### CI Pipeline Failing

**Problem**: Tests fail in GitHub Actions but pass locally

**Solution**:
- Check PostgreSQL service is running in CI
- Verify environment variables are set correctly
- Check for race conditions in async tests
- Review CI logs for missing dependencies

### Deployment Hanging

**Problem**: Deployment job never completes

**Solution**:
- Check SSH key is valid and added to GitHub secrets
- Verify server is accessible (not behind firewall)
- Check disk space on server (`df -h`)
- Verify Docker daemon is running on server

### Production Health Check Fails

**Problem**: Deployment completes but health check returns 500

**Solution**:
- SSH into server and check logs
- Verify database connection string is correct
- Check environment variables are loaded
- Confirm API keys are valid

## Best Practices

1. **Never skip CI**: Always let CI complete before merging
2. **Test locally first**: Run quality checks before pushing
3. **Small, atomic commits**: Easier to rollback if needed
4. **Monitor after deployment**: Watch for 30 minutes minimum
5. **Document incidents**: Keep deployment log up to date
6. **Review before approving**: Don't approve production blindly

## Future Enhancements

### Phase 3 Additions
- [ ] Add end-to-end tests in staging
- [ ] Implement canary deployments (gradual rollout)
- [ ] Add performance benchmarking in CI

### Phase 5 Additions
- [ ] Automated rollback on failure detection
- [ ] Blue-green deployment strategy
- [ ] Database migration automation

### Production Monitoring
- [ ] Integrate Prometheus metrics
- [ ] Set up Grafana dashboards
- [ ] Configure PagerDuty alerts
- [ ] Discord/Slack deployment notifications

## Emergency Contacts

**Deployment Issues**:
- GitHub Actions Support: https://github.com/support
- VPS Provider Support: [Your VPS dashboard]

**System Down**:
1. Check GitHub Actions status
2. Check VPS status page
3. Check exchange API status
4. Trigger kill switch if needed

---

## Quick Reference Commands

```bash
# View workflow runs
gh workflow list
gh run list --workflow=ci-quality-gate.yml

# Manually trigger deployment
gh workflow run cd-deploy.yml

# View workflow logs
gh run view <run-id> --log

# SSH to servers
ssh -i ~/.ssh/staging_key $STAGING_USER@$STAGING_HOST
ssh -i ~/.ssh/production_key $PRODUCTION_USER@$PRODUCTION_HOST

# Check deployment status
curl https://mftbot.example.com/health
curl https://mftbot.example.com/engine/status
```

---

**Remember**: Our philosophy is "move fast and **prove** it works". The CI/CD pipeline is your safety net. Trust the process, monitor carefully, and never skip validation steps.
