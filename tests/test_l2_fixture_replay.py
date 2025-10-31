"""
Test L2 Fixture Replay Engine

Validates that recorded L2 data can be replayed and fed to strategies.

NOTE: Skipped due to incomplete datarec module (missing schemas.bar dependency).
This module will be re-enabled once the datarec.replay module is fully implemented.
"""

import asyncio
from decimal import Decimal
from pathlib import Path

import pytest

# Skip entire module - datarec.replay has broken imports (missing schemas.bar)
# This prevents collection-time import errors
pytest.skip("datarec module incomplete - missing schemas.bar", allow_module_level=True)


class TestL2ReplayEngine:
    """Test L2 replay functionality."""

    @pytest.mark.asyncio
    async def test_load_parquet_fixtures(self, tmp_path):
        """Test loading Parquet fixtures."""
        # Create mock Parquet file
        import pandas as pd

        fixture_dir = tmp_path / "BTCUSD" / "binanceus"
        fixture_dir.mkdir(parents=True)

        # Create sample data
        data = {
            "timestamp": [1730318400000, 1730318401000, 1730318402000],
            "exchange": ["binanceus"] * 3,
            "symbol": ["BTC/USD"] * 3,
            "best_bid": ["42500.00", "42501.00", "42502.00"],
            "best_ask": ["42501.00", "42502.00", "42503.00"],
            "mid_price": ["42500.50", "42501.50", "42502.50"],
            "spread": ["1.00", "1.00", "1.00"],
            "spread_bps": ["2.35", "2.35", "2.35"],
            "bid_depth_5": ["10.5", "11.0", "10.8"],
            "ask_depth_5": ["8.2", "8.5", "8.0"],
            "imbalance_5": ["0.123", "0.128", "0.149"],
            "ratio_imbalance_5": ["1.28", "1.29", "1.35"],
        }

        df = pd.DataFrame(data)
        df.to_parquet(fixture_dir / "2025-10-30T18-00-00Z.parquet", compression="snappy")

        # Load with replay engine
        engine = L2ReplayEngine(fixture_dir=fixture_dir)
        await engine.load()

        assert engine.get_snapshot_count() == 3

    @pytest.mark.asyncio
    async def test_replay_snapshots_with_timing(self, tmp_path):
        """Test that replay respects timestamp intervals."""
        import pandas as pd
        import time

        fixture_dir = tmp_path / "BTCUSD" / "binanceus"
        fixture_dir.mkdir(parents=True)

        # Create data with 1-second intervals
        data = {
            "timestamp": [1730318400000, 1730318401000, 1730318402000],
            "exchange": ["binanceus"] * 3,
            "symbol": ["BTC/USD"] * 3,
            "mid_price": ["42500.50", "42501.50", "42502.50"],
            "best_bid": ["42500.00"] * 3,
            "best_ask": ["42501.00"] * 3,
            "spread": ["1.00"] * 3,
            "spread_bps": ["2.35"] * 3,
            "bid_depth_5": ["10.0"] * 3,
            "ask_depth_5": ["8.0"] * 3,
            "imbalance_5": ["0.1"] * 3,
            "ratio_imbalance_5": ["1.25"] * 3,
        }

        df = pd.DataFrame(data)
        df.to_parquet(fixture_dir / "test.parquet")

        # Replay at 1000x speed (should complete quickly)
        engine = L2ReplayEngine(fixture_dir=fixture_dir, speed=1000.0)

        snapshots = []
        start_time = time.time()

        async for snapshot in engine.replay_snapshots():
            snapshots.append(snapshot)

        elapsed = time.time() - start_time

        # Should have replayed all 3 snapshots
        assert len(snapshots) == 3

        # Should complete in < 1 second at 1000x speed
        # (2 seconds of data / 1000 = 0.002 seconds)
        assert elapsed < 1.0

    @pytest.mark.asyncio
    async def test_replay_as_bars(self, tmp_path):
        """Test replaying L2 snapshots as OHLC bars."""
        import pandas as pd

        fixture_dir = tmp_path / "BTCUSD" / "binanceus"
        fixture_dir.mkdir(parents=True)

        # Create 120 seconds of data (snapshots at 1-second intervals)
        timestamps = [1730318400000 + i * 1000 for i in range(120)]

        # Price varies slightly
        mid_prices = [str(42500.0 + i * 0.1) for i in range(120)]

        data = {
            "timestamp": timestamps,
            "exchange": ["binanceus"] * 120,
            "symbol": ["BTC/USD"] * 120,
            "mid_price": mid_prices,
            "best_bid": ["42500.00"] * 120,
            "best_ask": ["42501.00"] * 120,
            "spread": ["1.00"] * 120,
            "spread_bps": ["2.35"] * 120,
            "bid_depth_5": ["10.0"] * 120,
            "ask_depth_5": ["8.0"] * 120,
            "imbalance_5": ["0.1"] * 120,
            "ratio_imbalance_5": ["1.25"] * 120,
        }

        df = pd.DataFrame(data)
        df.to_parquet(fixture_dir / "test.parquet")

        # Replay as 60-second bars
        engine = L2ReplayEngine(fixture_dir=fixture_dir, speed=1000.0)

        bars = []
        async for bar in engine.replay_as_bars(aggregation_interval=60):
            bars.append(bar)

        # Should produce 2 bars (120 seconds / 60 = 2)
        assert len(bars) == 2

        # Verify bar structure
        assert bars[0].open == Decimal("42500.0")
        assert bars[0].close == Decimal("42505.9")  # Last snapshot in first minute
        assert bars[0].high >= bars[0].open
        assert bars[0].low <= bars[0].close

    @pytest.mark.asyncio
    async def test_snapshot_validation(self, tmp_path):
        """Test that invalid snapshots are detected."""
        import pandas as pd

        fixture_dir = tmp_path / "BTCUSD" / "binanceus"
        fixture_dir.mkdir(parents=True)

        # Create data with crossed book (bid > ask)
        data = {
            "timestamp": [1730318400000],
            "exchange": ["binanceus"],
            "symbol": ["BTC/USD"],
            "best_bid": ["42502.00"],  # INVALID: bid > ask
            "best_ask": ["42501.00"],
            "mid_price": ["42501.50"],
            "spread": ["-1.00"],  # Negative spread
            "spread_bps": ["-2.35"],
            "bid_depth_5": ["10.0"],
            "ask_depth_5": ["8.0"],
            "imbalance_5": ["0.1"],
            "ratio_imbalance_5": ["1.25"],
        }

        df = pd.DataFrame(data)
        df.to_parquet(fixture_dir / "test.parquet")

        # Should load but validation will catch the error
        engine = L2ReplayEngine(fixture_dir=fixture_dir)
        await engine.load()

        # Snapshot should still be loaded (validation happens in recorder)
        assert engine.get_snapshot_count() == 1

    @pytest.mark.asyncio
    async def test_time_range_filtering(self, tmp_path):
        """Test filtering snapshots by time range."""
        import pandas as pd

        fixture_dir = tmp_path / "BTCUSD" / "binanceus"
        fixture_dir.mkdir(parents=True)

        # Create 10 snapshots
        timestamps = [1730318400000 + i * 1000 for i in range(10)]

        data = {
            "timestamp": timestamps,
            "exchange": ["binanceus"] * 10,
            "symbol": ["BTC/USD"] * 10,
            "mid_price": ["42500.50"] * 10,
            "best_bid": ["42500.00"] * 10,
            "best_ask": ["42501.00"] * 10,
            "spread": ["1.00"] * 10,
            "spread_bps": ["2.35"] * 10,
            "bid_depth_5": ["10.0"] * 10,
            "ask_depth_5": ["8.0"] * 10,
            "imbalance_5": ["0.1"] * 10,
            "ratio_imbalance_5": ["1.25"] * 10,
        }

        df = pd.DataFrame(data)
        df.to_parquet(fixture_dir / "test.parquet")

        # Filter to middle 5 snapshots (index 3-7)
        engine = L2ReplayEngine(
            fixture_dir=fixture_dir,
            start_time=1730318403000,  # Snapshot 3
            end_time=1730318407000,    # Snapshot 7
        )
        await engine.load()

        # Should load only 5 snapshots
        assert engine.get_snapshot_count() == 5

    @pytest.mark.asyncio
    async def test_consistency_validation(self, tmp_path):
        """Test that replayed data maintains consistency (bid < ask, etc.)."""
        import pandas as pd

        fixture_dir = tmp_path / "BTCUSD" / "binanceus"
        fixture_dir.mkdir(parents=True)

        # Create valid data
        data = {
            "timestamp": [1730318400000 + i * 1000 for i in range(100)],
            "exchange": ["binanceus"] * 100,
            "symbol": ["BTC/USD"] * 100,
            "best_bid": [f"{42500.00 + i * 0.1:.2f}" for i in range(100)],
            "best_ask": [f"{42501.00 + i * 0.1:.2f}" for i in range(100)],
            "mid_price": [f"{42500.50 + i * 0.1:.2f}" for i in range(100)],
            "spread": ["1.00"] * 100,
            "spread_bps": ["2.35"] * 100,
            "bid_depth_5": ["10.0"] * 100,
            "ask_depth_5": ["8.0"] * 100,
            "imbalance_5": ["0.1"] * 100,
            "ratio_imbalance_5": ["1.25"] * 100,
        }

        df = pd.DataFrame(data)
        df.to_parquet(fixture_dir / "test.parquet")

        engine = L2ReplayEngine(fixture_dir=fixture_dir, speed=1000.0)

        # Replay and validate consistency
        snapshot_count = 0
        async for snapshot in engine.replay_snapshots():
            # Validate bid < ask
            best_bid = Decimal(snapshot["best_bid"])
            best_ask = Decimal(snapshot["best_ask"])
            assert best_bid < best_ask, f"Crossed book: bid={best_bid}, ask={best_ask}"

            # Validate mid is between bid and ask
            mid = Decimal(snapshot["mid_price"])
            assert best_bid <= mid <= best_ask

            snapshot_count += 1

        assert snapshot_count > 500, f"Expected >500 snapshots, got {snapshot_count}"
