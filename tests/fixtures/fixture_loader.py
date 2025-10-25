"""
Utility to load historical fixtures for testing.

This module provides helpers to load realistic market data fixtures
that were generated from actual historical price movements.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from mft.services.data.types_microstructure import OptionsSnapshot, Level2Snapshot, OrderBookLevel


FIXTURES_DIR = Path(__file__).parent


def load_options_fixture(filename: str) -> OptionsSnapshot:
    """
    Load an options data fixture from JSON.

    Args:
        filename: Name of fixture file (e.g., "btc_extreme_fear_2025_10_09.json")

    Returns:
        OptionsSnapshot instance
    """
    filepath = FIXTURES_DIR / "options_data" / filename

    with open(filepath) as f:
        data = json.load(f)

    # Convert timestamp string to datetime
    timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

    return OptionsSnapshot(
        symbol=data["symbol"],
        timestamp=timestamp,
        put_volume=data["put_volume"],
        call_volume=data["call_volume"],
        put_call_ratio=data["put_call_ratio"],
        put_open_interest=data["put_open_interest"],
        call_open_interest=data["call_open_interest"],
        total_open_interest=data["total_open_interest"],
        implied_volatility=data.get("implied_volatility"),
        iv_rank=data.get("iv_rank"),
        max_pain=data.get("max_pain"),
        gamma_exposure=data.get("gamma_exposure")
    )


def load_l2_fixture(filename: str) -> Level2Snapshot:
    """
    Load a Level 2 order book fixture from JSON.

    Args:
        filename: Name of fixture file (e.g., "btc_low_liquidity_2025_09_26.json")

    Returns:
        Level2Snapshot instance
    """
    filepath = FIXTURES_DIR / "l2_data" / filename

    with open(filepath) as f:
        data = json.load(f)

    # Convert timestamp string to datetime
    timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

    # Convert bid/ask data to OrderBookLevel objects
    bids = [
        OrderBookLevel(
            price=level["price"],
            quantity=level["quantity"],
            order_count=level["order_count"]
        )
        for level in data["bids"]
    ]

    asks = [
        OrderBookLevel(
            price=level["price"],
            quantity=level["quantity"],
            order_count=level["order_count"]
        )
        for level in data["asks"]
    ]

    return Level2Snapshot(
        symbol=data["symbol"],
        timestamp=timestamp,
        bids=bids,
        asks=asks
    )


def list_options_fixtures() -> List[str]:
    """List all available options fixtures."""
    options_dir = FIXTURES_DIR / "options_data"
    return [f.name for f in options_dir.glob("*.json") if f.is_file()]


def list_l2_fixtures() -> List[str]:
    """List all available L2 fixtures."""
    l2_dir = FIXTURES_DIR / "l2_data"
    return [f.name for f in l2_dir.glob("*.json") if f.is_file()]


def get_fixture_info(filename: str, fixture_type: str = "options") -> Dict:
    """
    Get metadata about a fixture without loading it.

    Args:
        filename: Name of fixture file
        fixture_type: Type of fixture ("options" or "l2")

    Returns:
        Dict with fixture metadata
    """
    if fixture_type == "options":
        filepath = FIXTURES_DIR / "options_data" / filename
    else:
        filepath = FIXTURES_DIR / "l2_data" / filename

    with open(filepath) as f:
        data = json.load(f)

    return {
        "symbol": data["symbol"],
        "timestamp": data["timestamp"],
        "description": data.get("description", "No description"),
        "filepath": str(filepath)
    }
