"""Unit tests for tools/validate_clean_ohlcv.py"""
import json
from pathlib import Path
import pandas as pd
import numpy as np
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "dev"))
import validate_clean_ohlcv as VC


class TestReadCSV:
    """Test CSV reading and column normalization."""

    def test_read_csv_with_standard_columns(self, tmp_path):
        """Test reading CSV with standard column names."""
        # ARRANGE
        csv_path = tmp_path / "test.csv"
        df = pd.DataFrame({
            "open_time": ["2025-01-01 00:00:00", "2025-01-01 00:01:00"],
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "volume": [1000.0, 1100.0]
        })
        df.to_csv(csv_path, index=False)

        # ACT
        result = VC._read_csv(csv_path)

        # ASSERT
        assert "open_time" in result.columns
        assert "open" in result.columns
        assert "high" in result.columns
        assert "low" in result.columns
        assert "close" in result.columns
        assert "volume" in result.columns
        assert len(result) == 2
        assert pd.api.types.is_datetime64_any_dtype(result["open_time"])

    def test_read_csv_with_alternate_column_names(self, tmp_path):
        """Test reading CSV with alternate column names (timestamp, o, h, l, c, v)."""
        # ARRANGE
        csv_path = tmp_path / "alt.csv"
        df = pd.DataFrame({
            "timestamp": ["2025-01-01 00:00:00", "2025-01-01 00:01:00"],
            "o": [100.0, 101.0],
            "h": [102.0, 103.0],
            "l": [99.0, 100.0],
            "c": [101.0, 102.0],
            "v": [1000.0, 1100.0]
        })
        df.to_csv(csv_path, index=False)

        # ACT
        result = VC._read_csv(csv_path)

        # ASSERT
        assert "open_time" in result.columns
        assert "open" in result.columns
        assert "high" in result.columns
        assert "low" in result.columns
        assert "close" in result.columns
        assert "volume" in result.columns

    def test_read_csv_missing_timestamp_column(self, tmp_path):
        """Test that reading CSV without timestamp column raises ValueError."""
        # ARRANGE
        csv_path = tmp_path / "no_ts.csv"
        df = pd.DataFrame({
            "open": [100.0],
            "high": [102.0],
            "low": [99.0],
            "close": [101.0],
            "volume": [1000.0]
        })
        df.to_csv(csv_path, index=False)

        # ACT & ASSERT
        with pytest.raises(ValueError, match="No timestamp column found"):
            VC._read_csv(csv_path)

    def test_read_csv_missing_required_price_columns(self, tmp_path):
        """Test that missing required columns raises ValueError."""
        # ARRANGE
        csv_path = tmp_path / "missing.csv"
        df = pd.DataFrame({
            "open_time": ["2025-01-01 00:00:00"],
            "open": [100.0],
            "high": [102.0]
            # Missing: low, close, volume
        })
        df.to_csv(csv_path, index=False)

        # ACT & ASSERT
        with pytest.raises(ValueError, match="Missing required columns"):
            VC._read_csv(csv_path)


class TestEnforceDtypes:
    """Test data type enforcement."""

    def test_enforce_dtypes_converts_numeric_columns(self):
        """Test that price/volume columns are converted to numeric."""
        # ARRANGE
        df = pd.DataFrame({
            "open_time": pd.date_range("2025-01-01", periods=3, freq="1min", tz="UTC"),
            "open": ["100", "101", "102"],
            "high": ["102", "103", "104"],
            "low": ["99", "100", "101"],
            "close": ["101", "102", "103"],
            "volume": ["1000", "1100", "1200"]
        })

        # ACT
        result = VC._enforce_dtypes(df)

        # ASSERT
        assert pd.api.types.is_numeric_dtype(result["open"])
        assert pd.api.types.is_numeric_dtype(result["high"])
        assert pd.api.types.is_numeric_dtype(result["low"])
        assert pd.api.types.is_numeric_dtype(result["close"])
        assert pd.api.types.is_numeric_dtype(result["volume"])

    def test_enforce_dtypes_handles_invalid_values(self):
        """Test that invalid values are coerced to NaN."""
        # ARRANGE
        df = pd.DataFrame({
            "open_time": pd.date_range("2025-01-01", periods=2, freq="1min", tz="UTC"),
            "open": ["100", "invalid"],
            "high": [102, 103],
            "low": [99, 100],
            "close": [101, 102],
            "volume": [1000, 1100]
        })

        # ACT
        result = VC._enforce_dtypes(df)

        # ASSERT
        assert pd.isna(result.loc[1, "open"])
        assert result.loc[0, "open"] == 100.0


class TestInferFreq:
    """Test frequency inference from DatetimeIndex."""

    def test_infer_freq_1min(self):
        """Test inference of 1-minute frequency."""
        # ARRANGE
        idx = pd.date_range("2025-01-01", periods=10, freq="1min", tz="UTC")

        # ACT
        freq = VC._infer_freq(idx)

        # ASSERT
        assert freq == pd.Timedelta(minutes=1)

    def test_infer_freq_15min(self):
        """Test inference of 15-minute frequency."""
        # ARRANGE
        idx = pd.date_range("2025-01-01", periods=10, freq="15min", tz="UTC")

        # ACT
        freq = VC._infer_freq(idx)

        # ASSERT
        assert freq == pd.Timedelta(minutes=15)

    def test_infer_freq_insufficient_data(self):
        """Test that insufficient data returns None."""
        # ARRANGE
        idx = pd.date_range("2025-01-01", periods=2, freq="1min", tz="UTC")

        # ACT
        freq = VC._infer_freq(idx)

        # ASSERT
        assert freq is None


class TestBuildExpectedIndex:
    """Test expected index generation."""

    def test_build_expected_index_1min(self):
        """Test building expected index for 1-minute bars."""
        # ARRANGE
        start = pd.Timestamp("2025-01-01 00:00:00", tz="UTC")
        end = pd.Timestamp("2025-01-01 00:05:00", tz="UTC")
        freq = pd.Timedelta(minutes=1)

        # ACT
        idx = VC._build_expected_index(start, end, freq)

        # ASSERT
        assert len(idx) == 6  # 0,1,2,3,4,5 minutes
        assert idx[0] == start
        assert idx[-1] == end

    def test_build_expected_index_15min(self):
        """Test building expected index for 15-minute bars."""
        # ARRANGE
        start = pd.Timestamp("2025-01-01 00:00:00", tz="UTC")
        end = pd.Timestamp("2025-01-01 01:00:00", tz="UTC")
        freq = pd.Timedelta(minutes=15)

        # ACT
        idx = VC._build_expected_index(start, end, freq)

        # ASSERT
        assert len(idx) == 5  # 0,15,30,45,60 minutes
        assert idx[0] == start
        assert idx[-1] == end


class TestDetectIssues:
    """Test gap, duplicate, and zero-volume detection."""

    def test_detect_duplicates(self):
        """Test detection of duplicate timestamps."""
        # ARRANGE
        df = pd.DataFrame({
            "open_time": pd.to_datetime([
                "2025-01-01 00:00:00",
                "2025-01-01 00:01:00",
                "2025-01-01 00:01:00",  # Duplicate
                "2025-01-01 00:02:00"
            ], utc=True),
            "open": [100, 101, 101.5, 102],
            "high": [102, 103, 103.5, 104],
            "low": [99, 100, 100.5, 101],
            "close": [101, 102, 102.5, 103],
            "volume": [1000, 1100, 1050, 1200]
        })

        # ACT
        _, dupes, zeros, gaps, freq, expected = VC._detect_issues(df)

        # ASSERT
        assert dupes == 1

    def test_detect_zero_volume(self):
        """Test detection of zero/negative volume."""
        # ARRANGE
        df = pd.DataFrame({
            "open_time": pd.date_range("2025-01-01", periods=5, freq="1min", tz="UTC"),
            "open": [100, 101, 102, 103, 104],
            "high": [102, 103, 104, 105, 106],
            "low": [99, 100, 101, 102, 103],
            "close": [101, 102, 103, 104, 105],
            "volume": [1000, 0, -10, 1200, 1300]  # 2 invalid volumes
        })

        # ACT
        _, dupes, zeros, gaps, freq, expected = VC._detect_issues(df)

        # ASSERT
        assert zeros == 2

    def test_detect_gaps(self):
        """Test detection of missing bars (gaps)."""
        # ARRANGE
        times = pd.date_range("2025-01-01", periods=5, freq="1min", tz="UTC")
        # Remove index 2 to create gap
        df = pd.DataFrame({
            "open_time": [times[0], times[1], times[3], times[4]],  # Missing times[2]
            "open": [100, 101, 103, 104],
            "high": [102, 103, 105, 106],
            "low": [99, 100, 102, 103],
            "close": [101, 102, 104, 105],
            "volume": [1000, 1100, 1300, 1400]
        })

        # ACT
        _, dupes, zeros, gaps, freq, expected = VC._detect_issues(df)

        # ASSERT
        assert gaps == 1  # One missing bar


class TestRepair:
    """Test data repair (duplicate removal, gap filling)."""

    def test_repair_removes_duplicates(self):
        """Test that duplicates are removed (keeping first)."""
        # ARRANGE
        idx = pd.date_range("2025-01-01", periods=3, freq="1min", tz="UTC")
        df = pd.DataFrame({
            "open": [100, 101, 101.5],
            "high": [102, 103, 103.5],
            "low": [99, 100, 100.5],
            "close": [101, 102, 102.5],
            "volume": [1000, 1100, 1050]
        }, index=[idx[0], idx[1], idx[1]])  # Duplicate idx[1]

        # ACT
        result = VC._repair(df, None, "drop")

        # ASSERT
        assert len(result) == 2  # Duplicate removed
        assert not result.index.duplicated().any()

    def test_repair_fills_gaps_with_ffill(self):
        """Test gap filling with forward fill."""
        # ARRANGE
        times = pd.date_range("2025-01-01", periods=5, freq="1min", tz="UTC")
        df = pd.DataFrame({
            "open": [100, 101, 103],
            "high": [102, 103, 105],
            "low": [99, 100, 102],
            "close": [101, 102, 104],
            "volume": [1000, 1100, 1300]
        }, index=[times[0], times[1], times[3]])  # Missing times[2]

        expected_idx = pd.date_range(times[0], times[4], freq="1min", tz="UTC")

        # ACT
        result = VC._repair(df, expected_idx, "ffill")

        # ASSERT
        assert len(result) == 5  # Gap filled
        assert result.loc[times[2], "close"] == 102  # Forward filled

    def test_repair_drops_gaps_with_drop(self):
        """Test gap filling with drop strategy."""
        # ARRANGE
        times = pd.date_range("2025-01-01", periods=5, freq="1min", tz="UTC")
        df = pd.DataFrame({
            "open": [100, 101, 103],
            "high": [102, 103, 105],
            "low": [99, 100, 102],
            "close": [101, 102, 104],
            "volume": [1000, 1100, 1300]
        }, index=[times[0], times[1], times[3]])

        expected_idx = pd.date_range(times[0], times[4], freq="1min", tz="UTC")

        # ACT
        result = VC._repair(df, expected_idx, "drop")

        # ASSERT
        assert len(result) == 3  # Gap rows dropped

    def test_repair_removes_zero_volume_rows(self):
        """Test that zero/negative volume rows are removed."""
        # ARRANGE
        idx = pd.date_range("2025-01-01", periods=3, freq="1min", tz="UTC")
        df = pd.DataFrame({
            "open": [100, 101, 102],
            "high": [102, 103, 104],
            "low": [99, 100, 101],
            "close": [101, 102, 103],
            "volume": [1000, 0, 1200]  # Zero volume at idx[1]
        }, index=idx)

        # ACT
        result = VC._repair(df, None, "drop")

        # ASSERT
        assert len(result) == 2  # Zero volume row removed
        assert (result["volume"] > 0).all()

    def test_repair_invalid_fill_strategy(self):
        """Test that invalid fill strategy raises ValueError."""
        # ARRANGE
        idx = pd.date_range("2025-01-01", periods=2, freq="1min", tz="UTC")
        df = pd.DataFrame({
            "open": [100, 101],
            "high": [102, 103],
            "low": [99, 100],
            "close": [101, 102],
            "volume": [1000, 1100]
        }, index=idx)

        expected_idx = pd.date_range(idx[0], idx[-1], freq="1min", tz="UTC")

        # ACT & ASSERT
        with pytest.raises(ValueError, match="fill must be one of"):
            VC._repair(df, expected_idx, "invalid")


class TestAddCostColumns:
    """Test cost column calculations."""

    def test_add_cost_columns(self):
        """Test that cost columns are added correctly."""
        # ARRANGE
        idx = pd.date_range("2025-01-01", periods=2, freq="1min", tz="UTC")
        df = pd.DataFrame({
            "open": [100, 101],
            "high": [102, 103],
            "low": [99, 100],
            "close": [101, 102],
            "volume": [1000, 1100]
        }, index=idx)

        # ACT
        result = VC._add_cost_columns(df, fee_bps=12.0, spread_bps=3.0, slip_bps=2.0)

        # ASSERT
        assert "assumed_fee_bps" in result.columns
        assert "assumed_spread_bps" in result.columns
        assert "assumed_slippage_bps" in result.columns
        assert "assumed_roundtrip_bps" in result.columns
        assert "assumed_roundtrip_frac" in result.columns
        assert result["assumed_fee_bps"].iloc[0] == 12.0
        assert result["assumed_spread_bps"].iloc[0] == 3.0
        assert result["assumed_slippage_bps"].iloc[0] == 2.0
        assert result["assumed_roundtrip_bps"].iloc[0] == 17.0
        assert result["assumed_roundtrip_frac"].iloc[0] == 0.0017
