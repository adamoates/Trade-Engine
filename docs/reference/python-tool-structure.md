# Python Tool Structure & Package Design

**Last Updated**: 2025-10-23
**Category**: Guide
**Status**: Active

Understanding how Python tools are structured and how the MFT project should evolve.

---

## Current State Analysis

### What We Have Now

```
MFT/
├── tools/                          # Standalone CLI scripts
│   ├── fetch_binance_ohlcv.py     # ✅ Good: Shebang, argparse, main()
│   └── validate_clean_ohlcv.py    # ✅ Good: Modular, piped workflow
├── scripts/                        # Ad-hoc scripts
│   ├── record_l2_data.py
│   ├── diagnose_l2_collection.py
│   └── validate_data.py
├── strategies/                     # Strategy implementations
│   ├── implementations/
│   └── research/
├── Makefile                        # ✅ Good: Workflow automation
├── requirements.txt               # ✅ Good: Minimal dependencies
└── README.md
```

**Architecture Type**: **Script-Based Tool Collection**
- Individual standalone scripts
- No shared library code
- Each tool is self-contained
- Good for: Quick utilities, one-off tasks
- Bad for: Code reuse, testing, distribution

---

## Python Tool Structure Patterns

### Pattern 1: Script-Based Tools (CURRENT STATE)

**Structure:**
```
project/
├── tools/
│   ├── tool1.py         # Standalone script
│   └── tool2.py         # Standalone script
├── Makefile             # Workflow orchestration
└── requirements.txt
```

**Characteristics:**
- ✅ Simple to understand
- ✅ No import complexity
- ✅ Each tool is independent
- ❌ Code duplication between tools
- ❌ Hard to test (no library separation)
- ❌ Not installable as package
- ❌ Can't import functionality into other projects

**When to use:**
- Small projects (<5 tools)
- One-person teams
- Disposable/temporary tooling
- Quick prototyping

**Our current tools fit this pattern:**
```python
#!/usr/bin/env python3
# tools/fetch_binance_ohlcv.py

import argparse, csv, sys
import requests

def main():
    ap = argparse.ArgumentParser(...)
    args = ap.parse_args()
    # ... logic here ...

if __name__ == "__main__":
    main()
```

---

### Pattern 2: Library + CLI (RECOMMENDED FOR MFT)

**Structure:**
```
mft/
├── mft/                          # Importable Python package
│   ├── __init__.py
│   ├── fetchers/                 # Reusable modules
│   │   ├── __init__.py
│   │   ├── binance.py
│   │   └── base.py
│   ├── validators/
│   │   ├── __init__.py
│   │   └── ohlcv.py
│   ├── regimes/
│   │   ├── __init__.py
│   │   └── detection.py
│   └── cli/                      # CLI entry points
│       ├── __init__.py
│       ├── fetch.py
│       ├── validate.py
│       └── backtest.py
├── setup.py                      # Package installer
├── pyproject.toml                # Modern Python packaging
├── requirements.txt
├── tests/                        # Unit tests
│   ├── test_fetchers.py
│   ├── test_validators.py
│   └── test_regimes.py
└── docs/
```

**Characteristics:**
- ✅ Code reuse (DRY principle)
- ✅ Testable (import modules)
- ✅ Installable (`pip install -e .`)
- ✅ CLI commands (`mft fetch`, `mft validate`)
- ✅ Importable in other projects
- ✅ Professional structure
- ❌ More upfront complexity

**When to use:**
- Growing projects (5+ tools)
- Multiple contributors
- Need for testing
- Want to distribute/share
- Long-term maintenance

**Example usage after install:**
```bash
# Install package
pip install -e .

# Use as CLI
mft fetch --market futures --symbol BTCUSDT --interval 5m --days 7

# Or import in Python
from mft.fetchers import BinanceFetcher
fetcher = BinanceFetcher()
data = fetcher.fetch_ohlcv("BTCUSDT", "5m", days=7)
```

---

### Pattern 3: Full Application Framework

**Structure:**
```
mft/
├── mft/
│   ├── core/                     # Core domain logic
│   ├── adapters/                 # External integrations
│   ├── services/                 # Business logic
│   ├── api/                      # REST/WebSocket API
│   ├── db/                       # Database models
│   └── cli/                      # CLI interface
├── alembic/                      # Database migrations
├── docker/                       # Containerization
├── k8s/                          # Kubernetes configs
├── setup.py
└── tests/
```

**When to use:**
- Production trading systems
- Multi-process architecture
- Database-backed state
- Web API + CLI + Worker processes
- Team of 3+ developers

**Not recommended for MFT yet** - overkill for current needs.

---

## Recommended Evolution Path for MFT

### Phase 1: Current State (✅ DONE)
**Status**: Script-based tools with Makefile orchestration

**What we have:**
- `tools/fetch_binance_ohlcv.py` - Standalone fetcher
- `tools/validate_clean_ohlcv.py` - Standalone validator
- `Makefile` - Workflow automation
- Good for: Getting started quickly

**Pros:**
- Simple to understand
- No packaging complexity
- Easy to modify

**Cons:**
- Code duplication emerging
- Hard to test comprehensively
- Can't import functions between tools

---

### Phase 2: Refactor to Library + CLI (RECOMMENDED NEXT)
**Status**: When adding 3+ more tools or when code duplication becomes painful

**Migration plan:**
1. Create `mft/` package directory
2. Extract shared code into modules
3. Keep CLI scripts thin (just argparse + call library)
4. Add `setup.py` for installation
5. Add comprehensive tests

**Before:**
```python
# tools/fetch_binance_ohlcv.py (200 lines)
# - API logic (100 lines)
# - CLI logic (50 lines)
# - Helper functions (50 lines)
```

**After:**
```python
# mft/fetchers/binance.py (library)
class BinanceFetcher:
    def fetch_ohlcv(self, symbol, interval, **kwargs):
        # ... reusable logic ...
        pass

# mft/cli/fetch.py (CLI wrapper)
def main():
    args = parse_args()
    fetcher = BinanceFetcher()
    data = fetcher.fetch_ohlcv(args.symbol, args.interval, ...)
    # ... output handling ...
```

**Benefits:**
- Testable: `from mft.fetchers import BinanceFetcher; test_it()`
- Reusable: Import in strategies, backtests, live trading
- Professional: Standard Python package structure
- Installable: `pip install -e .` for development

---

### Phase 3: Production Trading System (FUTURE)
**Status**: When going live with real trading

**Add:**
- Database layer (positions, orders, P&L history)
- WebSocket connections (real-time data)
- REST API (monitoring, control)
- Worker processes (data collection, trading, monitoring)
- Observability (metrics, logging, alerting)

**Not needed yet** - premature optimization.

---

## Standard Python Tool Components

### 1. Entry Point (`if __name__ == "__main__"`)

**Purpose**: Allow script to be run directly OR imported as library

```python
#!/usr/bin/env python3
# tools/fetch_binance_ohlcv.py

def fetch_ohlcv(symbol, interval, days):
    """Reusable function - can be imported."""
    # ... logic ...
    return data

def main():
    """CLI entry point."""
    args = parse_args()
    data = fetch_ohlcv(args.symbol, args.interval, args.days)
    write_output(data, args.out)

if __name__ == "__main__":
    main()
```

**Why this matters:**
```python
# Can run as script
$ python tools/fetch_binance_ohlcv.py --symbol BTCUSDT ...

# Can also import
from tools.fetch_binance_ohlcv import fetch_ohlcv
data = fetch_ohlcv("BTCUSDT", "5m", 7)  # No argparse needed
```

---

### 2. Argument Parsing (argparse)

**Our tools already do this well:**
```python
import argparse

def parse_args():
    ap = argparse.ArgumentParser(
        description="Fetch OHLCV from Binance"
    )
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--interval", required=True)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--out", type=Path, help="Output file")
    ap.add_argument("--stdout", action="store_true")
    return ap.parse_args()
```

**Best practices (we follow most):**
- ✅ Use `argparse` (not `sys.argv` manually)
- ✅ Provide `--help` text
- ✅ Use types (`type=int`, `type=Path`)
- ✅ Sensible defaults
- ✅ Required vs optional clear

---

### 3. Unix Philosophy (pipes, stdout)

**Our tools nail this:**
```python
# Write to stdout for piping
if args.stdout:
    writer = csv.writer(sys.stdout)
    # ... write data ...

# Or write to file
else:
    with open(args.out, "w") as f:
        writer = csv.writer(f)
        # ... write data ...
```

**This enables:**
```bash
# Pipe to validator
python fetch.py --stdout | python validate.py /dev/stdin --out clean.csv

# Pipe to jq
python fetch.py --stdout | jq '.'

# Pipe to grep
python fetch.py --stdout | grep "ERROR"
```

**Unix philosophy principles:**
1. ✅ Write programs that do one thing well
2. ✅ Write programs to work together (pipes)
3. ✅ Write programs to handle text streams

---

### 4. Configuration Hierarchy

**Common pattern:**
```
1. Hardcoded defaults (in code)
2. Config file (~/.mft/config.yaml)
3. Environment variables (MFT_SYMBOL=BTCUSDT)
4. Command-line arguments (--symbol BTCUSDT)

Later overrides earlier.
```

**Our current approach:**
```python
# Defaults in code
DEFAULT_INTERVAL = "15m"
DEFAULT_DAYS = 30

# Override with CLI args
args = parse_args()
interval = args.interval or DEFAULT_INTERVAL
```

**Could enhance with:**
```python
import os
from dotenv import load_dotenv

load_dotenv()  # Load .env file

# Hierarchy: defaults -> .env -> CLI
symbol = args.symbol or os.getenv("MFT_SYMBOL") or "BTCUSDT"
```

---

### 5. Error Handling & Exit Codes

**Good practice (we partially do this):**
```python
import sys

def main():
    try:
        data = fetch_ohlcv(args.symbol, args.interval, args.days)
        write_output(data, args.out)
        return 0  # Success
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user", file=sys.stderr)
        return 130  # Standard Unix code for Ctrl+C
    except requests.HTTPError as e:
        print(f"❌ HTTP error: {e}", file=sys.stderr)
        return 1  # General error
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
```

**Standard exit codes:**
- `0` - Success
- `1` - General error
- `2` - Misuse of command (bad args)
- `130` - Ctrl+C (SIGINT)

**Why this matters:**
```bash
# In shell scripts
make fetch || exit 1  # Stop if fetch fails

# In CI/CD
if ! python fetch.py --symbol BTCUSDT; then
    echo "Fetch failed!"
    exit 1
fi
```

---

### 6. Progress Reporting (stderr vs stdout)

**Our tools do this correctly:**
```python
# Data to stdout (for piping)
writer = csv.writer(sys.stdout)
writer.writerow([timestamp, open, high, low, close, volume])

# Progress to stderr (doesn't pollute pipe)
print(f"\rFetched: {count} candles", end="", file=sys.stderr)
```

**This allows:**
```bash
# Progress visible, but doesn't corrupt piped data
python fetch.py --stdout | python validate.py /dev/stdin
# ^^^ See progress on terminal
#     But piped data is clean
```

---

## When to Refactor: Decision Matrix

### Stay Script-Based If:
- ✅ Less than 5 tools total
- ✅ Minimal code overlap between tools
- ✅ No need for unit testing libraries
- ✅ No plans to distribute/share
- ✅ One-person project
- ✅ Tools are disposable/temporary

**Current MFT status**:
- 2 tools in `tools/` ✅
- 3 scripts in `scripts/` ✅
- Makefile orchestration ✅
- **VERDICT**: Script-based is fine for now

---

### Refactor to Library When:
- ❌ Adding 5+ more tools
- ❌ Duplicating code across tools (DRY violation)
- ❌ Need comprehensive unit tests
- ❌ Want to import functions between tools
- ❌ Multiple contributors
- ❌ Want to distribute (pip install)

**Future MFT triggers**:
- Adding live trading engine (need testable library)
- Adding web API (need to import trading logic)
- Adding more data sources (code reuse for fetchers)
- Open-sourcing (professional structure expected)

---

## Comparison: Our Tools vs Industry Examples

### Our Current Tools (Script-Based)

**fetch_binance_ohlcv.py:**
```python
#!/usr/bin/env python3
import argparse
import requests

def main():
    args = argparse.ArgumentParser(...)
    # ... all logic inline ...

if __name__ == "__main__":
    main()
```

**Similar to:**
- Unix utilities (`curl`, `wget`)
- Docker CLI scripts
- Git helper scripts (git-filter-branch, etc.)

---

### Library + CLI Examples

**Example: Black (code formatter)**
```
black/
├── black/                    # Library
│   ├── __init__.py
│   ├── parsing.py           # Reusable
│   ├── formatting.py        # Reusable
│   └── cli.py               # Thin CLI wrapper
├── setup.py
└── tests/
```

**Usage:**
```bash
# As CLI
black myfile.py

# As library
from black import format_str
formatted = format_str(code, mode=Mode())
```

**Example: pytest**
```
pytest/
├── _pytest/                  # Library
│   ├── main.py              # Core logic
│   ├── runner.py
│   └── ...
├── setup.py
└── scripts/
    └── pytest               # Thin CLI entry point
```

---

## Proposed Refactoring Plan (When Needed)

### Step 1: Create Package Structure
```bash
mkdir -p mft/{fetchers,validators,regimes,cli}
touch mft/__init__.py
touch mft/{fetchers,validators,regimes,cli}/__init__.py
```

### Step 2: Extract Library Code
```python
# mft/fetchers/binance.py
class BinanceFetcher:
    """Reusable Binance data fetcher."""

    def __init__(self, base_url=None, timeout=20):
        self.base_url = base_url or "https://api.binance.com"
        self.timeout = timeout

    def fetch_ohlcv(self, symbol, interval, days=None, start=None, end=None):
        """Fetch OHLCV data. Returns DataFrame."""
        # ... implementation ...
        return df
```

### Step 3: Create Thin CLI Wrappers
```python
# mft/cli/fetch.py
from mft.fetchers import BinanceFetcher

def main():
    args = parse_args()
    fetcher = BinanceFetcher()
    df = fetcher.fetch_ohlcv(
        symbol=args.symbol,
        interval=args.interval,
        days=args.days
    )

    # Output handling
    if args.stdout:
        df.to_csv(sys.stdout, index=False)
    else:
        df.to_csv(args.out, index=False)

if __name__ == "__main__":
    main()
```

### Step 4: Add setup.py
```python
# setup.py
from setuptools import setup, find_packages

setup(
    name="mft",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pandas>=2.1.0",
        "requests>=2.31.0",
        # ... from requirements.txt
    ],
    entry_points={
        "console_scripts": [
            "mft-fetch=mft.cli.fetch:main",
            "mft-validate=mft.cli.validate:main",
            "mft-backtest=mft.cli.backtest:main",
        ],
    },
)
```

### Step 5: Install & Use
```bash
# Install in development mode
pip install -e .

# Use CLI (commands now in PATH)
mft-fetch --market futures --symbol BTCUSDT --interval 5m --days 7

# Or import in Python
from mft.fetchers import BinanceFetcher
fetcher = BinanceFetcher()
data = fetcher.fetch_ohlcv("BTCUSDT", "5m", days=7)
```

---

## Recommendations for MFT

### Immediate (Now)
1. ✅ Keep script-based structure (working well)
2. ✅ Continue using Makefile for workflows
3. ✅ Add more inline documentation
4. ✅ Extract common constants to config file

### Near-Term (After 5+ tools)
1. Refactor to library + CLI structure
2. Add comprehensive unit tests
3. Create `setup.py` for installable package
4. Separate CLI logic from business logic

### Long-Term (Production Trading)
1. Full application framework
2. Database layer
3. WebSocket real-time data
4. REST API for monitoring
5. Containerization (Docker)

---

## Summary

**Current State**: Script-based tools with Makefile orchestration
- ✅ Appropriate for current project size
- ✅ Simple and maintainable
- ✅ Unix-philosophy compliant

**Next Evolution**: Library + CLI (when needed)
- Trigger: 5+ tools OR significant code duplication
- Benefits: Testability, reusability, professional structure
- Cost: Upfront refactoring effort

**Our tools already follow best practices:**
- ✅ Shebang (`#!/usr/bin/env python3`)
- ✅ Argparse for CLI
- ✅ Stdout/stderr separation
- ✅ Pipe-friendly (Unix philosophy)
- ✅ `if __name__ == "__main__"` pattern
- ✅ Clear, single-purpose tools

**Recommendation**: Stay script-based for now, but be ready to refactor to library + CLI when adding more tools or needing comprehensive tests.

---

## Related Documentation

- [Data Pipeline Guide](./data-pipeline-guide.md) - Current workflows
- [Development Workflow](./development-workflow.md) - Git and testing practices
- [Project Setup Checklist](./project-setup-checklist.md) - Environment setup

---

**Further Reading:**
- [The Hitchhiker's Guide to Python - Structuring Your Project](https://docs.python-guide.org/writing/structure/)
- [Python Packaging User Guide](https://packaging.python.org/)
- [Unix Philosophy](http://www.catb.org/~esr/writings/taoup/html/ch01s06.html)
