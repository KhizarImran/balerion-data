"""
MT5 multi-timeframe data collector.

Collects native MT5 bars at any supported timeframe for specified symbols
and saves to data/<category>/<symbol>/<symbol>_mt5_<tf>.parquet.

Usage:
    uv run python scripts/collect_mt5_multitf.py
    uv run python scripts/collect_mt5_multitf.py --symbols USDJPY XAUUSD US30 --tfs M15 H4
    uv run python scripts/collect_mt5_multitf.py --force          # full re-collect
    uv run python scripts/collect_mt5_multitf.py --update         # incremental: last 14 days
    uv run python scripts/collect_mt5_multitf.py --update --days 30
"""

import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

import mt5_utils
import config

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_SYMBOLS    = config.FX_SYMBOLS + config.INDEX_SYMBOLS
DEFAULT_TIMEFRAMES = ["M15", "H4"]

# Map MT5 timeframe string -> label used in filename
_TF_LABEL = {
    "M1":  "1min",
    "M5":  "5min",
    "M15": "15min",
    "M30": "30min",
    "H1":  "1h",
    "H4":  "4h",
    "D1":  "1d",
    "W1":  "1w",
    "MN1": "1mo",
}

# Bars per day (approx) by timeframe — used to size the fetch window
_BARS_PER_DAY = {
    "M1": 1440, "M5": 288, "M15": 96, "M30": 48,
    "H1": 24,   "H4": 6,   "D1":  1,
}


def _out_path(symbol: str, tf_str: str) -> Path:
    cat = mt5_utils.get_symbol_category(symbol)
    sym = symbol.lower()
    label = _TF_LABEL.get(tf_str, tf_str.lower())
    folder = (config.FX_DIR if cat == "fx" else config.INDICES_DIR) / sym
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{sym}_mt5_{label}"   # save_dataframe appends .parquet


def _update_symbol(symbol: str, tf_str: str, days: int) -> None:
    """Incremental update: fetch last `days` days and merge into existing file."""
    out     = _out_path(symbol, tf_str)
    parquet = out.with_suffix(".parquet")

    print(f"\n[UPDATE] {symbol} {tf_str}")

    existing = mt5_utils.load_existing_data(parquet) if parquet.exists() else None
    if existing is None:
        print(f"  No existing file — falling back to full collect")
        tf_const = mt5_utils.get_timeframe_constant(tf_str)
        df = mt5_utils.collect_maximum_data(symbol, tf_const)
        if df is not None:
            mt5_utils.save_dataframe(df, out, save_format="parquet")
        return

    actual_symbol = mt5_utils.find_symbol(symbol)
    if actual_symbol is None:
        print(f"  [ERROR] Symbol {symbol} not found in MT5")
        return

    tf_const   = mt5_utils.get_timeframe_constant(tf_str)
    bars_day   = _BARS_PER_DAY.get(tf_str, 96)
    fetch_bars = int(days * bars_day * 1.2) + 50   # 20% buffer

    rates = mt5.copy_rates_from_pos(actual_symbol, tf_const, 0, fetch_bars)
    if rates is None or len(rates) == 0:
        print(f"  [ERROR] MT5 fetch failed: {mt5.last_error()}")
        return

    new_df = pd.DataFrame(np.array(rates))
    new_df["timestamp"] = pd.to_datetime(new_df["time"], unit="s")
    new_df = new_df.drop(columns=["time"])
    if "tick_volume" in new_df.columns:
        new_df = new_df.rename(columns={"tick_volume": "volume"})
    cols = [c for c in ["timestamp", "open", "high", "low", "close", "volume", "spread", "real_volume"]
            if c in new_df.columns]
    new_df = new_df[cols].drop_duplicates("timestamp").sort_values("timestamp")

    combined = mt5_utils.append_new_data(existing, new_df)
    mt5_utils.save_dataframe(combined, out, save_format="parquet")


def main() -> None:
    parser = argparse.ArgumentParser(description="MT5 multi-timeframe collector")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS, metavar="SYM")
    parser.add_argument("--tfs",     nargs="+", default=DEFAULT_TIMEFRAMES, metavar="TF",
                        help="MT5 timeframe strings: M1 M5 M15 M30 H1 H4 D1")
    parser.add_argument("--force",  action="store_true", help="Full re-collect, overwrite existing")
    parser.add_argument("--update", action="store_true", help="Incremental update (merge last --days days)")
    parser.add_argument("--days",   type=int, default=14,  help="Days to fetch in --update mode (default: 14)")
    args = parser.parse_args()

    mode = "update" if args.update else ("force" if args.force else "skip-existing")
    print("=" * 60)
    print("  MT5 Multi-Timeframe Collector")
    print(f"  Symbols    : {args.symbols}")
    print(f"  Timeframes : {args.tfs}")
    print(f"  Mode       : {mode}" + (f" ({args.days}d)" if args.update else ""))
    print("=" * 60)

    if not mt5_utils.initialize_mt5():
        sys.exit(1)

    try:
        for symbol in args.symbols:
            for tf_str in args.tfs:
                if args.update:
                    _update_symbol(symbol, tf_str, args.days)
                    continue

                out     = _out_path(symbol, tf_str)
                parquet = out.with_suffix(".parquet")

                if parquet.exists() and not args.force:
                    existing = pd.read_parquet(parquet)
                    print(f"\n[SKIP] {symbol} {tf_str}: {parquet.name} exists "
                          f"({len(existing):,} bars, last: {existing['timestamp'].iloc[-1]}) "
                          f"-- use --force to re-collect or --update to extend")
                    continue

                tf_const = mt5_utils.get_timeframe_constant(tf_str)
                df = mt5_utils.collect_maximum_data(symbol, tf_const)
                if df is None:
                    continue

                mt5_utils.save_dataframe(df, out, save_format="parquet")

    finally:
        mt5_utils.shutdown_mt5()

    print("\nDone.")


if __name__ == "__main__":
    main()
