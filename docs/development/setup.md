# MFT Trading Bot - Complete Project Setup Checklist

## Overview

This checklist guides you through setting up the complete MFT trading bot development environment from scratch. Complete each section in order, checking off items as you go.

**Estimated Time**: 2-4 hours for complete setup

---

## Phase 0: Prerequisites (15 minutes)

### Local Machine Setup

- [ ] **Operating System**: macOS, Linux, or WSL2 on Windows
- [ ] **Git installed**: `git --version` (2.30+)
- [ ] **GitHub account** created and configured
- [ ] **SSH key** added to GitHub account
  ```bash
  ssh-keygen -t ed25519 -C "your_email@example.com"
  cat ~/.ssh/id_ed25519.pub  # Add to GitHub
  ```
- [ ] **GitHub CLI** installed (optional but recommended)
  ```bash
  # macOS
  brew install gh

  # Linux
  sudo apt install gh

  # Authenticate
  gh auth login
  ```

### Required Software

- [ ] **Python 3.11+** installed
  ```bash
  python3 --version  # Should be 3.11 or higher

  # macOS
  brew install python@3.11

  # Ubuntu/Debian
  sudo apt install python3.11 python3.11-venv
  ```

- [ ] **pip** updated to latest
  ```bash
  python3 -m pip install --upgrade pip
  ```

- [ ] **Docker Desktop** installed (for local testing)
  ```bash
  docker --version
  docker-compose --version
  ```

- [ ] **Code editor** configured (VS Code recommended)
  - Extensions: Python, Pylance, Docker, GitLens

### Python Development Tools

- [ ] **black** (code formatter)
  ```bash
  pip install black
  ```

- [ ] **ruff** (linter)
  ```bash
  pip install ruff
  ```

- [ ] **pytest** (testing framework)
  ```bash
  pip install pytest pytest-cov pytest-asyncio
  ```

- [ ] **mypy** (type checker) - optional
  ```bash
  pip install mypy
  ```

---

## Phase 1: Repository Setup (20 minutes)

### GitHub Repository

- [ ] **Create repository** on GitHub
  - Name: `mft-trading-bot` (or your preference)
  - Visibility: Private (recommended for trading bot)
  - Initialize with README: Yes
  - Add .gitignore: Python
  - License: MIT or None

- [ ] **Clone repository** locally
  ```bash
  cd ~/Code/Python  # Or your projects directory
  git clone git@github.com:YOUR_USERNAME/mft-trading-bot.git
  cd mft-trading-bot
  ```

- [ ] **Verify remote** is set
  ```bash
  git remote -v
  # Should show origin pointing to your GitHub repo
  ```

### Project Structure

- [ ] **Copy MFT project structure** from setup repository
  ```bash
  # Copy these directories/files:
  .claude/
  .github/
  docs/
  scripts/
  .gitignore
  CLAUDE.md
  ROADMAP.md
  README.md
  ```

- [ ] **Make scripts executable**
  ```bash
  chmod +x scripts/*.sh
  ```

- [ ] **Commit initial structure**
  ```bash
  git add .
  git commit -m "Initial project structure with CI/CD and documentation"
  git push origin main
  ```

---

## Phase 2: GitHub Configuration (30 minutes)

### Enable GitHub Actions

- [ ] Go to: Repository → **Settings** → **Actions** → **General**
- [ ] Select: **"Allow all actions and reusable workflows"**
- [ ] Under Workflow permissions:
  - [ ] Select: **"Read and write permissions"**
  - [ ] Check: **"Allow GitHub Actions to create and approve pull requests"**
- [ ] Click **Save**

### Configure Branch Protection

- [ ] Go to: **Settings** → **Branches** → **Add rule**
- [ ] Branch name pattern: `main`
- [ ] Enable:
  - [ ] **Require a pull request before merging**
    - Require approvals: 1
  - [ ] **Require status checks to pass before merging**
    - Require branches to be up to date
    - Add required checks:
      - `Backend - Lint & Test`
      - `Risk Manager - Extra Validation`
      - `Quality Gate - PASSED`
  - [ ] **Require conversation resolution before merging**
  - [ ] **Do not allow bypassing the above settings**
- [ ] Click **Create** or **Save changes**

### Add Repository Secrets (Skip for now, add in Phase 3+)

*Note: Add these when you have VPS set up*

- [ ] **Staging secrets** (Phase 3):
  - `STAGING_SSH_KEY`
  - `STAGING_HOST`
  - `STAGING_USER`

- [ ] **Production secrets** (Phase 6):
  - `PRODUCTION_SSH_KEY`
  - `PRODUCTION_HOST`
  - `PRODUCTION_USER`

- [ ] **Notification secrets** (optional):
  - `DISCORD_WEBHOOK`

### Test GitHub Actions

- [ ] **Create test branch**
  ```bash
  git checkout -b test/github-actions
  echo "# Testing CI" >> test.txt
  git add test.txt
  git commit -m "test: Verify GitHub Actions workflow"
  git push origin test/github-actions
  ```

- [ ] **Verify workflow runs**
  - Go to: Repository → **Actions** tab
  - You should see "CI - Quality Gate" running
  - Click to view logs
  - Verify it completes (may have warnings, that's OK)

- [ ] **Create pull request**
  - Go to: **Pull requests** → **New pull request**
  - Base: `main`, Compare: `test/github-actions`
  - Create PR and verify status checks appear

- [ ] **Merge or close test PR**
  - Delete test branch after verification

---

## Phase 3: Local Development Environment (45 minutes)

### Python Virtual Environment

- [ ] **Create virtual environment**
  ```bash
  cd ~/Code/Python/mft-trading-bot
  python3 -m venv .venv
  ```

- [ ] **Activate virtual environment**
  ```bash
  # macOS/Linux
  source .venv/bin/activate

  # Windows
  .venv\Scripts\activate

  # Verify
  which python  # Should point to .venv/bin/python
  ```

- [ ] **Create requirements.txt** (starter)
  ```bash
  cat > requirements.txt << EOF
  # Core dependencies
  asyncio
  aiohttp
  websockets
  uvloop

  # Data processing
  pandas
  numpy

  # Database
  psycopg2-binary
  sqlalchemy
  alembic

  # API (Phase 3)
  fastapi
  uvicorn
  pydantic

  # Development
  black
  ruff
  pytest
  pytest-cov
  pytest-asyncio
  mypy
  EOF
  ```

- [ ] **Install dependencies**
  ```bash
  pip install -r requirements.txt
  ```

- [ ] **Verify installation**
  ```bash
  python -c "import asyncio; print('asyncio works')"
  pytest --version
  black --version
  ruff --version
  ```

### VS Code Configuration (Optional)

- [ ] **Create .vscode/settings.json**
  ```json
  {
    "python.defaultInterpreterPath": ".venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.ruffEnabled": true,
    "python.formatting.provider": "black",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.organizeImports": true
    },
    "[python]": {
      "editor.defaultFormatter": "ms-python.black-formatter"
    }
  }
  ```

- [ ] **Add .vscode/ to .gitignore**
  ```bash
  echo ".vscode/" >> .gitignore
  ```

### Project Directories

- [ ] **Create project structure**
  ```bash
  mkdir -p engine/{core,risk,signals,execution}
  mkdir -p api/{routes,schemas,dependencies}
  mkdir -p scanner
  mkdir -p tests/{unit,integration,fixtures}
  mkdir -p config
  mkdir -p logs

  # Create __init__.py files
  touch engine/__init__.py
  touch engine/core/__init__.py
  touch engine/risk/__init__.py
  touch engine/signals/__init__.py
  touch engine/execution/__init__.py
  touch api/__init__.py
  touch scanner/__init__.py
  touch tests/__init__.py
  ```

### Test CI Locally

- [ ] **Run local CI checks**
  ```bash
  ./scripts/run-ci-checks.sh
  ```

- [ ] **Verify script works**
  - Should see colorized output
  - May have warnings (expected in Phase 0)
  - Should not error

---

## Phase 4: Exchange & VPS Setup (Optional - Phase 0+)

### Exchange Account

- [ ] **Create Binance account** (or your chosen exchange)
- [ ] **Enable API access**
- [ ] **Create testnet account**
  - Binance Futures Testnet: https://testnet.binancefuture.com
- [ ] **Generate testnet API keys**
  - Save securely (NOT in code)
- [ ] **Test API connectivity**
  ```bash
  curl https://testnet.binancefuture.com/fapi/v1/ping
  # Should return: {}
  ```

### VPS Setup (Phase 0 - Week 1)

- [ ] **Choose VPS provider**
  - Vultr (recommended)
  - DigitalOcean
  - AWS Lightsail
  - Linode

- [ ] **Provision VPS**
  - OS: Ubuntu 22.04 LTS
  - Size: 2 CPU, 4GB RAM minimum
  - Location: Near exchange servers (NYC for Binance)

- [ ] **SSH access configured**
  ```bash
  ssh root@your-vps-ip
  ```

- [ ] **Test latency to exchange**
  ```bash
  ping -c 10 api.binance.com
  # Target: <50ms average
  ```

- [ ] **Basic VPS hardening**
  ```bash
  # Update system
  apt update && apt upgrade -y

  # Create non-root user
  adduser mftbot
  usermod -aG sudo mftbot

  # Copy SSH key
  mkdir -p /home/mftbot/.ssh
  cp ~/.ssh/authorized_keys /home/mftbot/.ssh/
  chown -R mftbot:mftbot /home/mftbot/.ssh

  # Disable root SSH
  sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
  systemctl restart sshd
  ```

- [ ] **Install Docker on VPS**
  ```bash
  curl -fsSL https://get.docker.com -o get-docker.sh
  sh get-docker.sh
  usermod -aG docker mftbot
  ```

---

## Phase 5: Database Setup (Optional - Phase 2+)

### Local PostgreSQL (Docker)

- [ ] **Create docker-compose.test.yml**
  ```yaml
  version: '3.8'

  services:
    postgres:
      image: postgres:15-alpine
      environment:
        POSTGRES_USER: mft_user
        POSTGRES_PASSWORD: mft_password
        POSTGRES_DB: mft_test
      ports:
        - "5432:5432"
      volumes:
        - postgres_data:/var/lib/postgresql/data

  volumes:
    postgres_data:
  ```

- [ ] **Test local database**
  ```bash
  docker-compose -f docker-compose.test.yml up -d

  # Verify
  docker-compose -f docker-compose.test.yml ps

  # Test connection
  docker-compose -f docker-compose.test.yml exec postgres psql -U mft_user -d mft_test -c "SELECT 1"

  # Stop when done
  docker-compose -f docker-compose.test.yml down
  ```

---

## Phase 6: Documentation Review (15 minutes)

### Read Key Documentation

- [ ] **Read CLAUDE.md** completely
  - Understand project overview
  - Review critical rules
  - Study code patterns

- [ ] **Read ROADMAP.md**
  - Understand 7-phase plan
  - Note current phase
  - Review phase gate requirements

- [ ] **Review docs/guides/**
  - Skim github-actions-guide.md
  - Bookmark for reference

- [ ] **Review project docs in ~/Documents/trader/**
  - Read mft-architecture.md
  - Read mft-strategy-spec.md
  - Skim mft-risk-management.md

### Update Progress Tracking

- [ ] **Update ROADMAP.md Current Status section**
  ```markdown
  ### Current Phase
  Phase: Phase 0 - Infrastructure Setup

  ### Current Week
  Week: Week 1 of 24

  ### Next Milestone
  Target Date: [One week from now]
  Milestone: VPS configured and 24h L2 data recorded
  ```

---

## Phase 7: First Development Task (30 minutes)

### Create First Feature Branch

- [ ] **Create feature branch**
  ```bash
  git checkout -b feature/phase0-infrastructure
  ```

### Write Hello World Test

- [ ] **Create first test file**
  ```python
  # tests/test_hello.py
  def test_hello_world():
      """Verify test framework works"""
      assert True, "Test framework is working"

  def test_imports():
      """Verify core imports work"""
      import asyncio
      import pandas
      import pytest
      assert True, "All imports successful"
  ```

- [ ] **Run test**
  ```bash
  pytest tests/test_hello.py -v
  ```

- [ ] **Check coverage**
  ```bash
  pytest --cov=. tests/test_hello.py
  ```

### Create First Module

- [ ] **Create hello module**
  ```python
  # engine/core/hello.py
  """Hello world module to verify project structure"""

  def greet(name: str) -> str:
      """Return a greeting"""
      return f"Hello, {name}! Welcome to MFT Trading Bot."
  ```

- [ ] **Write test for module**
  ```python
  # tests/unit/test_hello_module.py
  from engine.core.hello import greet

  def test_greet():
      result = greet("Trader")
      assert result == "Hello, Trader! Welcome to MFT Trading Bot."
  ```

- [ ] **Run tests**
  ```bash
  pytest tests/ -v
  ```

### Run Full CI Checks

- [ ] **Run local CI**
  ```bash
  ./scripts/run-ci-checks.sh
  ```

- [ ] **Fix any issues**
  ```bash
  black engine/ tests/
  ruff check --fix engine/ tests/
  ```

### Commit and Push

- [ ] **Commit changes**
  ```bash
  git add .
  git commit -m "feat: Add hello world module and tests

  - Create basic project structure
  - Add first test to verify framework
  - Verify CI pipeline works
  "
  ```

- [ ] **Push to GitHub**
  ```bash
  git push origin feature/phase0-infrastructure
  ```

- [ ] **Create pull request**
  - Go to GitHub
  - Create PR: feature/phase0-infrastructure → main
  - Verify CI passes
  - Merge when ready

---

## Verification Checklist

### Local Environment ✅

- [ ] Python 3.11+ installed and activated
- [ ] All required packages installed
- [ ] Tests run successfully
- [ ] CI checks script works
- [ ] Code formatting works (black)
- [ ] Linting works (ruff)

### GitHub Configuration ✅

- [ ] Repository created and cloned
- [ ] GitHub Actions enabled
- [ ] Branch protection configured
- [ ] CI workflow runs successfully
- [ ] Can create and merge PRs

### Documentation ✅

- [ ] CLAUDE.md reviewed
- [ ] ROADMAP.md reviewed
- [ ] Project documentation reviewed
- [ ] Guides bookmarked for reference

### Ready for Phase 0 ✅

- [ ] Can run tests locally
- [ ] Can push to GitHub
- [ ] CI pipeline works
- [ ] Development workflow understood

---

## Troubleshooting

### Python Version Issues

**Problem**: `python3 --version` shows wrong version

**Solution**:
```bash
# macOS with brew
brew install python@3.11
brew link python@3.11

# Update PATH
export PATH="/usr/local/opt/python@3.11/bin:$PATH"

# Verify
python3.11 --version
```

### Virtual Environment Issues

**Problem**: Can't activate venv

**Solution**:
```bash
# Remove old venv
rm -rf .venv

# Create new venv with specific Python
python3.11 -m venv .venv

# Activate
source .venv/bin/activate
```

### GitHub Actions Not Running

**Problem**: Workflows don't appear in Actions tab

**Solution**:
1. Check if Actions are enabled in repository settings
2. Verify workflow files are in `.github/workflows/`
3. Check workflow YAML syntax is valid
4. Try pushing a commit to trigger workflow

### CI Checks Fail Locally

**Problem**: `./scripts/run-ci-checks.sh` fails

**Solution**:
```bash
# Make script executable
chmod +x scripts/run-ci-checks.sh

# Check bash is available
which bash

# Run with explicit bash
bash scripts/run-ci-checks.sh
```

---

## Next Steps

After completing this checklist:

1. **Phase 0 - Week 1**: Set up VPS and record 24h L2 data
2. **Phase 0 - Week 2**: Validate data quality and connectivity
3. **Phase 1 - Weeks 3-4**: Build instrument screener
4. **Phase 2 - Weeks 5-10**: Develop trading engine

Refer to ROADMAP.md for detailed phase breakdown.

---

**Congratulations!** 🎉

Your MFT trading bot development environment is now fully configured and ready for Phase 0 development.

**Estimated setup time**: 2-4 hours
**Your time**: ______ hours

Record any issues you encountered for future reference.
