#!/usr/bin/env python3
"""
Import trading logs into PostgreSQL database.

This script parses trading event logs and inserts them into the database for
analysis, auditing, and backtesting purposes.

Supported log formats:
1. JSON audit logs (audit_*.jsonl) - Signal generation and risk events
2. Structured JSON logs (*_*.log) - Order execution and position tracking

Usage:
    python scripts/import_logs_to_db.py --audit logs/audit_2025-10-29.jsonl
    python scripts/import_logs_to_db.py --trades logs/trades_2025-10-29_23-41-56_591707.log
    python scripts/import_logs_to_db.py --all logs/

CRITICAL: All financial calculations use Decimal (NON-NEGOTIABLE per CLAUDE.md)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trade_engine.db.postgres_adapter import PostgresDatabase


class LogImporter:
    """Import trading logs into PostgreSQL database."""

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize log importer.

        Args:
            database_url: PostgreSQL connection URL (defaults to DATABASE_URL env var)
        """
        self.db = PostgresDatabase(database_url=database_url)
        self.stats = {
            "audit_events": 0,
            "trade_events": 0,
            "position_events": 0,
            "risk_events": 0,
            "errors": 0,
        }

    def import_audit_log(self, file_path: Path) -> int:
        """
        Import audit log (JSONL format).

        Each line is a JSON object with:
        - ts: ISO timestamp
        - event: Event type (signal_generated, risk_block, bar_received, etc.)
        - signal: Signal data (optional)
        - bar: Bar data (optional)
        - reason: Risk block reason (optional)

        Args:
            file_path: Path to audit JSONL file

        Returns:
            Number of events imported
        """
        logger.info(f"Importing audit log: {file_path}")
        count = 0

        with open(file_path, "r") as f:
            for line_num, line in enumerate(f, start=1):
                try:
                    event = json.loads(line.strip())
                    self._process_audit_event(event)
                    count += 1
                except Exception as e:
                    logger.error(
                        f"Failed to process audit log line {line_num}: {e}",
                        line=line.strip()
                    )
                    self.stats["errors"] += 1

        logger.info(f"Imported {count} audit events from {file_path.name}")
        return count

    def _process_audit_event(self, event: Dict):
        """
        Process a single audit event.

        Audit events include:
        - signal_generated: Trading signal created by strategy
        - risk_block: Signal blocked by risk management
        - bar_received: New price bar received
        """
        event_type = event.get("event")
        timestamp = self._parse_timestamp(event.get("ts"))

        if event_type == "signal_generated":
            self.stats["audit_events"] += 1
            # Could log to a signals table if needed
            logger.debug(f"Signal generated: {event.get('signal', {}).get('symbol')}")

        elif event_type == "risk_block":
            # Log risk management block
            signal = event.get("signal", {})
            reason = event.get("reason", "Unknown")

            # Map to valid risk_event_type enum value
            # Valid types: kill_switch, daily_loss_limit, max_drawdown, position_limit, order_rejected
            event_type_mapped = "position_limit"  # Default for signal blocks

            self.db.log_risk_event(
                event_type=event_type_mapped,
                reason=reason,
                symbol=signal.get("symbol"),
                broker=None,  # Not available in audit logs
            )
            self.stats["risk_events"] += 1

        elif event_type == "bar_received":
            # Just count these, don't store (too much data)
            self.stats["audit_events"] += 1

    def import_trades_log(self, file_path: Path) -> int:
        """
        Import structured trades log (JSON per line from loguru).

        Each line is a JSON object with:
        - record.extra.event: Event type (order_placed, order_filled, position_opened, etc.)
        - record.extra: Event-specific data
        - record.time.timestamp: Unix timestamp

        Args:
            file_path: Path to trades log file

        Returns:
            Number of events imported
        """
        logger.info(f"Importing trades log: {file_path}")
        count = 0

        with open(file_path, "r") as f:
            for line_num, line in enumerate(f, start=1):
                try:
                    log_entry = json.loads(line.strip())
                    self._process_trade_event(log_entry)
                    count += 1
                except Exception as e:
                    logger.error(
                        f"Failed to process trade log line {line_num}: {e}",
                        line=line[:100]  # First 100 chars
                    )
                    self.stats["errors"] += 1

        logger.info(f"Imported {count} trade events from {file_path.name}")
        return count

    def _process_trade_event(self, log_entry: Dict):
        """
        Process a single trade log event.

        Trade events include:
        - order_placed: Order submitted to broker
        - order_filled: Order executed
        - position_opened: New position created
        - position_closed: Position closed with P&L
        - risk_limit_breached: Risk limit warning
        - kill_switch_triggered: Emergency shutdown
        """
        record = log_entry.get("record", {})
        extra = record.get("extra", {})
        event_type = extra.get("event")

        if not event_type:
            return

        if event_type == "order_filled":
            # Log trade to audit trail
            self._log_trade_from_event(extra)
            self.stats["trade_events"] += 1

        elif event_type == "position_opened":
            # Open position in database
            self._open_position_from_event(extra)
            self.stats["position_events"] += 1

        elif event_type == "position_closed":
            # Close position in database
            self._close_position_from_event(extra)
            self.stats["position_events"] += 1

        elif event_type == "risk_limit_breached":
            # Log risk event
            # Map limit_type to valid enum value
            limit_type = extra.get('limit_type', 'position_limit')

            # Map common limit types to database enum values
            limit_type_map = {
                'daily_loss': 'daily_loss_limit',
                'max_drawdown': 'max_drawdown',
                'position_size': 'position_limit',
                'position_limit': 'position_limit',
            }
            event_type_mapped = limit_type_map.get(limit_type, 'position_limit')

            self.db.log_risk_event(
                event_type=event_type_mapped,
                reason=f"{limit_type} limit breached",
                metric_name=limit_type,
                metric_value=self._safe_decimal(extra.get('current_value')),
                limit_value=self._safe_decimal(extra.get('limit_value')),
            )
            self.stats["risk_events"] += 1

        elif event_type == "kill_switch_triggered":
            # Log critical risk event
            # Valid enum value is "kill_switch" not "kill_switch_triggered"
            self.db.log_risk_event(
                event_type="kill_switch",
                reason=extra.get('reason', 'Unknown'),
                metric_value=self._safe_decimal(extra.get('metric_value')),
                limit_value=self._safe_decimal(extra.get('limit_value')),
            )
            self.stats["risk_events"] += 1

    def _log_trade_from_event(self, event: Dict):
        """
        Log a trade to the database from an order_filled event.

        Args:
            event: Event data with trade details
        """
        try:
            # Generate unique trade ID if not present
            trade_id = event.get("trade_id") or f"log_trade_{event.get('order_id')}"

            self.db.log_trade(
                trade_id=trade_id,
                order_id=event.get("order_id", "unknown"),
                symbol=event.get("symbol", "UNKNOWN"),
                broker=event.get("broker", "unknown"),
                side=event.get("side", "").lower(),
                price=self._safe_decimal(event.get("fill_price") or event.get("price")),
                qty=self._safe_decimal(event.get("size") or event.get("qty")),
                commission=self._safe_decimal(event.get("commission", "0")),
                strategy=event.get("strategy_id"),
            )
        except Exception as e:
            logger.error(f"Failed to log trade: {e}", event=event)
            self.stats["errors"] += 1

    def _open_position_from_event(self, event: Dict):
        """
        Open a position in the database from a position_opened event.

        Args:
            event: Event data with position details
        """
        try:
            # Map side to long/short
            side = event.get("side", "").upper()
            if side in ("BUY", "LONG"):
                side = "long"
            elif side in ("SELL", "SHORT"):
                side = "short"
            else:
                logger.warning(f"Unknown position side: {side}, defaulting to long")
                side = "long"

            self.db.open_position(
                symbol=event.get("symbol", "UNKNOWN"),
                side=side,
                entry_price=self._safe_decimal(event.get("entry_price")),
                qty=self._safe_decimal(event.get("size") or event.get("qty")),
                broker=event.get("broker", "unknown"),
                strategy=event.get("strategy_id"),
                notes=f"Imported from log - Position ID: {event.get('position_id')}"
            )
        except Exception as e:
            # Position may already exist - that's ok
            if "Position already open" in str(e):
                logger.debug(f"Position already exists: {event.get('symbol')}")
            else:
                logger.error(f"Failed to open position: {e}", event=event)
                self.stats["errors"] += 1

    def _close_position_from_event(self, event: Dict):
        """
        Close a position in the database from a position_closed event.

        Args:
            event: Event data with position closure details
        """
        try:
            self.db.close_position(
                symbol=event.get("symbol", "UNKNOWN"),
                broker=event.get("broker", "unknown"),
                exit_price=self._safe_decimal(event.get("exit_price")),
                exit_reason=event.get("exit_reason") or event.get("reason"),
            )
        except Exception as e:
            # Position may not exist - that's ok
            if "No open position found" in str(e):
                logger.debug(f"Position not found (may be already closed): {event.get('symbol')}")
            else:
                logger.error(f"Failed to close position: {e}", event=event)
                self.stats["errors"] += 1

    def _safe_decimal(self, value) -> Decimal:
        """
        Safely convert value to Decimal.

        Args:
            value: Value to convert (string, int, float, or Decimal)

        Returns:
            Decimal value

        Raises:
            ValueError: If value cannot be converted
        """
        if value is None:
            return Decimal("0")

        if isinstance(value, Decimal):
            return value

        # Convert to string first to avoid float precision issues
        return Decimal(str(value))

    def _parse_timestamp(self, ts_str: str) -> datetime:
        """
        Parse ISO timestamp string to datetime.

        Args:
            ts_str: ISO format timestamp string

        Returns:
            Datetime object (UTC)
        """
        if not ts_str:
            return datetime.now(timezone.utc)

        try:
            # Parse ISO format: "2025-10-29T07:14:47.130863Z"
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except Exception as e:
            logger.warning(f"Failed to parse timestamp '{ts_str}': {e}")
            return datetime.now(timezone.utc)

    def import_directory(self, directory: Path):
        """
        Import all log files from a directory.

        Args:
            directory: Path to directory containing log files
        """
        logger.info(f"Importing all logs from: {directory}")

        # Import audit logs
        audit_logs = sorted(directory.glob("audit_*.jsonl"))
        for log_file in audit_logs:
            try:
                self.import_audit_log(log_file)
            except Exception as e:
                logger.error(f"Failed to import audit log {log_file}: {e}")
                self.stats["errors"] += 1

        # Import trade logs
        trade_logs = sorted(directory.glob("trades_*.log"))
        for log_file in trade_logs:
            try:
                self.import_trades_log(log_file)
            except Exception as e:
                logger.error(f"Failed to import trade log {log_file}: {e}")
                self.stats["errors"] += 1

        # Import engine logs (if needed)
        engine_logs = sorted(directory.glob("trade_engine_*.log"))
        for log_file in engine_logs:
            try:
                self.import_trades_log(log_file)
            except Exception as e:
                logger.error(f"Failed to import engine log {log_file}: {e}")
                self.stats["errors"] += 1

    def print_stats(self):
        """Print import statistics."""
        logger.info("=" * 60)
        logger.info("Import Statistics:")
        logger.info(f"  Audit events:    {self.stats['audit_events']}")
        logger.info(f"  Trade events:    {self.stats['trade_events']}")
        logger.info(f"  Position events: {self.stats['position_events']}")
        logger.info(f"  Risk events:     {self.stats['risk_events']}")
        logger.info(f"  Errors:          {self.stats['errors']}")
        logger.info("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Import trading logs into PostgreSQL database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import specific audit log
  python scripts/import_logs_to_db.py --audit logs/audit_2025-10-29.jsonl

  # Import specific trade log
  python scripts/import_logs_to_db.py --trades logs/trades_2025-10-29_23-41-56_591707.log

  # Import all logs from directory
  python scripts/import_logs_to_db.py --all logs/

  # Import with custom database URL
  python scripts/import_logs_to_db.py --all logs/ --db-url postgresql://user:pass@localhost:5432/trade_engine
        """
    )

    parser.add_argument(
        "--audit",
        type=Path,
        help="Import single audit log file (JSONL format)"
    )
    parser.add_argument(
        "--trades",
        type=Path,
        help="Import single trade log file (structured JSON format)"
    )
    parser.add_argument(
        "--all",
        type=Path,
        help="Import all log files from directory"
    )
    parser.add_argument(
        "--db-url",
        type=str,
        help="PostgreSQL connection URL (default: DATABASE_URL env var)"
    )

    args = parser.parse_args()

    # Validate arguments
    if not any([args.audit, args.trades, args.all]):
        parser.error("Must specify --audit, --trades, or --all")

    # Initialize importer
    try:
        importer = LogImporter(database_url=args.db_url)
    except Exception as e:
        logger.error(f"Failed to initialize database connection: {e}")
        sys.exit(1)

    # Import logs
    try:
        if args.audit:
            if not args.audit.exists():
                logger.error(f"Audit log file not found: {args.audit}")
                sys.exit(1)
            importer.import_audit_log(args.audit)

        if args.trades:
            if not args.trades.exists():
                logger.error(f"Trade log file not found: {args.trades}")
                sys.exit(1)
            importer.import_trades_log(args.trades)

        if args.all:
            if not args.all.is_dir():
                logger.error(f"Directory not found: {args.all}")
                sys.exit(1)
            importer.import_directory(args.all)

        # Print statistics
        importer.print_stats()

    except KeyboardInterrupt:
        logger.warning("Import interrupted by user")
        importer.print_stats()
        sys.exit(1)
    except Exception as e:
        logger.error(f"Import failed: {e}")
        importer.print_stats()
        sys.exit(1)

    logger.success("Import completed successfully")


if __name__ == "__main__":
    main()
