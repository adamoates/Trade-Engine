# Broker Integration

This directory contains documentation for exchange connectivity and broker integrations.

## <æ Supported Brokers

The Trade Engine supports multiple exchanges across different asset classes:

### Cryptocurrency Futures
- **Binance Futures** - Primary L2 data feed, full long/short functionality
- **Kraken Futures** - US-accessible futures trading (recommended for US traders)

### Cryptocurrency Spot
- **Binance.us** - US-only spot trading (long-only mode, no shorting available)

## =Ë Available Documentation

### Current
- [Broker Comparison](comparison.md) - Feature comparison across all supported brokers
- [Broker Testing](testing.md) - Integration testing guide for broker adapters

### Coming Soon
- Kraken Futures Guide - Complete setup and usage guide
- Binance Futures Guide - Advanced features and optimization
- Binance.us Guide - US-compliant spot trading

## = Related Documentation

- [Broker Interface Specification](../reference/adapters/broker-interface.md) - Technical adapter interface
- [How to Add Brokers](../reference/adapters/how-to-add-adapters.md) - Implementation guide
- [Spot-Only Trading](../strategies/spot-only-trading.md) - Long-only mode for spot markets

## =¡ Quick Reference

### Choosing a Broker

**For US Traders**:
- Futures trading ’ **Kraken Futures** (US-accessible, full leverage)
- Spot trading ’ **Binance.us** (long-only, no shorts)

**For International Traders**:
- Primary ’ **Binance Futures** (best liquidity, lowest fees)
- Backup ’ **Kraken Futures** (alternative with good reliability)

### Key Differences

| Feature | Binance Futures | Kraken Futures | Binance.us |
|---------|----------------|----------------|------------|
| US Access | L No |  Yes |  Yes |
| Short Selling |  Yes |  Yes | L No |
| Max Leverage | 125x | 50x | N/A |
| L2 Data |  Yes |  Yes |  Yes |
| Funding Rates |  Yes |  Yes | L No |

---

**Last Updated**: 2025-10-31
