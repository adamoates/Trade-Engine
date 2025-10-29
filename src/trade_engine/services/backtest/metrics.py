"""
Backtesting Performance Metrics Calculator

Calculates comprehensive trading performance metrics including:
- Win rate, profit factor
- Sharpe ratio, Sortino ratio
- Maximum drawdown
- Average win/loss, expectancy
- Trade duration statistics

CRITICAL: All financial calculations use Decimal (NON-NEGOTIABLE per CLAUDE.md).
"""

import math
from decimal import Decimal
from typing import List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from loguru import logger


@dataclass
class Trade:
    """Single completed trade."""
    entry_time: datetime
    exit_time: datetime
    entry_price: Decimal
    exit_price: Decimal
    side: str  # "long" | "short"
    quantity: Decimal
    pnl: Decimal  # P&L in USD
    pnl_pct: Decimal  # P&L as percentage
    reason: str = ""  # Exit reason

    @property
    def duration_seconds(self) -> float:
        """Trade duration in seconds."""
        return (self.exit_time - self.entry_time).total_seconds()

    @property
    def is_winner(self) -> bool:
        """True if profitable trade."""
        return self.pnl > 0


@dataclass
class BacktestMetrics:
    """Complete backtesting performance metrics."""

    # Basic stats
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    # P&L metrics
    total_pnl: Decimal = Decimal("0")
    total_pnl_pct: Decimal = Decimal("0")
    gross_profit: Decimal = Decimal("0")
    gross_loss: Decimal = Decimal("0")

    # Win/Loss stats
    win_rate: float = 0.0  # 0.0 to 1.0
    profit_factor: float = 0.0  # gross_profit / abs(gross_loss)
    avg_win: Decimal = Decimal("0")
    avg_loss: Decimal = Decimal("0")
    largest_win: Decimal = Decimal("0")
    largest_loss: Decimal = Decimal("0")

    # Risk metrics
    max_drawdown: Decimal = Decimal("0")
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0

    # Expectancy
    expectancy: Decimal = Decimal("0")  # Average profit per trade
    expectancy_pct: Decimal = Decimal("0")

    # Duration stats
    avg_trade_duration_seconds: float = 0.0
    avg_winning_duration_seconds: float = 0.0
    avg_losing_duration_seconds: float = 0.0

    # Equity curve
    starting_equity: Decimal = Decimal("10000")
    ending_equity: Decimal = Decimal("10000")
    peak_equity: Decimal = Decimal("10000")

    # Time range
    start_time: datetime | None = None
    end_time: datetime | None = None

    # Trade list
    trades: List[Trade] = field(default_factory=list)


class MetricsCalculator:
    """
    Calculates comprehensive backtesting metrics from trade history.

    Uses Decimal for all financial calculations to avoid float rounding errors.
    """

    def __init__(self, starting_equity: Decimal = Decimal("10000")):
        """
        Initialize metrics calculator.

        Args:
            starting_equity: Starting capital (default: $10,000)
        """
        self.starting_equity = starting_equity
        self.trades: List[Trade] = []
        self.equity_curve: List[Decimal] = [starting_equity]

        logger.info(f"MetricsCalculator initialized | Starting equity: ${starting_equity:,.2f}")

    def add_trade(self, trade: Trade):
        """
        Record a completed trade.

        Args:
            trade: Completed Trade object
        """
        self.trades.append(trade)

        # Update equity curve
        current_equity = self.equity_curve[-1] + trade.pnl
        self.equity_curve.append(current_equity)

    def calculate(self) -> BacktestMetrics:
        """
        Calculate comprehensive metrics from all recorded trades.

        Returns:
            BacktestMetrics with all performance statistics
        """
        metrics = BacktestMetrics(
            starting_equity=self.starting_equity,
            trades=self.trades
        )

        if not self.trades:
            logger.warning("No trades to calculate metrics")
            return metrics

        # Basic counts
        metrics.total_trades = len(self.trades)
        metrics.winning_trades = sum(1 for t in self.trades if t.is_winner)
        metrics.losing_trades = metrics.total_trades - metrics.winning_trades

        # P&L calculations
        metrics.total_pnl = sum(t.pnl for t in self.trades)
        metrics.gross_profit = sum(t.pnl for t in self.trades if t.pnl > 0)
        metrics.gross_loss = sum(t.pnl for t in self.trades if t.pnl < 0)

        # Win rate
        if metrics.total_trades > 0:
            metrics.win_rate = metrics.winning_trades / metrics.total_trades

        # Profit factor
        if metrics.gross_loss != 0:
            metrics.profit_factor = float(metrics.gross_profit / abs(metrics.gross_loss))
        elif metrics.gross_profit > 0:
            metrics.profit_factor = float('inf')  # No losses

        # Average win/loss
        if metrics.winning_trades > 0:
            winning_pnls = [t.pnl for t in self.trades if t.is_winner]
            metrics.avg_win = sum(winning_pnls) / Decimal(str(metrics.winning_trades))
            metrics.largest_win = max(winning_pnls)

        if metrics.losing_trades > 0:
            losing_pnls = [t.pnl for t in self.trades if not t.is_winner]
            metrics.avg_loss = sum(losing_pnls) / Decimal(str(metrics.losing_trades))
            metrics.largest_loss = min(losing_pnls)  # Most negative

        # Expectancy (average profit per trade)
        if metrics.total_trades > 0:
            metrics.expectancy = metrics.total_pnl / Decimal(str(metrics.total_trades))

        # Equity curve calculations
        metrics.ending_equity = self.equity_curve[-1]
        metrics.peak_equity = max(self.equity_curve)

        # Maximum drawdown
        drawdowns = []
        peak = self.equity_curve[0]
        for equity in self.equity_curve:
            peak = max(peak, equity)
            drawdown = peak - equity
            drawdowns.append(drawdown)

        metrics.max_drawdown = max(drawdowns) if drawdowns else Decimal("0")
        if metrics.peak_equity > 0:
            metrics.max_drawdown_pct = float(metrics.max_drawdown / metrics.peak_equity)

        # Sharpe ratio (annualized)
        metrics.sharpe_ratio = self._calculate_sharpe_ratio()

        # Sortino ratio (annualized, downside deviation only)
        metrics.sortino_ratio = self._calculate_sortino_ratio()

        # Trade duration stats
        durations = [t.duration_seconds for t in self.trades]
        if durations:
            metrics.avg_trade_duration_seconds = sum(durations) / len(durations)

        winning_durations = [t.duration_seconds for t in self.trades if t.is_winner]
        if winning_durations:
            metrics.avg_winning_duration_seconds = sum(winning_durations) / len(winning_durations)

        losing_durations = [t.duration_seconds for t in self.trades if not t.is_winner]
        if losing_durations:
            metrics.avg_losing_duration_seconds = sum(losing_durations) / len(losing_durations)

        # Time range
        if self.trades:
            metrics.start_time = min(t.entry_time for t in self.trades)
            metrics.end_time = max(t.exit_time for t in self.trades)

        # Total P&L percentage
        if self.starting_equity > 0:
            metrics.total_pnl_pct = (metrics.total_pnl / self.starting_equity) * Decimal("100")

        # Expectancy percentage
        if self.starting_equity > 0:
            metrics.expectancy_pct = (metrics.expectancy / self.starting_equity) * Decimal("100")

        return metrics

    def _calculate_sharpe_ratio(self) -> float:
        """
        Calculate annualized Sharpe ratio.

        Sharpe Ratio = (Mean Return - Risk Free Rate) / Std Dev of Returns
        Assumes risk-free rate = 0 for simplicity.

        Returns:
            Sharpe ratio (annualized)
        """
        if len(self.trades) < 2:
            return 0.0

        # Calculate returns for each trade (as percentage)
        # Keep as Decimal for precision in statistical calculations
        returns = [t.pnl_pct for t in self.trades]

        mean_return = sum(returns) / len(returns)

        # Standard deviation (convert to float only for math.sqrt)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = float(variance) ** 0.5  # Use ** 0.5 instead of math.sqrt for Decimal

        if std_dev == 0:
            return 0.0

        sharpe = float(mean_return) / std_dev

        # Annualize (assuming ~252 trading days per year, ~60 trades per day for MFT)
        # For L2 scalping with 5-60 second holds, could have ~100+ trades per day
        # Use conservative 50 trades/day estimate
        trades_per_year = 252 * 50
        sharpe_annualized = sharpe * math.sqrt(trades_per_year / len(self.trades))

        return sharpe_annualized

    def _calculate_sortino_ratio(self) -> float:
        """
        Calculate annualized Sortino ratio (only penalizes downside volatility).

        Sortino Ratio = (Mean Return - Risk Free Rate) / Downside Deviation

        Returns:
            Sortino ratio (annualized)
        """
        if len(self.trades) < 2:
            return 0.0

        # Keep as Decimal for precision
        returns = [t.pnl_pct for t in self.trades]
        mean_return = sum(returns) / len(returns)

        # Downside deviation (only negative returns)
        negative_returns = [r for r in returns if r < 0]

        if not negative_returns:
            return float('inf')  # No downside volatility

        downside_variance = sum(r ** 2 for r in negative_returns) / len(returns)
        downside_dev = float(downside_variance) ** 0.5  # Use ** 0.5 for Decimal compatibility

        if downside_dev == 0:
            return 0.0

        sortino = float(mean_return) / downside_dev

        # Annualize
        trades_per_year = 252 * 50
        sortino_annualized = sortino * math.sqrt(trades_per_year / len(self.trades))

        return sortino_annualized


def format_metrics(metrics: BacktestMetrics) -> str:
    """
    Format metrics as human-readable text report.

    Args:
        metrics: BacktestMetrics object

    Returns:
        Formatted string report
    """
    lines = []
    lines.append("=" * 70)
    lines.append("BACKTEST PERFORMANCE REPORT")
    lines.append("=" * 70)
    lines.append("")

    # Time range
    if metrics.start_time and metrics.end_time:
        duration = metrics.end_time - metrics.start_time
        lines.append(f"Period:          {metrics.start_time.date()} to {metrics.end_time.date()}")
        lines.append(f"Duration:        {duration.days} days, {duration.seconds // 3600} hours")
    lines.append("")

    # Trade summary
    lines.append("TRADE SUMMARY")
    lines.append("-" * 70)
    lines.append(f"Total Trades:    {metrics.total_trades}")
    lines.append(f"Winning Trades:  {metrics.winning_trades} ({metrics.win_rate*100:.1f}%)")
    lines.append(f"Losing Trades:   {metrics.losing_trades} ({(1-metrics.win_rate)*100:.1f}%)")
    lines.append("")

    # P&L
    lines.append("PROFIT & LOSS")
    lines.append("-" * 70)
    lines.append(f"Total P&L:       ${metrics.total_pnl:,.2f} ({metrics.total_pnl_pct:+.2f}%)")
    lines.append(f"Gross Profit:    ${metrics.gross_profit:,.2f}")
    lines.append(f"Gross Loss:      ${metrics.gross_loss:,.2f}")
    lines.append(f"Profit Factor:   {metrics.profit_factor:.2f}")
    lines.append(f"Expectancy:      ${metrics.expectancy:.2f} per trade ({metrics.expectancy_pct:+.3f}%)")
    lines.append("")

    # Win/Loss stats
    lines.append("WIN/LOSS STATISTICS")
    lines.append("-" * 70)
    lines.append(f"Average Win:     ${metrics.avg_win:,.2f}")
    lines.append(f"Average Loss:    ${metrics.avg_loss:,.2f}")
    lines.append(f"Largest Win:     ${metrics.largest_win:,.2f}")
    lines.append(f"Largest Loss:    ${metrics.largest_loss:,.2f}")
    lines.append("")

    # Risk metrics
    lines.append("RISK METRICS")
    lines.append("-" * 70)
    lines.append(f"Max Drawdown:    ${metrics.max_drawdown:,.2f} ({metrics.max_drawdown_pct*100:.2f}%)")
    lines.append(f"Sharpe Ratio:    {metrics.sharpe_ratio:.2f} (annualized)")
    lines.append(f"Sortino Ratio:   {metrics.sortino_ratio:.2f} (annualized)")
    lines.append("")

    # Equity
    lines.append("EQUITY")
    lines.append("-" * 70)
    lines.append(f"Starting:        ${metrics.starting_equity:,.2f}")
    lines.append(f"Peak:            ${metrics.peak_equity:,.2f}")
    lines.append(f"Ending:          ${metrics.ending_equity:,.2f}")
    lines.append(f"Return:          {metrics.total_pnl_pct:+.2f}%")
    lines.append("")

    # Trade duration
    lines.append("TRADE DURATION")
    lines.append("-" * 70)
    lines.append(f"Avg Duration:    {metrics.avg_trade_duration_seconds:.1f} seconds")
    lines.append(f"Avg Win:         {metrics.avg_winning_duration_seconds:.1f} seconds")
    lines.append(f"Avg Loss:        {metrics.avg_losing_duration_seconds:.1f} seconds")
    lines.append("")

    lines.append("=" * 70)

    return "\n".join(lines)
