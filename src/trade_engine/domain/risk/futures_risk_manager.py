"""
Futures Risk Manager.

Adds leverage, margin, and liquidation monitoring to base risk management.
"""

from decimal import Decimal
from typing import Dict, Optional, Any
from loguru import logger

from trade_engine.domain.risk.risk_manager import RiskManager, RiskCheckResult


class FuturesRiskManager(RiskManager):
    """
    Risk management for leveraged futures trading.

    Extends base RiskManager with:
    - Leverage limits
    - Margin ratio monitoring
    - Liquidation buffer
    - Position-specific risk
    """

    def __init__(
        self,
        config: Dict[str, Any],
        max_leverage: int = 5,
        liquidation_buffer: Decimal = Decimal("0.15"),  # 15% safety margin
        maintenance_margin_rates: Optional[Dict[str, Decimal]] = None,
    ):
        """
        Initialize futures risk manager.

        Args:
            config: Full configuration dict (passed to base RiskManager)
            max_leverage: Maximum allowed leverage (1-125)
            liquidation_buffer: Minimum margin ratio before forced close
            maintenance_margin_rates: Optional dict of symbol -> MMR (e.g., {"BTCUSDT": Decimal("0.004")})
        """
        super().__init__(config)

        self.max_leverage = max_leverage
        self.liquidation_buffer = liquidation_buffer
        self.kill_switch_active = False

        # Default maintenance margin rates per symbol
        self.mmr_rates = maintenance_margin_rates or {
            "BTCUSDT": Decimal("0.004"),  # 0.4% for BTC
            "ETHUSDT": Decimal("0.005"),  # 0.5% for ETH
            "BNBUSDT": Decimal("0.010"),  # 1.0% for BNB and other alts
        }
        self.default_mmr = Decimal("0.010")  # 1.0% default for unknown symbols

        logger.info(
            f"FuturesRiskManager initialized | "
            f"MaxLeverage={max_leverage}x | "
            f"LiqBuffer={liquidation_buffer} | "
            f"MaxPos=${self.max_position_usd} | "
            f"DailyLoss=${self.max_daily_loss} | "
            f"MaxDD=${self.max_daily_loss}"  # Using daily loss as max DD for now
        )

    def validate_leverage(self, leverage: int) -> RiskCheckResult:
        """
        Validate leverage is within limits.

        Args:
            leverage: Requested leverage

        Returns:
            RiskCheckResult
        """
        if not isinstance(leverage, int) or leverage < 1:
            return RiskCheckResult(
                passed=False, reason=f"Leverage must be integer >= 1, got: {leverage}"
            )

        if leverage > self.max_leverage:
            return RiskCheckResult(
                passed=False,
                reason=f"Leverage {leverage}x exceeds maximum {self.max_leverage}x",
            )

        return RiskCheckResult(passed=True)

    def get_mmr_for_symbol(self, symbol: str) -> Decimal:
        """
        Get maintenance margin rate for a symbol.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")

        Returns:
            Maintenance margin rate as Decimal
        """
        return self.mmr_rates.get(symbol, self.default_mmr)

    def calculate_liquidation_price(
        self,
        entry_price: Decimal,
        leverage: int,
        side: str,
        symbol: Optional[str] = None,
        maintenance_margin_rate: Optional[Decimal] = None,
    ) -> Decimal:
        """
        Calculate liquidation price for a leveraged position.

        Formula (long):
            liq_price = entry * (1 - (1/leverage) + mmr)

        Formula (short):
            liq_price = entry * (1 + (1/leverage) - mmr)

        Args:
            entry_price: Entry price
            leverage: Leverage multiplier
            side: "long"/"buy" or "short"/"sell"
            symbol: Trading pair (optional, uses symbol-specific MMR if provided)
            maintenance_margin_rate: Override MMR (optional, uses symbol default if not provided)

        Returns:
            Liquidation price

        Example:
            >>> calculate_liquidation_price(
            ...     entry_price=Decimal("50000"),
            ...     leverage=5,
            ...     side="long",
            ...     symbol="BTCUSDT"
            ... )
            Decimal("40200.00")  # -19.6% from entry
        """
        # Determine MMR: explicit > symbol-specific > default
        if maintenance_margin_rate is None:
            if symbol:
                mmr = self.get_mmr_for_symbol(symbol)
            else:
                mmr = self.default_mmr
        else:
            mmr = maintenance_margin_rate

        leverage_factor = Decimal("1") / Decimal(str(leverage))

        if side.lower() in ("long", "buy"):
            # Long liquidation: entry * (1 - 1/leverage + mmr)
            liq_price = entry_price * (
                Decimal("1") - leverage_factor + mmr
            )
        else:
            # Short liquidation: entry * (1 + 1/leverage - mmr)
            liq_price = entry_price * (
                Decimal("1") + leverage_factor - mmr
            )

        return liq_price.quantize(Decimal("0.01"))

    def check_margin_health(
        self,
        account_balance: Decimal,
        maintenance_margin: Decimal,
        unrealized_pnl: Decimal,
    ) -> Dict[str, Any]:
        """
        Check margin health and determine action.

        Margin ratio = (balance + unrealized_pnl) / maintenance_margin

        Actions:
        - margin_ratio > buffer: OK
        - margin_ratio < buffer: WARNING
        - margin_ratio < 1.0: LIQUIDATION IMMINENT

        Args:
            account_balance: Account balance
            maintenance_margin: Required maintenance margin
            unrealized_pnl: Current unrealized P&L

        Returns:
            Dict with action, margin_ratio, and reason
        """
        if maintenance_margin == 0:
            return {
                "action": "ok",
                "margin_ratio": None,
                "reason": "No open positions",
            }

        equity = account_balance + unrealized_pnl
        margin_ratio = equity / maintenance_margin

        logger.debug(
            f"Margin check | "
            f"balance={account_balance} | "
            f"unrealized_pnl={unrealized_pnl} | "
            f"equity={equity} | "
            f"maintenance={maintenance_margin} | "
            f"ratio={margin_ratio}"
        )

        if margin_ratio < Decimal("1.0"):
            # Critical: Liquidation imminent
            logger.critical(
                f"LIQUIDATION IMMINENT | "
                f"margin_ratio={margin_ratio} | "
                f"equity={equity} | "
                f"maintenance={maintenance_margin}"
            )
            return {
                "action": "liquidate_all",
                "margin_ratio": margin_ratio,
                "reason": "Margin ratio below 1.0 - liquidation imminent",
            }

        elif margin_ratio < (Decimal("1.0") + self.liquidation_buffer):
            # Warning: Too close to liquidation
            logger.warning(
                f"Low margin ratio | "
                f"margin_ratio={margin_ratio} | "
                f"buffer={self.liquidation_buffer}"
            )
            return {
                "action": "reduce_position",
                "margin_ratio": margin_ratio,
                "reason": f"Margin ratio below safe buffer ({self.liquidation_buffer})",
            }

        else:
            # Healthy margin
            return {"action": "ok", "margin_ratio": margin_ratio, "reason": "Margin healthy"}

    def validate_position_with_leverage(
        self, balance: Decimal, price: Decimal, size: Decimal, leverage: int
    ) -> RiskCheckResult:
        """
        Validate position size considering leverage.

        With leverage, notional value can exceed balance:
        - notional = price * size
        - required_margin = notional / leverage
        - max_allowed = balance * leverage

        Args:
            balance: Account balance
            price: Entry price
            size: Position size
            leverage: Leverage multiplier

        Returns:
            RiskCheckResult
        """
        notional = price * size
        required_margin = notional / Decimal(str(leverage))
        max_allowed_notional = balance * Decimal(str(leverage))

        logger.debug(
            f"Position validation | "
            f"notional={notional} | "
            f"required_margin={required_margin} | "
            f"balance={balance} | "
            f"leverage={leverage} | "
            f"max_allowed={max_allowed_notional}"
        )

        # Check against absolute position limit (NON-NEGOTIABLE)
        if notional > self.max_position_usd:
            return RiskCheckResult(
                passed=False,
                reason=f"Position size ${notional} exceeds hard limit "
                f"${self.max_position_usd} (NON-NEGOTIABLE)",
            )

        # Check if we have enough margin
        if required_margin > balance:
            return RiskCheckResult(
                passed=False,
                reason=f"Insufficient margin: need ${required_margin}, have ${balance}",
            )

        # Check leverage doesn't push us too far
        if notional > max_allowed_notional:
            return RiskCheckResult(
                passed=False,
                reason=f"Position ${notional} exceeds {leverage}x leverage limit "
                f"of ${max_allowed_notional}",
            )

        return RiskCheckResult(passed=True)

    def can_open_position(
        self,
        balance: Decimal,
        price: Decimal,
        size: Decimal,
        leverage: int,
        current_pnl: Optional[Decimal] = None,
        peak_equity: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """
        Comprehensive pre-trade risk check.

        Checks:
        1. Leverage within limits
        2. Position size valid
        3. Daily loss limit not breached
        4. Drawdown limit not breached (if peak_equity provided)
        5. Kill switch not active

        Args:
            balance: Account balance
            price: Entry price
            size: Position size
            leverage: Leverage
            current_pnl: Daily P&L (optional)
            peak_equity: Peak equity for DD calc (optional)

        Returns:
            Dict with 'allowed' bool and 'reason' string
        """
        # Check kill switch
        if self.kill_switch_active:
            return {
                "allowed": False,
                "reason": "Kill switch active - all trading disabled",
            }

        # Validate leverage
        lev_check = self.validate_leverage(leverage)
        if not lev_check.passed:
            return {"allowed": False, "reason": lev_check.reason}

        # Validate position size
        size_check = self.validate_position_with_leverage(balance, price, size, leverage)
        if not size_check.passed:
            return {"allowed": False, "reason": size_check.reason}

        # Check daily loss limit
        if current_pnl is not None:
            if current_pnl < -self.max_daily_loss:
                self.trigger_kill_switch("Daily loss limit breached")
                return {
                    "allowed": False,
                    "reason": f"Daily loss ${abs(current_pnl)} exceeds limit ${self.max_daily_loss}",
                }

        # Check drawdown limit (using max_daily_loss as max drawdown for now)
        if peak_equity is not None and balance is not None:
            current_equity = balance + (current_pnl or Decimal("0"))
            drawdown = peak_equity - current_equity

            if drawdown > self.max_daily_loss:
                self.trigger_kill_switch("Max drawdown breached")
                return {
                    "allowed": False,
                    "reason": f"Drawdown ${drawdown} exceeds limit ${self.max_daily_loss}",
                }

        # All checks passed
        return {"allowed": True, "reason": "All risk checks passed"}

    def trigger_kill_switch(self, reason: str):
        """
        Emergency shutdown of all trading.

        Args:
            reason: Reason for kill switch activation
        """
        logger.critical(f"KILL SWITCH TRIGGERED | reason={reason}")
        self.kill_switch_active = True
        # Note: Position flattening handled by PositionManager._emergency_close_all()
        # Future enhancements: Cancel open orders, send MCP alerts (GitHub issue #TBD)
