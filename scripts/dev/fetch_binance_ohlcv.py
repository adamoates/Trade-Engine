#!/usr/bin/env python3
# tools/fetch_binance_ohlcv.py
# Fetch OHLCV from Binance Spot or Futures (no API key), with pagination, resume, progress, and stdout piping.
# Example:
#   python tools/fetch_binance_ohlcv.py --market futures --symbol BTCUSDT --interval 15m \
#     --start 2025-07-01 --end 2025-10-23 --out data/ohlcv/binance_futures_btcusdt_15m.csv
#   python tools/fetch_binance_ohlcv.py --market spot --symbol BTCUSDT --interval 5m --days 30 --stdout \
#     | python tools/validate_clean_ohlcv.py /dev/stdin --out data/clean/btc_usdt_5m_30d_clean.csv

import argparse, csv, sys, time, math, random
from pathlib import Path
from datetime import datetime, timezone, timedelta
import requests

# ---- Config ----
USER_AGENT = "MFT-Downloader/1.0 (+binance klines; no-key)"
# conservative pacing: target ~150 req/min (well below 1200/min public limit)
BASE_SLEEP = 0.40  # seconds between calls (adaptive backoff will add more on 429)
MAX_RETRY = 5
TIMEOUT   = 20

SPOT_BASE    = "https://api.binance.com"
FUTURES_BASE = "https://fapi.binance.com"   # USDⓈ-M (perpetual) futures

INTERVALS = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "8h": 28800, "12h": 43200,
    "1d": 86400, "3d": 259200, "1w": 604800, "1M": 2592000
}

def parse_ts(s: str | None) -> int | None:
    if not s: return None
    # Accept YYYY-MM-DD or ISO8601
    try:
        dt = datetime.fromisoformat(s.replace("Z","+00:00"))
    except ValueError:
        dt = datetime.strptime(s, "%Y-%m-%d")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)

def now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)

def clamp_symbol(sym: str) -> str:
    # Allow "BTC/USDT" or "BTCUSDT"
    return sym.replace("/", "").upper()

def infer_next_from_csv(path: Path) -> int | None:
    # Resume by reading last line's open_time (ms)
    if not path.exists() or path.stat().st_size == 0:
        return None
    last = None
    with path.open("r", newline="") as f:
        for row in csv.DictReader(f):
            last = row
    if last and "open_time" in last:
        try:
            return int(last["open_time"])
        except Exception:
            return None
    return None

def sleep_with_jitter(base: float):
    time.sleep(base + random.uniform(0, base*0.25))

def request_klines(base_url: str, endpoint: str, params: dict):
    url = base_url + endpoint
    headers = {"User-Agent": USER_AGENT}
    backoff = BASE_SLEEP
    for attempt in range(1, MAX_RETRY+1):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json(), r
            if r.status_code in (418, 429):  # rate limited / banned
                sleep_with_jitter(backoff * attempt)
                continue
            if r.status_code >= 500:
                sleep_with_jitter(backoff * attempt)
                continue
            # Non-retryable
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:
            if attempt == MAX_RETRY:
                raise
            sleep_with_jitter(backoff * attempt)
    raise RuntimeError("Unreachable")

def yield_klines(market: str, symbol: str, interval: str,
                 start_ms: int, end_ms: int | None, limit: int = 1000):
    """
    Yields kline arrays: [open_time, open, high, low, close, volume, close_time, qav, num_trades, tbbav, tbqav, ignore]
    """
    base = FUTURES_BASE if market == "futures" else SPOT_BASE
    endpoint = "/fapi/v1/klines" if market == "futures" else "/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
        "startTime": start_ms
    }
    if end_ms:
        params["endTime"] = end_ms

    # pagination loop
    while True:
        data, resp = request_klines(base, endpoint, params)
        if not isinstance(data, list) or len(data) == 0:
            break
        for row in data:
            yield row
        # advance startTime to next candle
        last_open = int(data[-1][0])
        # if we've reached or passed end, stop
        if end_ms and last_open >= end_ms:
            break
        # next page start is last_close_time + 1ms (or last_open + interval*1000)
        step = INTERVALS[interval] * 1000
        params["startTime"] = last_open + step
        # be nice to the API
        sleep_with_jitter(BASE_SLEEP)

def write_header_if_needed(writer: csv.writer, wrote_header: bool, out_to_file: bool):
    # when writing to stdout, we must write header explicitly once
    # when appending to an existing CSV, assume header already exists
    if not wrote_header and not out_to_file:
        writer.writerow(["open_time","open","high","low","close","volume","close_time","qav","num_trades","tbbav","tbqav"])
        return True
    return wrote_header

def main():
    ap = argparse.ArgumentParser(
        description="Fetch OHLCV from Binance Spot/Futures (no key), with pagination, resume, and progress bar."
    )
    ap.add_argument("--market", choices=["spot","futures"], default="spot", help="spot or futures (USDT perpetual)")
    ap.add_argument("--symbol", required=True, help="e.g., BTCUSDT or BTC/USDT")
    ap.add_argument("--interval", required=True, choices=list(INTERVALS.keys()), help="kline interval")
    ap.add_argument("--start", help="UTC start date (YYYY-MM-DD or ISO8601). Mutually exclusive with --days/--hours.")
    ap.add_argument("--end", help="UTC end date (YYYY-MM-DD or ISO8601). Default: now")
    ap.add_argument("--days", type=int, help="Fetch this many days back from now")
    ap.add_argument("--hours", type=int, help="Fetch this many hours back from now")
    ap.add_argument("--out", type=Path, help="Output CSV path (creates/append). Use --stdout to stream to stdout.")
    ap.add_argument("--stdout", action="store_true", help="Write CSV rows to stdout (pipe to validator).")
    ap.add_argument("--resume", action="store_true", help="Resume from --out last open_time if file exists.")
    ap.add_argument("--limit", type=int, default=1000, help="Max candles per request (<=1000).")
    ap.add_argument("--progress", action="store_true", help="Show simple textual progress.")
    ap.add_argument("--domain", default=None, help="Override domain (e.g., https://api.binance.us)")
    args = ap.parse_args()

    if not args.out and not args.stdout:
        ap.error("Provide --out or --stdout.")

    symbol = clamp_symbol(args.symbol)
    if args.limit > 1000: args.limit = 1000

    # Domain override (e.g., Binance.US)
    global SPOT_BASE, FUTURES_BASE
    if args.domain:
        # If custom domain is given, apply to both (user likely knows what they're doing)
        SPOT_BASE = args.domain.rstrip("/")
        FUTURES_BASE = args.domain.rstrip("/")

    # Determine time window
    end_ms = parse_ts(args.end) if args.end else now_ms()
    if args.days:
        start_ms = end_ms - args.days*86400*1000
    elif args.hours:
        start_ms = end_ms - args.hours*3600*1000
    elif args.start:
        start_ms = parse_ts(args.start)
    else:
        ap.error("Provide one of --start, --days, or --hours.")

    # Resume logic (only when writing to a file)
    if args.resume and args.out and args.out.exists():
        last_ms = infer_next_from_csv(args.out)
        if last_ms is not None:
            # jump forward by one interval to avoid duplicate last row
            start_ms = max(start_ms, last_ms + INTERVALS[args.interval]*1000)

    # Writer setup
    out_to_file = bool(args.out and not args.stdout)
    if args.stdout:
        f = sys.stdout
        writer = csv.writer(f, lineterminator="\n")
        wrote_header = False
    else:
        # append if file exists; else create with header
        header = ["open_time","open","high","low","close","volume","close_time","qav","num_trades","tbbav","tbqav"]
        file_exists = args.out.exists()
        f = args.out.open("a", newline="")
        writer = csv.writer(f, lineterminator="\n")
        if not file_exists:
            writer.writerow(header)
        wrote_header = True  # file path has header managed

    # Simple progress tracking
    shown = 0
    start_wall = time.time()

    try:
        count = 0
        for k in yield_klines(
            market=args.market, symbol=symbol, interval=args.interval,
            start_ms=start_ms, end_ms=end_ms, limit=args.limit
        ):
            # kline schema: [0] open_time, [1] open, [2] high, [3] low, [4] close, [5] volume, [6] close_time,
            # [7] quote_asset_volume, [8] number_of_trades, [9] taker_buy_base, [10] taker_buy_quote, [11] ignore
            if not wrote_header:
                wrote_header = write_header_if_needed(writer, wrote_header, out_to_file=False)
            writer.writerow([
                int(k[0]), k[1], k[2], k[3], k[4], k[5], int(k[6]), k[7], k[8], k[9], k[10]
            ])
            count += 1
            if args.progress:
                shown += 1
                if shown % 1000 == 0:
                    elapsed = time.time() - start_wall
                    rate = count / max(elapsed, 1e-6)
                    print(f"\rFetched: {count} candles @ {rate:.1f}/s", end="", file=sys.stderr)

        if args.progress:
            elapsed = time.time() - start_wall
            print(f"\nDone. Candles: {count}, elapsed {elapsed:.1f}s", file=sys.stderr)

    finally:
        if args.out and not args.stdout:
            f.close()

if __name__ == "__main__":
    main()
