# CLAUDE.md - Python Full-Stack Project Template

> **Version**: 1.0.0
> **Last Updated**: 2025-01-29
> **Template Type**: Python 3.11+ | FastAPI | SQLAlchemy 2.0 | React 19 | PostgreSQL | Linode

---

## Table of Contents

1. [Quick Reference Card](#quick-reference-card)
2. [MCP Server Setup](#mcp-server-setup)
3. [Project Overview](#project-overview)
4. [Tech Stack](#tech-stack)
5. [Project Structure](#project-structure)
6. [Development Setup](#development-setup)
7. [Development Commands](#development-commands)
8. [Environment Variables](#environment-variables)
9. [Database Management](#database-management)
10. [Testing Strategy](#testing-strategy)
11. [Code Style & Patterns](#code-style--patterns)
12. [API Documentation](#api-documentation)
13. [Error Handling](#error-handling)
14. [Performance Optimization](#performance-optimization)
15. [Security Checklist](#security-checklist)
16. [Deployment](#deployment)
17. [CI/CD Pipeline](#cicd-pipeline)
18. [Monitoring & Logging](#monitoring--logging)
19. [Troubleshooting](#troubleshooting)
20. [Contributing Guidelines](#contributing-guidelines)
21. [Changelog](#changelog)

---

## Quick Reference Card

### Most Common Commands

```bash
# 🚀 Start Development
poetry install                          # Install dependencies
poetry shell                           # Activate virtual environment
uvicorn app.main:app --reload         # Start backend (port 8000)
cd frontend && npm run dev            # Start frontend (port 5173)

# 🧪 Testing
pytest                                # Run all tests
pytest --cov                          # With coverage report
pytest -v tests/unit                  # Specific directory
pytest -k "test_user"                 # Match pattern

# 🗄️ Database
alembic revision --autogenerate -m "message"  # Create migration
alembic upgrade head                          # Apply migrations
alembic downgrade -1                          # Rollback one migration

# 🔍 Code Quality
ruff check .                          # Lint code
ruff format .                         # Format code
mypy .                                # Type checking

# 📦 Dependencies
poetry add package                    # Add runtime dependency
poetry add --group dev package        # Add dev dependency
poetry update                         # Update all dependencies

# 🐳 Docker
docker-compose up                     # Start all services
docker-compose up backend             # Start backend only
docker-compose logs -f backend        # Follow backend logs
docker-compose down                   # Stop all services

# 🔧 Debugging
poetry run python -m pdb app/main.py  # Debug with pdb
pytest --pdb                          # Drop into debugger on failure
```

### Key URLs (Development)

| Service | URL | Purpose |
|---------|-----|---------|
| Frontend | http://localhost:5173 | React UI |
| Backend API | http://localhost:8000 | FastAPI server |
| API Docs (Swagger) | http://localhost:8000/docs | Interactive API documentation |
| API Docs (ReDoc) | http://localhost:8000/redoc | Alternative API documentation |
| Database | localhost:5432 | PostgreSQL (not HTTP) |

### Port Configuration 🔧

```bash
# Backend
BACKEND_PORT=8000              # FastAPI server

# Frontend
FRONTEND_PORT=5173             # Vite dev server

# Database
POSTGRES_PORT=5432             # PostgreSQL

# Redis (optional)
REDIS_PORT=6379                # Cache/sessions
```

---

## MCP Server Setup

Model Context Protocol (MCP) servers extend Claude's capabilities. Install them in order of priority.

### Installation Commands

All MCP servers are installed using the Claude CLI:

```bash
# Check if Claude CLI is installed
claude --version

# List installed MCP servers
claude mcp list

# Test a specific server
claude mcp test <server-name>
```

---

### ✅ Essential (Install First)

**Install these immediately for core development workflows.**

#### 1. GitHub Operations
```bash
claude mcp add --npm @modelcontextprotocol/server-github
```
- **Purpose**: Create repos, manage issues, pull requests, branches
- **Setup Time**: ⏱️ 1 min
- **API Key Required**: Yes - [Get GitHub token](https://github.com/settings/tokens) (needs `repo`, `workflow` scopes)
- **Why Essential**: Core to modern development workflow

#### 2. Git Operations
```bash
claude mcp add --npm @modelcontextprotocol/server-git
```
- **Purpose**: Local git operations (commit, branch, merge, status)
- **Setup Time**: ⏱️ 1 min
- **API Key Required**: No
- **Why Essential**: Local version control integration

#### 3. File Operations
```bash
claude mcp add --npm @modelcontextprotocol/server-filesystem
```
- **Purpose**: Read, write, search files with proper permissions
- **Setup Time**: ⏱️ 1 min
- **API Key Required**: No
- **Why Essential**: Safer file operations with permission controls

---

### 🛡️ Security & Quality (Highly Recommended)

**Install these before writing production code.**

#### 4. Security Scanning
```bash
claude mcp add --url https://mcp.socket.dev/
```
- **Purpose**: Scan dependencies for vulnerabilities, malware, typosquatting
- **Setup Time**: ⏱️ 2 min
- **API Key Required**: Yes - [Get Socket.dev API key](https://socket.dev/)
- **Python Note**: Scans both `requirements.txt` and `pyproject.toml` files
- **Why Important**: Catches supply chain attacks before deployment

#### 5. NPM Security (for frontend dependencies)
```bash
claude mcp add --npm mcp-server-npm
```
- **Purpose**: Check npm packages for vulnerabilities
- **Setup Time**: ⏱️ 1 min
- **API Key Required**: No
- **Python Note**: Only relevant if using React/Node.js frontend

---

### 🎨 UI/UX (Install When Building UI)

**Install these when working on the frontend.**

#### 6. Animated Components
```bash
claude mcp add --npm @magicuidesign/mcp
```
- **Purpose**: Pre-built animated React components (copy-paste ready)
- **Setup Time**: ⏱️ 1 min
- **API Key Required**: No
- **Why Useful**: Speeds up UI development with production-ready components

#### 7. Shadcn UI Components
```bash
claude mcp add --npm shadcn-ui-mcp-server
```
- **Purpose**: Shadcn/ui component library integration
- **Setup Time**: ⏱️ 2 min
- **API Key Required**: No
- **Why Useful**: Consistent, accessible component system

#### 8. Figma Design Sync
```bash
claude mcp add --npm @figma/mcp
```
- **Purpose**: Sync designs, extract CSS, export assets from Figma
- **Setup Time**: ⏱️ 5 min
- **API Key Required**: Yes - [Get Figma token](https://www.figma.com/developers/api#access-tokens)
- **Why Useful**: Bridges design-to-code workflow

---

### 🧪 Testing & Automation (Install When Adding Tests)

**Install these when setting up test suites.**

#### 9. Puppeteer Automation
```bash
claude mcp add --npm @modelcontextprotocol/server-puppeteer
```
- **Purpose**: Browser automation for E2E tests
- **Setup Time**: ⏱️ 3 min
- **API Key Required**: No
- **Why Useful**: Legacy browser testing tool

#### 10. Playwright Testing (Recommended)
```bash
claude mcp add --npm @executeautomation/playwright-mcp-server
```
- **Purpose**: Modern web testing with multiple browsers
- **Setup Time**: ⏱️ 5 min
- **API Key Required**: No
- **Why Better**: Faster, more reliable than Puppeteer

---

### 🌐 Web & API Access

**Install these for external data access and web scraping.**

#### 11. HTTP Requests
```bash
claude mcp add --npm @modelcontextprotocol/server-fetch
```
- **Purpose**: Make HTTP requests from Claude
- **Setup Time**: ⏱️ 1 min
- **API Key Required**: No
- **Python Note**: Useful for testing external APIs your FastAPI app integrates with

#### 12. Brave Search
```bash
claude mcp add --npm @modelcontextprotocol/server-brave-search
```
- **Purpose**: Search the web for documentation, Stack Overflow answers
- **Setup Time**: ⏱️ 2 min
- **API Key Required**: Yes - [Get Brave Search API key](https://brave.com/search/api/)
- **Why Useful**: Lookup latest Python/FastAPI documentation

#### 13. Web Scraping
```bash
claude mcp add --npm @mendableai/firecrawl-mcp
```
- **Purpose**: Extract structured data from websites
- **Setup Time**: ⏱️ 5 min
- **API Key Required**: Yes - [Get Firecrawl API key](https://www.firecrawl.dev/)
- **Why Useful**: Gather data for testing, documentation research

#### 14. Browser Automation Cloud
```bash
claude mcp add --npm @browserbasehq/mcp-server-browserbase
```
- **Purpose**: Cloud-based browser automation (no local Chrome needed)
- **Setup Time**: ⏱️ 5 min
- **API Key Required**: Yes - [Get Browserbase API key](https://www.browserbase.com/)
- **Why Useful**: Run E2E tests without local browser setup

---

### 🧠 Productivity

**Install these to enhance Claude's capabilities.**

#### 15. Persistent Memory
```bash
claude mcp add --npm @modelcontextprotocol/server-memory
```
- **Purpose**: Remember context across sessions
- **Setup Time**: ⏱️ 1 min
- **API Key Required**: No
- **Why Useful**: Maintains project-specific context

#### 16. Sequential Thinking
```bash
claude mcp add --npm @modelcontextprotocol/server-sequential-thinking
```
- **Purpose**: Break down complex problems into steps
- **Setup Time**: ⏱️ 1 min
- **API Key Required**: No
- **Why Useful**: Better architectural decisions

---

### 🗄️ Database

**Install these for database operations.**

#### 17. PostgreSQL (Primary) ✅
```bash
claude mcp add --npm @modelcontextprotocol/server-postgres
```
- **Purpose**: Query, inspect, and manage PostgreSQL databases
- **Setup Time**: ⏱️ 2 min
- **API Key Required**: No (uses DATABASE_URL from env)
- **Python Note**: Essential for debugging SQLAlchemy queries
- **Why Essential**: Direct database introspection and debugging

#### 18. SQLite (Optional)
```bash
claude mcp add --npm @modelcontextprotocol/server-sqlite
```
- **Purpose**: Query SQLite databases (useful for testing)
- **Setup Time**: ⏱️ 1 min
- **API Key Required**: No
- **Why Useful**: Fast local testing without PostgreSQL

---

### 📋 Installation Best Practices

**Recommended Installation Order:**

1. **Day 1 (Essential)**: GitHub, Git, Filesystem (5 mins total)
2. **Day 2 (Security)**: Socket.dev security scanning (2 mins)
3. **Week 1 (Frontend)**: MagicUI, Shadcn when building UI (5 mins)
4. **Week 2 (Testing)**: Playwright when writing tests (5 mins)
5. **Week 3 (Database)**: PostgreSQL MCP when debugging queries (2 mins)
6. **As Needed**: Figma, Firecrawl, Browserbase, Brave Search (20 mins total)

**Verification After Installation:**

```bash
# List all installed servers
claude mcp list

# Test a specific server
claude mcp test @modelcontextprotocol/server-github

# Check server status
claude mcp status
```

**Troubleshooting:**

```bash
# Server not working?
claude mcp remove <server-name>
claude mcp add --npm <server-name>

# Clear cache
claude mcp clear-cache

# Reinstall all
claude mcp reinstall
```

---

## Project Overview

🔧 **Customize this section with your project's description.**

**[Project Name]** is a [brief description of what the application does].

**Key Features:**
- Feature 1
- Feature 2
- Feature 3

**Target Users:** [Who is this for?]

**Business Goals:** [What problem does this solve?]

---

## Tech Stack

### Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.11+ | Core language (modern type hints, performance) |
| **FastAPI** | 0.109+ | Async web framework (auto-docs, validation) |
| **SQLAlchemy** | 2.0+ | ORM (async support, modern API) |
| **Alembic** | 1.13+ | Database migrations |
| **Pydantic** | 2.5+ | Data validation (v2 performance boost) |
| **PostgreSQL** | 15+ | Primary database |
| **Redis** | 7+ | Caching, sessions (optional) |
| **Pytest** | 7+ | Testing framework |
| **Ruff** | 0.1+ | Linting & formatting (replaces Black, isort, flake8) |
| **Mypy** | 1.8+ | Static type checking |
| **Poetry** / **UV** | Latest | Dependency management |

### Frontend

| Technology | Version | Purpose |
|------------|---------|---------|
| **React** | 19+ | UI framework (concurrent features) |
| **TypeScript** | 5.3+ | Type safety |
| **Vite** | 5+ | Build tool (fast HMR) |
| **TanStack Query** | 5+ | Server state management |
| **Zustand** | 4+ | Client state management |
| **React Router** | 6+ | Routing |
| **Tailwind CSS** | 3+ | Styling |
| **Shadcn/ui** | Latest | Component library |

### Infrastructure

| Technology | Purpose |
|------------|---------|
| **Docker** | Containerization |
| **docker-compose** | Local development orchestration |
| **Nginx** | Reverse proxy, static file serving |
| **Gunicorn + Uvicorn** | Production ASGI server |
| **PostgreSQL** | Production database |
| **Linode** | Hosting platform |
| **GitHub Actions** | CI/CD pipeline |

### Why These Choices?

**FastAPI over Flask/Django:**
- Native async/await support (better performance)
- Automatic OpenAPI documentation
- Pydantic validation built-in
- Modern Python features (type hints)

**SQLAlchemy 2.0 over 1.4:**
- Better async support
- Improved type hints
- Cleaner API (less magic)

**Pydantic V2 over V1:**
- 5-50x faster validation
- Better error messages
- Improved type inference

**Poetry/UV over pip:**
- Deterministic dependency resolution
- Lockfile for reproducible builds
- Faster installs (UV is 10-100x faster)

**Ruff over Black + isort + flake8:**
- 10-100x faster
- All-in-one tool
- Drop-in replacement

---

## Project Structure

The project follows **Clean Architecture** principles with three distinct layers:

### Three-Layer Architecture

**Layer 1: Domain (Business Logic)** - Pure Python, no external dependencies
- `domain/strategies/` - Trading strategies (alpha generation)
- `domain/risk/` - Risk management logic
- `domain/models/` - Domain models (future use)

**Layer 2: Services (Orchestration)** - Application services that coordinate domain logic
- `services/trading/` - Live trading engine
- `services/backtest/` - Backtesting engine
- `services/data/` - Data aggregation & normalization
- `services/audit/` - Audit logging

**Layer 3: Adapters (Infrastructure)** - External integrations
- `adapters/brokers/` - Broker implementations (Binance, Kraken, etc.)
- `adapters/data_sources/` - Market data providers
- `adapters/feeds/` - Real-time data feeds (L2 order book)

### Complete Directory Structure

```
trade-engine/
├── src/
│   └── trade_engine/
│       ├── adapters/              # External integrations
│       │   ├── brokers/          # Broker implementations
│       │   │   ├── base.py       # Base broker interface (ABC)
│       │   │   ├── binance.py    # Binance Futures
│       │   │   ├── binance_us.py # Binance.us Spot
│       │   │   ├── kraken.py     # Kraken Futures
│       │   │   └── simulated.py  # Paper trading
│       │   ├── data_sources/     # Market data providers
│       │   │   ├── base.py       # Base data source interface
│       │   │   ├── binance.py    # Binance historical data
│       │   │   ├── alphavantage.py
│       │   │   ├── coingecko.py
│       │   │   ├── coinmarketcap.py
│       │   │   └── yahoo.py
│       │   └── feeds/            # Real-time data feeds
│       │       ├── base.py       # Base feed interface
│       │       └── binance_l2.py # L2 order book WebSocket
│       │
│       ├── domain/                # Business logic (pure Python)
│       │   ├── strategies/       # Trading strategies
│       │   │   ├── alpha_l2_imbalance.py    # L2 order book imbalance
│       │   │   ├── alpha_bollinger.py       # Bollinger Bands
│       │   │   ├── alpha_ma_crossover.py    # Moving average crossover
│       │   │   ├── alpha_macd.py            # MACD
│       │   │   ├── alpha_rsi_divergence.py  # RSI divergence
│       │   │   ├── market_regime.py         # Market regime detection
│       │   │   ├── signal_confirmation.py   # Multi-strategy confirmation
│       │   │   ├── asset_class_adapter.py   # Asset class handling
│       │   │   ├── portfolio_equal_weight.py
│       │   │   ├── risk_max_position_size.py
│       │   │   ├── indicator_performance_tracker.py
│       │   │   └── types.py                 # Strategy type definitions
│       │   ├── risk/             # Risk management
│       │   │   └── risk_manager.py          # Kill switch, position limits
│       │   └── models/           # Domain models (future use)
│       │
│       ├── services/              # Application services
│       │   ├── trading/          # Live trading
│       │   │   └── engine.py     # LiveRunner orchestration
│       │   ├── backtest/         # Backtesting
│       │   │   ├── engine.py     # Backtest engine
│       │   │   ├── l2_data_loader.py
│       │   │   └── metrics.py
│       │   ├── data/             # Data services
│       │   │   ├── aggregator.py # Multi-source data aggregation
│       │   │   ├── signal_normalizer.py
│       │   │   ├── web3_signals.py
│       │   │   └── types.py
│       │   └── audit/            # 📊 Audit logging (PRIMARY monitoring)
│       │       └── logger.py     # Structured JSON logging
│       │                         # Logs ALL events: bars, signals, orders, errors
│       │                         # Output: logs/audit_YYYY-MM-DD.jsonl
│       │
│       ├── core/                  # Core configuration
│       │   ├── config/           # YAML configurations
│       │   │   ├── paper.yaml    # Paper trading config
│       │   │   ├── live.yaml.template
│       │   │   └── poc_test.yaml
│       │   ├── types.py          # Shared type definitions (Signal, Position, Bar)
│       │   └── constants.py      # Application constants
│       │
│       ├── api/                   # API layer (Phase 3 - future)
│       │   └── routes/
│       ├── db/                    # Database layer (Phase 2 - future)
│       ├── schemas/               # Pydantic schemas (future use)
│       └── utils/                 # Utility functions (future use)
│
├── tests/                         # Test suite
│   ├── unit/                     # Unit tests (fast, isolated)
│   │   ├── test_broker_binance.py
│   │   ├── test_risk_manager.py
│   │   ├── test_runner_live.py
│   │   ├── test_alpha_*.py      # Strategy tests
│   │   └── ...
│   ├── integration/              # Integration tests
│   └── conftest.py              # Pytest fixtures
│
├── scripts/                       # Utility scripts
│   ├── dev/                      # Development scripts
│   │   ├── update_refactored_imports.py
│   │   ├── fix_test_patches.py
│   │   └── rebrand_imports.py
│   ├── benchmark_performance.py  # Performance benchmarking
│   └── ...
│
├── docs/                          # Documentation
│   ├── guides/                   # Setup and workflow guides
│   ├── architecture.md           # System design
│   ├── trading-strategies.md     # Strategy implementations
│   └── ...
│
├── data/                          # Market data (gitignored)
│   ├── .gitkeep                  # Keeps directory in git
│   ├── *.csv                     # OHLCV data files
│   ├── l2_snapshots/             # L2 order book snapshots
│   └── backtest_data/            # Historical data for backtesting
│
├── logs/                          # 📊 PRIMARY OUTPUT - View results here! (gitignored)
│   ├── audit_YYYY-MM-DD.jsonl    # Structured audit logs (JSON lines)
│   │                             # - Bar events (received, skipped)
│   │                             # - Signal events (generated, blocked)
│   │                             # - Order events (placed, executed)
│   │                             # - Error events (strategy, broker)
│   │                             # - P&L tracking, risk checks, lifecycle
│   └── *.log                     # Other runtime logs
│
├── benchmark_results/             # Performance benchmark data
│   └── *.json                    # Benchmark results
│
├── .github/                       # GitHub configuration
│   └── workflows/
│       └── ci-quality-gate.yml   # CI pipeline
│
├── CLAUDE.md                      # Project instructions for Claude Code
├── README.md                      # Project overview
├── ROADMAP.md                     # Development roadmap
├── pytest.ini                     # Pytest configuration
├── requirements.txt               # Python dependencies
├── pyproject.toml                 # Project metadata & dependencies
├── Dockerfile                     # Docker container definition
├── docker-compose.yml             # Multi-container Docker setup
└── .env.example                   # Environment variables template
│
├── docs/                             # Documentation
│   ├── api.md                       # API documentation
│   ├── architecture.md              # System architecture
│   └── deployment.md                # Deployment guide
│
├── .gitignore                        # Git ignore rules
├── .python-version                   # Python version (pyenv)
├── docker-compose.yml                # Local development setup
├── docker-compose.prod.yml           # Production setup
├── CLAUDE.md                         # This file
└── README.md                         # Project documentation
```

### Key Design Decisions

**Separation of Concerns:**
- **Endpoints**: HTTP layer only (request/response handling)
- **Schemas**: Data validation and serialization
- **Services**: Business logic (reusable across endpoints)
- **Models**: Database representation

**Why This Structure:**
- Testability: Services can be tested without HTTP layer
- Reusability: Business logic shared across endpoints
- Maintainability: Clear boundaries between layers
- Scalability: Easy to add new features

**Alternative Pattern (for small projects):**
```
app/
├── main.py          # All routes in one file
├── models.py        # All models
├── schemas.py       # All schemas
└── database.py      # DB config
```
Use this simpler structure if you have <10 models.

---

## Development Setup

### Prerequisites

- **Python**: 3.11 or higher ([Download](https://www.python.org/downloads/))
- **Node.js**: 20+ and npm 10+ ([Download](https://nodejs.org/))
- **PostgreSQL**: 15+ ([Download](https://www.postgresql.org/download/))
- **Git**: Latest version
- **Poetry** or **UV**: Choose one dependency manager

**Install Poetry:**
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

**Install UV (alternative, faster):**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Tool Comparison:**

| Feature | Poetry | UV | pip + venv |
|---------|--------|----|----|
| Speed | Medium | Very Fast (10-100x) | Slow |
| Lockfile | ✅ Yes | ✅ Yes | ❌ No |
| Dependency Resolution | ✅ Good | ✅ Excellent | ⚠️ Basic |
| PEP 621 Support | ✅ Yes | ✅ Yes | ✅ Yes |
| Maturity | Stable | New (2024) | Legacy |
| **Recommendation** | Production | Modern/Fast | Simple scripts |

---

### Initial Setup

#### 1. Clone Repository
```bash
git clone <repository-url>
cd <project-name>
```

#### 2. Backend Setup (Poetry)

```bash
cd backend

# Install dependencies
poetry install

# Activate virtual environment
poetry shell

# Copy environment variables
cp .env.example .env
# Edit .env with your database credentials

# Initialize database
alembic upgrade head

# (Optional) Seed development data
python scripts/seed_data.py
```

#### 2. Backend Setup (UV - Alternative)

```bash
cd backend

# Install dependencies (creates .venv automatically)
uv sync

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows

# Copy environment variables
cp .env.example .env
# Edit .env with your database credentials

# Initialize database
uv run alembic upgrade head

# (Optional) Seed development data
uv run python scripts/seed_data.py
```

#### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Copy environment variables
cp .env.example .env
# Edit .env with your backend URL (usually http://localhost:8000)
```

#### 4. Database Setup

**Option A: Local PostgreSQL**
```bash
# Create database
createdb myapp_dev

# Update backend/.env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/myapp_dev
```

**Option B: Docker PostgreSQL**
```bash
# Start PostgreSQL container
docker-compose up -d db

# Database URL (already configured in docker-compose.yml)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/myapp_dev
```

#### 5. Verify Setup

```bash
# Backend health check
cd backend
poetry run uvicorn app.main:app --reload
# Visit http://localhost:8000/docs (should see API documentation)

# Frontend dev server
cd frontend
npm run dev
# Visit http://localhost:5173 (should see React app)

# Run tests
cd backend && poetry run pytest
cd frontend && npm test
```

---

### Environment Variables

#### Backend (.env)

🔧 **Customize these values for your project.**

```bash
# Application
PROJECT_NAME="My API"
VERSION="1.0.0"
API_V1_STR="/api/v1"
DEBUG=true
ENVIRONMENT="development"  # development | staging | production

# Server
HOST="0.0.0.0"
PORT=8000
WORKERS=4  # Number of Gunicorn workers (production)

# Database
DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/myapp_dev"
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Security
SECRET_KEY="super-secret-key-change-in-production-use-openssl-rand-hex-32"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS (comma-separated list)
CORS_ORIGINS="http://localhost:5173,http://localhost:3000"

# Redis (optional)
REDIS_URL="redis://localhost:6379/0"

# Email (optional)
SMTP_HOST="smtp.gmail.com"
SMTP_PORT=587
SMTP_USER="your-email@gmail.com"
SMTP_PASSWORD="your-app-password"
SMTP_FROM="noreply@example.com"

# AWS S3 (optional)
AWS_ACCESS_KEY_ID="your-access-key"
AWS_SECRET_ACCESS_KEY="your-secret-key"
AWS_REGION="us-east-1"
AWS_S3_BUCKET="your-bucket-name"

# Logging
LOG_LEVEL="INFO"  # DEBUG | INFO | WARNING | ERROR | CRITICAL
LOG_FORMAT="json"  # json | text

# Sentry (optional)
SENTRY_DSN="https://xxx@sentry.io/xxx"

# Feature Flags
ENABLE_REGISTRATION=true
ENABLE_EMAIL_VERIFICATION=false
```

#### Frontend (.env)

```bash
# API
VITE_API_BASE_URL="http://localhost:8000"
VITE_API_VERSION="v1"

# Environment
VITE_ENVIRONMENT="development"

# Feature Flags
VITE_ENABLE_ANALYTICS=false
VITE_ENABLE_ERROR_TRACKING=false

# External Services
VITE_GOOGLE_ANALYTICS_ID=""
VITE_SENTRY_DSN=""
```

**Loading Environment Variables in Python:**

```python
# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings."""

    # Application
    PROJECT_NAME: str = "My API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 20

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"  # Ignore extra fields
    )

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

settings = get_settings()
```

**Usage:**
```python
from app.core.config import settings

print(settings.DATABASE_URL)
print(settings.DEBUG)
```

---

## Development Commands

### Virtual Environment Management

**Poetry:**
```bash
# Create/install environment
poetry install                    # Install from lockfile
poetry install --no-dev          # Production dependencies only

# Activate environment
poetry shell                     # Start new shell
poetry run python script.py      # Run command in environment

# Add dependencies
poetry add fastapi               # Runtime dependency
poetry add --group dev pytest    # Dev dependency
poetry add --group test coverage # Test dependency

# Update dependencies
poetry update                    # Update all
poetry update fastapi            # Update specific package

# Export requirements
poetry export -f requirements.txt --output requirements.txt
```

**UV (faster alternative):**
```bash
# Create/install environment
uv sync                          # Install from lockfile
uv sync --no-dev                 # Production dependencies only

# Run commands (auto-activates venv)
uv run python script.py          # Run any Python command
uv run pytest                    # Run tests
uv run alembic upgrade head      # Run migrations

# Add dependencies
uv add fastapi                   # Runtime dependency
uv add --dev pytest              # Dev dependency

# Update dependencies
uv sync --upgrade                # Update all
uv sync --upgrade fastapi        # Update specific package

# Export requirements
uv export > requirements.txt
```

---

### Running the Application

**Development Mode:**
```bash
# Backend (with hot reload)
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (with HMR)
cd frontend
npm run dev
```

**Production Mode:**
```bash
# Backend (with Gunicorn + Uvicorn workers)
cd backend
gunicorn app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --access-logfile - \
    --error-logfile -

# Frontend (build and serve)
cd frontend
npm run build
npm run preview  # Test production build locally
```

**Docker (recommended for local development):**
```bash
# Start all services
docker-compose up

# Start specific service
docker-compose up backend

# Rebuild after code changes
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Stop all services
docker-compose down

# Stop and remove volumes (⚠️ deletes database data)
docker-compose down -v
```

---

### Database Commands

**Alembic Migrations:**

```bash
# Create a new migration
alembic revision --autogenerate -m "Add user table"

# Apply migrations
alembic upgrade head              # Apply all pending
alembic upgrade +1                # Apply next migration
alembic upgrade <revision_id>     # Apply up to specific revision

# Rollback migrations
alembic downgrade -1              # Rollback one migration
alembic downgrade base            # Rollback all (⚠️ dangerous)
alembic downgrade <revision_id>   # Rollback to specific revision

# View migration history
alembic history                   # All migrations
alembic current                   # Current revision
alembic show <revision_id>        # Show specific migration

# Other
alembic stamp head                # Mark DB as up-to-date (no changes)
alembic branches                  # Show branch points
```

**Database Inspection:**
```bash
# Connect to database
psql $DATABASE_URL

# Or with docker-compose
docker-compose exec db psql -U postgres myapp_dev

# Common SQL commands
\dt                # List tables
\d users          # Describe table
\l                # List databases
\du               # List users
\q                # Quit
```

**Database Utilities:**
```bash
# Backup database
pg_dump $DATABASE_URL > backup.sql

# Restore database
psql $DATABASE_URL < backup.sql

# Reset database (⚠️ deletes all data)
alembic downgrade base
alembic upgrade head

# Seed development data
poetry run python scripts/seed_data.py
```

---

### Testing Commands

**Pytest:**
```bash
# Run all tests
pytest

# Verbose output
pytest -v

# Run specific test file
pytest tests/unit/test_services.py

# Run specific test function
pytest tests/unit/test_services.py::test_create_user

# Run tests matching pattern
pytest -k "test_user"              # Matches test_user_*
pytest -k "not slow"               # Exclude slow tests

# Coverage report
pytest --cov=app                   # Coverage for app/ directory
pytest --cov=app --cov-report=html # HTML report (opens htmlcov/index.html)
pytest --cov=app --cov-report=term-missing  # Show missing lines

# Stop on first failure
pytest -x

# Drop into debugger on failure
pytest --pdb

# Run only failed tests from last run
pytest --lf

# Run tests in parallel (requires pytest-xdist)
pytest -n auto                     # Auto-detect CPU count
pytest -n 4                        # Use 4 workers

# Markers (requires pytest.ini configuration)
pytest -m "unit"                   # Run only unit tests
pytest -m "integration"            # Run only integration tests
pytest -m "not slow"               # Exclude slow tests
```

**Test with specific environment:**
```bash
# Use test database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/myapp_test pytest
```

**Frontend Tests:**
```bash
cd frontend

# Run all tests
npm test

# Watch mode
npm test -- --watch

# Coverage
npm test -- --coverage

# Update snapshots
npm test -- -u
```

---

### Code Quality Commands

**Ruff (linting & formatting):**
```bash
# Lint code
ruff check .                       # Check all files
ruff check app/                    # Check specific directory
ruff check app/main.py             # Check specific file

# Auto-fix issues
ruff check --fix .                 # Fix auto-fixable issues

# Format code
ruff format .                      # Format all files
ruff format app/                   # Format specific directory

# Check formatting (CI)
ruff format --check .              # Exit 1 if not formatted

# Both lint and format
ruff check --fix . && ruff format .
```

**Mypy (type checking):**
```bash
# Type check all code
mypy .

# Type check specific directory
mypy app/

# Type check with strict mode
mypy --strict app/

# Show error codes
mypy --show-error-codes app/

# Ignore missing imports
mypy --ignore-missing-imports app/
```

**Pre-commit Hooks (recommended):**
```bash
# Install pre-commit
pip install pre-commit

# Install git hooks
pre-commit install

# Run on all files
pre-commit run --all-files

# Update hooks
pre-commit autoupdate
```

**Example `.pre-commit-config.yaml`:**
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

---

## Database Management

### SQLAlchemy 2.0 Patterns

**Database Configuration:**

```python
# app/core/database.py
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker
)
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # Log SQL queries in debug mode
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,  # Verify connections before using
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Don't expire objects after commit
)

# Base model class
class Base(DeclarativeBase):
    pass

# Dependency for FastAPI
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

**Base Model with Common Fields:**

```python
# app/models/base.py
from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

class BaseModel(Base, TimestampMixin):
    """Base model with common fields."""

    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
```

**Example Model:**

```python
# app/models/user.py
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class User(BaseModel):
    """User database model."""

    __tablename__ = "users"

    # Columns
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )
    full_name: Mapped[str | None] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    items: Mapped[list["Item"]] = relationship(
        "Item",
        back_populates="owner",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"
```

**Pydantic Schemas:**

```python
# app/schemas/user.py
from pydantic import BaseModel, EmailStr, Field, ConfigDict

# Base schema with common fields
class UserBase(BaseModel):
    email: EmailStr
    full_name: str | None = None

# Schema for creating user (has password)
class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100)

# Schema for updating user (all fields optional)
class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    password: str | None = Field(None, min_length=8, max_length=100)

# Schema for reading user (from database)
class UserResponse(UserBase):
    id: int
    is_active: bool

    # Pydantic v2: use ConfigDict
    model_config = ConfigDict(from_attributes=True)

# Schema with relationships
class UserWithItems(UserResponse):
    items: list["ItemResponse"] = []
```

**Service Layer (Business Logic):**

```python
# app/services/user.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password

class UserService:
    """User business logic."""

    @staticmethod
    async def create_user(db: AsyncSession, user_in: UserCreate) -> User:
        """Create a new user."""
        # Hash password
        hashed_password = get_password_hash(user_in.password)

        # Create user
        user = User(
            email=user_in.email,
            full_name=user_in.full_name,
            hashed_password=hashed_password
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

        return user

    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
        """Get user by email."""
        result = await db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_users(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100
    ) -> list[User]:
        """Get all users with pagination."""
        result = await db.execute(
            select(User)
            .offset(skip)
            .limit(limit)
            .order_by(User.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def update_user(
        db: AsyncSession,
        user: User,
        user_in: UserUpdate
    ) -> User:
        """Update user."""
        update_data = user_in.model_dump(exclude_unset=True)

        # Hash password if provided
        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(
                update_data.pop("password")
            )

        for field, value in update_data.items():
            setattr(user, field, value)

        await db.commit()
        await db.refresh(user)

        return user

    @staticmethod
    async def delete_user(db: AsyncSession, user: User) -> None:
        """Delete user."""
        await db.delete(user)
        await db.commit()

    @staticmethod
    async def authenticate(
        db: AsyncSession,
        email: str,
        password: str
    ) -> User | None:
        """Authenticate user."""
        user = await UserService.get_user_by_email(db, email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user
```

**API Endpoint:**

```python
# app/api/v1/endpoints/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new user."""
    # Check if user exists
    existing_user = await UserService.get_user_by_email(db, user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )

    # Create user
    user = await UserService.create_user(db, user_in)
    return user

@router.get("/", response_model=list[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """List all users."""
    users = await UserService.get_users(db, skip=skip, limit=limit)
    return users

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get user by ID."""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user

@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update user."""
    # Get user
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Update user
    user = await UserService.update_user(db, user, user_in)
    return user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete user."""
    # Get user
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Delete user
    await UserService.delete_user(db, user)
```

---

### Alembic Migration Patterns

**Create Migration:**
```bash
alembic revision --autogenerate -m "Add user table"
```

**Review Generated Migration:**
```python
# alembic/versions/xxxx_add_user_table.py
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

def downgrade() -> None:
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
```

**Common Migration Operations:**

```python
# Add column
op.add_column('users', sa.Column('phone', sa.String(20), nullable=True))

# Drop column
op.drop_column('users', 'phone')

# Add index
op.create_index('ix_users_phone', 'users', ['phone'])

# Drop index
op.drop_index('ix_users_phone', table_name='users')

# Add unique constraint
op.create_unique_constraint('uq_users_email', 'users', ['email'])

# Add foreign key
op.create_foreign_key(
    'fk_items_owner_id',
    'items', 'users',
    ['owner_id'], ['id'],
    ondelete='CASCADE'
)

# Rename table
op.rename_table('old_name', 'new_name')

# Rename column
op.alter_column('users', 'phone', new_column_name='phone_number')

# Data migration (insert, update, delete)
from sqlalchemy import table, column

users_table = table('users',
    column('id', sa.Integer),
    column('is_active', sa.Boolean)
)

op.execute(
    users_table.update()
    .where(users_table.c.id == 1)
    .values(is_active=True)
)
```

---

## Testing Strategy

### Test Organization

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests (fast, isolated)
│   ├── test_services.py     # Business logic tests
│   ├── test_utils.py        # Utility function tests
│   └── test_security.py     # Security function tests
├── integration/             # Integration tests (DB, external APIs)
│   ├── test_endpoints.py    # API endpoint tests
│   ├── test_database.py     # Database operation tests
│   └── test_auth.py         # Authentication flow tests
└── e2e/                     # End-to-end tests (full user flows)
    └── test_user_flow.py    # Complete user journey tests
```

### Test Fixtures

**conftest.py:**
```python
# tests/conftest.py
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from fastapi.testclient import TestClient
from httpx import AsyncClient
from app.main import app
from app.core.database import Base, get_db
from app.core.config import settings

# Test database URL (use in-memory SQLite for speed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def db_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        pool_pre_ping=True
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(db_engine):
    """Create test database session."""
    AsyncSessionLocal = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with AsyncSessionLocal() as session:
        yield session

@pytest.fixture
def client(db_session):
    """Create test client."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def async_client(db_session):
    """Create async test client."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()

@pytest.fixture
def sample_user():
    """Sample user data for testing."""
    return {
        "email": "test@example.com",
        "full_name": "Test User",
        "password": "testpassword123"
    }
```

### Unit Tests

**Test Services:**
```python
# tests/unit/test_services.py
import pytest
from app.services.user import UserService
from app.schemas.user import UserCreate, UserUpdate
from app.models.user import User

@pytest.mark.asyncio
async def test_create_user(db_session, sample_user):
    """Test creating a new user."""
    user_in = UserCreate(**sample_user)
    user = await UserService.create_user(db_session, user_in)

    assert user.id is not None
    assert user.email == sample_user["email"]
    assert user.full_name == sample_user["full_name"]
    assert user.hashed_password != sample_user["password"]  # Password hashed
    assert user.is_active is True

@pytest.mark.asyncio
async def test_get_user_by_email(db_session, sample_user):
    """Test getting user by email."""
    # Create user
    user_in = UserCreate(**sample_user)
    created_user = await UserService.create_user(db_session, user_in)

    # Get user by email
    user = await UserService.get_user_by_email(db_session, sample_user["email"])

    assert user is not None
    assert user.id == created_user.id
    assert user.email == sample_user["email"]

@pytest.mark.asyncio
async def test_get_user_by_email_not_found(db_session):
    """Test getting non-existent user by email."""
    user = await UserService.get_user_by_email(db_session, "nonexistent@example.com")
    assert user is None

@pytest.mark.asyncio
async def test_update_user(db_session, sample_user):
    """Test updating user."""
    # Create user
    user_in = UserCreate(**sample_user)
    user = await UserService.create_user(db_session, user_in)

    # Update user
    update_data = UserUpdate(full_name="Updated Name")
    updated_user = await UserService.update_user(db_session, user, update_data)

    assert updated_user.full_name == "Updated Name"
    assert updated_user.email == sample_user["email"]  # Email unchanged

@pytest.mark.asyncio
async def test_authenticate_success(db_session, sample_user):
    """Test successful authentication."""
    # Create user
    user_in = UserCreate(**sample_user)
    await UserService.create_user(db_session, user_in)

    # Authenticate
    user = await UserService.authenticate(
        db_session,
        sample_user["email"],
        sample_user["password"]
    )

    assert user is not None
    assert user.email == sample_user["email"]

@pytest.mark.asyncio
async def test_authenticate_wrong_password(db_session, sample_user):
    """Test authentication with wrong password."""
    # Create user
    user_in = UserCreate(**sample_user)
    await UserService.create_user(db_session, user_in)

    # Authenticate with wrong password
    user = await UserService.authenticate(
        db_session,
        sample_user["email"],
        "wrongpassword"
    )

    assert user is None

@pytest.mark.asyncio
async def test_authenticate_nonexistent_user(db_session):
    """Test authentication with non-existent user."""
    user = await UserService.authenticate(
        db_session,
        "nonexistent@example.com",
        "password"
    )

    assert user is None
```

### Integration Tests

**Test API Endpoints:**
```python
# tests/integration/test_endpoints.py
import pytest
from fastapi import status

@pytest.mark.asyncio
async def test_create_user_success(async_client, sample_user):
    """Test creating user via API."""
    response = await async_client.post("/api/v1/users/", json=sample_user)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == sample_user["email"]
    assert data["full_name"] == sample_user["full_name"]
    assert "id" in data
    assert "password" not in data  # Password not in response
    assert "hashed_password" not in data

@pytest.mark.asyncio
async def test_create_user_duplicate_email(async_client, sample_user):
    """Test creating user with duplicate email."""
    # Create first user
    await async_client.post("/api/v1/users/", json=sample_user)

    # Try to create duplicate
    response = await async_client.post("/api/v1/users/", json=sample_user)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already exists" in response.json()["detail"]

@pytest.mark.asyncio
async def test_create_user_invalid_email(async_client, sample_user):
    """Test creating user with invalid email."""
    sample_user["email"] = "invalid-email"
    response = await async_client.post("/api/v1/users/", json=sample_user)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

@pytest.mark.asyncio
async def test_list_users(async_client, sample_user):
    """Test listing users."""
    # Create users
    await async_client.post("/api/v1/users/", json=sample_user)
    await async_client.post("/api/v1/users/", json={
        **sample_user,
        "email": "another@example.com"
    })

    # List users
    response = await async_client.get("/api/v1/users/")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 2

@pytest.mark.asyncio
async def test_get_user(async_client, sample_user):
    """Test getting user by ID."""
    # Create user
    create_response = await async_client.post("/api/v1/users/", json=sample_user)
    user_id = create_response.json()["id"]

    # Get user
    response = await async_client.get(f"/api/v1/users/{user_id}")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == user_id
    assert data["email"] == sample_user["email"]

@pytest.mark.asyncio
async def test_get_user_not_found(async_client):
    """Test getting non-existent user."""
    response = await async_client.get("/api/v1/users/999")

    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.asyncio
async def test_update_user(async_client, sample_user):
    """Test updating user."""
    # Create user
    create_response = await async_client.post("/api/v1/users/", json=sample_user)
    user_id = create_response.json()["id"]

    # Update user
    update_data = {"full_name": "Updated Name"}
    response = await async_client.patch(f"/api/v1/users/{user_id}", json=update_data)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["full_name"] == "Updated Name"
    assert data["email"] == sample_user["email"]  # Email unchanged

@pytest.mark.asyncio
async def test_delete_user(async_client, sample_user):
    """Test deleting user."""
    # Create user
    create_response = await async_client.post("/api/v1/users/", json=sample_user)
    user_id = create_response.json()["id"]

    # Delete user
    response = await async_client.delete(f"/api/v1/users/{user_id}")

    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify user deleted
    get_response = await async_client.get(f"/api/v1/users/{user_id}")
    assert get_response.status_code == status.HTTP_404_NOT_FOUND
```

### E2E Tests

**Test Complete User Flow:**
```python
# tests/e2e/test_user_flow.py
import pytest
from fastapi import status

@pytest.mark.asyncio
async def test_complete_user_flow(async_client):
    """Test complete user registration and login flow."""
    # 1. Register user
    register_data = {
        "email": "newuser@example.com",
        "full_name": "New User",
        "password": "securepassword123"
    }
    register_response = await async_client.post("/api/v1/users/", json=register_data)
    assert register_response.status_code == status.HTTP_201_CREATED
    user = register_response.json()

    # 2. Login
    login_data = {
        "username": register_data["email"],
        "password": register_data["password"]
    }
    login_response = await async_client.post("/api/v1/auth/login", data=login_data)
    assert login_response.status_code == status.HTTP_200_OK
    tokens = login_response.json()
    access_token = tokens["access_token"]

    # 3. Access protected resource
    headers = {"Authorization": f"Bearer {access_token}"}
    me_response = await async_client.get("/api/v1/auth/me", headers=headers)
    assert me_response.status_code == status.HTTP_200_OK
    assert me_response.json()["email"] == register_data["email"]

    # 4. Update profile
    update_data = {"full_name": "Updated User"}
    update_response = await async_client.patch(
        f"/api/v1/users/{user['id']}",
        json=update_data,
        headers=headers
    )
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["full_name"] == "Updated User"

    # 5. Logout (if implemented)
    logout_response = await async_client.post("/api/v1/auth/logout", headers=headers)
    assert logout_response.status_code == status.HTTP_200_OK
```

### Test Configuration

**pytest.ini:**
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
markers =
    unit: Unit tests (fast, isolated)
    integration: Integration tests (DB, external APIs)
    e2e: End-to-end tests (full user flows)
    slow: Slow tests (> 1 second)
addopts =
    -v
    --strict-markers
    --tb=short
    --cov=app
    --cov-report=term-missing
    --cov-report=html
    --cov-fail-under=80
```

**Coverage Configuration (.coveragerc):**
```ini
[run]
source = app
omit =
    */tests/*
    */migrations/*
    */__pycache__/*
    */venv/*
    */.venv/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstractmethod
```

---

## Code Style & Patterns

### FastAPI Patterns

**Application Factory:**
```python
# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.router import api_router

def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(api_router, prefix=settings.API_V1_STR)

    # Health check
    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}

    return app

app = create_app()
```

**Router Aggregation:**
```python
# app/api/v1/router.py
from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, items

api_router = APIRouter()

api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(items.router, prefix="/items", tags=["items"])
```

**Dependency Injection:**
```python
# app/api/v1/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt
from app.core.config import settings
from app.core.database import get_db
from app.services.user import UserService
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await UserService.get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception

    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

async def get_current_superuser(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current superuser."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions"
        )
    return current_user
```

**Using Dependencies:**
```python
# app/api/v1/endpoints/items.py
from fastapi import APIRouter, Depends
from app.api.v1.dependencies import get_current_active_user
from app.models.user import User

router = APIRouter()

@router.get("/items/me")
async def read_own_items(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user's items."""
    return {"items": current_user.items}
```

### Security Patterns

**Password Hashing:**
```python
# app/core/security.py
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash password."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    return encoded_jwt
```

**Authentication Endpoint:**
```python
# app/api/v1/endpoints/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
from app.core.database import get_db
from app.core.security import create_access_token
from app.core.config import settings
from app.services.user import UserService

router = APIRouter(prefix="/auth")

@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """Login and get access token."""
    # Authenticate user
    user = await UserService.authenticate(
        db,
        email=form_data.username,
        password=form_data.password
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.get("/me")
async def read_users_me(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user."""
    return current_user
```

### Async Patterns

**When to Use Async:**

✅ **Use async when:**
- Making database queries
- Calling external APIs
- Reading/writing files
- WebSocket connections
- Any I/O-bound operations

❌ **Don't use async when:**
- Doing CPU-intensive computations
- No I/O operations involved

**Async Database Queries:**
```python
# ✅ Good: Async query
async def get_users(db: AsyncSession) -> list[User]:
    result = await db.execute(select(User))
    return list(result.scalars().all())

# ❌ Bad: Blocking query
def get_users(db: Session) -> list[User]:
    return db.query(User).all()  # Blocks event loop
```

**Async External API Calls:**
```python
import httpx

# ✅ Good: Async HTTP client
async def fetch_data(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()

# ❌ Bad: Blocking HTTP client
import requests

def fetch_data(url: str) -> dict:
    response = requests.get(url)  # Blocks event loop
    return response.json()
```

**Async Background Tasks:**
```python
from fastapi import BackgroundTasks

async def send_email(email: str, message: str):
    """Send email asynchronously."""
    # Simulated async email sending
    await asyncio.sleep(2)
    print(f"Email sent to {email}: {message}")

@router.post("/users/")
async def create_user(
    user_in: UserCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Create user and send welcome email."""
    user = await UserService.create_user(db, user_in)

    # Add background task
    background_tasks.add_task(
        send_email,
        user.email,
        "Welcome to our platform!"
    )

    return user
```

---

## API Documentation

FastAPI automatically generates interactive API documentation at:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/api/v1/openapi.json

### Customizing API Docs

**Add Response Models:**
```python
from fastapi import APIRouter, status
from app.schemas.user import UserResponse, UserCreate

router = APIRouter()

@router.post(
    "/users/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
    description="Create a new user with email and password",
    response_description="The created user"
)
async def create_user(user_in: UserCreate):
    """
    Create a new user with the following information:

    - **email**: User email address (must be unique)
    - **full_name**: User's full name (optional)
    - **password**: User password (min 8 characters)

    Returns the created user with ID and timestamps.
    """
    pass
```

**Add Response Examples:**
```python
from fastapi import APIRouter
from app.schemas.user import UserResponse

router = APIRouter()

@router.post(
    "/users/",
    response_model=UserResponse,
    responses={
        201: {
            "description": "User created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "email": "user@example.com",
                        "full_name": "John Doe",
                        "is_active": True
                    }
                }
            }
        },
        400: {
            "description": "User with this email already exists",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "User with this email already exists"
                    }
                }
            }
        }
    }
)
async def create_user(user_in: UserCreate):
    pass
```

**Add Tags and Metadata:**
```python
from fastapi import FastAPI

app = FastAPI(
    title="My API",
    description="A comprehensive API for managing users and items",
    version="1.0.0",
    terms_of_service="https://example.com/terms",
    contact={
        "name": "API Support",
        "url": "https://example.com/support",
        "email": "support@example.com"
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT"
    },
    openapi_tags=[
        {
            "name": "auth",
            "description": "Authentication and authorization"
        },
        {
            "name": "users",
            "description": "User management operations"
        },
        {
            "name": "items",
            "description": "Item CRUD operations"
        }
    ]
)
```

---

## Error Handling

### Custom Exceptions

```python
# app/exceptions.py
from fastapi import HTTPException, status

class BaseAPIException(HTTPException):
    """Base exception for API errors."""

    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=status_code, detail=detail)

class NotFoundException(BaseAPIException):
    """Resource not found."""

    def __init__(self, resource: str, identifier: str | int):
        super().__init__(
            detail=f"{resource} with id {identifier} not found",
            status_code=status.HTTP_404_NOT_FOUND
        )

class ConflictException(BaseAPIException):
    """Resource conflict (e.g., duplicate)."""

    def __init__(self, detail: str):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_409_CONFLICT
        )

class UnauthorizedException(BaseAPIException):
    """Unauthorized access."""

    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_401_UNAUTHORIZED
        )

class ForbiddenException(BaseAPIException):
    """Forbidden access."""

    def __init__(self, detail: str = "Not enough permissions"):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_403_FORBIDDEN
        )

class ValidationException(BaseAPIException):
    """Validation error."""

    def __init__(self, detail: str):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )
```

### Exception Handlers

```python
# app/main.py
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError
from app.exceptions import BaseAPIException

app = FastAPI()

@app.exception_handler(BaseAPIException)
async def api_exception_handler(request: Request, exc: BaseAPIException):
    """Handle custom API exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": exc.errors()
        }
    )

@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Handle database integrity errors."""
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "Database integrity error"}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions."""
    # Log the error
    print(f"Unhandled exception: {exc}")

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )
```

### Using Exceptions

```python
# app/api/v1/endpoints/users.py
from app.exceptions import NotFoundException, ConflictException

@router.get("/{user_id}")
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """Get user by ID."""
    user = await UserService.get_user_by_id(db, user_id)

    if not user:
        raise NotFoundException("User", user_id)

    return user

@router.post("/")
async def create_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """Create user."""
    # Check if email exists
    existing_user = await UserService.get_user_by_email(db, user_in.email)
    if existing_user:
        raise ConflictException("User with this email already exists")

    user = await UserService.create_user(db, user_in)
    return user
```

---

## Performance Optimization

### Database Optimization

**Connection Pooling:**
```python
# app/core/database.py
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=20,          # Number of persistent connections
    max_overflow=10,       # Additional connections if pool full
    pool_pre_ping=True,    # Verify connections before using
    pool_recycle=3600,     # Recycle connections after 1 hour
)
```

**Query Optimization:**
```python
# ✅ Good: Select specific columns
from sqlalchemy import select

async def get_user_emails(db: AsyncSession) -> list[str]:
    result = await db.execute(
        select(User.email)
    )
    return list(result.scalars().all())

# ❌ Bad: Select all columns
async def get_user_emails(db: AsyncSession) -> list[str]:
    result = await db.execute(select(User))
    users = result.scalars().all()
    return [user.email for user in users]
```

**Eager Loading (N+1 Prevention):**
```python
from sqlalchemy.orm import selectinload

# ✅ Good: Eager load relationships
async def get_users_with_items(db: AsyncSession) -> list[User]:
    result = await db.execute(
        select(User).options(selectinload(User.items))
    )
    return list(result.scalars().all())

# ❌ Bad: Lazy loading (N+1 queries)
async def get_users_with_items(db: AsyncSession) -> list[User]:
    result = await db.execute(select(User))
    users = list(result.scalars().all())
    for user in users:
        _ = user.items  # Triggers separate query for each user
    return users
```

**Pagination:**
```python
@router.get("/users/")
async def list_users(
    skip: int = 0,
    limit: int = 100,  # Max 100 per page
    db: AsyncSession = Depends(get_db)
):
    """List users with pagination."""
    result = await db.execute(
        select(User)
        .offset(skip)
        .limit(min(limit, 100))  # Enforce max limit
        .order_by(User.created_at.desc())
    )
    users = list(result.scalars().all())
    return users
```

### Caching

**Redis Caching:**
```python
# app/core/cache.py
import redis.asyncio as redis
from functools import wraps
import json

redis_client = redis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True
)

def cache(expire: int = 300):
    """Cache decorator."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"

            # Try to get from cache
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

            # Call function
            result = await func(*args, **kwargs)

            # Store in cache
            await redis_client.setex(
                cache_key,
                expire,
                json.dumps(result)
            )

            return result
        return wrapper
    return decorator

# Usage
@cache(expire=600)  # Cache for 10 minutes
async def get_popular_items(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(Item).where(Item.views > 1000).limit(10)
    )
    items = result.scalars().all()
    return [{"id": item.id, "name": item.name} for item in items]
```

### Response Compression

```python
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)
```

### Background Tasks

**For Long-Running Operations:**
```python
from fastapi import BackgroundTasks

@router.post("/reports/")
async def generate_report(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Generate report in background."""
    # Start background task
    background_tasks.add_task(generate_and_email_report, db)

    return {"message": "Report generation started"}

async def generate_and_email_report(db: AsyncSession):
    """Generate report and email it."""
    # Long-running operation
    await asyncio.sleep(60)  # Simulated processing
    # ... generate report and send email
```

---

## Security Checklist

### ✅ Essential Security Measures

**1. Environment Variables**
- [ ] All secrets in `.env` file (not committed to Git)
- [ ] `.env` listed in `.gitignore`
- [ ] `.env.example` provided with dummy values
- [ ] Production secrets stored in secure vault (e.g., AWS Secrets Manager)

**2. Password Security**
- [ ] Passwords hashed with bcrypt (via passlib)
- [ ] Minimum password length enforced (8+ characters)
- [ ] Never log passwords (even in debug mode)
- [ ] Password confirmation on sensitive actions

**3. Authentication & Authorization**
- [ ] JWT tokens with expiration (30 min access, 7 day refresh)
- [ ] Tokens invalidated on logout (if using token blacklist)
- [ ] Role-based access control (RBAC) implemented
- [ ] Protected routes require authentication

**4. Input Validation**
- [ ] All inputs validated with Pydantic schemas
- [ ] SQL injection prevented (use SQLAlchemy parameterized queries)
- [ ] XSS prevented (escape user input in templates)
- [ ] CSRF protection (if using cookies)

**5. CORS Configuration**
- [ ] CORS origins explicitly listed (not `*` in production)
- [ ] Credentials allowed only for trusted origins
- [ ] Preflight requests handled

**6. HTTPS**
- [ ] Force HTTPS in production (Nginx redirect)
- [ ] HSTS header enabled
- [ ] Secure cookies (`httponly`, `secure`, `samesite`)

**7. Rate Limiting**
- [ ] Rate limiting on auth endpoints (prevent brute force)
- [ ] Rate limiting on API endpoints (prevent abuse)
- [ ] IP-based blocking for repeated failures

**8. Database Security**
- [ ] Database user has minimal required permissions
- [ ] Database not exposed to public internet
- [ ] Connection strings use SSL/TLS
- [ ] Regular backups automated

**9. Dependency Security**
- [ ] Regular dependency updates (`poetry update`, `npm update`)
- [ ] Security scanning enabled (Socket.dev MCP, GitHub Dependabot)
- [ ] No known vulnerabilities in dependencies

**10. Logging & Monitoring**
- [ ] Sensitive data not logged (passwords, tokens, PII)
- [ ] Failed login attempts logged
- [ ] Suspicious activity alerts configured
- [ ] Error tracking enabled (Sentry)

---

## Deployment

### Deployment Platforms

This template recommends **Linode** for deployment, with both manual and Terraform options.

#### Why Linode?

| Feature | Linode | AWS | DigitalOcean |
|---------|--------|-----|--------------|
| **Pricing** | ✅ Simple, predictable | ⚠️ Complex, unpredictable | ✅ Simple |
| **Performance** | ✅ Excellent | ✅ Excellent | ✅ Good |
| **Setup Complexity** | ✅ Low | ❌ High | ✅ Low |
| **Documentation** | ✅ Excellent | ⚠️ Overwhelming | ✅ Good |
| **Support** | ✅ Responsive | ⚠️ Paid tiers | ✅ Good |
| **Best For** | Small-medium apps | Enterprise | Startups |

**Recommended Linode Plan for Small-Medium Apps:**
- **Shared CPU 4GB**: $24/month (good for 1000-5000 users)
- **Dedicated CPU 4GB**: $36/month (higher traffic, more predictable)

---

### Option 1: Manual Deployment to Linode

#### Step 1: Create Linode Instance

```bash
# 1. Sign up at https://www.linode.com/
# 2. Create a new Linode (Ubuntu 22.04 LTS recommended)
# 3. Choose region closest to your users
# 4. Select plan (Shared CPU 4GB recommended)
# 5. Set root password
# 6. Add SSH key (recommended)
```

#### Step 2: Initial Server Setup

```bash
# SSH into your server
ssh root@<your-linode-ip>

# Update system
apt update && apt upgrade -y

# Create non-root user
adduser deploy
usermod -aG sudo deploy
su - deploy

# Install dependencies
sudo apt install -y python3.11 python3.11-venv python3-pip \
    postgresql postgresql-contrib nginx git curl

# Install Node.js (for frontend)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -
echo 'export PATH="/home/deploy/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

#### Step 3: Setup PostgreSQL

```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE DATABASE myapp_prod;
CREATE USER myapp_user WITH PASSWORD 'secure-password-here';
GRANT ALL PRIVILEGES ON DATABASE myapp_prod TO myapp_user;
\q

# Configure PostgreSQL to allow local connections
sudo nano /etc/postgresql/15/main/pg_hba.conf
# Add line: local   myapp_prod   myapp_user   md5

# Restart PostgreSQL
sudo systemctl restart postgresql
```

#### Step 4: Deploy Application

```bash
# Clone repository
cd /var/www
sudo mkdir myapp
sudo chown deploy:deploy myapp
git clone <your-repo-url> myapp
cd myapp

# Backend setup
cd backend
poetry install --no-dev
cp .env.example .env
nano .env  # Edit with production values

# Run migrations
poetry run alembic upgrade head

# Frontend setup
cd ../frontend
npm install
npm run build
```

#### Step 5: Setup Systemd Service

```bash
# Create systemd service
sudo nano /etc/systemd/system/myapp.service
```

**Service Configuration:**
```ini
[Unit]
Description=MyApp FastAPI Application
After=network.target postgresql.service

[Service]
Type=notify
User=deploy
Group=deploy
WorkingDirectory=/var/www/myapp/backend
Environment="PATH=/var/www/myapp/backend/.venv/bin"
Environment="PYTHONPATH=/var/www/myapp/backend"
ExecStart=/var/www/myapp/backend/.venv/bin/gunicorn app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 \
    --access-logfile /var/log/myapp/access.log \
    --error-logfile /var/log/myapp/error.log \
    --log-level info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Create log directory
sudo mkdir -p /var/log/myapp
sudo chown deploy:deploy /var/log/myapp

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable myapp
sudo systemctl start myapp
sudo systemctl status myapp
```

#### Step 6: Setup Nginx

```bash
# Create Nginx configuration
sudo nano /etc/nginx/sites-available/myapp
```

**Nginx Configuration:**
```nginx
# Rate limiting zone
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL certificates (will be configured by Certbot)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Frontend (React)
    root /var/www/myapp/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;

        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # API docs
    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /redoc {
        proxy_pass http://127.0.0.1:8000/redoc;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Static files caching
    location ~* \.(jpg|jpeg|png|gif|ico|css|js|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/myapp /etc/nginx/sites-enabled/
sudo nginx -t  # Test configuration
sudo systemctl reload nginx

# Setup SSL with Let's Encrypt
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

#### Step 7: Setup Firewall

```bash
# Configure UFW
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

#### Step 8: Setup Monitoring & Backups

**Monitoring:**
```bash
# Install fail2ban (prevent brute force)
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Setup log rotation
sudo nano /etc/logrotate.d/myapp
```

**Log Rotation Configuration:**
```
/var/log/myapp/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    missingok
    create 0640 deploy deploy
    sharedscripts
    postrotate
        systemctl reload myapp
    endscript
}
```

**Automated Backups:**
```bash
# Create backup script
nano ~/backup.sh
```

**Backup Script:**
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/myapp"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
pg_dump -U myapp_user myapp_prod | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Backup uploaded files (if any)
tar -czf $BACKUP_DIR/uploads_$DATE.tar.gz /var/www/myapp/uploads

# Delete backups older than 30 days
find $BACKUP_DIR -type f -mtime +30 -delete

echo "Backup completed: $DATE"
```

```bash
# Make executable
chmod +x ~/backup.sh

# Add to crontab (daily at 2 AM)
crontab -e
# Add line:
0 2 * * * /home/deploy/backup.sh >> /var/log/backup.log 2>&1
```

---

### Option 2: Automated Deployment with Terraform

**Prerequisites:**
```bash
# Install Terraform
curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo apt-key add -
sudo apt-add-repository "deb [arch=amd64] https://apt.releases.hashicorp.com $(lsb_release -cs) main"
sudo apt update && sudo apt install terraform

# Install Linode CLI
pip install linode-cli
linode-cli configure  # Enter your Linode API token
```

**Project Structure:**
```
terraform/
├── main.tf              # Main infrastructure
├── variables.tf         # Input variables
├── outputs.tf           # Output values
├── providers.tf         # Provider configuration
└── user-data.sh         # Initialization script
```

**providers.tf:**
```hcl
terraform {
  required_providers {
    linode = {
      source  = "linode/linode"
      version = "~> 2.0"
    }
  }
}

provider "linode" {
  token = var.linode_token
}
```

**variables.tf:**
```hcl
variable "linode_token" {
  description = "Linode API token"
  type        = string
  sensitive   = true
}

variable "ssh_key" {
  description = "SSH public key"
  type        = string
}

variable "root_password" {
  description = "Root password for Linode"
  type        = string
  sensitive   = true
}

variable "region" {
  description = "Linode region"
  type        = string
  default     = "us-east"
}

variable "instance_type" {
  description = "Linode instance type"
  type        = string
  default     = "g6-standard-2"  # 4GB RAM
}

variable "db_password" {
  description = "PostgreSQL password"
  type        = string
  sensitive   = true
}

variable "domain" {
  description = "Domain name"
  type        = string
}
```

**main.tf:**
```hcl
# Linode instance
resource "linode_instance" "myapp" {
  label           = "myapp-production"
  image           = "linode/ubuntu22.04"
  region          = var.region
  type            = var.instance_type
  authorized_keys = [var.ssh_key]
  root_pass       = var.root_password

  # User data script
  metadata {
    user_data = base64encode(templatefile("${path.module}/user-data.sh", {
      db_password = var.db_password
      domain      = var.domain
    }))
  }

  tags = ["production", "myapp"]
}

# Firewall
resource "linode_firewall" "myapp" {
  label = "myapp-firewall"

  inbound {
    label    = "allow-ssh"
    action   = "ACCEPT"
    protocol = "TCP"
    ports    = "22"
    ipv4     = ["0.0.0.0/0"]
  }

  inbound {
    label    = "allow-http"
    action   = "ACCEPT"
    protocol = "TCP"
    ports    = "80"
    ipv4     = ["0.0.0.0/0"]
  }

  inbound {
    label    = "allow-https"
    action   = "ACCEPT"
    protocol = "TCP"
    ports    = "443"
    ipv4     = ["0.0.0.0/0"]
  }

  inbound_policy  = "DROP"
  outbound_policy = "ACCEPT"

  linodes = [linode_instance.myapp.id]
}

# Domain record (requires Linode DNS)
resource "linode_domain" "myapp" {
  domain    = var.domain
  type      = "master"
  soa_email = "admin@${var.domain}"
}

resource "linode_domain_record" "myapp_a" {
  domain_id   = linode_domain.myapp.id
  name        = ""
  record_type = "A"
  target      = linode_instance.myapp.ip_address
}

resource "linode_domain_record" "myapp_www" {
  domain_id   = linode_domain.myapp.id
  name        = "www"
  record_type = "A"
  target      = linode_instance.myapp.ip_address
}
```

**outputs.tf:**
```hcl
output "ip_address" {
  description = "Public IP address"
  value       = linode_instance.myapp.ip_address
}

output "ssh_command" {
  description = "SSH command"
  value       = "ssh root@${linode_instance.myapp.ip_address}"
}
```

**user-data.sh:**
```bash
#!/bin/bash
set -e

# Update system
apt update && apt upgrade -y

# Install dependencies
apt install -y python3.11 python3.11-venv python3-pip \
    postgresql postgresql-contrib nginx git curl

# Install Node.js
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

# Create deploy user
adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy
echo "deploy ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Setup PostgreSQL
sudo -u postgres psql <<EOF
CREATE DATABASE myapp_prod;
CREATE USER myapp_user WITH PASSWORD '${db_password}';
GRANT ALL PRIVILEGES ON DATABASE myapp_prod TO myapp_user;
EOF

# Clone and deploy app (you'd typically use CD pipeline instead)
mkdir -p /var/www/myapp
chown deploy:deploy /var/www/myapp

# Install Poetry
sudo -u deploy curl -sSL https://install.python-poetry.org | python3 -

# Setup systemd service (would be created by your deployment script)
# Setup Nginx (would be configured by your deployment script)

# Setup SSL
apt install -y certbot python3-certbot-nginx

echo "Server initialization complete!"
```

**Deploy with Terraform:**
```bash
cd terraform

# Create terraform.tfvars
cat > terraform.tfvars <<EOF
linode_token  = "your-linode-api-token"
ssh_key       = "ssh-rsa AAAA..."
root_password = "secure-root-password"
db_password   = "secure-db-password"
domain        = "yourdomain.com"
region        = "us-east"
EOF

# Initialize Terraform
terraform init

# Plan deployment
terraform plan

# Apply configuration
terraform apply

# Get output
terraform output
```

---

## CI/CD Pipeline

### GitHub Actions Workflow

**.github/workflows/ci.yml:**
```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  backend-test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: myapp_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Poetry
        run: |
          curl -sSL https://install.python-poetry.org | python3 -
          echo "$HOME/.local/bin" >> $GITHUB_PATH

      - name: Install dependencies
        working-directory: ./backend
        run: poetry install

      - name: Lint with Ruff
        working-directory: ./backend
        run: |
          poetry run ruff check .
          poetry run ruff format --check .

      - name: Type check with Mypy
        working-directory: ./backend
        run: poetry run mypy .

      - name: Run tests
        working-directory: ./backend
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/myapp_test
        run: poetry run pytest --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./backend/coverage.xml

  frontend-test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        working-directory: ./frontend
        run: npm ci

      - name: Lint
        working-directory: ./frontend
        run: npm run lint

      - name: Type check
        working-directory: ./frontend
        run: npm run type-check

      - name: Run tests
        working-directory: ./frontend
        run: npm test -- --coverage

      - name: Build
        working-directory: ./frontend
        run: npm run build
```

**.github/workflows/deploy.yml:**
```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'

    steps:
      - uses: actions/checkout@v4

      - name: Deploy to Linode
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.LINODE_HOST }}
          username: deploy
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /var/www/myapp
            git pull origin main

            # Backend
            cd backend
            poetry install --no-dev
            poetry run alembic upgrade head

            # Frontend
            cd ../frontend
            npm install
            npm run build

            # Restart services
            sudo systemctl restart myapp
            sudo systemctl reload nginx
```

---

## Monitoring & Logging

### 📊 Primary Monitoring Method: Audit Logs

**IMPORTANT**: Logs are the **PRIMARY interface** for viewing trading results (before UI in Phase 4).

The trading engine writes structured JSON logs to `logs/audit_YYYY-MM-DD.jsonl` for all trading activity.

### Log File Location

```bash
logs/
├── audit_2025-01-29.jsonl    # Today's audit log (JSON lines)
├── audit_2025-01-28.jsonl    # Yesterday's audit log
└── ...                       # Daily rotation
```

### Viewing Live Results

**Tail logs in real-time:**
```bash
# Watch all events as they happen
tail -f logs/audit_$(date +%Y-%m-%d).jsonl

# Pretty-print JSON for readability
tail -f logs/audit_$(date +%Y-%m-%d).jsonl | jq '.'

# Filter specific events
tail -f logs/audit_$(date +%Y-%m-%d).jsonl | jq 'select(.event == "signal_generated")'
tail -f logs/audit_$(date +%Y-%m-%d).jsonl | jq 'select(.event == "order_placed")'
tail -f logs/audit_$(date +%Y-%m-%d).jsonl | jq 'select(.event == "risk_block")'
```

### Logged Events

The `AuditLogger` (`services/audit/logger.py`) logs ALL trading activity:

**Bar Events:**
- `bar_received` - Completed bar from data feed
- `bar_skipped` - Skipped bar (zero volume, etc.)
- `bar_warning` - Bar quality issue (gap detected, etc.)

**Signal Events:**
- `signal_generated` - Strategy generated a trading signal
- `risk_block` - Signal blocked by risk manager (with reason)

**Order Events:**
- `order_placed` - Order successfully sent to broker
- `execution_error` - Order placement failed
- `broker_error` - Broker API error

**Strategy Events:**
- `strategy_error` - Strategy execution error

**Lifecycle Events:**
- `shutdown` - Graceful shutdown (with balance, positions)
- `emergency_shutdown` - Emergency kill switch triggered

### Log Entry Format

Each log entry is a JSON line with:
```json
{
  "ts": "2025-01-29T14:30:15.123Z",
  "event": "signal_generated",
  "signal": {
    "symbol": "BTCUSDT",
    "side": "buy",
    "qty": 0.01,
    "price": 50000.0,
    "sl": 49500.0,
    "tp": 50500.0,
    "reason": "L2 imbalance ratio 3.5x (strong bid pressure)"
  },
  "bar": {
    "timestamp": 1706538615000,
    "datetime": "2025-01-29T14:30:15",
    "open": 49950.0,
    "high": 50050.0,
    "low": 49900.0,
    "close": 50000.0,
    "volume": 15.3
  }
}
```

### Analyzing Results

**Count signal types:**
```bash
# How many buy vs sell signals today?
cat logs/audit_$(date +%Y-%m-%d).jsonl | jq -r 'select(.event == "signal_generated") | .signal.side' | sort | uniq -c

# How many signals were blocked by risk manager?
cat logs/audit_$(date +%Y-%m-%d).jsonl | jq -r 'select(.event == "risk_block") | .reason' | sort | uniq -c
```

**Extract all orders:**
```bash
# List all orders placed today
cat logs/audit_$(date +%Y-%m-%d).jsonl | jq 'select(.event == "order_placed")'
```

**Find errors:**
```bash
# Show all errors with reasons
cat logs/audit_$(date +%Y-%m-%d).jsonl | jq 'select(.event | endswith("_error"))'
```

### AuditLogger Usage (Code Example)

```python
from trade_engine.services.audit.logger import AuditLogger
from trade_engine.core.types import Bar, Signal

# Initialize (logs go to logs/audit_YYYY-MM-DD.jsonl)
audit = AuditLogger()

# Log bar received
audit.log_bar_received(bar)

# Log signal generated
audit.log_signal_generated(signal, bar)

# Log risk block
audit.log_risk_block(signal, reason="Daily loss limit exceeded")

# Log order placed
audit.log_order_placed(signal, order_id="12345")

# Log errors
audit.log_execution_error(signal, error="Insufficient balance")
audit.log_broker_error(signal, error="API rate limit")

# Log lifecycle
audit.log_shutdown(balance=10500.0, positions=2)
audit.log_emergency_shutdown(positions_closed=3)
```

### Future Monitoring (Phase 3+)

**Phase 3 (API Layer)**: FastAPI endpoints to query logs
- `/api/v1/trades` - List recent trades
- `/api/v1/signals` - List recent signals
- `/api/v1/performance` - P&L metrics

**Phase 4 (UI Layer)**: React dashboard
- Real-time signal feed
- P&L charts
- Risk limit monitoring
- Kill switch button

---

## Troubleshooting

### Common Issues

**1. Database Connection Errors**

```bash
# Error: "could not connect to server"
# Solution: Check PostgreSQL is running
sudo systemctl status postgresql
sudo systemctl start postgresql

# Error: "password authentication failed"
# Solution: Check DATABASE_URL in .env
# Format: postgresql+asyncpg://user:password@localhost:5432/dbname
```

**2. Migration Errors**

```bash
# Error: "Target database is not up to date"
# Solution: Run migrations
alembic upgrade head

# Error: "Can't locate revision identified by 'xxx'"
# Solution: Reset migration history
alembic downgrade base
alembic upgrade head
```

**3. Import Errors**

```python
# Error: ModuleNotFoundError: No module named 'app'
# Solution: Set PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:/path/to/backend"

# Or use relative imports in tests
from ..app.models.user import User
```

**4. Async Errors**

```python
# Error: "coroutine 'get_user' was never awaited"
# Solution: Use await with async functions
user = await UserService.get_user(db, user_id)  # ✅
user = UserService.get_user(db, user_id)       # ❌

# Error: "Event loop is closed"
# Solution: Use pytest-asyncio
@pytest.mark.asyncio  # Add this decorator
async def test_function():
    pass
```

**5. Port Already in Use**

```bash
# Error: "Address already in use"
# Solution: Find and kill process
lsof -i :8000
kill -9 <PID>

# Or use different port
uvicorn app.main:app --port 8001
```

---

## Contributing Guidelines

🔧 **Customize these guidelines for your project.**

### Workflow

1. **Fork & Clone**
   ```bash
   git clone <your-fork-url>
   cd <project-name>
   ```

2. **Create Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make Changes**
   - Write code following style guide
   - Add tests for new features
   - Update documentation

4. **Run Quality Checks**
   ```bash
   # Backend
   cd backend
   ruff check --fix .
   ruff format .
   mypy .
   pytest

   # Frontend
   cd frontend
   npm run lint
   npm run type-check
   npm test
   ```

5. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: Add user authentication"
   ```

   **Commit Convention:**
   - `feat:` New feature
   - `fix:` Bug fix
   - `docs:` Documentation
   - `refactor:` Code refactoring
   - `test:` Add tests
   - `chore:` Maintenance

6. **Push & Create PR**
   ```bash
   git push origin feature/your-feature-name
   ```
   Then create Pull Request on GitHub.

### Code Review Checklist

- [ ] Code follows style guide (Ruff for Python, ESLint for TypeScript)
- [ ] All tests pass
- [ ] Coverage maintained or improved
- [ ] Documentation updated
- [ ] No hardcoded secrets
- [ ] Error handling implemented
- [ ] Performance considered

---

## Changelog

Track documentation changes here for team visibility.

### [1.0.0] - 2025-01-29
- Initial template creation
- Complete Python/FastAPI stack documentation
- Linode deployment guides (manual + Terraform)
- MCP server setup instructions
- Testing strategy with examples
- Security checklist

🔧 **Add your project-specific changes below:**

### [Unreleased]
- Your changes here

---

## Additional Resources

### Official Documentation
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Docs](https://docs.sqlalchemy.org/en/20/)
- [Pydantic V2 Docs](https://docs.pydantic.dev/2.0/)
- [Alembic Docs](https://alembic.sqlalchemy.org/)
- [Pytest Docs](https://docs.pytest.org/)
- [Linode Docs](https://www.linode.com/docs/)

### Useful Tools
- [Postman](https://www.postman.com/) - API testing
- [DBeaver](https://dbeaver.io/) - Database client
- [HTTPie](https://httpie.io/) - CLI HTTP client
- [pgAdmin](https://www.pgadmin.org/) - PostgreSQL admin

### Community
- [FastAPI Discord](https://discord.gg/VQjSZaeJmf)
- [Python Discord](https://discord.gg/python)
- [/r/FastAPI](https://www.reddit.com/r/FastAPI/)

---

**Last Updated**: 2025-01-29
**Template Version**: 1.0.0
**Maintained By**: 🔧 [Your Name/Team]

---

*This CLAUDE.md template is designed to be comprehensive yet scannable. Remove sections that don't apply to your project, and expand areas that need more detail. Keep it updated as your project evolves!*
