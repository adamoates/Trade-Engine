"""
Backtesting framework for L2 imbalance strategy.

Modules:
- l2_data_loader: Load historical L2 orderbook snapshots
- metrics: Calculate performance metrics (win rate, Sharpe, drawdown, etc.)
- engine: Core backtesting engine that replays data through strategy

Usage:
    from trade_engine.services.backtest import run_backtest, L2StrategyConfig
    from decimal import Decimal

    results = run_backtest(
        data_file="data/l2_snapshots/l2_BTCUSDT_20251024.jsonl",
        starting_capital=Decimal("10000")
    )

    print(f"Win rate: {results.win_rate*100:.1f}%")
    print(f"Total P&L: ${results.total_pnl:,.2f}")
"""

from trade_engine.services.backtest.l2_data_loader import L2DataLoader, load_multiple_files
from trade_engine.services.backtest.metrics import (
    Trade,
    BacktestMetrics,
    MetricsCalculator,
    format_metrics
)
from trade_engine.services.backtest.engine import BacktestEngine, run_backtest
from trade_engine.services.strategies.alpha_l2_imbalance import L2StrategyConfig

__all__ = [
    "L2DataLoader",
    "load_multiple_files",
    "Trade",
    "BacktestMetrics",
    "MetricsCalculator",
    "format_metrics",
    "BacktestEngine",
    "run_backtest",
    "L2StrategyConfig",
]
