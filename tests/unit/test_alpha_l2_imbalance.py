"""Unit tests for L2ImbalanceStrategy."""
import time
import pytest
from decimal import Decimal
from unittest.mock import Mock, MagicMock
from trade_engine.domain.strategies.alpha_l2_imbalance import (
    L2ImbalanceStrategy,
    L2StrategyConfig
)
from trade_engine.core.types import Bar
from trade_engine.adapters.feeds.binance_l2 import OrderBook


class TestL2StrategyConfig:
    """Test L2StrategyConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = L2StrategyConfig()

        assert config.buy_threshold == Decimal("3.0")
        assert config.sell_threshold == Decimal("0.33")
        assert config.depth == 5
        assert config.position_size_usd == Decimal("1000")
        assert config.profit_target_pct == Decimal("0.2")
        assert config.stop_loss_pct == Decimal("0.15")

    def test_custom_config(self):
        """Test custom configuration."""
        config = L2StrategyConfig(
            buy_threshold=Decimal("2.5"),
            sell_threshold=Decimal("0.4"),
            depth=10
        )

        assert config.buy_threshold == Decimal("2.5")
        assert config.sell_threshold == Decimal("0.4")
        assert config.depth == 10


class TestL2ImbalanceStrategy:
    """Test L2ImbalanceStrategy class."""

    def setup_method(self):
        """Setup test fixtures."""
        self.symbol = "BTCUSDT"
        self.order_book = OrderBook(self.symbol)

        # Initialize with snapshot
        snapshot = {
            "lastUpdateId": 100,
            "bids": [["50000.0", "1.0"]],
            "asks": [["50001.0", "1.0"]]
        }
        self.order_book.apply_snapshot(snapshot)

        self.strategy = L2ImbalanceStrategy(
            symbol=self.symbol,
            order_book=self.order_book
        )

    def test_init(self):
        """Test strategy initialization."""
        assert self.strategy.symbol == "BTCUSDT"
        assert self.strategy.order_book == self.order_book
        assert self.strategy.in_position is False
        assert self.strategy.position_side is None
        assert self.strategy.signal_count == 0

    def test_no_signal_with_neutral_imbalance(self):
        """Test no signal generated when imbalance is neutral."""
        # Neutral order book (1:1 ratio)
        bar = Bar(
            timestamp=int(time.time() * 1000),
            open=Decimal("50000"),
            high=Decimal("50000"),
            low=Decimal("50000"),
            close=Decimal("50000"),
            volume=Decimal("0")
        )

        signals = self.strategy.on_bar(bar)
        assert len(signals) == 0

    def test_buy_signal_on_strong_bullish_imbalance(self):
        """Test BUY signal generated when imbalance > 3.0."""
        # Create bullish order book (3:1 bid/ask ratio)
        snapshot = {
            "lastUpdateId": 101,
            "bids": [["50000.0", "3.0"]],  # 3.0 BTC
            "asks": [["50001.0", "1.0"]]   # 1.0 BTC
        }
        self.order_book.apply_snapshot(snapshot)

        bar = Bar(
            timestamp=int(time.time() * 1000),
            open=Decimal("50000"),
            high=Decimal("50000"),
            low=Decimal("50000"),
            close=Decimal("50000"),
            volume=Decimal("0")
        )

        signals = self.strategy.on_bar(bar)

        assert len(signals) == 1
        signal = signals[0]
        assert signal.side == "buy"
        assert signal.symbol == "BTCUSDT"
        assert signal.price == Decimal("50000")
        assert signal.sl is not None
        assert signal.tp is not None
        assert self.strategy.in_position is True
        assert self.strategy.position_side == "long"

    def test_sell_signal_on_strong_bearish_imbalance(self):
        """Test SELL signal generated when imbalance < 0.33."""
        # Create bearish order book (1:4 bid/ask ratio = 0.25 < 0.33)
        snapshot = {
            "lastUpdateId": 101,
            "bids": [["50000.0", "1.0"]],  # 1.0 BTC
            "asks": [["50001.0", "4.0"]]   # 4.0 BTC (stronger signal)
        }
        self.order_book.apply_snapshot(snapshot)

        bar = Bar(
            timestamp=int(time.time() * 1000),
            open=Decimal("50000"),
            high=Decimal("50000"),
            low=Decimal("50000"),
            close=Decimal("50000"),
            volume=Decimal("0")
        )

        signals = self.strategy.on_bar(bar)

        assert len(signals) == 1
        signal = signals[0]
        assert signal.side == "sell"
        assert signal.symbol == "BTCUSDT"
        assert self.strategy.in_position is True
        assert self.strategy.position_side == "short"

    def test_cooldown_prevents_rapid_signals(self):
        """Test cooldown period prevents signal spam."""
        # Create bullish order book
        snapshot = {
            "lastUpdateId": 101,
            "bids": [["50000.0", "3.0"]],
            "asks": [["50001.0", "1.0"]]
        }
        self.order_book.apply_snapshot(snapshot)

        bar = Bar(
            timestamp=int(time.time() * 1000),
            open=Decimal("50000"),
            high=Decimal("50000"),
            low=Decimal("50000"),
            close=Decimal("50000"),
            volume=Decimal("0")
        )

        # First signal should generate
        signals1 = self.strategy.on_bar(bar)
        assert len(signals1) == 1

        # Reset position to test cooldown
        self.strategy._reset_position()

        # Immediate second call should NOT generate signal (cooldown)
        signals2 = self.strategy.on_bar(bar)
        assert len(signals2) == 0

        # After cooldown, should generate signal
        time.sleep(self.strategy.config.cooldown_seconds + 0.1)
        # Refresh order book so it's not stale
        self.order_book.apply_snapshot(snapshot)
        signals3 = self.strategy.on_bar(bar)
        assert len(signals3) == 1

    def test_exit_on_time_stop(self):
        """Test position exits after max hold time."""
        # Enter long position
        snapshot = {
            "lastUpdateId": 101,
            "bids": [["50000.0", "3.0"]],
            "asks": [["50001.0", "1.0"]]
        }
        self.order_book.apply_snapshot(snapshot)

        bar1 = Bar(
            timestamp=int(time.time() * 1000),
            open=Decimal("50000"),
            high=Decimal("50000"),
            low=Decimal("50000"),
            close=Decimal("50000"),
            volume=Decimal("0")
        )

        signals = self.strategy.on_bar(bar1)
        assert len(signals) == 1
        assert self.strategy.in_position is True

        # Fast-forward time beyond max hold time
        self.strategy.entry_time = time.time() - (self.strategy.config.max_hold_time_seconds + 1)

        # Next bar should trigger exit
        bar2 = Bar(
            timestamp=int(time.time() * 1000),
            open=Decimal("50100"),
            high=Decimal("50100"),
            low=Decimal("50100"),
            close=Decimal("50100"),
            volume=Decimal("0")
        )

        signals = self.strategy.on_bar(bar2)
        assert len(signals) == 1
        assert signals[0].side == "close"
        assert "time_stop" in signals[0].reason
        assert self.strategy.in_position is False

    def test_exit_on_take_profit(self):
        """Test position exits when profit target hit."""
        # Enter long position at 50000
        self.strategy._enter_position("long", Decimal("50000"))

        # Price moves up 0.2% (hit TP)
        profit_price = Decimal("50000") * (Decimal("1") + Decimal("0.2") / Decimal("100"))

        bar = Bar(
            timestamp=int(time.time() * 1000),
            open=profit_price,
            high=profit_price,
            low=profit_price,
            close=profit_price,
            volume=Decimal("0")
        )

        # Maintain bullish imbalance
        snapshot = {
            "lastUpdateId": 102,
            "bids": [["50100.0", "3.0"]],
            "asks": [["50101.0", "1.0"]]
        }
        self.order_book.apply_snapshot(snapshot)

        signals = self.strategy.on_bar(bar)
        assert len(signals) == 1
        assert signals[0].side == "close"
        assert "take_profit" in signals[0].reason

    def test_exit_on_stop_loss(self):
        """Test position exits when stop loss hit."""
        # Enter long position at 50000
        self.strategy._enter_position("long", Decimal("50000"))

        # Price moves down 0.15% (hit SL)
        loss_price = Decimal("50000") * (Decimal("1") - Decimal("0.15") / Decimal("100"))

        bar = Bar(
            timestamp=int(time.time() * 1000),
            open=loss_price,
            high=loss_price,
            low=loss_price,
            close=loss_price,
            volume=Decimal("0")
        )

        # Maintain order book
        snapshot = {
            "lastUpdateId": 102,
            "bids": [["49925.0", "1.0"]],
            "asks": [["49926.0", "1.0"]]
        }
        self.order_book.apply_snapshot(snapshot)

        signals = self.strategy.on_bar(bar)
        assert len(signals) == 1
        assert signals[0].side == "close"
        assert "stop_loss" in signals[0].reason

    def test_exit_on_imbalance_reversal_long(self):
        """Test long position exits when imbalance turns bearish."""
        # Enter long position
        self.strategy._enter_position("long", Decimal("50000"))

        # Create bearish imbalance (reversal)
        snapshot = {
            "lastUpdateId": 102,
            "bids": [["50000.0", "0.5"]],  # Less bid volume
            "asks": [["50001.0", "2.0"]]   # More ask volume
        }
        self.order_book.apply_snapshot(snapshot)

        bar = Bar(
            timestamp=int(time.time() * 1000),
            open=Decimal("50000"),
            high=Decimal("50000"),
            low=Decimal("50000"),
            close=Decimal("50000"),
            volume=Decimal("0")
        )

        signals = self.strategy.on_bar(bar)
        assert len(signals) == 1
        assert signals[0].side == "close"
        assert "imbalance_reversal" in signals[0].reason

    def test_exit_on_imbalance_reversal_short(self):
        """Test short position exits when imbalance turns bullish."""
        # Enter short position
        self.strategy._enter_position("short", Decimal("50000"))

        # Create bullish imbalance (reversal)
        snapshot = {
            "lastUpdateId": 102,
            "bids": [["50000.0", "2.0"]],  # More bid volume
            "asks": [["50001.0", "0.5"]]   # Less ask volume
        }
        self.order_book.apply_snapshot(snapshot)

        bar = Bar(
            timestamp=int(time.time() * 1000),
            open=Decimal("50000"),
            high=Decimal("50000"),
            low=Decimal("50000"),
            close=Decimal("50000"),
            volume=Decimal("0")
        )

        signals = self.strategy.on_bar(bar)
        assert len(signals) == 1
        assert signals[0].side == "close"
        assert "imbalance_reversal" in signals[0].reason

    def test_no_signal_when_order_book_invalid(self):
        """Test no signal when order book is invalid."""
        # Create invalid order book (empty)
        invalid_ob = OrderBook("BTCUSDT")
        strategy = L2ImbalanceStrategy(
            symbol="BTCUSDT",
            order_book=invalid_ob
        )

        bar = Bar(
            timestamp=int(time.time() * 1000),
            open=Decimal("50000"),
            high=Decimal("50000"),
            low=Decimal("50000"),
            close=Decimal("50000"),
            volume=Decimal("0")
        )

        signals = strategy.on_bar(bar)
        assert len(signals) == 0

    def test_no_signal_when_order_book_stale(self):
        """Test no signal generated when order book is stale (staleness check)."""
        # Create order book with bullish imbalance
        snapshot = {
            "lastUpdateId": 101,
            "bids": [["50000.0", "3.0"]],  # Strong bid
            "asks": [["50001.0", "1.0"]]
        }
        self.order_book.apply_snapshot(snapshot)

        # Manually set last_update_time to >1 second ago (stale)
        self.order_book.last_update_time = time.time() - 2.0

        bar = Bar(
            timestamp=int(time.time() * 1000),
            open=Decimal("50000"),
            high=Decimal("50000"),
            low=Decimal("50000"),
            close=Decimal("50000"),
            volume=Decimal("0")
        )

        # Despite bullish imbalance, should NOT generate signal (stale data)
        signals = self.strategy.on_bar(bar)
        assert len(signals) == 0

    def test_signal_generated_when_order_book_fresh(self):
        """Test signal is generated when order book is fresh (not stale)."""
        # Create order book with bullish imbalance
        snapshot = {
            "lastUpdateId": 101,
            "bids": [["50000.0", "3.0"]],
            "asks": [["50001.0", "1.0"]]
        }
        self.order_book.apply_snapshot(snapshot)  # Updates last_update_time to now

        bar = Bar(
            timestamp=int(time.time() * 1000),
            open=Decimal("50000"),
            high=Decimal("50000"),
            low=Decimal("50000"),
            close=Decimal("50000"),
            volume=Decimal("0")
        )

        # With fresh data, should generate signal
        signals = self.strategy.on_bar(bar)
        assert len(signals) == 1
        assert signals[0].side == "buy"

    def test_no_exit_signal_when_order_book_stale(self):
        """Test exit signal logic when order book becomes stale while in position."""
        # Enter long position
        self.strategy._enter_position("long", Decimal("50000"))
        assert self.strategy.in_position is True

        # Create bearish imbalance (should trigger exit normally)
        snapshot = {
            "lastUpdateId": 102,
            "bids": [["50000.0", "0.5"]],
            "asks": [["50001.0", "2.0"]]
        }
        self.order_book.apply_snapshot(snapshot)

        # Make order book stale
        self.order_book.last_update_time = time.time() - 2.0

        bar = Bar(
            timestamp=int(time.time() * 1000),
            open=Decimal("50000"),
            high=Decimal("50000"),
            low=Decimal("50000"),
            close=Decimal("50000"),
            volume=Decimal("0")
        )

        # With stale data, should NOT generate exit signal
        signals = self.strategy.on_bar(bar)
        assert len(signals) == 0
        assert self.strategy.in_position is True  # Still in position

    def test_spread_filter(self):
        """Test wide spread prevents signal generation."""
        # Create order book with wide spread
        snapshot = {
            "lastUpdateId": 101,
            "bids": [["50000.0", "3.0"]],
            "asks": [["50500.0", "1.0"]]  # 500 point spread (~100 bps)
        }
        self.order_book.apply_snapshot(snapshot)

        bar = Bar(
            timestamp=int(time.time() * 1000),
            open=Decimal("50000"),
            high=Decimal("50000"),
            low=Decimal("50000"),
            close=Decimal("50000"),
            volume=Decimal("0")
        )

        signals = self.strategy.on_bar(bar)
        # Should not generate signal due to wide spread
        assert len(signals) == 0

    def test_reset(self):
        """Test strategy reset."""
        # Enter position
        self.strategy._enter_position("long", Decimal("50000"))
        self.strategy.signal_count = 5
        self.strategy.last_signal_time = time.time()

        # Reset
        self.strategy.reset()

        assert self.strategy.in_position is False
        assert self.strategy.position_side is None
        assert self.strategy.entry_time is None
        assert self.strategy.entry_price is None
        assert self.strategy.signal_count == 0
        assert self.strategy.last_signal_time == 0.0

    def test_get_state(self):
        """Test get_state returns correct info."""
        # Enter position
        self.strategy._enter_position("long", Decimal("50000"))

        state = self.strategy.get_state()

        assert state["symbol"] == "BTCUSDT"
        assert state["in_position"] is True
        assert state["position_side"] == "long"
        assert state["entry_price"] == "50000"
        assert state["signal_count"] == 1
        assert "current_imbalance" in state
        assert "mid_price" in state

    def test_quantity_calculation(self):
        """Test position quantity is calculated correctly."""
        # Create bullish order book
        snapshot = {
            "lastUpdateId": 101,
            "bids": [["50000.0", "3.0"]],
            "asks": [["50001.0", "1.0"]]
        }
        self.order_book.apply_snapshot(snapshot)

        bar = Bar(
            timestamp=int(time.time() * 1000),
            open=Decimal("50000"),
            high=Decimal("50000"),
            low=Decimal("50000"),
            close=Decimal("50000"),
            volume=Decimal("0")
        )

        signals = self.strategy.on_bar(bar)
        assert len(signals) == 1

        # Qty = position_size_usd / price = 1000 / 50000 = 0.02
        expected_qty = Decimal("1000") / Decimal("50000")
        assert signals[0].qty == expected_qty

    def test_stop_loss_and_take_profit_calculation_long(self):
        """Test SL/TP calculation for long position."""
        # Create bullish order book
        snapshot = {
            "lastUpdateId": 101,
            "bids": [["50000.0", "3.0"]],
            "asks": [["50001.0", "1.0"]]
        }
        self.order_book.apply_snapshot(snapshot)

        bar = Bar(
            timestamp=int(time.time() * 1000),
            open=Decimal("50000"),
            high=Decimal("50000"),
            low=Decimal("50000"),
            close=Decimal("50000"),
            volume=Decimal("0")
        )

        signals = self.strategy.on_bar(bar)
        signal = signals[0]

        # Entry at 50000
        # TP = 50000 * (1 + 0.002) = 50100
        # SL = 50000 * (1 - 0.0015) = 49925
        expected_tp = Decimal("50000") * Decimal("1.002")
        expected_sl = Decimal("50000") * Decimal("0.9985")

        assert signal.tp == expected_tp
        assert signal.sl == expected_sl

    def test_stop_loss_and_take_profit_calculation_short(self):
        """Test SL/TP calculation for short position."""
        # Create bearish order book (1:4 ratio = 0.25 < 0.33)
        snapshot = {
            "lastUpdateId": 101,
            "bids": [["50000.0", "1.0"]],
            "asks": [["50001.0", "4.0"]]  # Stronger signal
        }
        self.order_book.apply_snapshot(snapshot)

        bar = Bar(
            timestamp=int(time.time() * 1000),
            open=Decimal("50000"),
            high=Decimal("50000"),
            low=Decimal("50000"),
            close=Decimal("50000"),
            volume=Decimal("0")
        )

        signals = self.strategy.on_bar(bar)
        signal = signals[0]

        # Entry at 50000
        # TP = 50000 * (1 - 0.002) = 49900
        # SL = 50000 * (1 + 0.0015) = 50075
        expected_tp = Decimal("50000") * Decimal("0.998")
        expected_sl = Decimal("50000") * Decimal("1.0015")

        assert signal.tp == expected_tp
        assert signal.sl == expected_sl


class TestL2ImbalanceStrategySpotOnly:
    """Test L2ImbalanceStrategy spot-only mode."""

    def setup_method(self):
        """Setup test fixtures for spot-only mode."""
        self.symbol = "BTCUSDT"
        self.order_book = OrderBook(self.symbol)

        # Initialize with snapshot
        snapshot = {
            "lastUpdateId": 100,
            "bids": [["50000.0", "1.0"]],
            "asks": [["50001.0", "1.0"]]
        }
        self.order_book.apply_snapshot(snapshot)

        # Create strategy with spot_only=True
        config = L2StrategyConfig(
            spot_only=True,
            buy_threshold=Decimal("3.0"),
            sell_threshold=Decimal("0.33")
        )
        self.strategy = L2ImbalanceStrategy(
            symbol=self.symbol,
            order_book=self.order_book,
            config=config
        )

    def test_spot_only_config(self):
        """Test spot_only configuration is set correctly."""
        assert self.strategy.config.spot_only is True

    def test_buy_signal_works_in_spot_only(self):
        """Test BUY signal still works in spot-only mode."""
        # Create bullish order book
        snapshot = {
            "lastUpdateId": 101,
            "bids": [["50000.0", "3.0"]],
            "asks": [["50001.0", "1.0"]]
        }
        self.order_book.apply_snapshot(snapshot)

        bar = Bar(
            timestamp=int(time.time() * 1000),
            open=Decimal("50000"),
            high=Decimal("50000"),
            low=Decimal("50000"),
            close=Decimal("50000"),
            volume=Decimal("0")
        )

        signals = self.strategy.on_bar(bar)

        # Should generate BUY signal
        assert len(signals) == 1
        assert signals[0].side == "buy"
        assert self.strategy.in_position is True
        assert self.strategy.position_side == "long"

    def test_sell_signal_ignored_in_spot_only(self):
        """Test SELL signal (short) is ignored in spot-only mode."""
        # Create bearish order book
        snapshot = {
            "lastUpdateId": 101,
            "bids": [["50000.0", "1.0"]],
            "asks": [["50001.0", "4.0"]]  # 1:4 = 0.25 < 0.33
        }
        self.order_book.apply_snapshot(snapshot)

        bar = Bar(
            timestamp=int(time.time() * 1000),
            open=Decimal("50000"),
            high=Decimal("50000"),
            low=Decimal("50000"),
            close=Decimal("50000"),
            volume=Decimal("0")
        )

        signals = self.strategy.on_bar(bar)

        # Should NOT generate signal (short not allowed)
        assert len(signals) == 0
        assert self.strategy.in_position is False

    def test_exit_signal_works_for_long_in_spot_only(self):
        """Test exit signals work for long positions in spot-only."""
        # Enter long position
        self.strategy._enter_position("long", Decimal("50000"))

        # Create bearish imbalance (reversal)
        snapshot = {
            "lastUpdateId": 102,
            "bids": [["50000.0", "0.5"]],
            "asks": [["50001.0", "2.0"]]
        }
        self.order_book.apply_snapshot(snapshot)

        bar = Bar(
            timestamp=int(time.time() * 1000),
            open=Decimal("50000"),
            high=Decimal("50000"),
            low=Decimal("50000"),
            close=Decimal("50000"),
            volume=Decimal("0")
        )

        signals = self.strategy.on_bar(bar)

        # Should exit long position
        assert len(signals) == 1
        assert signals[0].side == "close"
        assert "imbalance_reversal" in signals[0].reason


class TestL2ImbalanceStrategyKillSwitch:
    """Test L2ImbalanceStrategy with kill switch / emergency stop scenarios."""

    def setup_method(self):
        """Setup test fixtures for kill switch tests."""
        self.symbol = "BTCUSDT"
        self.order_book = OrderBook(self.symbol)

        # Initialize with snapshot
        snapshot = {
            "lastUpdateId": 100,
            "bids": [["50000.0", "1.0"]],
            "asks": [["50001.0", "1.0"]]
        }
        self.order_book.apply_snapshot(snapshot)

        self.strategy = L2ImbalanceStrategy(
            symbol=self.symbol,
            order_book=self.order_book
        )

    def test_reset_clears_position_on_kill_switch(self):
        """Test that reset() can be used to clear positions on kill switch."""
        # Enter long position
        self.strategy._enter_position("long", Decimal("50000"))
        assert self.strategy.in_position is True
        assert self.strategy.position_side == "long"
        assert self.strategy.entry_price == Decimal("50000")

        # Simulate kill switch: reset() clears all state
        self.strategy.reset()

        # Verify all position state is cleared
        assert self.strategy.in_position is False
        assert self.strategy.position_side is None
        assert self.strategy.entry_price is None
        assert self.strategy.entry_time is None
        assert self.strategy.signal_count == 0
        assert self.strategy.last_signal_time == 0.0

    def test_can_generate_signals_immediately_after_reset(self):
        """Test that strategy can generate signals immediately after reset (kill switch recovery)."""
        # Create bullish order book
        snapshot = {
            "lastUpdateId": 101,
            "bids": [["50000.0", "3.0"]],
            "asks": [["50001.0", "1.0"]]
        }
        self.order_book.apply_snapshot(snapshot)

        bar = Bar(
            timestamp=int(time.time() * 1000),
            open=Decimal("50000"),
            high=Decimal("50000"),
            low=Decimal("50000"),
            close=Decimal("50000"),
            volume=Decimal("0")
        )

        # Generate initial signal
        signals1 = self.strategy.on_bar(bar)
        assert len(signals1) == 1
        assert self.strategy.in_position is True

        # Simulate kill switch: reset position
        self.strategy.reset()
        assert self.strategy.in_position is False
        assert self.strategy.last_signal_time == 0.0  # Reset clears cooldown

        # After reset, strategy can immediately generate new signals
        # (This is intended behavior - reset clears cooldown)
        self.order_book.apply_snapshot(snapshot)
        signals2 = self.strategy.on_bar(bar)
        assert len(signals2) == 1  # Can trade immediately after reset
        assert self.strategy.in_position is True

    def test_exit_position_before_kill_switch(self):
        """Test that strategy can generate exit signal to close position before kill switch."""
        # Enter long position
        self.strategy._enter_position("long", Decimal("50000"))
        assert self.strategy.in_position is True

        # Price moves to stop loss
        loss_price = Decimal("50000") * Decimal("0.9985")  # -0.15% (SL)

        # Create order book for exit condition
        snapshot = {
            "lastUpdateId": 102,
            "bids": [["49925.0", "1.0"]],
            "asks": [["49926.0", "1.0"]]
        }
        self.order_book.apply_snapshot(snapshot)

        bar = Bar(
            timestamp=int(time.time() * 1000),
            open=loss_price,
            high=loss_price,
            low=loss_price,
            close=loss_price,
            volume=Decimal("0")
        )

        # Should generate exit signal (before kill switch is needed)
        signals = self.strategy.on_bar(bar)
        assert len(signals) == 1
        assert signals[0].side == "close"
        assert "stop_loss" in signals[0].reason
        assert self.strategy.in_position is False

    def test_strategy_state_after_emergency_stop(self):
        """Test that strategy state is valid after emergency stop (kill switch)."""
        # Enter position and generate some activity
        self.strategy._enter_position("long", Decimal("50000"))
        self.strategy.signal_count = 10
        self.strategy.last_signal_time = time.time()

        # Simulate emergency stop / kill switch
        self.strategy.reset()

        # Get state - should be valid with no position
        state = self.strategy.get_state()
        assert state["in_position"] is False
        assert state["position_side"] is None
        assert state["entry_price"] is None
        assert state["signal_count"] == 0
        assert "current_imbalance" in state
        assert "mid_price" in state

    def test_multiple_kill_switch_activations(self):
        """Test strategy handles multiple kill switch activations correctly."""
        # Create bullish order book
        snapshot = {
            "lastUpdateId": 101,
            "bids": [["50000.0", "3.0"]],
            "asks": [["50001.0", "1.0"]]
        }

        bar = Bar(
            timestamp=int(time.time() * 1000),
            open=Decimal("50000"),
            high=Decimal("50000"),
            low=Decimal("50000"),
            close=Decimal("50000"),
            volume=Decimal("0")
        )

        # Cycle 1: Enter position -> kill switch -> reset
        self.order_book.apply_snapshot(snapshot)
        signals = self.strategy.on_bar(bar)
        assert len(signals) == 1
        assert self.strategy.in_position is True

        self.strategy.reset()
        assert self.strategy.in_position is False

        # Cycle 2: Wait for cooldown, enter again -> kill switch -> reset
        time.sleep(self.strategy.config.cooldown_seconds + 0.1)
        self.order_book.apply_snapshot(snapshot)
        signals = self.strategy.on_bar(bar)
        assert len(signals) == 1
        assert self.strategy.in_position is True

        self.strategy.reset()
        assert self.strategy.in_position is False

        # Cycle 3: Verify strategy still works after multiple resets
        time.sleep(self.strategy.config.cooldown_seconds + 0.1)
        self.order_book.apply_snapshot(snapshot)
        signals = self.strategy.on_bar(bar)
        assert len(signals) == 1
        assert self.strategy.in_position is True


class TestL2StrategyTimestampTypes:
    """Test that L2 strategy uses correct types for timestamps."""

    def test_entry_time_is_int_not_float(self):
        """Test entry_time is int (Unix timestamp in seconds)."""
        # ARRANGE
        order_book = Mock(spec=OrderBook)
        order_book.is_valid.return_value = True
        order_book.calculate_imbalance.return_value = Decimal("4.0")  # Strong buy signal
        order_book.get_spread_bps.return_value = Decimal("10")
        order_book.get_mid_price.return_value = Decimal("50000")

        strategy = L2ImbalanceStrategy("BTCUSDT", order_book)
        bar = Bar(
            timestamp=time.time(),
            open=Decimal("50000"),
            high=Decimal("50000"),
            low=Decimal("50000"),
            close=Decimal("50000"),
            volume=Decimal("100")
        )

        # ACT
        before_time = int(time.time())
        signals = strategy.on_bar(bar)
        after_time = int(time.time())

        # ASSERT
        assert len(signals) == 1
        assert strategy.entry_time is not None
        assert isinstance(strategy.entry_time, int), f"entry_time should be int, got {type(strategy.entry_time)}"
        assert before_time <= strategy.entry_time <= after_time + 1

    def test_last_signal_time_is_int_not_float(self):
        """Test last_signal_time is int (Unix timestamp in seconds)."""
        # ARRANGE
        order_book = Mock(spec=OrderBook)
        order_book.is_valid.return_value = True
        order_book.calculate_imbalance.return_value = Decimal("4.0")
        order_book.get_spread_bps.return_value = Decimal("10")
        order_book.get_mid_price.return_value = Decimal("50000")

        strategy = L2ImbalanceStrategy("BTCUSDT", order_book)
        bar = Bar(
            timestamp=time.time(),
            open=Decimal("50000"),
            high=Decimal("50000"),
            low=Decimal("50000"),
            close=Decimal("50000"),
            volume=Decimal("100")
        )

        # ACT
        before_time = int(time.time())
        signals = strategy.on_bar(bar)
        after_time = int(time.time())

        # ASSERT
        assert isinstance(strategy.last_signal_time, int), f"last_signal_time should be int, got {type(strategy.last_signal_time)}"
        assert before_time <= strategy.last_signal_time <= after_time + 1

    def test_timestamps_initialized_as_int(self):
        """Test strategy initializes timestamps as int (not float)."""
        # ARRANGE & ACT
        order_book = Mock(spec=OrderBook)
        strategy = L2ImbalanceStrategy("BTCUSDT", order_book)

        # ASSERT
        assert strategy.entry_time is None  # Not set yet
        assert isinstance(strategy.last_signal_time, int), "last_signal_time should be int"
        assert strategy.last_signal_time == 0  # Initial value

    def test_timestamp_arithmetic_uses_integers(self):
        """Test cooldown calculation uses integer arithmetic."""
        # ARRANGE
        order_book = Mock(spec=OrderBook)
        order_book.is_valid.return_value = True
        order_book.calculate_imbalance.return_value = Decimal("4.0")
        order_book.get_spread_bps.return_value = Decimal("10")
        order_book.get_mid_price.return_value = Decimal("50000")

        config = L2StrategyConfig(cooldown_seconds=2)
        strategy = L2ImbalanceStrategy("BTCUSDT", order_book, config)
        bar = Bar(
            timestamp=time.time(),
            open=Decimal("50000"),
            high=Decimal("50000"),
            low=Decimal("50000"),
            close=Decimal("50000"),
            volume=Decimal("100")
        )

        # ACT: Generate first signal
        signals1 = strategy.on_bar(bar)
        assert len(signals1) == 1  # Signal generated

        # ACT: Try to generate second signal immediately (should be blocked by cooldown)
        signals2 = strategy.on_bar(bar)
        assert len(signals2) == 0  # Blocked by cooldown

        # ACT: Wait for cooldown and try again
        time.sleep(2.1)
        order_book.calculate_imbalance.return_value = Decimal("0.25")  # Exit signal
        signals3 = strategy.on_bar(bar)
        # Should generate exit signal (no cooldown on exits)
        assert len(signals3) == 1
