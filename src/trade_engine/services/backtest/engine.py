"""
L2 Imbalance Strategy Backtesting Engine

Replays historical L2 orderbook data through the L2ImbalanceStrategy
and tracks all trades, P&L, and performance metrics.

Usage:
    engine = BacktestEngine(
        data_file="data/l2_snapshots/l2_BTCUSDT_20251024.jsonl",
        starting_capital=Decimal("10000")
    )
    results = engine.run()
    print(results.report)
"""

from decimal import Decimal
from typing import Optional, Dict
from datetime import datetime
from pathlib import Path
from loguru import logger

from trade_engine.services.backtest.l2_data_loader import L2DataLoader
from trade_engine.services.backtest.metrics import MetricsCalculator, Trade, BacktestMetrics, format_metrics
from trade_engine.domain.strategies.alpha_l2_imbalance import L2ImbalanceStrategy, L2StrategyConfig
from trade_engine.core.types import Bar


class BacktestEngine:
    """
    Backtesting engine for L2 imbalance strategy.

    Replays historical L2 orderbook snapshots through the strategy,
    simulates trade execution, and calculates comprehensive performance metrics.
    """

    def __init__(
        self,
        data_file: str | Path,
        starting_capital: Decimal = Decimal("10000"),
        strategy_config: Optional[L2StrategyConfig] = None
    ):
        """
        Initialize backtesting engine.

        Args:
            data_file: Path to JSONL file with L2 snapshots
            starting_capital: Starting equity (default: $10,000)
            strategy_config: L2 strategy configuration (uses defaults if None)
        """
        self.data_file = Path(data_file)
        self.starting_capital = starting_capital
        self.strategy_config = strategy_config or L2StrategyConfig()

        # Components
        self.data_loader = L2DataLoader(self.data_file)
        self.metrics_calc = MetricsCalculator(starting_capital)

        # State tracking
        self.current_equity = starting_capital
        self.in_position = False
        self.position_side: Optional[str] = None  # "long" | "short"
        self.entry_price: Optional[Decimal] = None
        self.entry_time: Optional[datetime] = None
        self.position_qty: Optional[Decimal] = None

        # Counters
        self.snapshots_processed = 0
        self.signals_generated = 0

        logger.info("=" * 70)
        logger.info("BACKTEST ENGINE INITIALIZED")
        logger.info("=" * 70)
        logger.info(f"Data file:        {self.data_file.name}")
        logger.info(f"Starting capital: ${self.starting_capital:,.2f}")
        logger.info(f"Strategy config:")
        logger.info(f"  Buy threshold:  {self.strategy_config.buy_threshold}")
        logger.info(f"  Sell threshold: {self.strategy_config.sell_threshold}")
        logger.info(f"  Depth:          {self.strategy_config.depth} levels")
        logger.info(f"  Position size:  ${self.strategy_config.position_size_usd:,.2f}")
        logger.info(f"  Profit target:  {self.strategy_config.profit_target_pct}%")
        logger.info(f"  Stop loss:      {self.strategy_config.stop_loss_pct}%")
        logger.info("=" * 70)

    def run(self) -> BacktestMetrics:
        """
        Run backtest on historical data.

        Returns:
            BacktestMetrics with complete performance results
        """
        logger.info("Starting backtest...")

        # Create strategy (note: strategy needs an order_book reference)
        # We'll create a placeholder and update it each snapshot
        strategy = None

        try:
            for order_book in self.data_loader.load():
                self.snapshots_processed += 1

                # Create/update strategy with current order book
                if strategy is None:
                    strategy = L2ImbalanceStrategy(
                        symbol=order_book.symbol,
                        order_book=order_book,
                        config=self.strategy_config
                    )
                else:
                    # Update strategy's order book reference
                    strategy.order_book = order_book

                # Create Bar from order book snapshot (for strategy interface)
                mid_price = order_book.get_mid_price()
                if not mid_price:
                    continue

                bar = Bar(
                    timestamp=int(order_book.last_update_time * 1000),
                    open=mid_price,
                    high=mid_price,
                    low=mid_price,
                    close=mid_price,
                    volume=Decimal("0"),  # Not applicable for L2
                    gap_flag=False,
                    zero_vol_flag=False
                )

                # Generate signals
                signals = strategy.on_bar(bar)

                # Process signals
                for signal in signals:
                    self.signals_generated += 1
                    self._process_signal(signal, order_book.last_update_time)

                # Log progress
                if self.snapshots_processed % 10000 == 0:
                    logger.info(
                        f"Processed {self.snapshots_processed:,} snapshots | "
                        f"Trades: {len(self.metrics_calc.trades)} | "
                        f"Equity: ${self.current_equity:,.2f}"
                    )

        except KeyboardInterrupt:
            logger.warning("Backtest interrupted by user")
        except Exception as e:
            logger.error(f"Backtest error: {e}")
            raise

        # Calculate final metrics
        logger.info("Calculating metrics...")
        metrics = self.metrics_calc.calculate()

        # Log summary
        logger.info("=" * 70)
        logger.info("BACKTEST COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Snapshots processed: {self.snapshots_processed:,}")
        logger.info(f"Signals generated:   {self.signals_generated}")
        logger.info(f"Trades executed:     {metrics.total_trades}")
        logger.info(f"Win rate:            {metrics.win_rate*100:.1f}%")
        logger.info(f"Total P&L:           ${metrics.total_pnl:,.2f} ({metrics.total_pnl_pct:+.2f}%)")
        logger.info(f"Sharpe ratio:        {metrics.sharpe_ratio:.2f}")
        logger.info(f"Max drawdown:        ${metrics.max_drawdown:,.2f} ({metrics.max_drawdown_pct*100:.2f}%)")
        logger.info("=" * 70)

        return metrics

    def _process_signal(self, signal, timestamp: float):
        """
        Process a trading signal (entry or exit).

        Args:
            signal: Signal from strategy
            timestamp: Current timestamp
        """
        current_time = datetime.fromtimestamp(timestamp)

        if signal.side in ["buy", "sell"]:
            # Entry signal
            if not self.in_position:
                self._enter_position(signal, current_time)

        elif signal.side == "close":
            # Exit signal
            if self.in_position:
                self._exit_position(signal, current_time)

    def _enter_position(self, signal, entry_time: datetime):
        """
        Enter a position.

        Args:
            signal: Entry signal
            entry_time: Entry timestamp
        """
        self.in_position = True
        self.position_side = "long" if signal.side == "buy" else "short"
        self.entry_price = signal.price
        self.entry_time = entry_time
        self.position_qty = signal.qty

        logger.debug(
            f"ENTER {self.position_side.upper()} | "
            f"Price: {self.entry_price} | "
            f"Qty: {self.position_qty:.4f} | "
            f"Reason: {signal.reason}"
        )

    def _exit_position(self, signal, exit_time: datetime):
        """
        Exit a position and record trade.

        Args:
            signal: Exit signal
            exit_time: Exit timestamp
        """
        if not self.in_position or not self.entry_price or not self.entry_time:
            return

        exit_price = signal.price

        # Calculate P&L
        if self.position_side == "long":
            pnl = (exit_price - self.entry_price) * self.position_qty
            pnl_pct = ((exit_price - self.entry_price) / self.entry_price) * Decimal("100")
        else:  # short
            pnl = (self.entry_price - exit_price) * self.position_qty
            pnl_pct = ((self.entry_price - exit_price) / self.entry_price) * Decimal("100")

        # Update equity
        self.current_equity += pnl

        # Record trade
        trade = Trade(
            entry_time=self.entry_time,
            exit_time=exit_time,
            entry_price=self.entry_price,
            exit_price=exit_price,
            side=self.position_side,
            quantity=self.position_qty,
            pnl=pnl,
            pnl_pct=pnl_pct,
            reason=signal.reason
        )

        self.metrics_calc.add_trade(trade)

        logger.debug(
            f"EXIT {self.position_side.upper()} | "
            f"Entry: {self.entry_price} | "
            f"Exit: {exit_price} | "
            f"P&L: ${pnl:+,.2f} ({pnl_pct:+.2f}%) | "
            f"Reason: {signal.reason}"
        )

        # Reset position
        self.in_position = False
        self.position_side = None
        self.entry_price = None
        self.entry_time = None
        self.position_qty = None


def run_backtest(
    data_file: str | Path,
    starting_capital: Decimal = Decimal("10000"),
    strategy_config: Optional[L2StrategyConfig] = None,
    output_file: Optional[str | Path] = None
) -> BacktestMetrics:
    """
    Convenience function to run a backtest.

    Args:
        data_file: Path to L2 data file
        starting_capital: Starting equity
        strategy_config: Strategy configuration
        output_file: Optional path to save report

    Returns:
        BacktestMetrics object
    """
    engine = BacktestEngine(
        data_file=data_file,
        starting_capital=starting_capital,
        strategy_config=strategy_config
    )

    metrics = engine.run()

    # Generate report
    report = format_metrics(metrics)
    print(report)

    # Save report if requested
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(report)
        logger.info(f"Report saved to: {output_path}")

    return metrics
