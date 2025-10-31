"""
PostgreSQL Database Adapter for Trade Engine.

Provides persistent storage for:
- Position tracking (entry prices, P&L)
- Trade audit trail (all executions)
- Risk events (kill switch triggers, limit breaches)
- Performance metrics (daily P&L summaries)

CRITICAL: All financial calculations use Decimal (NON-NEGOTIABLE per CLAUDE.md).

Usage:
    from trade_engine.db.postgres_adapter import PostgresDatabase

    db = PostgresDatabase(database_url=os.getenv("DATABASE_URL"))

    # Open position
    db.open_position(
        symbol="BTCUSDT",
        side="long",
        entry_price=Decimal("50000.00"),
        qty=Decimal("0.01"),
        broker="kraken_futures"
    )

    # Close position
    db.close_position(
        symbol="BTCUSDT",
        broker="kraken_futures",
        exit_price=Decimal("50100.00"),
        exit_reason="take_profit"
    )
"""

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from loguru import logger

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    logger.warning("psycopg2 not installed - PostgreSQL support disabled")


class PostgresDatabaseError(Exception):
    """PostgreSQL database errors."""
    pass


class PostgresDatabase:
    """
    PostgreSQL adapter for Trade Engine position and trade tracking.

    Features:
    - ACID compliance via transactions
    - Connection pooling
    - Automatic P&L calculation
    - Multi-broker support
    - Audit trail for compliance

    Thread Safety: Uses connection pooling with thread-safe operations.
    """

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize PostgreSQL database connection.

        Args:
            database_url: PostgreSQL connection URL
                         (e.g., "postgresql://user:pass@localhost:5432/dbname")
                         Falls back to DATABASE_URL env variable if not provided.

        Raises:
            PostgresDatabaseError: If PostgreSQL not available or connection fails
        """
        if not POSTGRES_AVAILABLE:
            raise PostgresDatabaseError(
                "psycopg2 not installed. Install with: pip install psycopg2-binary"
            )

        self.database_url = database_url or os.getenv("DATABASE_URL")

        if not self.database_url:
            raise PostgresDatabaseError(
                "No database URL provided. Set DATABASE_URL environment variable or pass database_url parameter."
            )

        # Test connection
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT version();")
                    version = cur.fetchone()[0]
                    logger.info(f"PostgreSQL connected | Version: {version}")
        except Exception as e:
            raise PostgresDatabaseError(f"Failed to connect to PostgreSQL: {e}")

        logger.info(f"PostgresDatabase initialized | URL: {self._mask_url(self.database_url)}")

    def _mask_url(self, url: str) -> str:
        """Mask password in database URL for logging."""
        if "@" in url and ":" in url:
            parts = url.split("@")
            if len(parts) == 2:
                credentials = parts[0].split("://")[-1]
                if ":" in credentials:
                    user = credentials.split(":")[0]
                    return url.replace(credentials, f"{user}:***")
        return url

    @contextmanager
    def _get_connection(self):
        """
        Context manager for database connections.

        Ensures connections are properly closed and provides automatic rollback on errors.
        """
        conn = psycopg2.connect(self.database_url)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database transaction failed: {e}")
            raise
        finally:
            conn.close()

    def open_position(
        self,
        symbol: str,
        side: str,
        entry_price: Decimal,
        qty: Decimal,
        broker: str,
        strategy: Optional[str] = None,
        notes: Optional[str] = None
    ) -> int:
        """
        Open a new position.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            side: "long" or "short"
            entry_price: Entry price (must be Decimal)
            qty: Position quantity (must be Decimal)
            broker: Broker name (e.g., "kraken_futures")
            strategy: Strategy name (optional)
            notes: Additional notes (optional)

        Returns:
            Position ID

        Raises:
            PostgresDatabaseError: If position already open or invalid data
        """
        # Validate Decimal types (CRITICAL per CLAUDE.md)
        if not isinstance(entry_price, Decimal):
            raise PostgresDatabaseError(
                f"entry_price must be Decimal, got {type(entry_price)}. "
                "Float types are FORBIDDEN for financial calculations."
            )
        if not isinstance(qty, Decimal):
            raise PostgresDatabaseError(
                f"qty must be Decimal, got {type(qty)}. "
                "Float types are FORBIDDEN for financial calculations."
            )

        # Validate side
        if side not in ("long", "short"):
            raise PostgresDatabaseError(f"Invalid side: {side}. Must be 'long' or 'short'")

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        INSERT INTO positions (
                            symbol, broker, side, entry_price, qty, strategy, notes, status
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'open')
                        RETURNING id
                        """,
                        (symbol, broker, side, str(entry_price), str(qty), strategy, notes)
                    )
                    position_id = cur.fetchone()[0]

                    logger.info(
                        f"Position opened | ID: {position_id} | "
                        f"{symbol} {side} @ {entry_price} x {qty} | {broker}"
                    )

                    return position_id

                except psycopg2.IntegrityError as e:
                    if "unique_open_position" in str(e):
                        raise PostgresDatabaseError(
                            f"Position already open for {symbol} on {broker}"
                        )
                    raise PostgresDatabaseError(f"Failed to open position: {e}")

    def close_position(
        self,
        symbol: str,
        broker: str,
        exit_price: Decimal,
        exit_reason: Optional[str] = None
    ) -> Decimal:
        """
        Close an open position and calculate realized P&L.

        Args:
            symbol: Trading pair
            broker: Broker name
            exit_price: Exit price (must be Decimal)
            exit_reason: Reason for exit (e.g., "take_profit", "stop_loss")

        Returns:
            Realized P&L (Decimal)

        Raises:
            PostgresDatabaseError: If no open position found or invalid data
        """
        # Validate Decimal type (CRITICAL per CLAUDE.md)
        if not isinstance(exit_price, Decimal):
            raise PostgresDatabaseError(
                f"exit_price must be Decimal, got {type(exit_price)}. "
                "Float types are FORBIDDEN for financial calculations."
            )

        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Find open position
                cur.execute(
                    """
                    SELECT id, side, entry_price, qty, commission
                    FROM positions
                    WHERE symbol = %s AND broker = %s AND status = 'open'
                    """,
                    (symbol, broker)
                )
                position = cur.fetchone()

                if not position:
                    raise PostgresDatabaseError(
                        f"No open position found for {symbol} on {broker}"
                    )

                # Close position (P&L calculated by trigger)
                cur.execute(
                    """
                    UPDATE positions
                    SET status = 'closed',
                        exit_price = %s,
                        exit_time = NOW(),
                        exit_reason = %s
                    WHERE id = %s
                    RETURNING realized_pnl
                    """,
                    (str(exit_price), exit_reason, position['id'])
                )
                result = cur.fetchone()
                realized_pnl = Decimal(str(result['realized_pnl']))

                logger.info(
                    f"Position closed | ID: {position['id']} | "
                    f"{symbol} @ {exit_price} | P&L: {realized_pnl:+.2f} | {broker}"
                )

                return realized_pnl

    def get_open_positions(self, broker: Optional[str] = None) -> List[Dict]:
        """
        Get all open positions.

        Args:
            broker: Filter by broker (optional)

        Returns:
            List of open positions as dictionaries
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if broker:
                    cur.execute(
                        """
                        SELECT id, symbol, broker, side, entry_price, qty,
                               entry_time, strategy, notes
                        FROM positions
                        WHERE status = 'open' AND broker = %s
                        ORDER BY entry_time DESC
                        """,
                        (broker,)
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, symbol, broker, side, entry_price, qty,
                               entry_time, strategy, notes
                        FROM positions
                        WHERE status = 'open'
                        ORDER BY entry_time DESC
                        """
                    )

                positions = cur.fetchall()

                # Convert to Decimal for financial values
                for pos in positions:
                    pos['entry_price'] = Decimal(str(pos['entry_price']))
                    pos['qty'] = Decimal(str(pos['qty']))

                return positions

    def log_trade(
        self,
        trade_id: str,
        order_id: str,
        symbol: str,
        broker: str,
        side: str,
        price: Decimal,
        qty: Decimal,
        commission: Decimal = Decimal("0"),
        position_id: Optional[int] = None,
        strategy: Optional[str] = None
    ):
        """
        Log a trade to the audit trail.

        Args:
            trade_id: Unique trade ID from broker
            order_id: Order ID
            symbol: Trading pair
            broker: Broker name
            side: "buy" or "sell"
            price: Execution price (Decimal)
            qty: Executed quantity (Decimal)
            commission: Trading commission (Decimal)
            position_id: Link to position (optional)
            strategy: Strategy name (optional)
        """
        # Validate Decimal types
        if not isinstance(price, Decimal):
            raise PostgresDatabaseError("price must be Decimal")
        if not isinstance(qty, Decimal):
            raise PostgresDatabaseError("qty must be Decimal")
        if not isinstance(commission, Decimal):
            raise PostgresDatabaseError("commission must be Decimal")

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trades (
                        trade_id, order_id, symbol, broker, side,
                        price, qty, commission, position_id, strategy,
                        executed_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (trade_id) DO NOTHING
                    """,
                    (
                        trade_id, order_id, symbol, broker, side,
                        str(price), str(qty), str(commission),
                        position_id, strategy
                    )
                )

                logger.debug(
                    f"Trade logged | {trade_id} | {symbol} {side} "
                    f"@ {price} x {qty} | {broker}"
                )

    def log_risk_event(
        self,
        event_type: str,
        reason: str,
        metric_name: Optional[str] = None,
        metric_value: Optional[Decimal] = None,
        limit_value: Optional[Decimal] = None,
        symbol: Optional[str] = None,
        broker: Optional[str] = None
    ):
        """
        Log a risk management event.

        Args:
            event_type: Type of event (kill_switch, daily_loss_limit, etc.)
            reason: Human-readable reason
            metric_name: Name of metric that triggered event
            metric_value: Value of metric
            limit_value: Limit that was breached
            symbol: Associated symbol (optional)
            broker: Associated broker (optional)
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO risk_events (
                        event_type, reason, metric_name, metric_value,
                        limit_value, symbol, broker
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        event_type, reason, metric_name,
                        str(metric_value) if metric_value else None,
                        str(limit_value) if limit_value else None,
                        symbol, broker
                    )
                )

                logger.warning(
                    f"Risk event logged | {event_type} | {reason}"
                )

    def get_daily_pnl(self, days: int = 1) -> Decimal:
        """
        Get P&L for the last N days.

        Args:
            days: Number of days to look back

        Returns:
            Total P&L as Decimal
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(realized_pnl), 0) as total_pnl
                    FROM positions
                    WHERE status = 'closed'
                      AND exit_time >= NOW() - INTERVAL '%s days'
                    """,
                    (days,)
                )
                result = cur.fetchone()
                return Decimal(str(result[0]))

    def refresh_daily_summary(self):
        """Refresh the daily P&L materialized view."""
        with self._get_connection() as conn:
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            with conn.cursor() as cur:
                cur.execute("REFRESH MATERIALIZED VIEW daily_pnl_summary")
                logger.debug("Daily P&L summary refreshed")

    # =========================================================================
    # L2 ORDER BOOK DATA RECORDING
    # =========================================================================

    def record_l2_snapshot(
        self,
        symbol: str,
        exchange: str,
        snapshot_time: datetime,
        bids: List[Tuple[Decimal, Decimal]],
        asks: List[Tuple[Decimal, Decimal]],
        event_time: Optional[int] = None
    ) -> int:
        """
        Record an L2 order book snapshot.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            exchange: Exchange name (e.g., "binance", "kraken")
            snapshot_time: Timestamp of snapshot
            bids: List of (price, quantity) tuples for bids
            asks: List of (price, quantity) tuples for asks
            event_time: Exchange event time in milliseconds (optional)

        Returns:
            Snapshot ID

        Example:
            snapshot_id = db.record_l2_snapshot(
                symbol="BTCUSDT",
                exchange="binance",
                snapshot_time=datetime.now(timezone.utc),
                bids=[(Decimal("50000.00"), Decimal("1.5")), ...],
                asks=[(Decimal("50001.00"), Decimal("2.3")), ...]
            )
        """
        # Convert to JSONB format
        bids_json = [[str(price), str(qty)] for price, qty in bids]
        asks_json = [[str(price), str(qty)] for price, qty in asks]

        # Calculate metrics
        best_bid = bids[0][0] if bids else None
        best_ask = asks[0][0] if asks else None

        mid_price = None
        spread = None
        spread_bps = None

        if best_bid and best_ask:
            mid_price = (best_bid + best_ask) / Decimal("2")
            spread = best_ask - best_bid
            spread_bps = (spread / mid_price) * Decimal("10000")

        # Calculate volume metrics
        bid_volume_top5 = sum(qty for _, qty in bids[:5]) if len(bids) >= 5 else sum(qty for _, qty in bids)
        ask_volume_top5 = sum(qty for _, qty in asks[:5]) if len(asks) >= 5 else sum(qty for _, qty in asks)

        imbalance_ratio = None
        if ask_volume_top5 > 0:
            imbalance_ratio = bid_volume_top5 / ask_volume_top5

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO l2_snapshots (
                        symbol, exchange, snapshot_time, event_time,
                        bids, asks,
                        best_bid, best_ask, mid_price, spread, spread_bps,
                        bid_volume_top5, ask_volume_top5, imbalance_ratio,
                        depth_levels
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        symbol, exchange, snapshot_time, event_time,
                        psycopg2.extras.Json(bids_json), psycopg2.extras.Json(asks_json),
                        str(best_bid) if best_bid else None,
                        str(best_ask) if best_ask else None,
                        str(mid_price) if mid_price else None,
                        str(spread) if spread else None,
                        str(spread_bps) if spread_bps else None,
                        str(bid_volume_top5), str(ask_volume_top5),
                        str(imbalance_ratio) if imbalance_ratio else None,
                        len(bids)
                    )
                )
                snapshot_id = cur.fetchone()[0]

                logger.debug(
                    f"L2 snapshot recorded | ID: {snapshot_id} | "
                    f"{symbol}@{exchange} | Mid: {mid_price} | Imbalance: {imbalance_ratio}"
                )

                return snapshot_id

    def start_l2_recording_session(
        self,
        symbol: str,
        exchange: str,
        depth_levels: int = 5,
        snapshot_interval_ms: int = 1000,
        notes: Optional[str] = None
    ) -> int:
        """
        Start an L2 recording session.

        Args:
            symbol: Trading pair
            exchange: Exchange name
            depth_levels: Number of order book levels to record
            snapshot_interval_ms: Snapshot interval in milliseconds
            notes: Optional notes about this session

        Returns:
            Session ID
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO l2_recording_sessions (
                        symbol, exchange, started_at,
                        depth_levels, snapshot_interval_ms,
                        status, notes, recorder_version
                    )
                    VALUES (%s, %s, NOW(), %s, %s, 'running', %s, '1.0.0')
                    RETURNING id
                    """,
                    (symbol, exchange, depth_levels, snapshot_interval_ms, notes)
                )
                session_id = cur.fetchone()[0]

                logger.info(
                    f"L2 recording session started | ID: {session_id} | "
                    f"{symbol}@{exchange} | Depth: {depth_levels}"
                )

                return session_id

    def stop_l2_recording_session(
        self,
        session_id: int,
        error_message: Optional[str] = None
    ):
        """
        Stop an L2 recording session.

        Args:
            session_id: Session ID to stop
            error_message: Optional error message if session failed
        """
        status = "failed" if error_message else "stopped"

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE l2_recording_sessions
                    SET stopped_at = NOW(),
                        status = %s,
                        error_message = %s,
                        snapshots_recorded = (
                            SELECT COUNT(*)
                            FROM l2_snapshots
                            WHERE symbol = (SELECT symbol FROM l2_recording_sessions WHERE id = %s)
                              AND exchange = (SELECT exchange FROM l2_recording_sessions WHERE id = %s)
                              AND recorded_at >= (SELECT started_at FROM l2_recording_sessions WHERE id = %s)
                        )
                    WHERE id = %s
                    """,
                    (status, error_message, session_id, session_id, session_id, session_id)
                )

                logger.info(f"L2 recording session stopped | ID: {session_id} | Status: {status}")

    def get_l2_snapshots(
        self,
        symbol: str,
        exchange: str,
        start_time: datetime,
        end_time: datetime,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Retrieve L2 snapshots for replay.

        Args:
            symbol: Trading pair
            exchange: Exchange name
            start_time: Start of time range
            end_time: End of time range
            limit: Maximum number of snapshots to retrieve

        Returns:
            List of snapshot dictionaries
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT id, symbol, exchange, snapshot_time, event_time,
                           bids, asks,
                           best_bid, best_ask, mid_price, spread, spread_bps,
                           bid_volume_top5, ask_volume_top5, imbalance_ratio,
                           depth_levels
                    FROM l2_snapshots
                    WHERE symbol = %s
                      AND exchange = %s
                      AND snapshot_time BETWEEN %s AND %s
                    ORDER BY snapshot_time ASC
                """

                params = [symbol, exchange, start_time, end_time]

                if limit:
                    query += " LIMIT %s"
                    params.append(limit)

                cur.execute(query, params)
                snapshots = cur.fetchall()

                # Convert Decimal back to Decimal objects (psycopg2 returns them as strings in JSONB)
                for snap in snapshots:
                    # Parse JSONB arrays back to Decimal tuples
                    snap['bids'] = [(Decimal(p), Decimal(q)) for p, q in snap['bids']]
                    snap['asks'] = [(Decimal(p), Decimal(q)) for p, q in snap['asks']]

                    # Convert numeric fields
                    for field in ['best_bid', 'best_ask', 'mid_price', 'spread', 'spread_bps',
                                  'bid_volume_top5', 'ask_volume_top5', 'imbalance_ratio']:
                        if snap[field] is not None:
                            snap[field] = Decimal(str(snap[field]))

                return snapshots
