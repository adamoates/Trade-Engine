"""
Position Manager Service.

Centralizes position lifecycle management for futures trading.
"""

from decimal import Decimal
from datetime import datetime, timezone
from typing import Dict, Optional, Any
from loguru import logger

from trade_engine.adapters.brokers.base import BrokerAdapter
from trade_engine.domain.risk.futures_risk_manager import FuturesRiskManager
from trade_engine.services.data.funding_rate_service import FundingRateService
from trade_engine.db.postgres_adapter import PostgresDatabase


class PositionManager:
    """
    Manage position lifecycle for futures trading.

    Responsibilities:
    - Pre-trade risk validation
    - Position opening with leverage
    - Position monitoring (margin, funding)
    - Position closing
    - Database logging
    """

    def __init__(
        self,
        broker: BrokerAdapter,
        risk_manager: FuturesRiskManager,
        funding_service: FundingRateService,
        database: PostgresDatabase,
    ):
        """
        Initialize position manager.

        Args:
            broker: Broker adapter (e.g., BinanceFuturesBroker)
            risk_manager: Futures risk manager
            funding_service: Funding rate service
            database: Database adapter
        """
        self.broker = broker
        self.risk = risk_manager
        self.funding = funding_service
        self.db = database

        # Track realized P&L for current trading session
        self.session_realized_pnl = Decimal("0")
        self.daily_realized_pnl = Decimal("0")
        self.last_reset_time = datetime.now(timezone.utc)

        logger.info("Position manager initialized")

    def open_position(
        self,
        symbol: str,
        side: str,
        size: Decimal,
        leverage: int = 3,
        sl: Optional[Decimal] = None,
        tp: Optional[Decimal] = None,
        strategy: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Open a new leveraged position with full risk checks.

        Steps:
        1. Get account balance
        2. Get current price
        3. Check funding rate
        4. Validate with risk manager
        5. Set leverage on exchange
        6. Execute order
        7. Log to database

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            side: "long" or "short" (or "buy"/"sell")
            size: Position size in base currency
            leverage: Leverage multiplier (1-125)
            sl: Stop loss price (optional)
            tp: Take profit price (optional)
            strategy: Strategy name for tracking

        Returns:
            Dict with order details and success status
        """
        logger.info(
            f"Opening position | symbol={symbol} | "
            f"side={side} | size={size} | leverage={leverage}"
        )

        try:
            # 1. Get account state
            balance = self.broker.balance()
            price = self.broker.get_ticker_price(symbol)

            logger.debug(f"Account state | balance={balance} | price={price}")

            # 2. Check funding rate
            funding_rate = self.funding.get_current_funding_rate(symbol)
            daily_funding = self.funding.estimate_daily_funding(symbol, size, price)

            if daily_funding > Decimal("10.00"):
                logger.warning(
                    f"High funding cost | daily_cost={daily_funding} | "
                    f"rate={funding_rate}"
                )

            # 3. Risk validation
            risk_check = self.risk.can_open_position(
                balance=balance, price=price, size=size, leverage=leverage
            )

            if not risk_check["allowed"]:
                logger.error(f"Risk check failed | reason={risk_check['reason']}")
                return {"success": False, "reason": risk_check["reason"]}

            # 4. Set leverage
            self.broker.set_leverage(symbol, leverage)
            logger.info(f"Leverage set to {leverage}x for {symbol}")

            # 5. Execute order
            if side.lower() in ("long", "buy"):
                order_id = self.broker.buy(symbol, size, sl=sl, tp=tp)
            else:
                order_id = self.broker.sell(symbol, size, sl=sl, tp=tp)

            logger.info(f"Order executed | order_id={order_id}")

            # 6. Log to database
            self.db.open_position(
                symbol=symbol,
                side=side,
                entry_price=price,
                qty=size,
                broker=self.broker.__class__.__name__,
                strategy=strategy,
                notes=f"Leverage: {leverage}x, Funding: {funding_rate}",
            )

            # 7. Calculate liquidation price
            liq_price = self.risk.calculate_liquidation_price(
                entry_price=price, leverage=leverage, side=side
            )

            logger.info(
                f"Position opened | symbol={symbol} | "
                f"entry={price} | liquidation={liq_price} | leverage={leverage}"
            )

            return {
                "success": True,
                "order_id": order_id,
                "entry_price": price,
                "liquidation_price": liq_price,
                "funding_rate": funding_rate,
                "estimated_daily_funding": daily_funding,
            }

        except Exception as e:
            logger.error(f"Failed to open position: {e}", exc_info=True)
            return {"success": False, "reason": str(e)}

    def monitor_positions(self) -> None:
        """
        Monitor all open positions for margin health.

        Checks:
        - Margin ratio
        - Unrealized P&L
        - Liquidation distance

        Takes action if needed:
        - Close position if margin too low
        - Log warnings
        - Update database
        """
        try:
            # Get all positions from broker
            positions = self.broker.positions()

            if not positions:
                logger.debug("No open positions to monitor")
                return

            balance = self.broker.balance()

            # Calculate total maintenance margin and unrealized P&L
            total_maintenance = Decimal("0")
            total_unrealized = Decimal("0")

            for symbol, pos in positions.items():
                total_maintenance += pos.maintenance_margin or Decimal("0")
                total_unrealized += pos.unrealized_pnl or Decimal("0")

                logger.debug(
                    f"Position status | symbol={symbol} | "
                    f"size={pos.size} | entry={pos.entry_price} | "
                    f"current={pos.current_price} | pnl={pos.unrealized_pnl}"
                )

            # Check overall margin health
            margin_check = self.risk.check_margin_health(
                account_balance=balance,
                maintenance_margin=total_maintenance,
                unrealized_pnl=total_unrealized,
            )

            logger.info(
                f"Margin health check | action={margin_check['action']} | "
                f"ratio={margin_check.get('margin_ratio')} | "
                f"reason={margin_check['reason']}"
            )

            # Take action if needed
            if margin_check["action"] == "liquidate_all":
                logger.critical("EMERGENCY: Closing all positions to avoid liquidation")
                self._emergency_close_all()

            elif margin_check["action"] == "reduce_position":
                logger.warning("Reducing positions due to low margin")
                self._reduce_largest_position()

            # Log PnL snapshot with realized P&L
            self.db.log_pnl_snapshot(
                broker=self.broker.__class__.__name__,
                balance=balance,
                unrealized_pnl=total_unrealized,
                realized_pnl=self.daily_realized_pnl,
                margin_ratio=margin_check.get("margin_ratio"),
                open_positions=len(positions),
            )

        except Exception as e:
            logger.error(f"Error monitoring positions: {e}", exc_info=True)

    def close_position(
        self, symbol: str, reason: str = "Manual close"
    ) -> Dict[str, Any]:
        """
        Close an open position.

        Args:
            symbol: Trading pair
            reason: Reason for closing

        Returns:
            Dict with close details and success status
        """
        logger.info(f"Closing position | symbol={symbol} | reason={reason}")

        try:
            # Get position from broker
            positions = self.broker.positions()

            if symbol not in positions:
                logger.warning(f"No open position for {symbol}")
                return {"success": False, "reason": f"No open position for {symbol}"}

            pos = positions[symbol]
            exit_price = self.broker.get_ticker_price(symbol)

            # Calculate realized P&L
            realized_pnl = pos.unrealized_pnl if pos.unrealized_pnl else Decimal("0")

            # Close on exchange
            self.broker.close_all(symbol)

            # Update realized P&L tracking
            self.session_realized_pnl += realized_pnl
            self.daily_realized_pnl += realized_pnl

            # Check if we need to reset daily P&L (new UTC day)
            self._check_daily_reset()

            # Log to database
            self.db.close_position(
                symbol=symbol,
                broker=self.broker.__class__.__name__,
                exit_price=exit_price,
                exit_reason=reason,
            )

            logger.info(
                f"Position closed | symbol={symbol} | "
                f"realized_pnl={realized_pnl} | "
                f"daily_total={self.daily_realized_pnl}"
            )

            return {
                "success": True,
                "exit_price": exit_price,
                "realized_pnl": realized_pnl,
                "daily_realized_pnl": self.daily_realized_pnl,
            }

        except Exception as e:
            logger.error(f"Failed to close position: {e}", exc_info=True)
            return {"success": False, "reason": str(e)}

    def _emergency_close_all(self) -> None:
        """Emergency close all positions."""
        try:
            positions = self.broker.positions()

            for symbol in positions.keys():
                self.close_position(symbol, reason="Emergency margin call")

            # Trigger kill switch
            self.risk.trigger_kill_switch("Margin call - all positions closed")

            # Log critical risk event
            self.db.log_risk_event(
                event_type="kill_switch",
                reason="Emergency margin call triggered",
                symbol=None,
                broker=self.broker.__class__.__name__,
            )

        except Exception as e:
            logger.critical(f"FAILED TO CLOSE POSITIONS: {e}", exc_info=True)

    def _reduce_largest_position(self) -> None:
        """Reduce the largest position by 50%."""
        try:
            positions = self.broker.positions()

            if not positions:
                return

            # Find largest position by notional value
            largest = max(
                positions.items(), key=lambda x: abs(x[1].size * x[1].current_price)
            )

            symbol = largest[0]
            pos = largest[1]
            reduce_size = abs(pos.size) * Decimal("0.5")

            logger.warning(
                f"Reducing position | symbol={symbol} | "
                f"current_size={pos.size} | reduce_by={reduce_size}"
            )

            # Execute reduction
            side = "sell" if pos.size > 0 else "buy"

            if side == "sell":
                self.broker.sell(symbol, reduce_size)
            else:
                self.broker.buy(symbol, reduce_size)

            logger.info(f"Position reduced for {symbol}")

        except Exception as e:
            logger.error(f"Failed to reduce position: {e}", exc_info=True)

    def _check_daily_reset(self) -> None:
        """Reset daily P&L if we've moved to a new UTC day."""
        now = datetime.now(timezone.utc)
        if now.date() > self.last_reset_time.date():
            logger.info(
                f"Daily P&L reset | previous_day={self.daily_realized_pnl} | "
                f"session_total={self.session_realized_pnl}"
            )
            self.daily_realized_pnl = Decimal("0")
            self.last_reset_time = now

    def get_realized_pnl(self) -> Dict[str, Decimal]:
        """
        Get current realized P&L statistics.

        Returns:
            Dict with session_pnl and daily_pnl
        """
        return {
            "session_pnl": self.session_realized_pnl,
            "daily_pnl": self.daily_realized_pnl,
            "last_reset": self.last_reset_time,
        }
