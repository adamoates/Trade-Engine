# MFT Trading Bot - Data Pipeline Makefile
# Quick commands for fetch → validate → detect → backtest workflow

PYTHON := python3
DATA_DIR := data
OHLCV_DIR := $(DATA_DIR)/ohlcv
CLEAN_DIR := $(DATA_DIR)/clean
REGIME_DIR := $(DATA_DIR)/regimes
BACKTEST_DIR := $(DATA_DIR)/backtest

# Default symbol and parameters
SYMBOL := BTCUSDT
INTERVAL := 5m
DAYS := 7

.PHONY: help
help:
	@echo "MFT Trading Bot - Data Pipeline Commands"
	@echo ""
	@echo "Quick Start:"
	@echo "  make fetch-futures-5m-7d    # Fetch 7 days of BTC futures 5m data"
	@echo "  make fetch-spot-15m-30d     # Fetch 30 days of BTC spot 15m data"
	@echo "  make pipeline-futures-5m    # Complete: fetch → validate → detect → backtest"
	@echo ""
	@echo "Individual Steps:"
	@echo "  make fetch-futures          # Fetch futures OHLCV"
	@echo "  make fetch-spot             # Fetch spot OHLCV"
	@echo "  make validate               # Validate & clean OHLCV"
	@echo "  make detect-regimes         # Detect market regimes"
	@echo "  make backtest               # Run backtest"
	@echo ""
	@echo "Piped Workflows:"
	@echo "  make pipe-futures-clean     # Fetch futures → validate → clean CSV"
	@echo "  make pipe-spot-clean        # Fetch spot → validate → clean CSV"
	@echo ""
	@echo "Configuration:"
	@echo "  SYMBOL=$(SYMBOL) INTERVAL=$(INTERVAL) DAYS=$(DAYS)"
	@echo ""
	@echo "Examples:"
	@echo "  make fetch-futures SYMBOL=ETHUSDT INTERVAL=15m DAYS=30"
	@echo "  make pipeline-futures-5m"

# ================================
# Quick Shortcuts (Recommended)
# ================================

.PHONY: fetch-futures-5m-7d
fetch-futures-5m-7d:
	@echo "📥 Fetching 7 days of BTCUSDT futures 5m data..."
	@$(PYTHON) tools/fetch_binance_ohlcv.py \
		--market futures \
		--symbol BTCUSDT \
		--interval 5m \
		--days 7 \
		--out $(OHLCV_DIR)/binance_futures_btcusdt_5m_7d.csv \
		--resume --progress

.PHONY: fetch-futures-15m-7d
fetch-futures-15m-7d:
	@echo "📥 Fetching 7 days of BTCUSDT futures 15m data..."
	@$(PYTHON) tools/fetch_binance_ohlcv.py \
		--market futures \
		--symbol BTCUSDT \
		--interval 15m \
		--days 7 \
		--out $(OHLCV_DIR)/binance_futures_btcusdt_15m_7d.csv \
		--resume --progress

.PHONY: fetch-spot-5m-30d
fetch-spot-5m-30d:
	@echo "📥 Fetching 30 days of BTCUSDT spot 5m data..."
	@$(PYTHON) tools/fetch_binance_ohlcv.py \
		--market spot \
		--symbol BTCUSDT \
		--interval 5m \
		--days 30 \
		--out $(OHLCV_DIR)/binance_spot_btcusdt_5m_30d.csv \
		--resume --progress

.PHONY: fetch-spot-15m-30d
fetch-spot-15m-30d:
	@echo "📥 Fetching 30 days of BTCUSDT spot 15m data..."
	@$(PYTHON) tools/fetch_binance_ohlcv.py \
		--market spot \
		--symbol BTCUSDT \
		--interval 15m \
		--days 30 \
		--out $(OHLCV_DIR)/binance_spot_btcusdt_15m_30d.csv \
		--resume --progress

# ================================
# Complete Pipelines
# ================================

.PHONY: pipeline-futures-5m
pipeline-futures-5m: dirs
	@echo "🔄 Running complete pipeline: futures 5m (fetch → validate → detect → backtest)"
	@echo ""
	@echo "Step 1/4: Fetch..."
	@$(PYTHON) tools/fetch_binance_ohlcv.py \
		--market futures --symbol BTCUSDT --interval 5m --days 7 \
		--out $(OHLCV_DIR)/binance_futures_btcusdt_5m_7d_raw.csv --resume --progress
	@echo ""
	@echo "Step 2/4: Validate & clean..."
	@$(PYTHON) tools/validate_clean_ohlcv.py \
		$(OHLCV_DIR)/binance_futures_btcusdt_5m_7d_raw.csv \
		--out $(OHLCV_DIR)/binance_futures_btcusdt_5m_7d.csv \
		--report $(CLEAN_DIR)/binance_futures_btcusdt_5m_7d_report.json \
		--fill drop --fee-bps 4
	@echo ""
	@echo "Step 3/4: Detect regimes..."
	@$(PYTHON) scripts/detect_regimes.py \
		$(OHLCV_DIR)/binance_futures_btcusdt_5m_7d.csv \
		--output $(REGIME_DIR)/binance_futures_btcusdt_5m_7d_regimes.jsonl
	@echo ""
	@echo "Step 4/4: Backtest..."
	@$(PYTHON) scripts/backtest_trending_v3.py \
		$(REGIME_DIR)/binance_futures_btcusdt_5m_7d_regimes.jsonl \
		--timeframe 5m \
		--export $(BACKTEST_DIR)/binance_futures_btcusdt_5m_7d_results.json
	@echo ""
	@echo "✅ Pipeline complete!"
	@echo "Results: $(BACKTEST_DIR)/binance_futures_btcusdt_5m_7d_results.json"

.PHONY: pipeline-futures-15m
pipeline-futures-15m: dirs
	@echo "🔄 Running complete pipeline: futures 15m (fetch → validate → detect → backtest)"
	@echo ""
	@echo "Step 1/4: Fetch..."
	@$(PYTHON) tools/fetch_binance_ohlcv.py \
		--market futures --symbol BTCUSDT --interval 15m --days 7 \
		--out $(OHLCV_DIR)/binance_futures_btcusdt_15m_7d_raw.csv --resume --progress
	@echo ""
	@echo "Step 2/4: Validate & clean..."
	@$(PYTHON) tools/validate_clean_ohlcv.py \
		$(OHLCV_DIR)/binance_futures_btcusdt_15m_7d_raw.csv \
		--out $(OHLCV_DIR)/binance_futures_btcusdt_15m_7d.csv \
		--report $(CLEAN_DIR)/binance_futures_btcusdt_15m_7d_report.json \
		--fill drop --fee-bps 4
	@echo ""
	@echo "Step 3/4: Detect regimes..."
	@$(PYTHON) scripts/detect_regimes.py \
		$(OHLCV_DIR)/binance_futures_btcusdt_15m_7d.csv \
		--output $(REGIME_DIR)/binance_futures_btcusdt_15m_7d_regimes.jsonl
	@echo ""
	@echo "Step 4/4: Backtest..."
	@$(PYTHON) scripts/backtest_trending_v3.py \
		$(REGIME_DIR)/binance_futures_btcusdt_15m_7d_regimes.jsonl \
		--timeframe 15m \
		--export $(BACKTEST_DIR)/binance_futures_btcusdt_15m_7d_results.json
	@echo ""
	@echo "✅ Pipeline complete!"
	@echo "Results: $(BACKTEST_DIR)/binance_futures_btcusdt_15m_7d_results.json"

# ================================
# Piped Workflows (Fetch → Validate)
# ================================

.PHONY: pipe-futures-clean
pipe-futures-clean: dirs
	@echo "🔄 Piped workflow: futures → validator → clean CSV"
	@$(PYTHON) tools/fetch_binance_ohlcv.py \
		--market futures --symbol $(SYMBOL) --interval $(INTERVAL) --days $(DAYS) --stdout \
	| $(PYTHON) tools/validate_clean_ohlcv.py /dev/stdin \
		--out $(CLEAN_DIR)/binance_futures_$(SYMBOL)_$(INTERVAL)_$(DAYS)d_clean.csv \
		--report $(CLEAN_DIR)/binance_futures_$(SYMBOL)_$(INTERVAL)_$(DAYS)d_report.json \
		--fill drop --fee-bps 4
	@echo "✅ Clean data: $(CLEAN_DIR)/binance_futures_$(SYMBOL)_$(INTERVAL)_$(DAYS)d_clean.csv"

.PHONY: pipe-spot-clean
pipe-spot-clean: dirs
	@echo "🔄 Piped workflow: spot → validator → clean CSV"
	@$(PYTHON) tools/fetch_binance_ohlcv.py \
		--market spot --symbol $(SYMBOL) --interval $(INTERVAL) --days $(DAYS) --stdout \
	| $(PYTHON) tools/validate_clean_ohlcv.py /dev/stdin \
		--out $(CLEAN_DIR)/binance_spot_$(SYMBOL)_$(INTERVAL)_$(DAYS)d_clean.csv \
		--report $(CLEAN_DIR)/binance_spot_$(SYMBOL)_$(INTERVAL)_$(DAYS)d_report.json \
		--fill drop --fee-bps 12
	@echo "✅ Clean data: $(CLEAN_DIR)/binance_spot_$(SYMBOL)_$(INTERVAL)_$(DAYS)d_clean.csv"

# ================================
# Individual Steps (Configurable)
# ================================

.PHONY: fetch-futures
fetch-futures: dirs
	@echo "📥 Fetching futures: $(SYMBOL) $(INTERVAL) $(DAYS)d"
	@$(PYTHON) tools/fetch_binance_ohlcv.py \
		--market futures \
		--symbol $(SYMBOL) \
		--interval $(INTERVAL) \
		--days $(DAYS) \
		--out $(OHLCV_DIR)/binance_futures_$(SYMBOL)_$(INTERVAL)_$(DAYS)d.csv \
		--resume --progress

.PHONY: fetch-spot
fetch-spot: dirs
	@echo "📥 Fetching spot: $(SYMBOL) $(INTERVAL) $(DAYS)d"
	@$(PYTHON) tools/fetch_binance_ohlcv.py \
		--market spot \
		--symbol $(SYMBOL) \
		--interval $(INTERVAL) \
		--days $(DAYS) \
		--out $(OHLCV_DIR)/binance_spot_$(SYMBOL)_$(INTERVAL)_$(DAYS)d.csv \
		--resume --progress

.PHONY: validate
validate: dirs
	@echo "🧹 Validating & cleaning OHLCV..."
	@$(PYTHON) tools/validate_clean_ohlcv.py \
		$(OHLCV_DIR)/$(FILE).csv \
		--out $(CLEAN_DIR)/$(FILE)_clean.csv \
		--report $(CLEAN_DIR)/$(FILE)_report.json \
		--fill drop

.PHONY: detect-regimes
detect-regimes: dirs
	@echo "🔍 Detecting market regimes..."
	@$(PYTHON) scripts/detect_regimes.py \
		$(OHLCV_DIR)/$(FILE).csv \
		--output $(REGIME_DIR)/$(FILE)_regimes.jsonl

.PHONY: backtest
backtest: dirs
	@echo "📊 Running backtest..."
	@$(PYTHON) scripts/backtest_trending_v3.py \
		$(REGIME_DIR)/$(FILE)_regimes.jsonl \
		--timeframe $(INTERVAL) \
		--export $(BACKTEST_DIR)/$(FILE)_results.json

# ================================
# Utilities
# ================================

.PHONY: dirs
dirs:
	@mkdir -p $(OHLCV_DIR) $(CLEAN_DIR) $(REGIME_DIR) $(BACKTEST_DIR)

.PHONY: clean-data
clean-data:
	@echo "🗑️  Cleaning all data directories..."
	@rm -rf $(OHLCV_DIR)/* $(CLEAN_DIR)/* $(REGIME_DIR)/* $(BACKTEST_DIR)/*
	@echo "✅ Data cleaned"

.PHONY: test-pipeline
test-pipeline: dirs
	@echo "🧪 Testing pipeline with 2 days of 5m futures data..."
	@$(PYTHON) tools/fetch_binance_ohlcv.py \
		--market futures --symbol BTCUSDT --interval 5m --days 2 \
		--out $(OHLCV_DIR)/test_futures_btcusdt_5m_2d.csv --progress
	@$(PYTHON) tools/validate_clean_ohlcv.py \
		$(OHLCV_DIR)/test_futures_btcusdt_5m_2d.csv \
		--out $(CLEAN_DIR)/test_futures_btcusdt_5m_2d_clean.csv \
		--report $(CLEAN_DIR)/test_report.json \
		--fill drop --fee-bps 4
	@cat $(CLEAN_DIR)/test_report.json
	@echo ""
	@echo "✅ Pipeline test complete"

.PHONY: show-report
show-report:
	@echo "📋 Latest quality reports:"
	@find $(CLEAN_DIR) -name "*_report.json" -exec echo {} \; -exec cat {} \; -exec echo "" \;

# ================================
# Option 1 (Futures Pivot) Helpers
# ================================

.PHONY: option1-test
option1-test: dirs
	@echo "🎯 Option 1 Testing: Futures 5m & 15m backtest"
	@echo ""
	@echo "=== 5m Timeframe ==="
	@$(MAKE) pipeline-futures-5m
	@echo ""
	@echo "=== 15m Timeframe ==="
	@$(MAKE) pipeline-futures-15m
	@echo ""
	@echo "✅ Option 1 testing complete"
	@echo "Compare results:"
	@echo "  - 5m:  $(BACKTEST_DIR)/binance_futures_btcusdt_5m_7d_results.json"
	@echo "  - 15m: $(BACKTEST_DIR)/binance_futures_btcusdt_15m_7d_results.json"

.PHONY: option1-compare
option1-compare:
	@echo "📊 Comparing Futures vs Spot (5m)..."
	@echo ""
	@echo "=== Futures 5m (last 7d) ==="
	@jq '{total_trades, win_rate_pct, avg_trade_pct, total_pnl_usd, avg_entry_atr_pct}' \
		$(BACKTEST_DIR)/binance_futures_btcusdt_5m_7d_results.json 2>/dev/null || echo "Not found"
	@echo ""
	@echo "=== Spot 5m (from previous test) ==="
	@jq '{total_trades, win_rate_pct, avg_trade_pct, total_pnl_usd}' \
		$(BACKTEST_DIR)/trending_v3_5m_7d.json 2>/dev/null || echo "Not found"
