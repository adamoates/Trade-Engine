"""
Generate realistic Options and L2 data from historical OHLCV data.

This utility creates realistic market microstructure fixtures based on
actual historical price movements from Binance data.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def calculate_pcr_from_price_action(
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: float
) -> tuple[float, float]:
    """
    Estimate Put-Call Ratio based on price action.

    Logic:
    - Strong down days (close << open_price) -> high PCR (fear)
    - Strong up days (close >> open_price) -> low PCR (greed)
    - High volatility (wide range) -> higher PCR
    - Low volume -> neutral PCR

    Returns:
        (put_call_ratio, implied_volatility)
    """
    # Calculate price change percentage
    price_change_pct = ((close - open_price) / open_price) * 100

    # Calculate range (volatility proxy)
    range_pct = ((high - low) / open_price) * 100

    # Base PCR starts at neutral (1.0)
    pcr = 1.0

    # Adjust for price direction
    if price_change_pct < -5:  # Big down day
        pcr += abs(price_change_pct) / 10  # PCR increases with fear
    elif price_change_pct > 5:  # Big up day
        pcr -= price_change_pct / 15  # PCR decreases with greed

    # Adjust for volatility (higher volatility = more uncertainty = higher PCR)
    if range_pct > 10:
        pcr += (range_pct - 10) / 20

    # Clamp PCR to realistic bounds
    pcr = max(0.2, min(3.0, pcr))

    # Calculate implied volatility (correlates with range)
    iv = 0.4 + (range_pct / 30)  # Base 40% + range factor
    iv = max(0.2, min(1.5, iv))

    return pcr, iv


def generate_l2_from_price(
    price: float,
    volume: float,
    volatility: float,
    pcr: float
) -> Dict:
    """
    Generate realistic Level 2 order book from price context.

    Args:
        price: Current market price
        volume: Trading volume (affects liquidity)
        volatility: Price volatility (affects spread)
        pcr: Put-Call Ratio (affects order book imbalance)

    Returns:
        L2 snapshot with bids/asks
    """
    # Spread widens with volatility, tightens with volume
    spread_bps = (volatility * 15) / max(1, volume / 10)
    spread_bps = max(5, min(50, spread_bps))
    spread = price * (spread_bps / 10000)

    # Determine order book imbalance from PCR
    # High PCR (fear) = more sell pressure (thinner bids, thicker asks)
    # Low PCR (greed) = more buy pressure (thicker bids, thinner asks)
    if pcr > 1.3:  # Bearish
        bid_multiplier = 0.7
        ask_multiplier = 1.3
    elif pcr < 0.7:  # Bullish
        bid_multiplier = 1.3
        ask_multiplier = 0.7
    else:  # Neutral
        bid_multiplier = 1.0
        ask_multiplier = 1.0

    # Generate 10 levels on each side
    bids = []
    asks = []

    best_bid = price - (spread / 2)
    best_ask = price + (spread / 2)

    base_quantity = volume / 50  # Base liquidity from volume

    for i in range(10):
        # Bids (descending price)
        bid_price = best_bid - (i * spread * 0.5)
        bid_qty = base_quantity * (1 + i * 0.1) * bid_multiplier
        bids.append({
            "price": round(bid_price, 2),
            "quantity": round(bid_qty, 4),
            "order_count": max(3, int(bid_qty * 5))
        })

        # Asks (ascending price)
        ask_price = best_ask + (i * spread * 0.5)
        ask_qty = base_quantity * (1 + i * 0.1) * ask_multiplier
        asks.append({
            "price": round(ask_price, 2),
            "quantity": round(ask_qty, 4),
            "order_count": max(3, int(ask_qty * 5))
        })

    return {
        "bids": bids,
        "asks": asks
    }


def generate_fixtures_from_ohlcv(ohlcv_file: Path):
    """Generate Options and L2 fixtures from OHLCV data."""

    with open(ohlcv_file) as f:
        data = json.load(f)

    metadata = data["metadata"]
    candles = data["data"]

    fixtures_dir = ohlcv_file.parent
    symbol = metadata["symbol"].replace("USDT", "")

    # Find interesting candles for fixtures
    scenarios = []

    for i, candle in enumerate(candles):
        timestamp_ms = candle["timestamp"]
        timestamp = datetime.fromtimestamp(timestamp_ms / 1000)

        open_price = candle["open"]
        high = candle["high"]
        low = candle["low"]
        close = candle["close"]
        volume = candle["volume"]

        price_change = ((close - open_price) / open_price) * 100
        range_pct = ((high - low) / open_price) * 100

        # Identify interesting scenarios
        scenario_type = None
        if price_change < -5 and range_pct > 8:
            scenario_type = "extreme_fear"
        elif price_change > 5 and range_pct > 6:
            scenario_type = "extreme_greed"
        elif volume < 5 and range_pct < 2:
            scenario_type = "low_liquidity"
        elif range_pct > 10:
            scenario_type = "high_volatility"

        if scenario_type:
            scenarios.append({
                "type": scenario_type,
                "timestamp": timestamp,
                "candle": candle,
                "index": i
            })

    # Generate fixtures for each scenario type (max 2 per type)
    scenario_counts = {}

    for scenario in scenarios:
        stype = scenario["type"]

        # Limit to 2 fixtures per scenario type
        if scenario_counts.get(stype, 0) >= 2:
            continue

        scenario_counts[stype] = scenario_counts.get(stype, 0) + 1

        candle = scenario["candle"]
        timestamp = scenario["timestamp"]

        # Calculate PCR and IV
        pcr, iv = calculate_pcr_from_price_action(
            candle["open"],
            candle["high"],
            candle["low"],
            candle["close"],
            candle["volume"]
        )

        # Generate Options data
        options_data = {
            "symbol": symbol,
            "timestamp": timestamp.isoformat() + "Z",
            "description": f"Historical {stype.replace('_', ' ')} from {timestamp.strftime('%Y-%m-%d')}",
            "put_volume": round(10000 * pcr, 1),
            "call_volume": 10000.0,
            "put_call_ratio": round(pcr, 3),
            "put_open_interest": round(50000 * pcr, 1),
            "call_open_interest": 50000.0,
            "total_open_interest": round(50000 * (1 + pcr), 1),
            "implied_volatility": round(iv, 2),
            "iv_rank": round(min(99, iv * 100), 1),
            "max_pain": round(candle["close"] * 0.95, 2),
            "gamma_exposure": round((pcr - 1) * 100000000, 0)
        }

        # Generate L2 data
        l2_data = generate_l2_from_price(
            candle["close"],
            candle["volume"],
            (candle["high"] - candle["low"]) / candle["open"],
            pcr
        )
        l2_data.update({
            "symbol": symbol,
            "timestamp": timestamp.isoformat() + "Z",
            "description": f"Historical {stype.replace('_', ' ')} from {timestamp.strftime('%Y-%m-%d')}"
        })

        # Save fixtures
        date_str = timestamp.strftime("%Y_%m_%d")

        options_file = fixtures_dir / f"options_data/{symbol.lower()}_{stype}_{date_str}.json"
        options_file.parent.mkdir(exist_ok=True)
        with open(options_file, 'w') as f:
            json.dump(options_data, f, indent=2)

        l2_file = fixtures_dir / f"l2_data/{symbol.lower()}_{stype}_{date_str}.json"
        l2_file.parent.mkdir(exist_ok=True)
        with open(l2_file, 'w') as f:
            json.dump(l2_data, f, indent=2)

        print(f"Generated {stype} fixtures for {timestamp.strftime('%Y-%m-%d')}")


if __name__ == "__main__":
    # Generate from existing OHLCV data
    fixtures_dir = Path(__file__).parent
    ohlcv_file = fixtures_dir / "btc_usdt_binance_1d_sample.json"

    if ohlcv_file.exists():
        print(f"Generating realistic fixtures from {ohlcv_file}")
        generate_fixtures_from_ohlcv(ohlcv_file)
        print("Done!")
    else:
        print(f"OHLCV file not found: {ohlcv_file}")
