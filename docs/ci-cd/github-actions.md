# GitHub Actions Complete Guide for MFT Trading Bot

## Table of Contents
1. [Overview](#overview)
2. [Workflow Architecture](#workflow-architecture)
3. [Setup Instructions](#setup-instructions)
4. [Phase-by-Phase Activation](#phase-by-phase-activation)
5. [Best Practices](#best-practices)
6. [Troubleshooting](#troubleshooting)
7. [Advanced Configuration](#advanced-configuration)

---

## Overview

The MFT trading bot uses GitHub Actions to implement a two-phase CI/CD pipeline that enforces our core principle: **"Move fast and PROVE it works"**.

### Why GitHub Actions?

- **Automated Quality Gates**: No human can be trusted to run tests every time
- **Consistency**: Same checks run for everyone, every time
- **Speed**: Parallel execution of checks (5-10 minute feedback)
- **Security**: Secrets management built-in
- **Cost**: Free for public repos, 2,000 minutes/month for private
- **Integration**: Native GitHub integration (no external services)

### Philosophy

For a financial trading system, we CANNOT afford to deploy bugs. Our pipeline enforces:
- ✅ Code quality through automated linting and formatting
- ✅ Correctness through comprehensive testing
- ✅ Safety through risk-critical code validation
- ✅ Security through dependency audits and secret scanning
- ✅ Reliability through staging validation before production

---

## Workflow Architecture

### Phase 1: Continuous Integration (CI) - Quality Gate

**File**: `.github/workflows/ci-quality-gate.yml`

```yaml
Trigger: Every push or pull request
Purpose: Answer "Is this code safe and high-quality?"
Duration: ~5 minutes
Result: Pass ✅ or Fail ❌ (blocks merge if fails)
```

**Jobs Pipeline**:
```
1. Backend Quality
   ├── Black formatting check
   ├── Ruff linting
   ├── pytest unit tests
   ├── PostgreSQL integration tests
   └── Coverage analysis (80% minimum)

2. Risk-Critical Checks
   ├── Scan for float() in financial code
   ├── Verify risk limits defined
   └── Confirm kill switch exists

3. Frontend Quality
   ├── ESLint checks
   ├── Jest/Vitest tests
   └── Build verification

4. Security Scan
   ├── Python safety check
   ├── npm audit
   └── TruffleHog secret detection

5. Quality Gate Final
   └── All jobs must pass ✅
```

### Phase 2: Continuous Deployment (CD) - Release Engine

**File**: `.github/workflows/cd-deploy.yml`

```yaml
Trigger: Merge to main branch (or manual)
Purpose: Deploy verified code to staging and production
Duration: ~10 minutes
Result: Deployed to staging, awaiting production approval
```

**Deployment Pipeline**:
```
1. Re-verify Quality
   └── Run all CI checks again (never trust)

2. Build Docker Images
   ├── Backend (trading engine)
   ├── API (FastAPI server)
   └── Frontend (React app)
   └── Tag with version, push to registry

3. Deploy to Staging
   ├── SSH to staging VPS
   ├── Pull new images
   ├── docker-compose up
   └── Run smoke tests

4. Deploy to Production ⚠️ MANUAL APPROVAL
   ├── Wait for approval from project lead
   ├── SSH to production VPS
   ├── Pull same images from staging
   ├── docker-compose up
   └── Run health checks
```

---

## Setup Instructions

### Step 1: Enable GitHub Actions

1. Navigate to your repository on GitHub
2. Go to: **Settings** → **Actions** → **General**
3. Under "Actions permissions":
   - Select: **"Allow all actions and reusable workflows"**
4. Under "Workflow permissions":
   - Select: **"Read and write permissions"**
   - Check: **"Allow GitHub Actions to create and approve pull requests"**
5. Click **Save**

### Step 2: Configure Repository Secrets

Navigate to: **Settings** → **Secrets and variables** → **Actions**

Click **"New repository secret"** and add each of these:

#### Staging Environment Secrets (Phase 3+)
```
Name: STAGING_SSH_KEY
Value: [Contents of your staging VPS private SSH key]
```

```
Name: STAGING_HOST
Value: staging.mftbot.example.com (or IP: 192.168.1.100)
```

```
Name: STAGING_USER
Value: ubuntu (or your VPS username)
```

#### Production Environment Secrets (Phase 6+)
```
Name: PRODUCTION_SSH_KEY
Value: [Contents of your production VPS private SSH key]
```

```
Name: PRODUCTION_HOST
Value: mftbot.example.com (or IP: 192.168.1.200)
```

```
Name: PRODUCTION_USER
Value: ubuntu (or your VPS username)
```

#### Optional Notification Secrets
```
Name: DISCORD_WEBHOOK
Value: https://discord.com/api/webhooks/...
```

**Important**: `GITHUB_TOKEN` is automatically provided - do not create it manually

### Step 3: Set Up Branch Protection

Protect your `main` branch to enforce CI checks:

1. Go to: **Settings** → **Branches**
2. Click **"Add rule"** or **"Add branch protection rule"**
3. Branch name pattern: `main`
4. Enable these settings:

```
✅ Require a pull request before merging
   ├── Require approvals: 1
   └── Dismiss stale pull request approvals when new commits are pushed

✅ Require status checks to pass before merging
   ├── Require branches to be up to date before merging
   ├── Status checks that are required:
   │   ├── Backend - Lint & Test
   │   ├── Risk Manager - Extra Validation
   │   └── Quality Gate - PASSED

✅ Require conversation resolution before merging

✅ Do not allow bypassing the above settings
   (Even admins must follow these rules)

✅ Restrict who can push to matching branches
   (Optional: limit to specific team members)
```

5. Click **"Create"** or **"Save changes"**

### Step 4: Test Your Setup

```bash
# Create a test branch
git checkout -b test/ci-setup

# Make a small change
echo "# Testing CI" >> test_ci.txt
git add test_ci.txt
git commit -m "test: Verify CI pipeline works"

# Push and watch GitHub Actions
git push origin test/ci-setup
```

Then:
1. Go to GitHub → **Actions** tab
2. You should see the CI workflow running
3. Click on the workflow run to view logs
4. Verify all checks pass (or see what fails)

---

## Phase-by-Phase Activation

### Phase 0-1: Planning & Screener (Weeks 1-4)

**CI Status**: Partially active
- Formatting checks will run
- Linting will run (but may show warnings)
- Tests will pass with "no tests found" message
- Risk checks will pass with warnings

**What to do**:
- Set up GitHub Actions now
- Configure branch protection
- Get familiar with workflow runs
- Run `./scripts/run-ci-checks.sh` locally

**Expected behavior**: CI passes with warnings ⚠️ (this is OK)

### Phase 2: Engine Development (Weeks 5-10)

**CI Status**: Fully active
- ALL checks must pass ✅
- Test coverage enforced (80% minimum)
- Risk-critical validation active

**What to do**:
- Write tests for all engine components
- Ensure coverage >80%
- Use Decimal (not float) for financial calculations
- Implement risk manager and kill switch

**Expected behavior**: CI must pass completely (no warnings)

### Phase 3: API Server (Weeks 11-12)

**CI Status**: Fully active + CD activates
- All CI checks continue
- CD pipeline begins deploying to staging
- Smoke tests run on staging

**What to do**:
- Configure staging VPS
- Add staging secrets to GitHub
- Test staging deployments
- Verify health check endpoints work

**Expected behavior**: Automatic staging deployments after merge

### Phase 4: UI Development (Weeks 13-14)

**CI Status**: Frontend checks activate
- ESLint checks run
- Frontend tests run
- Build verification active

**What to do**:
- Configure frontend linting
- Write React component tests
- Ensure `npm run build` succeeds

**Expected behavior**: Full-stack CI checks pass

### Phase 5-6: Paper Trading & Micro-Capital (Weeks 15-22)

**CI Status**: Full CI/CD with production gate
- All checks enforced
- Staging deployments automatic
- Production deployments require approval

**What to do**:
- Configure production VPS
- Add production secrets to GitHub
- Test manual approval workflow
- Validate production health checks

**Expected behavior**: Staging automatic, production manual approval

### Phase 7: Production Scaling (Week 23+)

**CI Status**: Mature CI/CD
- Add monitoring integrations
- Add performance benchmarks
- Add canary deployment options

**What to do**:
- Integrate monitoring tools
- Set up alerting (Discord/Slack)
- Consider blue-green deployments

---

## Best Practices

### 1. Local CI Checks First

**Always run local checks before pushing**:

```bash
# Run before every push
./scripts/run-ci-checks.sh

# If it passes locally, it should pass in CI
git push origin your-branch
```

**Why**: Catches issues in seconds instead of waiting 5 minutes for CI

### 2. Commit Message Convention

Use semantic commit messages:

```bash
# Format: <type>: <description>
#
# Types:
#   feat:     New feature
#   fix:      Bug fix
#   refactor: Code restructuring
#   test:     Adding tests
#   docs:     Documentation
#   chore:    Maintenance

# Examples:
git commit -m "feat: Add L2 order book processor with snapshot handling"
git commit -m "fix: Correct imbalance calculation for empty order book"
git commit -m "test: Add integration tests for risk manager kill switch"
git commit -m "refactor: Extract signal validation to separate method"
```

**Why**: Clear history, easier debugging, better changelogs

### 3. Small, Atomic Commits

**DO**:
```bash
git commit -m "feat: Add calculate_imbalance function"
git commit -m "test: Add tests for calculate_imbalance with edge cases"
git commit -m "docs: Document imbalance calculation algorithm"
```

**DON'T**:
```bash
git commit -m "Fixed everything and added tests and updated docs"
```

**Why**: Easier to review, easier to revert, clearer history

### 4. Pull Request Best Practices

**PR Title**: Should be clear and descriptive
```
Good: "Add order book imbalance calculation with 5-level depth"
Bad:  "Updated some files"
```

**PR Description Template**:
```markdown
## What Changed
Brief summary of what this PR does

## Why
Explanation of why this change is needed

## How It Was Tested
- [ ] Unit tests pass locally
- [ ] Integration tests pass locally
- [ ] Manual testing performed
- [ ] CI checks pass

## Checklist
- [ ] Code follows project style guidelines
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No float usage in financial code
- [ ] Risk limits respected
```

### 5. Handling CI Failures

When CI fails:

1. **Don't panic** - CI is helping you catch bugs
2. **Read the logs** - Click "Details" next to failed check
3. **Reproduce locally** - Run `./scripts/run-ci-checks.sh`
4. **Fix the issue** - Address the specific failure
5. **Test locally again** - Verify fix works
6. **Push** - CI will automatically re-run

**Common failures and fixes**:

```bash
# Black formatting failure
black engine/ api/ tests/

# Ruff linting failure
ruff check --fix engine/ api/ tests/

# Test failure
pytest tests/ -v  # See which test failed
# Fix the code or test
pytest tests/test_specific.py  # Re-run specific test

# Coverage failure (below 80%)
pytest --cov=engine --cov-report=term-missing
# Identify uncovered lines and add tests
```

### 6. Security Best Practices

**Never commit secrets**:
```bash
# Check before committing
git diff --cached

# If you see API keys, passwords, etc:
git reset HEAD <file>
# Add to .gitignore
echo ".env" >> .gitignore
```

**Use environment variables**:
```python
# ❌ DON'T
API_KEY = "abc123..."

# ✅ DO
import os
API_KEY = os.getenv('EXCHANGE_API_KEY')
```

**Rotate secrets if exposed**:
1. Revoke the exposed secret immediately
2. Generate new secret
3. Update GitHub Secrets
4. Test that services still work

### 7. Deployment Best Practices

**Before approving production deployment**:

```bash
# Checklist for production approval:
[ ] All CI checks passed
[ ] Staging deployment successful
[ ] Staging smoke tests passed
[ ] Code review completed
[ ] No critical bugs in staging
[ ] Risk-critical code extra reviewed
[ ] Off-hours deployment (if possible)
[ ] Rollback plan prepared
```

**After production deployment**:

```bash
# Monitor for 30 minutes:
[ ] Check error logs
[ ] Verify WebSocket connections
[ ] Confirm trades executing
[ ] Validate P&L tracking
[ ] Test kill switch (in safe way)
[ ] Monitor system health metrics
```

### 8. Emergency Procedures

**If you need to skip CI** (emergencies only):
```bash
git commit -m "hotfix: Critical production bug [skip ci]"
```

**⚠️ WARNING**: This bypasses ALL quality checks. Only use for true emergencies.

**If production deployment fails**:
```bash
# Immediate rollback
ssh $PRODUCTION_USER@$PRODUCTION_HOST
cd /opt/mft-bot
docker-compose down
docker-compose pull <previous-stable-tag>
docker-compose up -d

# Verify
curl http://localhost:8000/health
```

### 9. Monitoring CI/CD Health

**Weekly review**:
```bash
# Check CI success rate
gh run list --workflow=ci-quality-gate.yml --limit=50

# Should be >90% pass rate
# If lower, investigate common failures
```

**Monthly review**:
- Review failed workflow runs
- Identify patterns in failures
- Update CI configuration if needed
- Review and update branch protection rules

---

## Troubleshooting

### Problem: CI Takes Too Long (>10 minutes)

**Diagnosis**:
```bash
# View workflow run times
gh run list --workflow=ci-quality-gate.yml
```

**Solutions**:
1. Check if tests are slow (add `--durations=10` to pytest)
2. Parallelize test execution
3. Use caching for dependencies
4. Optimize database fixtures

### Problem: Tests Pass Locally, Fail in CI

**Common Causes**:
1. **Missing dependency**: Add to `requirements.txt`
2. **Environment difference**: Check Python version
3. **Race condition**: Tests depend on order or timing
4. **Database state**: Tests aren't cleaning up properly

**Debugging**:
```bash
# View full CI logs
gh run view <run-id> --log

# Look for:
# - ImportError (missing dependency)
# - AssertionError (test logic issue)
# - TimeoutError (async race condition)
```

### Problem: Cannot Merge PR (Branch Protection)

**Error**: "Required status check... is expected"

**Solution**:
1. Check which status check is blocking
2. View failed check details
3. Fix the issue
4. Push to your branch (CI re-runs automatically)

### Problem: Production Deployment Hangs

**Cause**: Waiting for manual approval (this is expected)

**Solution**:
1. Go to repository → **Actions**
2. Click the running workflow
3. Look for "Review deployments" button
4. Click **"Approve deployment"**

### Problem: Secrets Not Working

**Symptoms**: SSH connection fails, API calls fail

**Debugging**:
```yaml
# Add to workflow temporarily for debugging:
- name: Debug secrets
  run: |
    echo "Host length: ${#PRODUCTION_HOST}"
    echo "User length: ${#PRODUCTION_USER}"
    # Don't echo actual values!
```

**Common issues**:
- Secret name typo
- Extra whitespace in secret value
- SSH key needs newlines preserved
- Wrong secret set for environment

### Problem: Docker Build Fails

**Error**: "Cannot find Dockerfile"

**Solution**:
```bash
# Verify Dockerfiles exist
ls -la Dockerfile.backend
ls -la Dockerfile.api
ls -la ui/Dockerfile

# If missing, create or update workflow to skip:
continue-on-error: true
```

---

## Advanced Configuration

### Caching Dependencies

Speed up CI by caching dependencies:

```yaml
- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: '3.11'
    cache: 'pip'  # Caches pip packages

- name: Set up Node.js
  uses: actions/setup-node@v4
  with:
    node-version: '18'
    cache: 'npm'  # Caches npm packages
```

### Matrix Testing

Test against multiple Python versions:

```yaml
strategy:
  matrix:
    python-version: ['3.11', '3.12']

steps:
  - uses: actions/setup-python@v5
    with:
      python-version: ${{ matrix.python-version }}
```

### Conditional Workflows

Run different checks based on changed files:

```yaml
- name: Run backend tests
  if: contains(github.event.head_commit.message, 'backend') ||
      contains(github.event.head_commit.modified, 'engine/')
  run: pytest tests/
```

### Deployment Environments

Configure multiple deployment targets:

```yaml
# Add to repository settings:
# Settings → Environments

# Create "staging" environment:
# - No protection rules
# - Auto-deploy

# Create "production" environment:
# - Required reviewers: [list team members]
# - Wait timer: 5 minutes
# - Deployment branches: main only
```

### Notifications

Add Discord/Slack notifications:

```yaml
- name: Notify deployment success
  if: success()
  uses: sarisia/actions-status-discord@v1
  with:
    webhook: ${{ secrets.DISCORD_WEBHOOK }}
    status: Success
    title: "Production Deployment"
    description: "Version ${{ github.sha }} deployed successfully"
```

---

## Quick Reference Commands

```bash
# View all workflows
gh workflow list

# View recent runs
gh run list --limit 20

# View specific workflow runs
gh run list --workflow=ci-quality-gate.yml

# View workflow run details
gh run view <run-id>

# View workflow run logs
gh run view <run-id> --log

# Re-run failed workflow
gh run rerun <run-id>

# Manually trigger workflow
gh workflow run cd-deploy.yml

# Enable/disable workflow
gh workflow enable ci-quality-gate.yml
gh workflow disable ci-quality-gate.yml

# Download workflow artifacts
gh run download <run-id>
```

---

## Resources

- **GitHub Actions Docs**: https://docs.github.com/en/actions
- **Workflow Syntax**: https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions
- **GitHub CLI**: https://cli.github.com/
- **Actions Marketplace**: https://github.com/marketplace?type=actions

---

**Remember**: The CI/CD pipeline is your safety net for a financial trading system. It catches bugs, enforces quality, and protects production. Trust the process, monitor carefully, and never skip validation steps.
