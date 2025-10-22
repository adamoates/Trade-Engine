# CI/CD Setup Guide

## Overview

The MFT trading bot implements a robust two-phase CI/CD pipeline using GitHub Actions that enforces our "move fast and **prove** it works" philosophy.

## Quick Start

### 1. Enable GitHub Actions

Ensure GitHub Actions is enabled for your repository:
- Navigate to: Repository → Settings → Actions → General
- Select: "Allow all actions and reusable workflows"
- Save changes

### 2. Configure Required Secrets

Add these secrets in: Repository → Settings → Secrets and variables → Actions

#### Staging Environment (Phase 3+)
```
STAGING_SSH_KEY       - SSH private key for staging VPS
STAGING_HOST          - Staging server hostname/IP
STAGING_USER          - SSH username for staging
```

#### Production Environment (Phase 6+)
```
PRODUCTION_SSH_KEY    - SSH private key for production VPS
PRODUCTION_HOST       - Production server hostname/IP
PRODUCTION_USER       - SSH username for production
```

**Note**: `GITHUB_TOKEN` is automatically provided by GitHub Actions

### 3. Local Development Workflow

Before pushing code:

```bash
# Run local CI checks
./scripts/run-ci-checks.sh

# If all checks pass:
git add .
git commit -m "Your descriptive commit message"
git push origin your-branch
```

## What Happens When You Push

### Phase 1: Continuous Integration (Automatic)

Every push or pull request triggers: `.github/workflows/ci-quality-gate.yml`

**The pipeline will:**

1. **Backend Quality Checks**
   - Format checking with Black
   - Linting with Ruff
   - Unit tests with pytest
   - Integration tests with PostgreSQL
   - Coverage analysis (80% minimum)

2. **Risk-Critical Validation**
   - Scans for `float()` usage in financial code
   - Verifies risk limits are configured
   - Confirms kill switch exists

3. **Frontend Quality Checks** (Phase 4+)
   - ESLint checks
   - Jest/Vitest tests
   - Build verification

4. **Security Scanning**
   - Dependency audits (safety, npm audit)
   - Secret exposure detection (TruffleHog)

**Result**: Green checkmark ✅ or red X ❌ on your PR

### Phase 2: Continuous Deployment (On Merge to Main)

When code is merged to `main`: `.github/workflows/cd-deploy.yml`

**The pipeline will:**

1. **Re-verify Quality**
   - Runs all CI checks again (never trust a merge)

2. **Build Docker Images**
   - Creates production containers
   - Tags with version
   - Pushes to GitHub Container Registry

3. **Deploy to Staging** (Automatic)
   - Deploys to staging environment
   - Runs smoke tests
   - Validates functionality

4. **Deploy to Production** (Manual Approval Required)
   - Pauses for approval
   - Project lead reviews and approves
   - Deploys exact same images tested in staging
   - Runs production health checks

## Branch Protection Rules (Recommended)

Configure branch protection for `main`:

1. Navigate to: Repository → Settings → Branches → Add rule
2. Branch name pattern: `main`
3. Enable:
   - ✅ Require a pull request before merging
   - ✅ Require status checks to pass before merging
     - Select: `Backend - Lint & Test`
     - Select: `Risk Manager - Extra Validation`
   - ✅ Require branches to be up to date before merging
   - ✅ Do not allow bypassing the above settings

This ensures no code reaches `main` without passing all quality gates.

## Development Phases

### Phase 0-1 (Current)
- CI checks will mostly pass with warnings
- No tests yet (expected)
- Focus on code formatting and linting

### Phase 2 (Engine Development)
- All CI checks must pass
- Test coverage required (80%+)
- Risk-critical validation active

### Phase 3 (API Server)
- CD pipeline activates
- Staging deployments begin
- Health checks enforced

### Phase 4 (UI Development)
- Frontend CI checks activate
- Full stack deployments

### Phase 5-6 (Production)
- Production deployments with manual approval
- Full monitoring and alerting

## Troubleshooting

### CI Fails But Works Locally

**Problem**: Tests pass on your machine but fail in GitHub Actions

**Common causes**:
- Missing dependency in requirements.txt
- Environment variable not set in CI
- PostgreSQL connection issue
- Async test race condition

**Solution**:
```bash
# Check CI logs in GitHub Actions
# Look for the specific error
# Fix and push again
```

### Can't Merge PR

**Problem**: GitHub blocks merge with "Required status checks must pass"

**Solution**:
- Click "Details" next to failing check
- Review logs to see what failed
- Fix the issue locally
- Run `./scripts/run-ci-checks.sh`
- Push fix to your branch

### Deployment Hangs

**Problem**: CD workflow stuck at "Waiting for approval"

**Solution**:
- This is expected behavior for production deployments
- Project lead must approve via GitHub Actions UI
- Navigate to: Actions → CD workflow run → Review deployments → Approve

## Best Practices

### Before Starting Work
```bash
# Pull latest changes
git checkout main
git pull

# Create feature branch
git checkout -b feature/your-feature-name
```

### During Development
```bash
# Run checks frequently
./scripts/run-ci-checks.sh

# Fix issues immediately
black engine/ api/ tests/
ruff check --fix engine/ api/ tests/
```

### Before Pushing
```bash
# Final check
./scripts/run-ci-checks.sh

# Commit with descriptive message
git commit -m "feat: Add imbalance calculation with 5-level depth

- Implement calculate_imbalance() function
- Add unit tests with 95% coverage
- Validate against manual calculations
"

# Push
git push origin feature/your-feature-name
```

### Creating PR
1. Go to GitHub repository
2. Click "Compare & pull request"
3. Write clear description explaining:
   - What changed
   - Why it changed
   - How it was tested
4. Request review from team member
5. Wait for CI to pass (green checkmarks)
6. Address any review feedback
7. Merge when approved and CI passes

## Monitoring CI/CD

### View Workflow Runs
```bash
# Using GitHub CLI
gh workflow list
gh run list --workflow=ci-quality-gate.yml
gh run view <run-id> --log
```

### Check Deployment Status
```bash
# Staging
curl https://staging.mftbot.example.com/health

# Production
curl https://mftbot.example.com/health
```

## Cost Considerations

### GitHub Actions Minutes

Free tier: 2,000 minutes/month for public repos, 500 for private

**Estimated usage per push:**
- CI workflow: ~5 minutes
- CD workflow: ~10 minutes

**Monthly estimate (10 pushes/week):**
- 40 pushes × 5 min = 200 minutes
- Well within free tier

### Container Registry Storage

GitHub Container Registry: Free for public repos

**Storage usage:**
- ~500MB per image set
- Keep last 10 versions: ~5GB
- Well within free limits

## Emergency Procedures

### Disable CI Temporarily

If CI is blocking urgent hotfix:

```bash
# Add [skip ci] to commit message
git commit -m "hotfix: Critical bug fix [skip ci]"
```

**WARNING**: Only use for true emergencies. This bypasses all quality checks.

### Rollback Production

If deployment causes issues:

```bash
# SSH into production
ssh $PRODUCTION_USER@$PRODUCTION_HOST

# Rollback Docker containers
cd /opt/mft-bot
docker-compose down
docker-compose pull <previous-version-tag>
docker-compose up -d
```

## Next Steps

1. **Now**: Set up GitHub Actions and secrets
2. **Phase 2**: Add comprehensive tests
3. **Phase 3**: Configure VPS and test deployments
4. **Phase 5**: Enable production deployments
5. **Phase 7**: Add monitoring and alerting integrations

## Resources

- **Workflows**: `.github/workflows/`
- **Deployment docs**: `docs/deployment.md`
- **Local CI script**: `scripts/run-ci-checks.sh`
- **GitHub Actions docs**: https://docs.github.com/en/actions

---

**Remember**: The CI/CD pipeline is your safety net. It catches bugs before they reach production. Trust the process, monitor carefully, and never skip validation steps.
