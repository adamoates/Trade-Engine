"""
Structured logging configuration for Trade Engine.

Provides JSON-formatted logs with proper context for trading operations.
Designed to scale from local development to production with minimal changes.

Architecture:
- Phase 0-2 (Local): JSON logs → local files → manual analysis
- Phase 3+ (Production): JSON logs → Postgres/S3 → Grafana dashboards
- Future: Event-sourced trade ledger for compliance

Usage:
    from trade_engine.core.logging_config import get_logger

    logger = get_logger(__name__)
    logger.info("order_placed", symbol="BTC/USDT", side="BUY", size=0.1, order_id="12345")
"""

import sys
import json
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime
from decimal import Decimal

from loguru import logger
import structlog


# Custom JSON encoder for Decimal types (NON-NEGOTIABLE)
class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types properly."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)  # Convert to string to preserve precision
        return super().default(obj)


def decimal_processor(
    logger: Any,
    method_name: str,
    event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """Structlog processor to convert Decimals to strings."""
    for key, value in event_dict.items():
        if isinstance(value, Decimal):
            event_dict[key] = str(value)
    return event_dict


def configure_logging(
    level: str = "INFO",
    log_dir: Optional[Path] = None,
    enable_console: bool = True,
    enable_file: bool = True,
    rotation: str = "1 day",
    retention: str = "90 days",
    compression: str = "zip",
    serialize: bool = True
) -> None:
    """
    Configure structured logging for the entire application.

    Args:
        level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files (default: logs/)
        enable_console: Enable console output
        enable_file: Enable file output
        rotation: When to rotate logs (e.g., "1 day", "500 MB")
        retention: How long to keep logs
        compression: Compression format for old logs
        serialize: Use JSON format (recommended for production)
    """
    # Remove default logger
    logger.remove()

    # Console handler (human-readable in dev, JSON in prod)
    if enable_console:
        if serialize:
            # JSON format for production
            logger.add(
                sys.stderr,
                level=level,
                serialize=True,
                backtrace=True,
                diagnose=True
            )
        else:
            # Human-readable format for development
            logger.add(
                sys.stderr,
                level=level,
                format=(
                    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                    "<level>{level: <8}</level> | "
                    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                    "<level>{message}</level>"
                ),
                colorize=True
            )

    # File handlers
    if enable_file:
        log_dir = log_dir or Path("logs")

        # Create log directory with error handling
        try:
            log_dir.mkdir(exist_ok=True, parents=True)
        except PermissionError as e:
            logger.error(f"Cannot create log directory {log_dir}: insufficient permissions")
            raise PermissionError(f"Failed to create log directory {log_dir}: {e}") from e
        except OSError as e:
            logger.error(f"Cannot create log directory {log_dir}: {e}")
            raise OSError(f"Failed to create log directory {log_dir}: {e}") from e

        # Main application log (all events)
        logger.add(
            log_dir / "trade_engine_{time}.log",
            level=level,
            rotation=rotation,
            retention=retention,
            compression=compression,
            serialize=serialize,
            backtrace=True,
            diagnose=True
        )

        # Trading activity log (INFO+ only, for audit trail)
        logger.add(
            log_dir / "trades_{time}.log",
            level="INFO",
            rotation=rotation,
            retention=retention,
            compression=compression,
            serialize=serialize,
            filter=lambda record: any(
                keyword in record["message"]
                for keyword in [
                    "order_placed", "order_filled", "order_cancelled",
                    "position_opened", "position_closed",
                    "trade_executed", "pnl_update",
                    "risk_limit", "kill_switch"
                ]
            )
        )

        # Error log (WARNING+ only)
        logger.add(
            log_dir / "errors_{time}.log",
            level="WARNING",
            rotation=rotation,
            retention=retention,
            compression=compression,
            serialize=serialize
        )


# TODO(Phase 3): Configure structlog for centralized logging
# Currently using loguru exclusively. Structlog integration planned for
# Phase 3 when pushing logs to Postgres/TimescaleDB.
# def configure_structlog():
#     """Configure structlog for structured logging with context."""
#     structlog.configure(
#         processors=[
#             structlog.stdlib.filter_by_level,
#             structlog.stdlib.add_logger_name,
#             structlog.stdlib.add_log_level,
#             structlog.stdlib.PositionalArgumentsFormatter(),
#             structlog.processors.TimeStamper(fmt="iso"),
#             structlog.processors.StackInfoRenderer(),
#             structlog.processors.format_exc_info,
#             decimal_processor,  # Handle Decimal types
#             structlog.processors.UnicodeDecoder(),
#             structlog.processors.JSONRenderer()
#         ],
#         context_class=dict,
#         logger_factory=structlog.stdlib.LoggerFactory(),
#         cache_logger_on_first_use=True,
#     )


def get_logger(name: str) -> Any:
    """
    Get a logger instance for the given module.

    Args:
        name: Module name (use __name__)

    Returns:
        Logger instance with structured logging support
    """
    return logger.bind(module=name)


class TradingLogger:
    """
    Specialized logger for trading events with standardized fields.

    Ensures all trading events have consistent structure for:
    - Post-trade analysis
    - Compliance audits
    - Performance monitoring
    """

    def __init__(self, strategy_id: Optional[str] = None):
        """
        Initialize trading logger.

        Args:
            strategy_id: Optional strategy identifier for filtering logs
        """
        self.logger = logger
        self.strategy_id = strategy_id

    def _base_context(self) -> Dict[str, Any]:
        """Get base context for all trading logs."""
        context = {}
        if self.strategy_id:
            context["strategy_id"] = self.strategy_id
        return context

    def order_placed(
        self,
        symbol: str,
        side: str,
        size: Decimal,
        price: Optional[Decimal] = None,
        order_type: str = "MARKET",
        order_id: Optional[str] = None,
        **kwargs
    ):
        """Log order placement."""
        context = self._base_context()
        context.update({
            "event": "order_placed",
            "symbol": symbol,
            "side": side,
            "size": str(size),
            "price": str(price) if price else None,
            "order_type": order_type,
            "order_id": order_id,
            **kwargs
        })
        self.logger.info("order_placed", **context)

    def order_filled(
        self,
        symbol: str,
        side: str,
        size: Decimal,
        fill_price: Decimal,
        order_id: str,
        commission: Decimal,
        **kwargs
    ):
        """Log order fill."""
        context = self._base_context()
        context.update({
            "event": "order_filled",
            "symbol": symbol,
            "side": side,
            "size": str(size),
            "fill_price": str(fill_price),
            "order_id": order_id,
            "commission": str(commission),
            **kwargs
        })
        self.logger.info("order_filled", **context)

    def order_cancelled(
        self,
        symbol: str,
        side: str,
        order_id: str,
        reason: Optional[str] = None,
        **kwargs
    ):
        """Log order cancellation."""
        context = self._base_context()
        context.update({
            "event": "order_cancelled",
            "symbol": symbol,
            "side": side,
            "order_id": order_id,
            "reason": reason,
            **kwargs
        })
        self.logger.info("order_cancelled", **context)

    def position_opened(
        self,
        symbol: str,
        side: str,
        size: Decimal,
        entry_price: Decimal,
        position_id: str,
        **kwargs
    ):
        """Log position opening."""
        context = self._base_context()
        context.update({
            "event": "position_opened",
            "symbol": symbol,
            "side": side,
            "size": str(size),
            "entry_price": str(entry_price),
            "position_id": position_id,
            **kwargs
        })
        self.logger.info("position_opened", **context)

    def position_closed(
        self,
        symbol: str,
        side: str,
        size: Decimal,
        entry_price: Decimal,
        exit_price: Decimal,
        pnl: Decimal,
        position_id: str,
        **kwargs
    ):
        """Log position closing."""
        context = self._base_context()
        context.update({
            "event": "position_closed",
            "symbol": symbol,
            "side": side,
            "size": str(size),
            "entry_price": str(entry_price),
            "exit_price": str(exit_price),
            "pnl": str(pnl),
            "position_id": position_id,
            **kwargs
        })
        self.logger.info("position_closed", **context)

    def risk_limit_breached(
        self,
        limit_type: str,
        current_value: Decimal,
        limit_value: Decimal,
        action: str = "REJECTED",
        **kwargs
    ):
        """Log risk limit breach."""
        context = self._base_context()
        context.update({
            "event": "risk_limit_breached",
            "limit_type": limit_type,
            "current_value": str(current_value),
            "limit_value": str(limit_value),
            "action": action,
            **kwargs
        })
        self.logger.warning("risk_limit_breached", **context)

    def kill_switch_triggered(
        self,
        reason: str,
        metric_value: Optional[Decimal] = None,
        limit_value: Optional[Decimal] = None,
        **kwargs
    ):
        """Log kill switch trigger."""
        context = self._base_context()
        context.update({
            "event": "kill_switch_triggered",
            "reason": reason,
            "metric_value": str(metric_value) if metric_value else None,
            "limit_value": str(limit_value) if limit_value else None,
            **kwargs
        })
        self.logger.critical("kill_switch_triggered", **context)

    def pnl_update(
        self,
        symbol: str,
        realized_pnl: Decimal,
        unrealized_pnl: Decimal,
        total_pnl: Decimal,
        **kwargs
    ):
        """Log PnL update."""
        context = self._base_context()
        context.update({
            "event": "pnl_update",
            "symbol": symbol,
            "realized_pnl": str(realized_pnl),
            "unrealized_pnl": str(unrealized_pnl),
            "total_pnl": str(total_pnl),
            **kwargs
        })
        self.logger.info("pnl_update", **context)


# NOTE: Logging is NOT initialized automatically on import.
# Applications must explicitly call configure_logging() at startup.
#
# Example (in main.py or application entry point):
#
#     from trade_engine.core.logging_config import configure_logging
#
#     if __name__ == "__main__":
#         configure_logging(
#             level=os.getenv("TRADE_ENGINE_LOG_LEVEL", "INFO"),
#             serialize=os.getenv("TRADE_ENGINE_LOG_JSON", "false").lower() == "true"
#         )
#         # ... start application
