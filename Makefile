# MFT Trading Bot - Data Pipeline Makefile
# Complete fetch → validate → detect → backtest workflow

PYTHON := python3

# ========= Flexible Parameters (override at call time) =========
# Usage: make full M=futures S=ETHUSDT I=15m D=7
M ?= spot                # spot | futures
S ?= BTCUSDT             # symbol (no slash)
I ?= 15m                 # interval (1m,5m,15m,1h,...)
D ?= 30                  # days back (or use START/END)
START ?=                 # YYYY-MM-DD (UTC)
END ?=                   # YYYY-MM-DD (UTC)
DOMAIN ?=                # e.g., https://api.binance.us (optional)

# ========= Directories =========
DATA_DIR   ?= data
RAW_DIR    ?= $(DATA_DIR)/ohlcv
CLEAN_DIR  ?= $(DATA_DIR)/clean
REGIME_DIR ?= $(DATA_DIR)/regimes
BACKTEST_DIR ?= $(DATA_DIR)/backtest

# ========= Cost Assumptions (round-trip bps) =========
FEE_BPS   ?= 12          # Default: spot fees (0.12%)
SPREAD_BPS?= 3           # Bid-ask spread
SLIP_BPS  ?= 2           # Market impact slippage

# ========= Auto-Generated Filenames =========
# Lowercase symbol for filenames
S_LOWER := $(shell echo $(S) | tr '[:upper:]' '[:lower:]')
RAW_FILE   := $(RAW_DIR)/binance_$(M)_$(S_LOWER)_$(I).csv
CLEAN_FILE := $(CLEAN_DIR)/binance_$(M)_$(S_LOWER)_$(I)_clean.csv
REPORT_FILE:= $(CLEAN_FILE:.csv=_report.json)
REGIME_FILE:= $(REGIME_DIR)/$(S_LOWER)_$(I)_regimes.jsonl
BACKTEST_FILE:= $(BACKTEST_DIR)/$(S_LOWER)_$(I)_results.json

# ========= Help =========
.PHONY: help
help:
	@echo "MFT Trading Bot - Data Pipeline Commands"
	@echo ""
	@echo "🚀 Quick Start (Parameterized):"
	@echo "  make full M=futures S=BTCUSDT I=5m D=7     # Complete pipeline"
	@echo "  make pipe M=spot S=ETHUSDT I=15m D=30      # Piped (no raw file)"
	@echo "  make fetch M=futures S=BTCUSDT I=5m D=7    # Fetch only"
	@echo ""
	@echo "🎯 Option 1 Testing (Futures Pivot):"
	@echo "  make option1-test                          # Test futures 5m & 15m"
	@echo "  make option1-compare                       # Compare futures vs spot"
	@echo ""
	@echo "📋 Individual Steps:"
	@echo "  make fetch       # Fetch to file (resumable)"
	@echo "  make validate    # Validate & clean"
	@echo "  make detect      # Detect regimes"
	@echo "  make backtest    # Run backtest"
	@echo "  make pipe        # One-shot: fetch → validate (no raw file)"
	@echo "  make full        # Complete: fetch → validate → detect → backtest"
	@echo ""
	@echo "⚙️  Parameters (override with make VAR=value):"
	@echo "  M=$(M)              # Market: spot | futures"
	@echo "  S=$(S)            # Symbol (no slash)"
	@echo "  I=$(I)              # Interval: 1m,5m,15m,1h,..."
	@echo "  D=$(D)              # Days back from now"
	@echo "  START=$(START)         # Or use YYYY-MM-DD start"
	@echo "  END=$(END)           # And YYYY-MM-DD end"
	@echo "  DOMAIN=$(DOMAIN)       # Optional: https://api.binance.us"
	@echo ""
	@echo "💰 Cost Assumptions (bps):"
	@echo "  FEE_BPS=$(FEE_BPS)        # Round-trip fees (spot: 12, futures: 4)"
	@echo "  SPREAD_BPS=$(SPREAD_BPS)      # Bid-ask spread"
	@echo "  SLIP_BPS=$(SLIP_BPS)        # Slippage"
	@echo ""
	@echo "📚 Examples:"
	@echo "  make full M=futures S=ETHUSDT I=15m START=2025-07-01 END=2025-10-23"
	@echo "  make pipe M=spot S=BTCUSDT I=5m D=30"
	@echo "  make backtest S=BTCUSDT I=5m  # Run backtest on existing regimes"
	@echo "  make full M=futures S=BTCUSDT I=5m D=7 FEE_BPS=4  # Futures fees"
	@echo ""
	@echo "🧹 Utilities:"
	@echo "  make dirs                # Create data directories"
	@echo "  make clean-data          # Delete all data files"
	@echo "  make test-pipeline       # Quick 2-day test"
	@echo "  make show-report         # Display quality reports"

# ========= Core Targets =========

.PHONY: dirs
dirs:
	@mkdir -p $(RAW_DIR) $(CLEAN_DIR) $(REGIME_DIR) $(BACKTEST_DIR)

# Fetch to file (resumable). Use D (days) or START/END.
.PHONY: fetch
fetch: dirs
	@echo "📥 Fetching $(M) $(S) $(I) $(if $(D),$(D)d,$(START) to $(END))"
	@$(PYTHON) tools/fetch_binance_ohlcv.py \
		--market $(M) --symbol $(S) --interval $(I) \
		$(if $(D),--days $(D)) \
		$(if $(START),--start $(START)) \
		$(if $(END),--end $(END)) \
		$(if $(DOMAIN),--domain $(DOMAIN)) \
		--out $(RAW_FILE) --resume --progress

# Validate/clean a fetched CSV (drop incomplete bars by default)
.PHONY: validate
validate: dirs
	@echo "🧹 Validating $(RAW_FILE)"
	@$(PYTHON) tools/validate_clean_ohlcv.py $(RAW_FILE) \
		--out $(CLEAN_FILE) --report $(REPORT_FILE) --fill drop \
		--fee-bps $(FEE_BPS) --spread-bps $(SPREAD_BPS) --slip-bps $(SLIP_BPS)
	@echo "✅ Clean: $(CLEAN_FILE)"
	@echo "📋 Report: $(REPORT_FILE)"

# Detect regimes on clean data
.PHONY: detect
detect: dirs
	@echo "🔍 Detecting regimes → $(REGIME_FILE)"
	@$(PYTHON) scripts/detect_regimes.py $(CLEAN_FILE) --output $(REGIME_FILE)
	@echo "✅ Regimes: $(REGIME_FILE)"

# Run backtest on regimes
.PHONY: backtest
backtest: dirs
	@echo "📊 Running backtest: $(I) timeframe"
	@$(PYTHON) scripts/backtest_trending_v3.py \
		$(REGIME_FILE) \
		--timeframe $(I) \
		--export $(BACKTEST_FILE)
	@echo "✅ Results: $(BACKTEST_FILE)"
	@echo ""
	@echo "📈 Summary:"
	@jq '{total_trades, win_rate_pct, avg_trade_pct, total_pnl_usd, sharpe_ratio}' \
		$(BACKTEST_FILE) 2>/dev/null || echo "Parse failed (check file)"

# One-shot pipe: fetch → validate (no raw file on disk)
.PHONY: pipe
pipe: dirs
	@echo "🔄 Piped: fetch → validate for $(M) $(S) $(I)"
	@$(PYTHON) tools/fetch_binance_ohlcv.py \
		--market $(M) --symbol $(S) --interval $(I) \
		$(if $(D),--days $(D)) $(if $(START),--start $(START)) $(if $(END),--end $(END)) \
		$(if $(DOMAIN),--domain $(DOMAIN)) --stdout --progress \
	| $(PYTHON) tools/validate_clean_ohlcv.py /dev/stdin \
		--out $(CLEAN_FILE) --report $(REPORT_FILE) --fill drop \
		--fee-bps $(FEE_BPS) --spread-bps $(SPREAD_BPS) --slip-bps $(SLIP_BPS)
	@echo "✅ Clean: $(CLEAN_FILE)"

# Full pipeline using resumable fetch
.PHONY: full
full: fetch validate detect backtest
	@echo ""
	@echo "✅ Complete pipeline finished!"
	@echo "   Raw:      $(RAW_FILE)"
	@echo "   Clean:    $(CLEAN_FILE)"
	@echo "   Regimes:  $(REGIME_FILE)"
	@echo "   Backtest: $(BACKTEST_FILE)"

# ========= Option 1 (Futures Pivot) Testing =========

.PHONY: option1-test
option1-test: dirs
	@echo "🎯 Option 1 Testing: Futures 5m & 15m backtest"
	@echo ""
	@echo "=== 5m Timeframe ==="
	@$(MAKE) full M=futures S=BTCUSDT I=5m D=7 FEE_BPS=4
	@echo ""
	@echo "=== 15m Timeframe ==="
	@$(MAKE) full M=futures S=BTCUSDT I=15m D=7 FEE_BPS=4
	@echo ""
	@echo "✅ Option 1 testing complete!"
	@echo "Compare results:"
	@echo "  5m:  $(BACKTEST_DIR)/btcusdt_5m_results.json"
	@echo "  15m: $(BACKTEST_DIR)/btcusdt_15m_results.json"

.PHONY: option1-compare
option1-compare:
	@echo "📊 Comparing Futures vs Spot (5m)..."
	@echo ""
	@echo "=== Futures 5m (last 7d) ==="
	@jq '{total_trades, win_rate_pct, avg_trade_pct, total_pnl_usd, sharpe_ratio}' \
		$(BACKTEST_DIR)/btcusdt_5m_results.json 2>/dev/null || echo "Not found (run option1-test first)"
	@echo ""
	@echo "=== Spot 5m (from previous test) ==="
	@jq '{total_trades, win_rate_pct, avg_trade_pct, total_pnl_usd}' \
		$(BACKTEST_DIR)/trending_v3_5m_7d.json 2>/dev/null || echo "Not found"

# ========= Quick Shortcuts (Legacy Compatibility) =========

.PHONY: fetch-futures-5m-7d
fetch-futures-5m-7d:
	@$(MAKE) fetch M=futures S=BTCUSDT I=5m D=7

.PHONY: fetch-futures-15m-7d
fetch-futures-15m-7d:
	@$(MAKE) fetch M=futures S=BTCUSDT I=15m D=7

.PHONY: fetch-spot-5m-30d
fetch-spot-5m-30d:
	@$(MAKE) fetch M=spot S=BTCUSDT I=5m D=30

.PHONY: fetch-spot-15m-30d
fetch-spot-15m-30d:
	@$(MAKE) fetch M=spot S=BTCUSDT I=15m D=30

.PHONY: pipeline-futures-5m
pipeline-futures-5m:
	@$(MAKE) full M=futures S=BTCUSDT I=5m D=7 FEE_BPS=4

.PHONY: pipeline-futures-15m
pipeline-futures-15m:
	@$(MAKE) full M=futures S=BTCUSDT I=15m D=7 FEE_BPS=4

# ========= Utilities =========

.PHONY: clean-data
clean-data:
	@echo "🗑️  Cleaning all data directories..."
	@rm -rf $(RAW_DIR)/* $(CLEAN_DIR)/* $(REGIME_DIR)/* $(BACKTEST_DIR)/*
	@echo "✅ Data cleaned"

.PHONY: test-pipeline
test-pipeline:
	@echo "🧪 Testing pipeline with 2 days of 5m futures data..."
	@$(MAKE) full M=futures S=BTCUSDT I=5m D=2 FEE_BPS=4
	@echo ""
	@echo "✅ Pipeline test complete"

.PHONY: show-report
show-report:
	@echo "📋 Latest quality reports:"
	@find $(CLEAN_DIR) -name "*_report.json" -exec echo {} \; -exec cat {} \; -exec echo "" \;
