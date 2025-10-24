# 4-Hour Live Trading POC - Continuation Guide

**Branch**: `feature/poc-live-trading`
**Goal**: Complete and run 4-hour live trading test with $500 capital targeting $6 profit

## Progress: 2/5 Components Complete ✅

### ✅ Completed
1. **WebSocket Data Stream** (`app/data/binance_stream.py`)
   - Real-time 5-minute candle streaming
   - Auto-reconnection handling
   - Testnet and live support

2. **Position Manager** (`app/engine/position_manager.py`)
   - Position tracking with unrealized P&L
   - Stop loss / take profit checking
   - Trade history and statistics

### 🔨 Still Needed (Est. 2-3 hours)

3. **Simple MA Crossover Strategy**
   - File: `app/strategies/ma_crossover_simple.py`
   - Logic: Buy when fast MA crosses above slow MA, sell on reverse
   - Parameters: MA(9) and MA(21)
   - Inputs: List of candles
   - Output: "BUY", "SELL", or "HOLD" signal

4. **Trading Runner**
   - File: `tools/run_live_poc.py`
   - Orchestrates: Data stream → Strategy → Position manager → Broker
   - Event loop: On each candle close, check signals and execute
   - Reporting: Log trades, check targets, generate metrics

5. **End-to-End Testing**
   - Test data stream connection
   - Test position manager calculations
   - Test strategy signal generation
   - Dry run without actual trades

## Quick Start to Continue

```bash
# 1. Ensure on correct branch
git checkout feature/poc-live-trading
git pull origin feature/poc-live-trading

# 2. Verify environment
source .venv/bin/activate
pip install websockets  # If not already installed

# 3. Test data stream (should print live candles)
python -m app.data.binance_stream
# Press Ctrl+C after seeing a few candles

# 4. Create remaining components (see templates below)
```

## Component Templates

### 3. MA Crossover Strategy (Create: `app/strategies/ma_crossover_simple.py`)

```python
"""Simple MA crossover strategy for POC."""

from typing import List, Optional
from dataclasses import dataclass


@dataclass
class Candle:
    """Candle data."""
    close: float
    # ... (match structure from binance_stream.py)


class MACrossoverStrategy:
    """
    Moving average crossover strategy.

    - Buy: Fast MA crosses above Slow MA
    - Sell: Fast MA crosses below Slow MA
    """

    def __init__(self, fast_period: int = 9, slow_period: int = 21):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.candle_history: List[Candle] = []

    def update(self, candle: Candle) -> Optional[str]:
        """
        Update with new candle and generate signal.

        Returns:
            "BUY", "SELL", or None
        """
        self.candle_history.append(candle)

        # Need enough history
        if len(self.candle_history) < self.slow_period + 1:
            return None

        # Calculate MAs
        closes = [c.close for c in self.candle_history]

        fast_ma_prev = sum(closes[-self.fast_period-1:-1]) / self.fast_period
        fast_ma_curr = sum(closes[-self.fast_period:]) / self.fast_period

        slow_ma_prev = sum(closes[-self.slow_period-1:-1]) / self.slow_period
        slow_ma_curr = sum(closes[-self.slow_period:]) / self.slow_period

        # Detect crossovers
        if fast_ma_prev <= slow_ma_prev and fast_ma_curr > slow_ma_curr:
            return "BUY"  # Bullish crossover
        elif fast_ma_prev >= slow_ma_prev and fast_ma_curr < slow_ma_curr:
            return "SELL"  # Bearish crossover

        return None
```

### 4. Trading Runner (Create: `tools/run_live_poc.py`)

```python
"""4-hour live trading POC runner."""

import asyncio
import os
from datetime import datetime, timedelta
from loguru import logger

from app.data.binance_stream import BinanceKlineStream, Candle
from app.engine.position_manager import PositionManager
from app.adapters.broker_binance import BinanceFuturesBroker
from app.strategies.ma_crossover_simple import MACrossoverStrategy


class POCRunner:
    """Run 4-hour live trading test."""

    def __init__(self):
        # Config
        self.capital = 500.0
        self.profit_target = 6.0
        self.max_loss = 15.0
        self.duration_hours = 4
        self.position_size_usd = 150.0  # 30% of capital

        # Components
        self.position_mgr = PositionManager(self.capital)
        self.broker = BinanceFuturesBroker(testnet=True)
        self.strategy = MACrossoverStrategy(fast_period=9, slow_period=21)

        # State
        self.start_time = datetime.now()
        self.end_time = self.start_time + timedelta(hours=self.duration_hours)
        self.current_prices = {}
        self.running = True

    async def on_candle(self, candle: Candle):
        """Handle new candle."""
        self.current_prices[candle.symbol] = candle.close

        # Check stop conditions
        stats = self.position_mgr.get_stats(self.current_prices)
        if stats['total_pnl'] >= self.profit_target:
            logger.success(f"🎯 PROFIT TARGET REACHED: ${stats['total_pnl']:.2f}")
            self.running = False
            return

        if stats['total_pnl'] <= -self.max_loss:
            logger.error(f"🛑 MAX LOSS HIT: ${stats['total_pnl']:.2f}")
            self.running = False
            return

        # Check time limit
        if datetime.now() >= self.end_time:
            logger.info("⏰ Time limit reached")
            self.running = False
            return

        # Generate signal
        signal = self.strategy.update(candle)

        if signal == "BUY":
            await self.execute_buy(candle)
        elif signal == "SELL":
            await self.execute_sell(candle)

    async def execute_buy(self, candle: Candle):
        """Execute buy signal."""
        symbol = candle.symbol

        # Close any short position
        if symbol in self.position_mgr.positions:
            self.position_mgr.close_position(symbol, candle.close, "SIGNAL")

        # Open long position
        if self.position_mgr.can_open_position(symbol, self.position_size_usd, self.current_prices):
            qty = self.position_size_usd / candle.close

            # Calculate stops
            sl = candle.close * 0.99  # 1% stop loss
            tp = candle.close * 1.015  # 1.5% take profit

            # Execute on exchange
            try:
                order_id = self.broker.buy(symbol, qty, sl=sl, tp=tp)

                # Track in position manager
                self.position_mgr.open_position(
                    symbol=symbol,
                    side="LONG",
                    entry_price=candle.close,
                    quantity=qty,
                    stop_loss=sl,
                    take_profit=tp
                )
            except Exception as e:
                logger.error(f"Order failed: {e}")

    async def execute_sell(self, candle: Candle):
        """Execute sell signal."""
        symbol = candle.symbol

        # Close any long position
        if symbol in self.position_mgr.positions:
            self.position_mgr.close_position(symbol, candle.close, "SIGNAL")
            # TODO: Execute actual close on broker

    async def run(self):
        """Run the POC test."""
        logger.info("=" * 80)
        logger.info("🚀 4-HOUR LIVE TRADING POC TEST")
        logger.info("=" * 80)
        logger.info(f"Capital: ${self.capital:.2f}")
        logger.info(f"Target: ${self.profit_target:.2f}")
        logger.info(f"Max Loss: ${self.max_loss:.2f}")
        logger.info(f"Duration: {self.duration_hours} hours")
        logger.info("=" * 80)

        # Start data stream
        stream = BinanceKlineStream(
            symbols=["BTCUSDT", "ETHUSDT"],
            interval="5m",
            on_candle=self.on_candle,
            testnet=True
        )

        # Run until stopped
        await stream.start()

        # Final report
        self.print_final_report()

    def print_final_report(self):
        """Print final performance report."""
        stats = self.position_mgr.get_stats(self.current_prices)

        logger.info("=" * 80)
        logger.info("📊 FINAL REPORT")
        logger.info("=" * 80)
        logger.info(f"Initial Capital: ${stats['initial_capital']:.2f}")
        logger.info(f"Final Equity: ${stats['equity']:.2f}")
        logger.info(f"Total P&L: ${stats['total_pnl']:+.2f}")
        logger.info(f"Return: {stats['return_pct']:+.2f}%")
        logger.info(f"Total Trades: {stats['total_trades']}")
        logger.info(f"Win Rate: {stats['win_rate']:.1%}")
        logger.info("=" * 80)


if __name__ == "__main__":
    runner = POCRunner()
    asyncio.run(runner.run())
```

## Testing Checklist

- [ ] Data stream connects and prints live candles
- [ ] Position manager correctly calculates P&L
- [ ] Strategy generates signals on test data
- [ ] Broker can execute test orders on testnet
- [ ] Runner orchestrates all components
- [ ] Stops work (profit target, max loss, time limit)

## Running the POC

```bash
# Set up environment variables
export BINANCE_TESTNET_API_KEY="your_key_here"
export BINANCE_TESTNET_API_SECRET="your_secret_here"

# Run the test
python tools/run_live_poc.py
```

## Expected Timeline

- **Component 3 (Strategy)**: 30 minutes
- **Component 4 (Runner)**: 1 hour
- **Component 5 (Testing)**: 30 minutes
- **4-Hour Live Test**: 4 hours
- **Analysis & Report**: 30 minutes

**Total**: ~7 hours to completion

## Success Criteria

✅ Bot runs for full 4 hours without crashes
✅ All trades logged and tracked
✅ Real-time P&L calculated correctly
✅ Final report generated
🎯 Ideally: $6+ profit achieved (but not guaranteed - market dependent)

## Files Modified/Created

```
feature/poc-live-trading branch:
├── app/
│   ├── data/
│   │   └── binance_stream.py          ✅ Complete
│   ├── engine/
│   │   └── position_manager.py        ✅ Complete
│   └── strategies/
│       └── ma_crossover_simple.py     🔨 TODO
├── tools/
│   └── run_live_poc.py                🔨 TODO
└── docs/
    └── guides/
        └── poc-4hour-live-test.md     ✅ Complete
```
