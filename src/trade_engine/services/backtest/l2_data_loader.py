"""
L2 Order Book Data Loader for Backtesting

Loads historical L2 orderbook snapshots from JSONL files recorded by
scripts/record_l2_data.py and converts them to OrderBook objects for replay.

Usage:
    loader = L2DataLoader("data/l2_snapshots/l2_BTCUSDT_20251024.jsonl")
    for snapshot in loader.load():
        # snapshot is an OrderBook object
        imbalance = snapshot.calculate_imbalance(depth=5)
"""

import json
from pathlib import Path
from typing import Iterator, List, Optional
from datetime import datetime
from decimal import Decimal
from loguru import logger

from trade_engine.services.adapters.feed_binance_l2 import OrderBook


class L2DataLoader:
    """
    Loads historical L2 orderbook data from JSONL files.

    Supports both JSONL format (one snapshot per line) and single-snapshot
    JSON files (for testing).
    """

    def __init__(self, file_path: str | Path):
        """
        Initialize L2 data loader.

        Args:
            file_path: Path to JSONL file or JSON file
        """
        self.file_path = Path(file_path)

        if not self.file_path.exists():
            raise FileNotFoundError(f"L2 data file not found: {self.file_path}")

        self.snapshots_loaded = 0
        self.errors = 0

        logger.info(f"L2DataLoader initialized: {self.file_path.name}")

    def _parse_snapshot(self, data: dict) -> Optional[OrderBook]:
        """
        Parse JSON snapshot into OrderBook object.

        Args:
            data: Snapshot dict from JSON

        Returns:
            OrderBook object or None on error
        """
        try:
            symbol = data.get('symbol', 'UNKNOWN')

            # Create OrderBook
            order_book = OrderBook(symbol)

            # Parse bids
            for bid in data.get('bids', []):
                if isinstance(bid, list) and len(bid) >= 2:
                    price = Decimal(str(bid[0]))
                    qty = Decimal(str(bid[1]))
                    if qty > 0:
                        order_book.bids[price] = qty
                elif isinstance(bid, dict):
                    price = Decimal(str(bid['price']))
                    qty = Decimal(str(bid['quantity']))
                    if qty > 0:
                        order_book.bids[price] = qty

            # Parse asks
            for ask in data.get('asks', []):
                if isinstance(ask, list) and len(ask) >= 2:
                    price = Decimal(str(ask[0]))
                    qty = Decimal(str(ask[1]))
                    if qty > 0:
                        order_book.asks[price] = qty
                elif isinstance(ask, dict):
                    price = Decimal(str(ask['price']))
                    qty = Decimal(str(ask['quantity']))
                    if qty > 0:
                        order_book.asks[price] = qty

            # Set timestamp
            timestamp_str = data.get('timestamp', '')
            if timestamp_str:
                try:
                    dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    order_book.last_update_time = dt.timestamp()
                except ValueError:
                    order_book.last_update_time = datetime.utcnow().timestamp()
            else:
                order_book.last_update_time = datetime.utcnow().timestamp()

            # Validate order book
            if not order_book.bids or not order_book.asks:
                logger.warning(f"Empty order book at {timestamp_str}")
                return None

            return order_book

        except Exception as e:
            logger.error(f"Error parsing snapshot: {e}")
            self.errors += 1
            return None

    def load(self) -> Iterator[OrderBook]:
        """
        Load and yield OrderBook snapshots from file.

        Yields:
            OrderBook objects in chronological order
        """
        logger.info(f"Loading L2 data from {self.file_path}")

        # Detect file format
        is_jsonl = self.file_path.suffix == '.jsonl'

        try:
            with open(self.file_path, 'r') as f:
                if is_jsonl:
                    # JSONL format - one snapshot per line
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue

                        try:
                            data = json.loads(line)
                            order_book = self._parse_snapshot(data)

                            if order_book:
                                self.snapshots_loaded += 1
                                yield order_book

                            # Log progress every 1000 snapshots
                            if self.snapshots_loaded % 1000 == 0:
                                logger.info(f"Loaded {self.snapshots_loaded} snapshots...")

                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error at line {line_num}: {e}")
                            self.errors += 1
                else:
                    # Single JSON file (test fixtures)
                    data = json.load(f)
                    order_book = self._parse_snapshot(data)

                    if order_book:
                        self.snapshots_loaded += 1
                        yield order_book

        except Exception as e:
            logger.error(f"Error loading L2 data: {e}")
            raise

        logger.info(
            f"Loaded {self.snapshots_loaded} snapshots "
            f"({self.errors} errors) from {self.file_path.name}"
        )

    def load_all(self) -> List[OrderBook]:
        """
        Load all snapshots into memory (use with caution for large files).

        Returns:
            List of OrderBook objects
        """
        return list(self.load())


def load_multiple_files(file_paths: List[str | Path]) -> Iterator[OrderBook]:
    """
    Load and merge L2 data from multiple files in chronological order.

    Args:
        file_paths: List of JSONL/JSON file paths

    Yields:
        OrderBook objects in chronological order
    """
    for file_path in file_paths:
        loader = L2DataLoader(file_path)
        yield from loader.load()
