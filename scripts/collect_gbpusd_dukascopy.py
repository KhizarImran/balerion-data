"""
GBPUSD H1 data collection via Dukascopy Bank (dukascopy-python).

Dukascopy offers significantly deeper history than MT5/IC Markets — typically
back to 2003-2004 for major FX pairs. This script collects all available H1
bars for GBP/USD and saves to data/fx/gbpusd_dukascopy_1h.parquet.

The file is named distinctly (_dukascopy_) to avoid collision with any
MT5-sourced gbpusd_1m.parquet file.

Usage:
    # Initial collection — fetches everything from START_DATE to today
    python scripts/collect_gbpusd_dukascopy.py

    # Incremental update — merges the last N days into the existing file
    python scripts/collect_gbpusd_dukascopy.py --update

    # Update but fetch more days (e.g. missed a few weeks)
    python scripts/collect_gbpusd_dukascopy.py --update --days 30

    # Force re-collect everything, overwriting the existing file
    python scripts/collect_gbpusd_dukascopy.py --force
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import dukascopy_python
from dukascopy_python.instruments import INSTRUMENT_FX_MAJORS_GBP_USD

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Dukascopy GBPUSD history starts around 2003-05. Using 2003-01-01 as the
# target so we always attempt to grab everything available.
START_DATE = datetime(2003, 1, 1, tzinfo=timezone.utc)

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "fx" / "gbpusd_dukascopy_1h.parquet"

INSTRUMENT = INSTRUMENT_FX_MAJORS_GBP_USD  # "GBP/USD"
INTERVAL = dukascopy_python.INTERVAL_HOUR_1
OFFER_SIDE = dukascopy_python.OFFER_SIDE_BID  # bid-side OHLCV; standard for FX backtesting

# Fetch in annual chunks to stay well within the library's internal limit and
# give clean progress output for a multi-year pull.
CHUNK_YEARS = 1

# Smart-skip: don't update if latest bar is younger than this
FRESHNESS_THRESHOLD_HOURS = 1


# ---------------------------------------------------------------------------
# Core fetch helper
# ---------------------------------------------------------------------------


def _fetch_chunk(start: datetime, end: datetime, label: str) -> pd.DataFrame:
    """
    Fetch one date-range chunk from Dukascopy. Returns an empty DataFrame on
    failure rather than raising, so the caller can decide whether to abort.
    """
    try:
        df = dukascopy_python.fetch(
            INSTRUMENT,
            INTERVAL,
            OFFER_SIDE,
            start,
            end,
            max_retries=7,
            limit=30_000,
            debug=False,
        )
        if df is None or df.empty:
            print(f"    [WARN] No data returned for {label}")
            return pd.DataFrame()
        print(f"    [OK] {label}: {len(df):,} bars")
        return df
    except Exception as exc:
        print(f"    [WARN] Error fetching {label}: {exc}")
        return pd.DataFrame()


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardise the DataFrame from dukascopy-python:
    - Move timestamp out of index into a column
    - Ensure UTC-aware datetime
    - Keep only timestamp, open, high, low, close, volume
    - Deduplicate and sort
    """
    if df.empty:
        return df

    # The library returns timestamp as the index named 'timestamp'
    df = df.reset_index()

    # Ensure the timestamp column is UTC-aware
    if "timestamp" not in df.columns:
        # Fallback: first column is the timestamp
        df = df.rename(columns={df.columns[0]: "timestamp"})

    ts = df["timestamp"]
    if hasattr(ts.dtype, "tz") and ts.dtype.tz is not None:
        # Already tz-aware (e.g. datetime64[ms, UTC]) — just normalise to UTC,
        # do NOT call pd.to_datetime(..., utc=True) which corrupts ms-precision data
        df["timestamp"] = ts.dt.tz_convert("UTC")
    else:
        # Naive or integer — parse and localise
        df["timestamp"] = pd.to_datetime(ts, utc=True)

    # Keep standard columns only (volume may be named differently in some versions)
    col_map = {}
    for col in df.columns:
        lower = col.lower()
        if lower in ("open", "high", "low", "close", "volume"):
            col_map[col] = lower
    df = df.rename(columns=col_map)

    keep = [c for c in ["timestamp", "open", "high", "low", "close", "volume"] if c in df.columns]
    df = df[keep]

    df = df.drop_duplicates(subset=["timestamp"], keep="last")
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Full collection
# ---------------------------------------------------------------------------


def collect(force: bool = False):
    """Fetch all available history from START_DATE to now and save."""
    print(f"\n{'=' * 70}")
    print(f"GBPUSD H1 - Full Collection via Dukascopy")
    print(f"Started  : {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"From     : {START_DATE:%Y-%m-%d}")
    print(f"To       : {datetime.now(tz=timezone.utc):%Y-%m-%d}")
    print(f"Output   : {OUTPUT_PATH}")
    print(f"{'=' * 70}\n")

    if OUTPUT_PATH.exists() and not force:
        print(f"[INFO] {OUTPUT_PATH.name} already exists.")
        print("       Use --update to add new bars, or --force to re-collect everything.")
        return

    end_date = datetime.now(tz=timezone.utc).replace(minute=0, second=0, microsecond=0)

    # Split the full range into annual chunks for cleaner progress output
    chunks = []
    chunk_start = START_DATE
    while chunk_start < end_date:
        chunk_end = min(
            datetime(
                chunk_start.year + CHUNK_YEARS,
                chunk_start.month,
                chunk_start.day,
                tzinfo=timezone.utc,
            ),
            end_date,
        )
        chunks.append((chunk_start, chunk_end))
        chunk_start = chunk_end

    print(f"Fetching {len(chunks)} annual chunk(s)...\n")

    frames = []
    for i, (cs, ce) in enumerate(chunks, 1):
        label = f"{cs:%Y-%m-%d} -> {ce:%Y-%m-%d}  [{i}/{len(chunks)}]"
        df_chunk = _fetch_chunk(cs, ce, label)
        if not df_chunk.empty:
            frames.append(_normalise(df_chunk))

    if not frames:
        print("\n[ERROR] No data collected from Dukascopy — aborting")
        sys.exit(1)

    df = pd.concat(frames, ignore_index=True)
    # Final dedup + sort after concat (each chunk is already normalised)
    df = df.drop_duplicates(subset=["timestamp"], keep="last")
    df = df.sort_values("timestamp").reset_index(drop=True)

    _print_summary(df)
    _save(df)

    print(f"\n[OK] Done. Run with --update to keep the file fresh going forward.")


# ---------------------------------------------------------------------------
# Incremental update
# ---------------------------------------------------------------------------


def update(days: int = 7, force: bool = False):
    """Fetch the last `days` of bars and merge into the existing file."""
    print(f"\n{'=' * 70}")
    print(f"GBPUSD H1 - Incremental Update via Dukascopy")
    print(f"{'=' * 70}\n")

    if not OUTPUT_PATH.exists():
        print("[WARN] No existing file found - running full collection instead")
        collect(force=True)
        return

    existing = pd.read_parquet(OUTPUT_PATH)
    ts = existing["timestamp"]
    if hasattr(ts.dtype, "tz") and ts.dtype.tz is not None:
        existing["timestamp"] = ts.dt.tz_convert("UTC")
    else:
        existing["timestamp"] = pd.to_datetime(ts, utc=True)
    latest = existing["timestamp"].max()
    print(f"  Existing : {len(existing):,} rows  |  latest bar: {latest:%Y-%m-%d %H:%M} UTC")

    age_hours = (datetime.now(tz=timezone.utc) - latest).total_seconds() / 3600
    if age_hours < FRESHNESS_THRESHOLD_HOURS and not force:
        print(f"  [INFO] Data is only {age_hours:.1f}h old - skipping (use --force to override)")
        return

    # Fetch from slightly before the latest bar to ensure no gap
    fetch_from = latest - timedelta(hours=1)
    fetch_to = datetime.now(tz=timezone.utc).replace(minute=0, second=0, microsecond=0)

    # Also respect the --days window as a floor
    days_floor = datetime.now(tz=timezone.utc) - timedelta(days=days)
    fetch_from = min(fetch_from, days_floor)

    label = f"{fetch_from:%Y-%m-%d} -> {fetch_to:%Y-%m-%d}"
    print(f"  Fetching : {label}")
    new_df = _fetch_chunk(fetch_from, fetch_to, label)

    if new_df.empty:
        print("  [ERROR] No new data returned - file unchanged")
        return

    new_df = _normalise(new_df)

    # Merge
    combined = pd.concat([existing, new_df], ignore_index=True)
    before = len(combined)
    combined = combined.drop_duplicates(subset=["timestamp"], keep="last")
    combined = combined.sort_values("timestamp").reset_index(drop=True)
    net_new = len(combined) - len(existing)
    dupes = before - len(combined)

    print(
        f"  Merged   : {len(existing):,} existing + {len(new_df):,} fetched = {len(combined):,} total  ({net_new:+,} net new, {dupes} dupes removed)"
    )

    if net_new <= 0:
        print("  [INFO] No new bars added - file unchanged")
        return

    # Backup -> save -> remove backup
    backup = OUTPUT_PATH.with_suffix(".parquet.backup")
    OUTPUT_PATH.rename(backup)
    try:
        _save(combined)
        backup.unlink()
        print(f"  [OK] File updated")
    except Exception as exc:
        print(f"  [ERROR] Save failed ({exc}) - restoring backup")
        backup.rename(OUTPUT_PATH)
        raise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print_summary(df: pd.DataFrame):
    span = df["timestamp"].max() - df["timestamp"].min()
    print(f"\n  Summary:")
    print(f"    Rows  : {len(df):,}")
    print(
        f"    Range : {df['timestamp'].min():%Y-%m-%d %H:%M} UTC -> {df['timestamp'].max():%Y-%m-%d %H:%M} UTC"
    )
    print(f"    Span  : {span.days:,} days  (~{span.days / 365.25:.1f} years)")
    print(f"    Cols  : {df.columns.tolist()}")


def _save(df: pd.DataFrame):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    print(f"  [OK] Saved : {OUTPUT_PATH}  ({size_mb:.2f} MB,  {len(df):,} rows)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Collect or update GBPUSD H1 data from Dukascopy Bank",
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
        help="Skip freshness check / overwrite existing file on full collection",
    )
    args = parser.parse_args()

    if args.update:
        update(days=args.days, force=args.force)
    else:
        collect(force=args.force)


if __name__ == "__main__":
    main()
