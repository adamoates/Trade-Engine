"""Unit tests for tools/fetch_binance_ohlcv.py"""
import csv
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
import pytest
import requests
from tools import fetch_binance_ohlcv as FB


class TestParsers:
    """Test timestamp parsing and symbol formatting."""

    def test_parse_ts_with_iso8601(self):
        """Test parsing ISO8601 timestamp."""
        # ACT
        result = FB.parse_ts("2025-01-01T00:00:00Z")

        # ASSERT
        expected = int(datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
        assert result == expected

    def test_parse_ts_with_yyyy_mm_dd(self):
        """Test parsing YYYY-MM-DD date."""
        # ACT
        result = FB.parse_ts("2025-01-01")

        # ASSERT
        expected = int(datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
        assert result == expected

    def test_parse_ts_with_none(self):
        """Test parsing None returns None."""
        # ACT
        result = FB.parse_ts(None)

        # ASSERT
        assert result is None

    def test_parse_ts_adds_utc_timezone(self):
        """Test that naive datetimes are interpreted as UTC."""
        # ACT
        result = FB.parse_ts("2025-01-01")

        # ASSERT
        # Should be interpreted as UTC, not local time
        expected = int(datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
        assert result == expected

    def test_now_ms_returns_milliseconds(self):
        """Test that now_ms returns timestamp in milliseconds."""
        # ACT
        result = FB.now_ms()

        # ASSERT
        # Should be within last minute (reasonable for test)
        now = datetime.now(timezone.utc).timestamp() * 1000
        assert abs(result - now) < 60000  # Within 60 seconds

    def test_clamp_symbol_removes_slash(self):
        """Test that clamp_symbol removes slash from BTC/USDT."""
        # ACT
        result = FB.clamp_symbol("BTC/USDT")

        # ASSERT
        assert result == "BTCUSDT"

    def test_clamp_symbol_uppercases(self):
        """Test that clamp_symbol uppercases symbol."""
        # ACT
        result = FB.clamp_symbol("btcusdt")

        # ASSERT
        assert result == "BTCUSDT"

    def test_clamp_symbol_already_formatted(self):
        """Test that already-formatted symbol passes through."""
        # ACT
        result = FB.clamp_symbol("BTCUSDT")

        # ASSERT
        assert result == "BTCUSDT"


class TestInferNextFromCSV:
    """Test CSV resume logic."""

    def test_infer_next_from_nonexistent_file(self, tmp_path):
        """Test that nonexistent file returns None."""
        # ARRANGE
        path = tmp_path / "nonexistent.csv"

        # ACT
        result = FB.infer_next_from_csv(path)

        # ASSERT
        assert result is None

    def test_infer_next_from_empty_file(self, tmp_path):
        """Test that empty file returns None."""
        # ARRANGE
        path = tmp_path / "empty.csv"
        path.touch()

        # ACT
        result = FB.infer_next_from_csv(path)

        # ASSERT
        assert result is None

    def test_infer_next_from_csv_with_data(self, tmp_path):
        """Test that last row's open_time is returned."""
        # ARRANGE
        path = tmp_path / "data.csv"
        with path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["open_time", "open", "high", "low", "close", "volume"])
            writer.writerow([1609459200000, "100", "102", "99", "101", "1000"])
            writer.writerow([1609459260000, "101", "103", "100", "102", "1100"])

        # ACT
        result = FB.infer_next_from_csv(path)

        # ASSERT
        assert result == 1609459260000

    def test_infer_next_from_csv_with_invalid_data(self, tmp_path):
        """Test that invalid open_time returns None."""
        # ARRANGE
        path = tmp_path / "invalid.csv"
        with path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["open_time", "open", "high", "low", "close", "volume"])
            writer.writerow(["invalid", "100", "102", "99", "101", "1000"])

        # ACT
        result = FB.infer_next_from_csv(path)

        # ASSERT
        assert result is None


class TestRequestKlines:
    """Test HTTP request handling with retries and backoff."""

    def test_request_klines_success(self):
        """Test successful HTTP 200 response."""
        # ARRANGE
        mock_data = [[1609459200000, "100", "102", "99", "101", "1000", 1609459259999, "100000", 500, "500", "50000", "0"]]
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data

        with patch("requests.get", return_value=mock_response):
            # ACT
            data, resp = FB.request_klines(
                FB.SPOT_BASE,
                "/api/v3/klines",
                {"symbol": "BTCUSDT", "interval": "1m"}
            )

            # ASSERT
            assert data == mock_data
            assert resp.status_code == 200

    def test_request_klines_retries_on_429(self):
        """Test that 429 rate limit triggers retry."""
        # ARRANGE
        mock_fail = Mock()
        mock_fail.status_code = 429
        mock_success = Mock()
        mock_success.status_code = 200
        mock_success.json.return_value = []

        call_count = {"n": 0}

        def side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return mock_fail
            return mock_success

        with patch("requests.get", side_effect=side_effect):
            with patch("tools.fetch_binance_ohlcv.sleep_with_jitter"):
                # ACT
                data, resp = FB.request_klines(FB.SPOT_BASE, "/api/v3/klines", {})

                # ASSERT
                assert call_count["n"] == 2  # Retried once
                assert resp.status_code == 200

    def test_request_klines_retries_on_500(self):
        """Test that 500 server error triggers retry."""
        # ARRANGE
        mock_fail = Mock()
        mock_fail.status_code = 500
        mock_success = Mock()
        mock_success.status_code = 200
        mock_success.json.return_value = []

        call_count = {"n": 0}

        def side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return mock_fail
            return mock_success

        with patch("requests.get", side_effect=side_effect):
            with patch("tools.fetch_binance_ohlcv.sleep_with_jitter"):
                # ACT
                data, resp = FB.request_klines(FB.SPOT_BASE, "/api/v3/klines", {})

                # ASSERT
                assert call_count["n"] == 2  # Retried once

    def test_request_klines_raises_on_400(self):
        """Test that 400 bad request raises immediately (no retry)."""
        # ARRANGE
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"

        with patch("requests.get", return_value=mock_response):
            # ACT & ASSERT
            with pytest.raises(RuntimeError, match="HTTP 400"):
                FB.request_klines(FB.SPOT_BASE, "/api/v3/klines", {})

    def test_request_klines_raises_after_max_retries(self):
        """Test that max retries exhausted raises exception."""
        # ARRANGE
        mock_response = Mock()
        mock_response.status_code = 429

        with patch("requests.get", return_value=mock_response):
            with patch("tools.fetch_binance_ohlcv.sleep_with_jitter"):
                with patch("tools.fetch_binance_ohlcv.MAX_RETRY", 3):
                    # ACT & ASSERT
                    with pytest.raises(RuntimeError):
                        FB.request_klines(FB.SPOT_BASE, "/api/v3/klines", {})


class TestYieldKlines:
    """Test kline pagination and yielding."""

    def test_yield_klines_single_page(self):
        """Test fetching klines that fit in single page."""
        # ARRANGE
        mock_data = [
            [1609459200000, "100", "102", "99", "101", "1000", 1609459259999, "100000", 500, "500", "50000", "0"],
            [1609459260000, "101", "103", "100", "102", "1100", 1609459319999, "110000", 550, "550", "55000", "0"]
        ]

        call_count = {"n": 0}
        def side_effect(*args, **kwargs):
            call_count["n"] += 1
            mock = Mock()
            mock.status_code = 200
            if call_count["n"] == 1:
                mock.json.return_value = mock_data
            else:
                mock.json.return_value = []  # Return empty for pagination check
            return mock

        with patch("requests.get", side_effect=side_effect):
            with patch("tools.fetch_binance_ohlcv.sleep_with_jitter"):  # Avoid sleep delays
                # ACT
                klines = list(FB.yield_klines(
                    "spot", "BTCUSDT", "1m",
                    start_ms=1609459200000,
                    end_ms=1609459319999,
                    limit=1000
                ))

                # ASSERT
                assert len(klines) == 2
                assert klines[0][0] == 1609459200000
                assert klines[1][0] == 1609459260000

    def test_yield_klines_pagination(self):
        """Test pagination across multiple requests."""
        # ARRANGE
        # First page: 2 klines
        page1 = [
            [1609459200000, "100", "102", "99", "101", "1000", 1609459259999, "100000", 500, "500", "50000", "0"],
            [1609459260000, "101", "103", "100", "102", "1100", 1609459319999, "110000", 550, "550", "55000", "0"]
        ]
        # Second page: 1 kline
        page2 = [
            [1609459320000, "102", "104", "101", "103", "1200", 1609459379999, "120000", 600, "600", "60000", "0"]
        ]

        call_count = {"n": 0}

        def side_effect(*args, **kwargs):
            call_count["n"] += 1
            mock = Mock()
            mock.status_code = 200
            if call_count["n"] == 1:
                mock.json.return_value = page1
            elif call_count["n"] == 2:
                mock.json.return_value = page2
            else:
                mock.json.return_value = []
            return mock

        with patch("requests.get", side_effect=side_effect):
            with patch("tools.fetch_binance_ohlcv.sleep_with_jitter"):
                # ACT
                klines = list(FB.yield_klines(
                    "spot", "BTCUSDT", "1m",
                    start_ms=1609459200000,
                    end_ms=1609459379999,
                    limit=1000
                ))

                # ASSERT
                assert len(klines) == 3
                # Note: call_count will be 3 (page1, page2, empty) due to pagination check

    def test_yield_klines_stops_at_end_ms(self):
        """Test that pagination stops when reaching end_ms."""
        # ARRANGE
        mock_data = [
            [1609459200000, "100", "102", "99", "101", "1000", 1609459259999, "100000", 500, "500", "50000", "0"],
            [1609459260000, "101", "103", "100", "102", "1100", 1609459319999, "110000", 550, "550", "55000", "0"]
        ]
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data

        with patch("requests.get", return_value=mock_response):
            with patch("tools.fetch_binance_ohlcv.sleep_with_jitter"):  # Avoid sleep delays
                # ACT
                klines = list(FB.yield_klines(
                    "spot", "BTCUSDT", "1m",
                    start_ms=1609459200000,
                    end_ms=1609459200000,  # End at first kline
                    limit=1000
                ))

                # ASSERT
                # Should stop after first page because last_open >= end_ms
                assert len(klines) == 2  # Returns all from first page

    def test_yield_klines_empty_response(self):
        """Test handling of empty response."""
        # ARRANGE
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch("requests.get", return_value=mock_response):
            # ACT
            klines = list(FB.yield_klines(
                "spot", "BTCUSDT", "1m",
                start_ms=1609459200000,
                end_ms=1609459319999,
                limit=1000
            ))

            # ASSERT
            assert len(klines) == 0

    def test_yield_klines_futures_market(self):
        """Test that futures market uses correct endpoint."""
        # ARRANGE
        call_count = {"n": 0}
        def side_effect(*args, **kwargs):
            call_count["n"] += 1
            mock = Mock()
            mock.status_code = 200
            if call_count["n"] == 1:
                mock.json.return_value = [[1609459200000, "100", "102", "99", "101", "1000", 1609459259999, "100000", 500, "500", "50000", "0"]]
            else:
                mock.json.return_value = []  # Return empty for pagination check
            return mock

        with patch("requests.get", side_effect=side_effect) as mock_get:
            with patch("tools.fetch_binance_ohlcv.sleep_with_jitter"):  # Avoid sleep delays
                # ACT
                list(FB.yield_klines(
                    "futures", "BTCUSDT", "1m",
                    start_ms=1609459200000,
                    end_ms=1609459259999,
                    limit=1000
                ))

                # ASSERT
                call_args = mock_get.call_args_list[0]  # Check first call
                url = call_args[0][0]
                assert "/fapi/v1/klines" in url or call_args[1].get("params") is not None


class TestWriteHeaderIfNeeded:
    """Test CSV header writing logic."""

    def test_write_header_if_needed_to_stdout(self):
        """Test that header is written to stdout on first call."""
        # ARRANGE
        mock_writer = Mock()
        wrote_header = False

        # ACT
        result = FB.write_header_if_needed(mock_writer, wrote_header, out_to_file=False)

        # ASSERT
        assert result is True
        mock_writer.writerow.assert_called_once()
        header = mock_writer.writerow.call_args[0][0]
        assert "open_time" in header

    def test_write_header_if_needed_already_written(self):
        """Test that header is not written twice."""
        # ARRANGE
        mock_writer = Mock()
        wrote_header = True

        # ACT
        result = FB.write_header_if_needed(mock_writer, wrote_header, out_to_file=False)

        # ASSERT
        assert result is True
        mock_writer.writerow.assert_not_called()

    def test_write_header_if_needed_to_file(self):
        """Test that header is not written when out_to_file=True."""
        # ARRANGE
        mock_writer = Mock()
        wrote_header = False

        # ACT
        result = FB.write_header_if_needed(mock_writer, wrote_header, out_to_file=True)

        # ASSERT
        assert result is False
        mock_writer.writerow.assert_not_called()
