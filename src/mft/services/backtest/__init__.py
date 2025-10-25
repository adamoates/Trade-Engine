"""
Backtesting framework for L2 imbalance strategy.

Modules:
- l2_data_loader: Load historical L2 orderbook snapshots
- metrics: Calculate performance metrics (win rate, Sharpe, drawdown, etc.)
- engine: Core backtesting engine that replays data through strategy

Usage:
    from mft.services.backtest import run_backtest, L2StrategyConfig
    from decimal import Decimal

    results = run_backtest(
        data_file="data/l2_snapshots/l2_BTCUSDT_20251024.jsonl",
        starting_capital=Decimal("10000")
    )

    print(f"Win rate: {results.win_rate*100:.1f}%")
    print(f"Total P&L: ${results.total_pnl:,.2f}")
"""

from mft.services.backtest.l2_data_loader import L2DataLoader, load_multiple_files
from mft.services.backtest.metrics import (
    Trade,
    BacktestMetrics,
    MetricsCalculator,
    format_metrics
)
from mft.services.backtest.engine import BacktestEngine, run_backtest
from mft.services.strategies.alpha_l2_imbalance import L2StrategyConfig

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
