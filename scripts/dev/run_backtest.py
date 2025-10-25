#!/usr/bin/env python3
"""
L2 Imbalance Strategy Backtesting Runner

Run backtests on historical L2 orderbook data to validate strategy performance.

Usage:
    # Basic backtest (uses default parameters)
    python tools/run_backtest.py --data data/l2_snapshots/l2_BTCUSDT_20251024.jsonl

    # Custom capital and strategy parameters
    python tools/run_backtest.py \
        --data data/l2_snapshots/l2_BTCUSDT_20251024.jsonl \
        --capital 10000 \
        --buy-threshold 3.0 \
        --sell-threshold 0.33 \
        --depth 5 \
        --position-size 1000 \
        --tp 0.2 \
        --sl 0.15

    # Save report to file
    python tools/run_backtest.py \
        --data data/l2_snapshots/l2_BTCUSDT_20251024.jsonl \
        --output results/backtest_btc_20251024.txt

    # Backtest multiple files
    python tools/run_backtest.py \
        --data data/l2_snapshots/l2_BTCUSDT_*.jsonl \
        --capital 10000

    # Use test fixture for quick testing
    python tools/run_backtest.py \
        --data tests/fixtures/l2_data/btc_strong_rally_2025_10_12.json \
        --capital 1000

Performance Gates (from CLAUDE.md):
- Win rate: >50% required to proceed to paper trading
- Sharpe ratio: >1.0 preferred
- Max drawdown: <10% of capital preferred
- Profit factor: >1.5 preferred
"""

import sys
import argparse
import json
from pathlib import Path
from decimal import Decimal
from datetime import datetime
import glob

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from mft.services.backtest import run_backtest, L2StrategyConfig, BacktestMetrics


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Run L2 imbalance strategy backtest',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Data
    parser.add_argument(
        '--data',
        type=str,
        required=True,
        help='Path to L2 data file (JSONL or JSON). Supports wildcards for multiple files.'
    )

    # Capital
    parser.add_argument(
        '--capital',
        type=float,
        default=10000.0,
        help='Starting capital in USD (default: 10000)'
    )

    # Strategy parameters
    parser.add_argument(
        '--buy-threshold',
        type=float,
        default=3.0,
        help='Buy signal threshold (bid/ask ratio, default: 3.0)'
    )
    parser.add_argument(
        '--sell-threshold',
        type=float,
        default=0.33,
        help='Sell signal threshold (bid/ask ratio, default: 0.33)'
    )
    parser.add_argument(
        '--depth',
        type=int,
        default=5,
        help='Order book depth to analyze (default: 5 levels)'
    )
    parser.add_argument(
        '--position-size',
        type=float,
        default=1000.0,
        help='Position size in USD (default: 1000)'
    )
    parser.add_argument(
        '--tp',
        type=float,
        default=0.2,
        help='Take profit percentage (default: 0.2)'
    )
    parser.add_argument(
        '--sl',
        type=float,
        default=0.15,
        help='Stop loss percentage (default: 0.15)'
    )
    parser.add_argument(
        '--max-hold',
        type=int,
        default=60,
        help='Maximum hold time in seconds (default: 60)'
    )

    # Output
    parser.add_argument(
        '--output',
        type=str,
        help='Save report to file (default: print to console)'
    )
    parser.add_argument(
        '--json',
        type=str,
        help='Save metrics as JSON to file'
    )

    # Logging
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging (DEBUG level)'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress non-critical output'
    )

    return parser.parse_args()


def metrics_to_dict(metrics: BacktestMetrics) -> dict:
    """
    Convert BacktestMetrics to JSON-serializable dict.

    Args:
        metrics: BacktestMetrics object

    Returns:
        Dict with all metrics
    """
    return {
        "summary": {
            "total_trades": metrics.total_trades,
            "winning_trades": metrics.winning_trades,
            "losing_trades": metrics.losing_trades,
            "win_rate": metrics.win_rate,
        },
        "pnl": {
            "total_pnl": float(metrics.total_pnl),
            "total_pnl_pct": float(metrics.total_pnl_pct),
            "gross_profit": float(metrics.gross_profit),
            "gross_loss": float(metrics.gross_loss),
            "profit_factor": metrics.profit_factor,
            "expectancy": float(metrics.expectancy),
            "expectancy_pct": float(metrics.expectancy_pct),
        },
        "win_loss_stats": {
            "avg_win": float(metrics.avg_win),
            "avg_loss": float(metrics.avg_loss),
            "largest_win": float(metrics.largest_win),
            "largest_loss": float(metrics.largest_loss),
        },
        "risk": {
            "max_drawdown": float(metrics.max_drawdown),
            "max_drawdown_pct": metrics.max_drawdown_pct,
            "sharpe_ratio": metrics.sharpe_ratio,
            "sortino_ratio": metrics.sortino_ratio,
        },
        "equity": {
            "starting": float(metrics.starting_equity),
            "peak": float(metrics.peak_equity),
            "ending": float(metrics.ending_equity),
        },
        "duration": {
            "avg_trade_seconds": metrics.avg_trade_duration_seconds,
            "avg_win_seconds": metrics.avg_winning_duration_seconds,
            "avg_loss_seconds": metrics.avg_losing_duration_seconds,
        },
        "period": {
            "start": metrics.start_time.isoformat() if metrics.start_time else None,
            "end": metrics.end_time.isoformat() if metrics.end_time else None,
        }
    }


def evaluate_performance(metrics: BacktestMetrics) -> dict:
    """
    Evaluate if performance meets Phase 5 gate criteria.

    Args:
        metrics: BacktestMetrics object

    Returns:
        Dict with pass/fail results
    """
    criteria = {
        "win_rate_50pct": {
            "target": 0.50,
            "actual": metrics.win_rate,
            "passed": metrics.win_rate >= 0.50,
            "description": "Win rate must be ≥50% to proceed to paper trading"
        },
        "sharpe_ratio_1": {
            "target": 1.0,
            "actual": metrics.sharpe_ratio,
            "passed": metrics.sharpe_ratio >= 1.0,
            "description": "Sharpe ratio ≥1.0 preferred (risk-adjusted returns)"
        },
        "profit_factor_1_5": {
            "target": 1.5,
            "actual": metrics.profit_factor,
            "passed": metrics.profit_factor >= 1.5,
            "description": "Profit factor ≥1.5 preferred (gross profit / gross loss)"
        },
        "max_drawdown_10pct": {
            "target": 0.10,
            "actual": metrics.max_drawdown_pct,
            "passed": metrics.max_drawdown_pct <= 0.10,
            "description": "Max drawdown ≤10% preferred"
        },
        "positive_expectancy": {
            "target": 0.0,
            "actual": float(metrics.expectancy),
            "passed": metrics.expectancy > 0,
            "description": "Positive expectancy required (avg profit per trade > 0)"
        }
    }

    # Calculate overall pass
    critical_passed = criteria["win_rate_50pct"]["passed"] and criteria["positive_expectancy"]["passed"]
    all_passed = all(c["passed"] for c in criteria.values())

    return {
        "criteria": criteria,
        "critical_passed": critical_passed,
        "all_passed": all_passed,
        "recommendation": (
            "✅ PROCEED to paper trading (meets critical criteria)" if critical_passed
            else "❌ DO NOT proceed - improve strategy or adjust parameters"
        )
    }


def main():
    """Main entry point."""
    args = parse_args()

    # Configure logging
    if args.quiet:
        logger.remove()
        logger.add(sys.stderr, level="WARNING")
    elif args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.remove()
        logger.add(sys.stderr, level="INFO")

    # Resolve data files (support wildcards)
    data_files = glob.glob(args.data)
    if not data_files:
        logger.error(f"No files found matching: {args.data}")
        sys.exit(1)

    if len(data_files) > 1:
        logger.warning(f"Multiple files found: {len(data_files)} files")
        logger.warning("Currently only the first file will be used")
        # TODO: Implement multi-file backtesting
        data_file = data_files[0]
    else:
        data_file = data_files[0]

    logger.info(f"Data file: {data_file}")

    # Create strategy config
    strategy_config = L2StrategyConfig(
        buy_threshold=Decimal(str(args.buy_threshold)),
        sell_threshold=Decimal(str(args.sell_threshold)),
        depth=args.depth,
        position_size_usd=Decimal(str(args.position_size)),
        profit_target_pct=Decimal(str(args.tp)),
        stop_loss_pct=Decimal(str(args.sl)),
        max_hold_time_seconds=args.max_hold
    )

    # Run backtest
    try:
        metrics = run_backtest(
            data_file=data_file,
            starting_capital=Decimal(str(args.capital)),
            strategy_config=strategy_config,
            output_file=args.output
        )

        # Evaluate performance
        print("\n")
        logger.info("=" * 70)
        logger.info("PERFORMANCE EVALUATION (Phase 5 Gate Criteria)")
        logger.info("=" * 70)

        evaluation = evaluate_performance(metrics)

        for name, criterion in evaluation["criteria"].items():
            status = "✅ PASS" if criterion["passed"] else "❌ FAIL"
            logger.info(f"{status} | {criterion['description']}")
            logger.info(f"       Target: {criterion['target']} | Actual: {criterion['actual']:.3f}")
            logger.info("")

        logger.info("=" * 70)
        logger.info(f"RECOMMENDATION: {evaluation['recommendation']}")
        logger.info("=" * 70)

        # Save JSON if requested
        if args.json:
            json_data = {
                "backtest_date": datetime.now().isoformat(),
                "data_file": str(data_file),
                "strategy_config": {
                    "buy_threshold": float(strategy_config.buy_threshold),
                    "sell_threshold": float(strategy_config.sell_threshold),
                    "depth": strategy_config.depth,
                    "position_size_usd": float(strategy_config.position_size_usd),
                    "profit_target_pct": float(strategy_config.profit_target_pct),
                    "stop_loss_pct": float(strategy_config.stop_loss_pct),
                    "max_hold_time_seconds": strategy_config.max_hold_time_seconds,
                },
                "metrics": metrics_to_dict(metrics),
                "evaluation": evaluation
            }

            json_path = Path(args.json)
            json_path.parent.mkdir(parents=True, exist_ok=True)
            with open(json_path, 'w') as f:
                json.dump(json_data, f, indent=2)
            logger.info(f"JSON metrics saved to: {json_path}")

        # Exit code based on performance
        if evaluation["critical_passed"]:
            sys.exit(0)  # Success
        else:
            sys.exit(1)  # Failure (below gate criteria)

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        raise


if __name__ == '__main__':
    main()
