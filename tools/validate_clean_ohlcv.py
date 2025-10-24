#!/usr/bin/env python3
# tools/validate_clean_ohlcv.py
# Validate & clean OHLCV candles for backtesting.
# Usage examples at bottom.

import argparse, json, sys
from pathlib import Path
import numpy as np
import pandas as pd

REQUIRED_COLS = ["open_time","open","high","low","close","volume"]

def _read_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Try common timestamp column names
    ts_cols = [c for c in df.columns if c.lower() in ("time","timestamp","date","datetime","open_time")]
    if not ts_cols:
        raise ValueError("No timestamp column found. Expected one of: time, timestamp, date, datetime, open_time")
    ts = ts_cols[0]
    df = df.rename(columns={ts: "open_time"})
    # Parse datetime, coerce errors
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True, errors="coerce")
    # Standardize price/volume names if present
    rename_map = {}
    for c in df.columns:
        cl = c.lower()
        if cl in ("o","open"): rename_map[c] = "open"
        if cl in ("h","high"): rename_map[c] = "high"
        if cl in ("l","low"):  rename_map[c] = "low"
        if cl in ("c","close","adjclose","adj_close"): rename_map[c] = "close"
        if cl in ("v","volume","vol"): rename_map[c] = "volume"
    df = df.rename(columns=rename_map)
    # Keep only necessary + extras
    missing = [c for c in ["open","high","low","close","volume"] if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    return df

def _enforce_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["open","high","low","close","volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

def _infer_freq(index: pd.DatetimeIndex) -> pd.Timedelta | None:
    if len(index) < 3: return None
    diffs = np.diff(index.view("int64"))  # ns
    # use median diff
    med = np.median(diffs)
    if med <= 0: return None
    return pd.to_timedelta(int(med), unit="ns")

def _build_expected_index(start: pd.Timestamp, end: pd.Timestamp, freq: pd.Timedelta) -> pd.DatetimeIndex:
    # Convert Timedelta to freq string if possible
    seconds = int(freq / pd.Timedelta(seconds=1))
    if seconds % 60 == 0:
        step = f"{seconds//60}T"
    else:
        step = f"{seconds}S"
    return pd.date_range(start=start, end=end, freq=step, tz="UTC")

def _detect_issues(df: pd.DataFrame):
    df = df.sort_values("open_time").set_index("open_time")
    dupes = int(df.index.duplicated().sum())
    zeros = int((df["volume"]<=0).sum())
    freq = _infer_freq(df.index)
    gaps = 0
    expected = None
    if freq is not None and len(df) >= 3:
        expected = _build_expected_index(df.index[0], df.index[-1], freq)
        gaps = int(len(expected) - len(df.index.unique()))
    return df, dupes, zeros, gaps, freq, expected

def _repair(df: pd.DataFrame, expected_index: pd.DatetimeIndex | None, fill: str):
    df = df.sort_index()
    # Drop duplicates (keep first)
    df = df[~df.index.duplicated(keep="first")]
    # Reindex if we have expected grid
    if expected_index is not None:
        df = df.reindex(expected_index)
        df["gap_flag"] = df["open"].isna() | df["high"].isna() | df["low"].isna() | df["close"].isna() | df["volume"].isna()
        if fill == "ffill":
            df[["open","high","low","close","volume"]] = df[["open","high","low","close","volume"]].ffill()
        elif fill == "drop":
            df = df.dropna(subset=["open","high","low","close","volume"])
        elif fill == "nan":
            pass
        else:
            raise ValueError("fill must be one of: drop | ffill | nan")
    else:
        df["gap_flag"] = False
    # Remove zero/neg volume rows but mark them
    df["zero_vol_flag"] = (df["volume"]<=0) & df["volume"].notna()
    df = df[~df["zero_vol_flag"]]
    return df

def _add_cost_columns(df: pd.DataFrame, fee_bps: float, spread_bps: float, slip_bps: float):
    # Add round-trip cost (fraction, not %)
    rt_bps = fee_bps + spread_bps + slip_bps
    df["assumed_fee_bps"] = fee_bps
    df["assumed_spread_bps"] = spread_bps
    df["assumed_slippage_bps"] = slip_bps
    df["assumed_roundtrip_bps"] = rt_bps
    df["assumed_roundtrip_frac"] = rt_bps / 1e4
    return df

def main():
    ap = argparse.ArgumentParser(description="Validate & clean OHLCV candles for backtesting (UTC, gaps, dupes, zeros).")
    ap.add_argument("input", type=Path, help="Input CSV with OHLCV")
    ap.add_argument("--out", type=Path, required=True, help="Output cleaned CSV")
    ap.add_argument("--report", type=Path, default=None, help="Output JSON quality report")
    ap.add_argument("--fill", choices=["drop","ffill","nan"], default="nan",
                    help="How to handle missing bars after aligning to expected grid")
    ap.add_argument("--drop-before", type=str, default=None, help="Drop rows before this UTC (e.g., 2025-01-01)")
    ap.add_argument("--drop-after", type=str, default=None, help="Drop rows after this UTC")
    ap.add_argument("--fee-bps", type=float, default=12.0, help="Round-trip fees in bps (default 12bps = 0.12%)")
    ap.add_argument("--spread-bps", type=float, default=3.0, help="Assumed spread in bps")
    ap.add_argument("--slip-bps", type=float, default=2.0, help="Assumed slippage in bps")
    args = ap.parse_args()

    df = _read_csv(args.input)
    df = _enforce_dtypes(df)
    # Time window
    if args.drop_before:
        df = df[df["open_time"] >= pd.Timestamp(args.drop_before, tz="UTC")]
    if args.drop_after:
        df = df[df["open_time"] <= pd.Timestamp(args.drop_after, tz="UTC")]

    df, dupes, zeros, gaps, freq, expected = _detect_issues(df)

    cleaned = _repair(df, expected, args.fill)
    cleaned = _add_cost_columns(cleaned, args.fee_bps, args.spread_bps, args.slip_bps)

    # Final sort & write
    cleaned = cleaned.sort_index()
    cleaned.to_csv(args.out, index_label="open_time", float_format="%.10f")

    # Build report
    rep = {
        "input": str(args.input),
        "out": str(args.out),
        "rows_in": int(len(df)),
        "rows_out": int(len(cleaned)),
        "dupes_detected": dupes,
        "zero_volume_detected": zeros,
        "gaps_detected": gaps,
        "freq_inferred_seconds": (int(freq.total_seconds()) if isinstance(freq, pd.Timedelta) else None),
        "filled_method": args.fill,
        "gap_rows_flagged": int(cleaned["gap_flag"].sum()) if "gap_flag" in cleaned.columns else 0,
        "zero_vol_rows_dropped": int((df["volume"]<=0).sum()) if "volume" in df.columns else 0,
        "assumptions_bps": {
            "fee": args.fee_bps, "spread": args.spread_bps, "slippage": args.slip_bps,
            "roundtrip": args.fee_bps + args.spread_bps + args.slip_bps
        }
    }
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        with open(args.report, "w") as f:
            json.dump(rep, f, indent=2, default=str)
    else:
        print(json.dumps(rep, indent=2, default=str))

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
