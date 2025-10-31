# CI/CD & Automation

This directory contains documentation for continuous integration, deployment, and automated quality gates.

## =€ Overview

The Trade Engine uses **GitHub Actions** for automated testing, quality checks, and deployment.

## =Ë Available Documentation

- [CI/CD Setup](setup.md) - Quick-start configuration guide
- [GitHub Actions](github-actions.md) - Complete workflow reference

### Coming Soon
- Quality Gates Guide - Detailed explanation of all automated checks

## ™ Automated Workflows

### Continuous Integration (CI)
**Trigger**: Every push and pull request
**File**: `.github/workflows/ci-quality-gate.yml`

**Quality Gates**:
-  Code formatting (Black)
-  Linting (Ruff)
-  Type checking (mypy)
-  Unit tests (pytest)
-  Integration tests (PostgreSQL)
-  Test coverage (80% minimum)
-  Financial code audit (Decimal usage)
-  Risk limit validation
-  Security scanning

**Result**: Code cannot be merged unless ALL checks pass

### Continuous Deployment (CD)
**Trigger**: Merge to main branch
**File**: `.github/workflows/cd-deploy.yml`

**Pipeline**:
1. Re-verify all CI checks
2. Build production Docker images
3. Deploy to staging (automatic)
4. Manual approval gate
5. Deploy to production (after approval)

## =á Safety Features

### Pre-Merge Validation
- No float usage in financial code (NON-NEGOTIABLE)
- Risk limits defined and enforced
- Kill switch implementation verified
- No secrets in code (API keys via environment)

### Deployment Gates
- Staging must pass health checks
- Manual approval required for production
- Rollback plan documented
- Database migrations applied safely

## =' Local CI Simulation

Run the same checks locally before pushing:

```bash
# Format and lint
black src/ tests/
ruff check src/ tests/

# Type check
mypy src/

# Run tests with coverage
pytest --cov=src/trade_engine --cov-report=term-missing -v

# All checks at once
black --check src/ tests/ && \
isort --check-only src/ tests/ && \
ruff check src/ tests/ && \
pytest --cov=src/trade_engine -v
```

## = Related Documentation

- [Development Workflow](../development/workflow.md) - Daily development practices
- [Git Workflow](../development/git-workflow.md) - Branching and PR strategy
- [Deployment Guide](../operations/deployment.md) - Production deployment procedures

## =Ê Quality Metrics

### Coverage Requirements
- Overall: 80% minimum
- Risk management code: 100% required
- Trading logic: 90%+ recommended

### Performance Benchmarks
- Unit tests: <30s
- Integration tests: <2min
- Full CI pipeline: <5min

---

**Last Updated**: 2025-10-31
