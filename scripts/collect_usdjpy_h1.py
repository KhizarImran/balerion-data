"""
USDJPY H1 (1-hour) data collection and update script.

Collects a minimum of 6 months of 1-hour OHLCV bars for USDJPY from MT5
and saves to data/fx/usdjpy_1h.parquet.

Usage:
    # Initial collection (or re-collect everything)
    python scripts/collect_usdjpy_h1.py

    # Incremental update (fetch recent bars and merge)
    python scripts/collect_usdjpy_h1.py --update

    # Update but fetch more days than default (e.g. if you missed weeks)
    python scripts/collect_usdjpy_h1.py --update --days 30

    # Force update even if data is fresh
    python scripts/collect_usdjpy_h1.py --update --force
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

import MetaTrader5 as mt5
import numpy as np
import pandas as pd
import pytz

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

SCRIPTS_DIR = Path(__file__).parent
BASE_DIR = SCRIPTS_DIR.parent
DATA_DIR = BASE_DIR / "data"
FX_DIR = DATA_DIR / "fx"

SYMBOL = "USDJPY"
SYMBOL_ALTERNATIVES = ["USDJPY", "USDJPY.a", "USDJPYm", "USDJPY."]
TIMEFRAME_STR = "H1"
OUTPUT_PATH = FX_DIR / "usdjpy" / "usdjpy_1h.parquet"

# Minimum history to collect on first run (in days)
MIN_HISTORY_DAYS = 185  # ~6 months + buffer

# MT5 bars per request ceiling
MAX_BARS_PER_REQUEST = 99999

# Smart-skip: don't update if latest bar is younger than this (hours)
FRESHNESS_THRESHOLD_HOURS = 1


# ---------------------------------------------------------------------------
# MT5 helpers
# ---------------------------------------------------------------------------


def _tf_constant():
    """Return the MT5 timeframe constant for H1."""
    return mt5.TIMEFRAME_H1


def _init_mt5() -> bool:
    if not mt5.initialize():
        print(f"[ERROR] MT5 initialization failed: {mt5.last_error()}")
        return False
    print("[OK] MT5 initialized")
    return True


def _shutdown_mt5():
    mt5.shutdown()
    print("[OK] MT5 connection closed")


def _find_symbol() -> str | None:
    """Try each alternative name until one resolves in MT5."""
    for name in SYMBOL_ALTERNATIVES:
        info = mt5.symbol_info(name)
        if info is not None:
            if not info.visible:
                if not mt5.symbol_select(name, True):
                    continue
                print(f"  [INFO] Enabled {name} in Market Watch")
            return name
    print(f"[ERROR] Could not find {SYMBOL} or any of its alternatives in MT5")
    return None


def _rates_to_df(rates) -> pd.DataFrame:
    """Convert MT5 rates (structured array / list) to a clean DataFrame."""
    if isinstance(rates, list):
        df = pd.DataFrame(np.array(rates))
    else:
        df = pd.DataFrame(rates)

    # time -> timestamp (UTC)
    df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.drop(columns=["time"])

    # Normalise volume column name
    if "tick_volume" in df.columns:
        df = df.rename(columns={"tick_volume": "volume"})

    # Keep only the columns we care about (plus optional ones if present)
    keep = ["timestamp", "open", "high", "low", "close", "volume"]
    for opt in ["spread", "real_volume"]:
        if opt in df.columns:
            keep.append(opt)
    existing = [c for c in keep if c in df.columns]
    return df[existing]


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------


def collect_full_history(actual_symbol: str) -> pd.DataFrame:
    """
    Fetch maximum available H1 history from MT5, going back in chunks
    until we have at least MIN_HISTORY_DAYS of data or hit the broker limit.
    """
    tf = _tf_constant()

    print(f"\n  Fetching initial batch ({MAX_BARS_PER_REQUEST} bars) ...")
    rates = mt5.copy_rates_from_pos(actual_symbol, tf, 0, MAX_BARS_PER_REQUEST)
    if rates is None or len(rates) == 0:
        print(f"[ERROR] No data returned: {mt5.last_error()}")
        return pd.DataFrame()

    all_rates = list(rates)
    earliest_ts = int(pd.DataFrame(rates)["time"].min())
    earliest_dt = datetime.fromtimestamp(earliest_ts, tz=pytz.utc)
    latest_dt = datetime.fromtimestamp(int(pd.DataFrame(rates)["time"].max()), tz=pytz.utc)

    print(f"  [OK] Got {len(rates):,} bars  |  {earliest_dt:%Y-%m-%d} -> {latest_dt:%Y-%m-%d}")

    # How far back do we need to go?
    target_start = latest_dt - timedelta(days=MIN_HISTORY_DAYS)

    attempt = 0
    max_attempts = 20  # safety cap

    while earliest_dt > target_start and attempt < max_attempts:
        attempt += 1
        fetch_from = earliest_dt - timedelta(hours=1)
        older = mt5.copy_rates_from(actual_symbol, tf, fetch_from, MAX_BARS_PER_REQUEST)

        if older is None or len(older) == 0:
            print(f"  [INFO] No earlier data at attempt {attempt} - broker limit reached")
            break

        older_df = pd.DataFrame(older)
        new_earliest_ts = int(older_df["time"].min())

        if new_earliest_ts >= earliest_ts:
            print(f"  [INFO] Earliest data reached at attempt {attempt}")
            break

        new_bars = [r for r in older if r["time"] < earliest_ts]
        all_rates = new_bars + all_rates
        earliest_ts = new_earliest_ts
        earliest_dt = datetime.fromtimestamp(earliest_ts, tz=pytz.utc)

        span_days = (latest_dt - earliest_dt).days
        print(
            f"    Attempt {attempt}: {len(all_rates):,} bars total  |  earliest: {earliest_dt:%Y-%m-%d}  |  span: {span_days}d"
        )

        if earliest_dt <= target_start:
            print(f"  [OK] Reached 6-month target ({span_days} days of history)")
            break

    df = _rates_to_df(all_rates)

    # Deduplicate & sort
    before = len(df)
    df = df.drop_duplicates(subset=["timestamp"], keep="first")
    df = df.sort_values("timestamp").reset_index(drop=True)
    if len(df) < before:
        print(f"  [INFO] Removed {before - len(df):,} duplicate timestamps")

    span = df["timestamp"].max() - df["timestamp"].min()
    print(f"\n  Collection complete:")
    print(f"    Rows     : {len(df):,}")
    print(
        f"    Range    : {df['timestamp'].min():%Y-%m-%d %H:%M} UTC -> {df['timestamp'].max():%Y-%m-%d %H:%M} UTC"
    )
    print(f"    Span     : {span.days} days ({span.days / 30.44:.1f} months)")

    if span.days < MIN_HISTORY_DAYS:
        print(f"  [WARN] Only {span.days} days retrieved; broker may not hold more H1 history")

    return df


# ---------------------------------------------------------------------------
# Incremental update
# ---------------------------------------------------------------------------


def collect_recent(actual_symbol: str, days: int) -> pd.DataFrame:
    """Fetch the most recent `days` worth of H1 bars."""
    tf = _tf_constant()
    # H1: 24 bars/day * days * 0.75 (weekend discount) + buffer
    bars_to_fetch = int(days * 24 * 0.75) + 48

    rates = mt5.copy_rates_from_pos(actual_symbol, tf, 0, bars_to_fetch)
    if rates is None or len(rates) == 0:
        print(f"[ERROR] No recent data returned: {mt5.last_error()}")
        return pd.DataFrame()

    df = _rates_to_df(rates)
    cutoff = datetime.now(tz=pytz.utc) - timedelta(days=days)
    df = df[df["timestamp"] >= cutoff]
    return df


def update(days: int = 7, force: bool = False):
    """Incremental update: load existing file, fetch recent bars, merge & save."""
    print(f"\n{'=' * 70}")
    print(f"USDJPY H1 - Incremental Update")
    print(f"{'=' * 70}")

    if not OUTPUT_PATH.exists():
        print("[WARN] No existing file found - running full collection instead")
        collect(force=True)
        return

    existing = pd.read_parquet(OUTPUT_PATH)
    existing["timestamp"] = pd.to_datetime(existing["timestamp"], utc=True)
    latest = existing["timestamp"].max()
    print(f"  Existing: {len(existing):,} rows  |  latest bar: {latest:%Y-%m-%d %H:%M} UTC")

    # Smart-skip check
    age_hours = (datetime.now(tz=pytz.utc) - latest).total_seconds() / 3600
    if age_hours < FRESHNESS_THRESHOLD_HOURS and not force:
        print(f"  [INFO] Data is only {age_hours:.1f}h old - skipping (use --force to override)")
        return

    if not _init_mt5():
        sys.exit(1)

    try:
        actual_symbol = _find_symbol()
        if actual_symbol is None:
            sys.exit(1)

        print(f"  Fetching last {days} days of H1 data ...")
        new_df = collect_recent(actual_symbol, days)
        if new_df.empty:
            print("[ERROR] Failed to retrieve recent data")
            sys.exit(1)

        print(f"  [OK] Fetched {len(new_df):,} recent bars")

        # Merge
        combined = pd.concat([existing, new_df], ignore_index=True)
        before = len(combined)
        combined = combined.drop_duplicates(subset=["timestamp"], keep="last")
        combined = combined.sort_values("timestamp").reset_index(drop=True)
        net_new = len(combined) - len(existing)
        removed = before - len(combined)

        print(
            f"  Merged  : {len(existing):,} + {len(new_df):,} -> {len(combined):,} rows  ({net_new:+,} net new, {removed} dupes removed)"
        )

        if net_new <= 0:
            print("  [INFO] No new bars - file unchanged")
            return

        # Backup -> save -> remove backup
        backup = OUTPUT_PATH.with_suffix(".parquet.backup")
        OUTPUT_PATH.rename(backup)
        try:
            _save(combined)
            backup.unlink()
            print(f"  [OK] File updated successfully")
        except Exception as exc:
            print(f"[ERROR] Save failed: {exc} - restoring backup")
            backup.rename(OUTPUT_PATH)
            raise

    finally:
        _shutdown_mt5()


# ---------------------------------------------------------------------------
# Save helper
# ---------------------------------------------------------------------------


def _save(df: pd.DataFrame):
    import os

    FX_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    print(f"  [OK] Saved: {OUTPUT_PATH}  ({size_mb:.2f} MB,  {len(df):,} rows)")


# ---------------------------------------------------------------------------
# Full collection entry point
# ---------------------------------------------------------------------------


def collect(force: bool = False):
    """Full collection: fetch all available H1 history and save."""
    print(f"\n{'=' * 70}")
    print(f"USDJPY H1 - Full Collection")
    print(f"Started : {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(
        f"Target  : >= {MIN_HISTORY_DAYS} days ({MIN_HISTORY_DAYS / 30.44:.1f} months) of H1 bars"
    )
    print(f"Output  : {OUTPUT_PATH}")
    print(f"{'=' * 70}")

    if OUTPUT_PATH.exists() and not force:
        print(f"\n[INFO] {OUTPUT_PATH.name} already exists.")
        print("       Use --update to add new bars, or pass --force to re-collect everything.")
        return

    if not _init_mt5():
        sys.exit(1)

    try:
        actual_symbol = _find_symbol()
        if actual_symbol is None:
            sys.exit(1)

        info = mt5.symbol_info(actual_symbol)
        print(f"\n  Symbol : {info.name}")
        print(f"  Desc   : {info.description}")

        df = collect_full_history(actual_symbol)
        if df.empty:
            print("[ERROR] No data collected - aborting")
            sys.exit(1)

        _save(df)

    finally:
        _shutdown_mt5()

    print(f"\n[OK] Done. Run with --update to keep the file fresh going forward.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Collect or update USDJPY H1 data from MT5",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Incremental update: merge recent bars into the existing file",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="(--update only) How many recent days to fetch (default: 7)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip freshness check / overwrite existing file",
    )
    args = parser.parse_args()

    if args.update:
        update(days=args.days, force=args.force)
    else:
        collect(force=args.force)


if __name__ == "__main__":
    main()
