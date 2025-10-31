# Broker Testing Guide

Complete guide to testing the Breakout Detector strategy with real broker APIs (Binance.us and Kraken Futures).

## Overview

This guide covers:
1. **Connectivity testing** - Verify API credentials and connection
2. **Authentication testing** - Confirm API keys work correctly
3. **Balance retrieval** - Read account balances (read-only, safe)
4. **Strategy integration** - Test breakout detector with real broker interfaces
5. **Order placement** - Test trades (Kraken demo only)

## Test Suite: `test_brokers_connectivity.py`

Located at: `examples/test_brokers_connectivity.py`

**Features**:
- ✅ Safe read-only operations by default
- ✅ Tests both Binance.us and Kraken Futures
- ✅ Graceful handling of missing credentials
- ✅ Clear success/failure reporting
- ✅ Breakout detector integration verification
- ✅ Optional order placement testing (Kraken demo only)

## Quick Start

### 1. Test Without Credentials (Safe)

```bash
PYTHONPATH=src python examples/test_brokers_connectivity.py
```

**Result**: Shows which credentials are missing and provides setup instructions.

### 2. Test Specific Broker

```bash
# Test only Binance.us
PYTHONPATH=src python examples/test_brokers_connectivity.py --broker binance

# Test only Kraken
PYTHONPATH=src python examples/test_brokers_connectivity.py --broker kraken
```

### 3. Test with Order Placement (Kraken Demo Only)

```bash
PYTHONPATH=src python examples/test_brokers_connectivity.py --broker kraken --enable-orders
```

**⚠️ WARNING**: This places real orders in Kraken's demo environment (no real money, but tests actual order flow).

---

## Binance.us Setup

### About Binance.us
- **Type**: Spot trading only (LONG positions only, no shorting)
- **Testnet**: ❌ NOT AVAILABLE
- **Recommendation**: Test with small amounts or use SimulatedBroker first

### Getting API Keys

1. **Create Account**: https://www.binance.us/
2. **Verify Identity**: Complete KYC (required for trading)
3. **Generate API Keys**:
   - Go to: Account → API Management
   - Create New Key
   - **Enable**: "Enable Reading" (required)
   - **Enable**: "Enable Spot & Margin Trading" (required for orders)
   - **Disable**: "Enable Withdrawals" (for safety)
4. **Save Credentials**: Copy API Key and Secret (shown only once!)

### Set Environment Variables

```bash
# Add to ~/.bashrc or ~/.zshrc for persistence
export BINANCE_US_API_KEY="your_actual_api_key_here"
export BINANCE_US_API_SECRET="your_actual_api_secret_here"

# Or set temporarily for current session
export BINANCE_US_API_KEY="..."
export BINANCE_US_API_SECRET="..."
```

### Test Connection

```bash
PYTHONPATH=src python examples/test_brokers_connectivity.py --broker binance
```

**Expected Output** (with valid credentials):
```
✅ Credentials found
✅ Broker initialized successfully
✅ Authentication successful
✅ Balance retrieved: $XXX.XX USDT
✅ Breakout detector integration successful
```

### Safety Notes for Binance.us

⚠️ **IMPORTANT**:
- **No testnet** - All API calls go to production
- **Start small** - Test with minimal balances first
- **Use SimulatedBroker** - Test strategy logic before live trading
- **Set IP restrictions** - Limit API key to your IP address
- **Disable withdrawals** - Keep withdrawal permission OFF
- **Monitor closely** - Watch all trades carefully

### Common Binance.us Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Invalid API key` | Wrong key or typo | Double-check environment variables |
| `Signature invalid` | Wrong secret or clock skew | Verify secret, check system time |
| `IP not whitelisted` | IP restrictions enabled | Add your IP or disable restriction |
| `Insufficient balance` | Not enough USDT | Deposit funds or reduce position size |
| `MIN_NOTIONAL` | Order too small | Increase position size (min ~$10) |

---

## Kraken Futures Setup

### About Kraken Futures
- **Type**: Perpetual futures (supports LONG and SHORT)
- **Testnet**: ✅ **DEMO ENVIRONMENT AVAILABLE**
- **Recommendation**: Always test with demo first

### Getting Demo Credentials (SAFE)

1. **Access Demo**: https://demo-futures.kraken.com/
2. **Create Demo Account**: No KYC required, instant access
3. **Get Demo Funds**: Account starts with $10,000 demo balance
4. **Generate API Keys**:
   - Go to: Settings → API
   - Create New Key
   - **Enable**: All permissions (it's demo, no risk)
   - Save credentials

### Set Demo Environment Variables

```bash
# Add to ~/.bashrc or ~/.zshrc
export KRAKEN_DEMO_API_KEY="your_demo_api_key"
export KRAKEN_DEMO_API_SECRET="your_demo_api_secret"

# Or set temporarily
export KRAKEN_DEMO_API_KEY="..."
export KRAKEN_DEMO_API_SECRET="..."
```

### Test Connection

```bash
# Test connectivity only (no orders)
PYTHONPATH=src python examples/test_brokers_connectivity.py --broker kraken

# Test with order placement (DEMO - safe)
PYTHONPATH=src python examples/test_brokers_connectivity.py --broker kraken --enable-orders
```

**Expected Output** (with valid credentials):
```
✅ Credentials found
✅ Broker initialized successfully (DEMO)
✅ Authentication successful
✅ Balance retrieved: $10000.00 (demo)
✅ Breakout detector integration successful
✅ Order placed successfully: ORDER_ID (demo)
```

### Getting Production Credentials (REAL MONEY)

⚠️ **ONLY AFTER SUCCESSFUL DEMO TESTING**

1. **Create Account**: https://futures.kraken.com/
2. **Verify Identity**: Complete KYC
3. **Deposit Funds**: Transfer from Kraken spot account
4. **Generate API Keys**: Same process as demo

### Set Production Environment Variables

```bash
# Production (REAL MONEY - BE CAREFUL!)
export KRAKEN_API_KEY="your_production_api_key"
export KRAKEN_API_SECRET="your_production_api_secret"
```

### Safety Notes for Kraken

✅ **RECOMMENDED WORKFLOW**:
1. Test with **demo** environment first (set `demo=True`)
2. Run strategy for 30+ days in demo
3. Verify win rate >50% and profit factor >1.0
4. Only then consider production with small capital

⚠️ **PRODUCTION SAFETY**:
- **Start tiny** - $100-500 max for first week
- **Set strict limits** - Max position size, daily loss limits
- **Monitor 24/7** - Futures trade around the clock
- **Use stop losses** - Always set SL on every position
- **Paper trade first** - 60 days minimum (per project roadmap)

---

## Test Workflow

### Phase 1: Connectivity Testing (SAFE)

Test broker connections without placing orders:

```bash
# Test all brokers (read-only, safe)
PYTHONPATH=src python examples/test_brokers_connectivity.py

# Test specific broker
PYTHONPATH=src python examples/test_brokers_connectivity.py --broker binance
PYTHONPATH=src python examples/test_brokers_connectivity.py --broker kraken
```

**What's tested**:
- ✅ API credentials valid
- ✅ Connection successful
- ✅ Authentication working
- ✅ Balance retrieval (read-only)
- ✅ Breakout detector integration

**Risk**: ✅ **ZERO** - No orders placed, read-only operations

### Phase 2: Simulated Trading

Test strategy logic with simulated broker:

```bash
PYTHONPATH=src python examples/test_breakout_simple.py
PYTHONPATH=src python examples/test_breakout_with_binance_us.py
```

**What's tested**:
- ✅ Strategy signal generation
- ✅ Order placement logic
- ✅ Position sizing
- ✅ Stop loss / take profit calculations

**Risk**: ✅ **ZERO** - Uses SimulatedBroker, no real trades

### Phase 3: Demo Environment (Kraken Only)

Test with real broker in demo mode:

```bash
PYTHONPATH=src python examples/test_brokers_connectivity.py --broker kraken --enable-orders
```

**What's tested**:
- ✅ Real API order flow
- ✅ Order execution
- ✅ Position tracking
- ✅ Error handling

**Risk**: ✅ **ZERO** - Demo funds only, no real money

### Phase 4: Production (EXTREME CAUTION)

⚠️ **ONLY AFTER**:
- ✅ 60+ days successful demo trading (Kraken)
- ✅ Win rate >50%
- ✅ Profit factor >1.0
- ✅ Drawdown acceptable
- ✅ All risk limits tested

**NOT COVERED IN THIS GUIDE** - Requires additional production readiness:
- Live monitoring dashboard
- Alert systems
- Kill switch tested
- Risk limits enforced
- Capital allocation strategy

---

## Understanding Test Output

### Successful Test Example

```
================================================================================
🔌 Broker Connectivity & Integration Test Suite
================================================================================

🧪 Testing Binance.us Spot Broker
================================================================================
✅ Credentials found
✅ Broker initialized successfully
✅ Authentication successful
✅ Balance retrieved: $1,234.56 USDT
✅ Breakout detector integration successful

📊 Binance.us Test Summary:
   Credentials: ✅
   Connection: ✅
   Authentication: ✅
   Balance: ✅
   USDT Balance: $1234.56

================================================================================
📊 Final Test Summary
================================================================================

Binance.us Spot:
   Status: ✅ PASSED
   Connection: ✅
   Authentication: ✅
   Balance: $1234.56

✅ ALL TESTS PASSED

Brokers are ready for use with breakout detector strategy!
```

### Missing Credentials Example

```
❌ Binance.us credentials not found
   Set BINANCE_US_API_KEY and BINANCE_US_API_SECRET to test

❌ Kraken demo credentials not found
   Set KRAKEN_DEMO_API_KEY and KRAKEN_DEMO_API_SECRET to test
   Get demo credentials at: https://demo-futures.kraken.com/

================================================================================
❌ NO CREDENTIALS FOUND
================================================================================

Set environment variables to test broker connectivity:

Binance.us:
  export BINANCE_US_API_KEY='your_key'
  export BINANCE_US_API_SECRET='your_secret'

Kraken Futures Demo:
  export KRAKEN_DEMO_API_KEY='your_demo_key'
  export KRAKEN_DEMO_API_SECRET='your_demo_secret'
```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'requests'"

**Solution**:
```bash
.venv/bin/pip install requests
```

### "Invalid API key"

**Causes**:
1. Wrong API key copied
2. Typo in environment variable
3. API key deleted/regenerated on exchange

**Solution**:
- Verify environment variables: `echo $BINANCE_US_API_KEY`
- Check for extra spaces or newlines
- Regenerate API key on exchange

### "Signature invalid"

**Causes**:
1. Wrong API secret
2. System clock out of sync
3. Different secret between spot/futures

**Solution**:
- Verify secret is correct
- Sync system clock: `sudo ntpdate -s time.nist.gov` (Mac/Linux)
- Regenerate API keys if needed

### "IP not whitelisted"

**Cause**: API key restricted to specific IP addresses

**Solution**:
- Check your current IP: `curl ifconfig.me`
- Add IP to whitelist on exchange
- Or remove IP restrictions (less secure)

### "Insufficient balance"

**Cause**: Not enough USDT/USD for trade

**Solution**:
- Deposit funds
- Reduce position size in strategy config
- Check minimum notional requirements

### Test passes but no signals generated

**This is normal!** The connectivity test only processes 10 bars, which isn't enough for signal generation. This proves:
- ✅ Broker connection works
- ✅ Strategy integration works
- ✅ No errors in the flow

To generate signals, use the full integration tests with 30+ bars.

---

## Integration with Breakout Detector

### Code Example: Binance.us

```python
from decimal import Decimal
from trade_engine.adapters.brokers.binance_us import BinanceUSSpotBroker
from trade_engine.domain.strategies.alpha_breakout_detector import (
    BreakoutSetupDetector,
    BreakoutConfig
)

# Initialize broker (requires env vars set)
broker = BinanceUSSpotBroker()

# Initialize strategy
config = BreakoutConfig(
    volume_spike_threshold=Decimal("2.0"),
    position_size_usd=Decimal("100")  # Small for testing
)
strategy = BreakoutSetupDetector(symbol="BTCUSDT", config=config)

# Process market data and execute signals
for bar in market_data:
    signals = strategy.on_bar(bar)

    for signal in signals:
        if signal.side == "buy":
            # Execute order
            order_id = broker.buy(
                symbol=signal.symbol,
                qty=signal.qty,
                sl=signal.sl,
                tp=signal.tp
            )
            print(f"Order placed: {order_id}")
```

### Code Example: Kraken Demo

```python
from decimal import Decimal
from trade_engine.adapters.brokers.kraken import KrakenFuturesBroker
from trade_engine.domain.strategies.alpha_breakout_detector import (
    BreakoutSetupDetector,
    BreakoutConfig
)

# Initialize broker in DEMO mode (safe)
broker = KrakenFuturesBroker(demo=True)

# Initialize strategy
config = BreakoutConfig(
    volume_spike_threshold=Decimal("2.0"),
    position_size_usd=Decimal("100")
)
strategy = BreakoutSetupDetector(symbol="PF_XBTUSD", config=config)

# Process market data and execute signals
for bar in market_data:
    signals = strategy.on_bar(bar)

    for signal in signals:
        # Execute order (demo environment)
        if signal.side == "buy":
            order_id = broker.buy(
                symbol=signal.symbol,
                qty=signal.qty,
                sl=signal.sl,
                tp=signal.tp
            )
        elif signal.side == "sell":
            order_id = broker.sell(
                symbol=signal.symbol,
                qty=signal.qty,
                sl=signal.sl,
                tp=signal.tp
            )

        print(f"Demo order placed: {order_id}")
```

---

## Next Steps

After successful connectivity testing:

1. **Run Full Integration Tests**:
   ```bash
   PYTHONPATH=src python examples/test_breakout_simple.py
   PYTHONPATH=src python examples/test_breakout_with_binance_us.py
   ```

2. **Backtest Strategy**:
   - Use historical data
   - Validate strategy performance
   - Optimize parameters

3. **Paper Trade (Kraken Demo)**:
   - Run for 60+ days
   - Track all trades
   - Calculate performance metrics

4. **Live Trading Preparation**:
   - Set up monitoring
   - Configure alerts
   - Test kill switch
   - Define risk limits

5. **Production (Micro-Capital)**:
   - Start with $100-500
   - Run for 30 days
   - Verify profitability
   - Scale gradually

---

## Security Best Practices

### API Key Security

✅ **DO**:
- Use environment variables for keys
- Add keys to `.gitignore` (never commit)
- Set IP whitelist restrictions
- Disable withdrawal permissions
- Rotate keys periodically (every 90 days)
- Use separate keys for testing vs production

❌ **DON'T**:
- Hard-code keys in source files
- Share keys in chat/email
- Use production keys for testing
- Grant unnecessary permissions
- Store keys in plain text files

### Testing Security

✅ **DO**:
- Start with read-only operations
- Test with demo environments
- Use small position sizes initially
- Monitor all test trades
- Keep test credentials separate

❌ **DON'T**:
- Skip testing phases
- Test with large amounts
- Leave tests running unmonitored
- Mix demo and production credentials

---

## Summary

This testing guide provides:
- ✅ Safe broker connectivity testing
- ✅ Support for Binance.us (production) and Kraken (demo)
- ✅ Read-only operations by default
- ✅ Clear success/failure reporting
- ✅ Breakout detector integration verification
- ✅ Optional order testing (Kraken demo only)

**Current Status**:
- ✅ Test suite implemented: `test_brokers_connectivity.py`
- ✅ Handles missing credentials gracefully
- ✅ Tests both Binance.us and Kraken
- ✅ Integrates with breakout detector strategy
- ✅ Comprehensive documentation provided

**To Run Tests**:
```bash
# Without credentials (shows setup instructions)
PYTHONPATH=src python examples/test_brokers_connectivity.py

# With credentials (actual testing)
export BINANCE_US_API_KEY="..."
export BINANCE_US_API_SECRET="..."
PYTHONPATH=src python examples/test_brokers_connectivity.py --broker binance
```

The broker integration is **ready for testing** once you provide API credentials!
