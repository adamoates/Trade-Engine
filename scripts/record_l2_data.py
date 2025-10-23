#!/usr/bin/env python3
"""
Phase 0 Week 1: L2 Order Book Data Recorder

Records 24 hours of Level 2 order book snapshots from Binance Futures.
Saves to JSON files with timestamps for later analysis.

Usage:
    python record_l2_data.py --symbol BTCUSDT --duration 24

Requirements:
    - ccxt library installed
    - Internet connection
    - Disk space for ~1-5GB of data (24h)
"""

import argparse
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from decimal import Decimal

import ccxt
from loguru import logger


class L2DataRecorder:
    """Records Level 2 order book data from Binance Futures"""

    def __init__(self, symbol: str, duration_hours: int = 24, depth: int = 5, resume: bool = True):
        """
        Initialize the L2 data recorder.

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            duration_hours: How many hours to record
            depth: Order book depth to capture (default 5 levels)
            resume: If True, resume writing to existing file from today (default: True)
        """
        self.symbol = symbol
        self.duration_hours = duration_hours
        self.depth = depth
        self.exchange = ccxt.binanceus({
            'enableRateLimit': True
            # Binance.US only has spot markets, no futures
        })

        # Create data directory
        self.data_dir = Path('data/l2_snapshots')
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with DATE ONLY (not timestamp) for restart resilience
        # This allows the script to resume writing to the same file if it crashes
        date_str = datetime.now().strftime('%Y%m%d')
        symbol_str = symbol.replace("/", "")
        self.output_file = self.data_dir / f'l2_{symbol_str}_{date_str}.jsonl'

        # Check if file already exists (resume mode)
        self.is_resuming = False
        if resume and self.output_file.exists():
            file_size = self.output_file.stat().st_size
            if file_size > 0:
                self.is_resuming = True
                logger.warning(f"⚠️  File already exists: {self.output_file.name}")
                logger.warning(f"⚠️  Size: {file_size / 1024 / 1024:.2f} MB")
                logger.warning(f"⚠️  RESUMING: Will append to existing file")
            else:
                logger.info(f"Empty file exists, will overwrite: {self.output_file.name}")

        logger.info(f"Initialized L2 recorder for {symbol}")
        logger.info(f"Duration: {duration_hours} hours")
        logger.info(f"Depth: {depth} levels")
        logger.info(f"Output: {self.output_file}")
        logger.info(f"Mode: {'RESUME (append)' if self.is_resuming else 'NEW (overwrite)'}")

    def fetch_order_book(self) -> dict:
        """
        Fetch current order book snapshot.

        Returns:
            dict: Order book data with timestamp
        """
        try:
            order_book = self.exchange.fetch_order_book(self.symbol, limit=self.depth)

            # Add our timestamp (exchange timestamp may lag)
            snapshot = {
                'timestamp': datetime.utcnow().isoformat(),
                'exchange_timestamp': order_book.get('timestamp'),
                'symbol': self.symbol,
                'bids': order_book['bids'][:self.depth],
                'asks': order_book['asks'][:self.depth],
                'nonce': order_book.get('nonce')
            }

            return snapshot

        except Exception as e:
            logger.error(f"Error fetching order book: {e}")
            return None

    def calculate_imbalance(self, snapshot: dict) -> dict:
        """
        Calculate bid/ask volume imbalance from snapshot.

        Args:
            snapshot: Order book snapshot

        Returns:
            dict: Imbalance metrics
        """
        bids = snapshot.get('bids', [])
        asks = snapshot.get('asks', [])

        if not bids or not asks:
            return {'ratio': None, 'bid_volume': 0, 'ask_volume': 0}

        # Calculate total volume at each side (price * quantity)
        bid_volume = sum(Decimal(str(price)) * Decimal(str(qty)) for price, qty in bids)
        ask_volume = sum(Decimal(str(price)) * Decimal(str(qty)) for price, qty in asks)

        # Calculate ratio (handle division by zero)
        ratio = None
        if ask_volume > 0:
            ratio = float(bid_volume / ask_volume)

        return {
            'ratio': ratio,
            'bid_volume': float(bid_volume),
            'ask_volume': float(ask_volume)
        }

    def record(self):
        """
        Main recording loop - runs for specified duration.
        """
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=self.duration_hours)

        logger.info(f"Starting recording at {start_time}")
        logger.info(f"Will stop at {end_time}")
        logger.info(f"Writing to {self.output_file}")

        snapshots_recorded = 0
        errors = 0

        # Open in append mode if resuming, otherwise write mode
        file_mode = 'a' if self.is_resuming else 'w'
        logger.info(f"File mode: {file_mode} ({'append' if file_mode == 'a' else 'overwrite'})")

        with open(self.output_file, file_mode) as f:
            while datetime.now() < end_time:
                snapshot = self.fetch_order_book()

                if snapshot:
                    # Calculate imbalance for this snapshot
                    imbalance = self.calculate_imbalance(snapshot)
                    snapshot['imbalance'] = imbalance

                    # Write to file (one JSON object per line)
                    f.write(json.dumps(snapshot) + '\n')
                    f.flush()  # Ensure data is written

                    snapshots_recorded += 1

                    # Log progress every 100 snapshots
                    if snapshots_recorded % 100 == 0:
                        elapsed = datetime.now() - start_time
                        ratio_str = f"{imbalance['ratio']:.3f}" if imbalance['ratio'] is not None else 'N/A'
                        logger.info(
                            f"Recorded {snapshots_recorded} snapshots | "
                            f"Elapsed: {elapsed} | "
                            f"Last ratio: {ratio_str}"
                        )
                else:
                    errors += 1
                    if errors > 10:
                        logger.warning(f"High error count: {errors}")

                # Sleep 1 second between snapshots
                time.sleep(1)

        # Final summary
        duration = datetime.now() - start_time
        logger.info("=" * 60)
        logger.info("Recording Complete!")
        logger.info(f"Total snapshots: {snapshots_recorded}")
        logger.info(f"Total errors: {errors}")
        logger.info(f"Actual duration: {duration}")
        logger.info(f"Output file: {self.output_file}")
        logger.info(f"File size: {self.output_file.stat().st_size / 1024 / 1024:.2f} MB")
        logger.info("=" * 60)


def main():
    """Parse arguments and start recording."""
    parser = argparse.ArgumentParser(
        description='Record L2 order book data from Binance Futures'
    )
    parser.add_argument(
        '--symbol',
        type=str,
        default='BTC/USDT',
        help='Trading pair (default: BTC/USDT)'
    )
    parser.add_argument(
        '--duration',
        type=int,
        default=24,
        help='Recording duration in hours (default: 24)'
    )
    parser.add_argument(
        '--depth',
        type=int,
        default=5,
        help='Order book depth (default: 5 levels)'
    )
    parser.add_argument(
        '--no-resume',
        action='store_true',
        help='Do not resume from existing file, always create new file'
    )

    args = parser.parse_args()

    # Validate symbol format
    if '/' not in args.symbol:
        logger.error(f"Invalid symbol format: {args.symbol}. Use format like BTC/USDT")
        return

    try:
        recorder = L2DataRecorder(
            symbol=args.symbol,
            duration_hours=args.duration,
            depth=args.depth,
            resume=not args.no_resume  # Invert flag: --no-resume means resume=False
        )
        recorder.record()
    except KeyboardInterrupt:
        logger.warning("Recording interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == '__main__':
    main()
