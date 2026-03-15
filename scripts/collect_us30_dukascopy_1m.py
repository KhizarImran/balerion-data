"""
collect_us30_dukascopy_1m.py
-----------------------------
Downloads the full available history of Dukascopy US30 (Dow Jones) 1-minute
bid OHLCV bars and saves to:

    data/indices/us30/us30_dukascopy_1m.parquet

Dukascopy 1-minute US30 data is available from 2013-01-02 onward.
Annual chunks are used to keep progress readable and avoid large single requests.

Usage
-----
    # Full collection from 2013 to now (skips if file already exists)
    python scripts/collect_us30_dukascopy_1m.py

    # Force re-download, overwriting existing file
    python scripts/collect_us30_dukascopy_1m.py --force

    # Incremental update — merge the last N days into the existing file
    python scripts/collect_us30_dukascopy_1m.py --update

    # Update with a custom lookback window (useful if you missed several weeks)
    python scripts/collect_us30_dukascopy_1m.py --update --days 30
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import dukascopy_python
from dukascopy_python import instruments as I

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INSTRUMENT = I.INSTRUMENT_IDX_AMERICA_E_D_J_IND  # "E_D&J-Ind" (US30)
INTERVAL = dukascopy_python.INTERVAL_MIN_1
OFFER_SIDE = dukascopy_python.OFFER_SIDE_BID  # bid OHLCV, standard for backtesting

# Earliest known date with data on Dukascopy for US30 at 1-minute resolution
DATA_START = datetime(2013, 1, 2, tzinfo=timezone.utc)

# Fetch one month at a time — 1-min bars are ~44 k rows/month, manageable chunks
CHUNK_MONTHS = 1

# Smart-skip: don't re-fetch if newest bar is younger than this many hours
FRESHNESS_THRESHOLD_HOURS = 1

BASE_DIR = Path(__file__).parent.parent
OUTPUT_PATH = BASE_DIR / "data" / "indices" / "us30" / "us30_dukascopy_1m.parquet"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _month_chunks(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    """Split [start, end) into monthly intervals."""
    chunks = []
    cs = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    while cs < end:
        # Advance by one month
        if cs.month == 12:
            ce = cs.replace(year=cs.year + 1, month=1)
        else:
            ce = cs.replace(month=cs.month + 1)
        ce = min(ce, end)
        chunks.append((cs, ce))
        cs = ce
    return chunks


def _fetch_chunk(start: datetime, end: datetime, label: str) -> pd.DataFrame:
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
            print(f"    [WARN] No data for {label}")
            return pd.DataFrame()
        print(f"    [OK] {label}: {len(df):,} bars")
        return df
    except Exception as exc:
        print(f"    [WARN] Error fetching {label}: {exc}")
        return pd.DataFrame()


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    """Move timestamp from index -> column, ensure UTC, keep OHLCV only."""
    if df.empty:
        return df

    df = df.reset_index()

    if "timestamp" not in df.columns:
        df = df.rename(columns={df.columns[0]: "timestamp"})

    ts = df["timestamp"]
    if hasattr(ts.dtype, "tz") and ts.dtype.tz is not None:
        df["timestamp"] = ts.dt.tz_convert("UTC")
    else:
        df["timestamp"] = pd.to_datetime(ts, utc=True)

    col_map = {
        c: c.lower() for c in df.columns if c.lower() in ("open", "high", "low", "close", "volume")
    }
    df = df.rename(columns=col_map)

    keep = [c for c in ["timestamp", "open", "high", "low", "close", "volume"] if c in df.columns]
    df = df[keep]
    df = df.drop_duplicates(subset=["timestamp"], keep="last")
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def _load_existing() -> pd.DataFrame:
    df = pd.read_parquet(OUTPUT_PATH)
    ts = df["timestamp"]
    if hasattr(ts.dtype, "tz") and ts.dtype.tz is not None:
        df["timestamp"] = ts.dt.tz_convert("UTC")
    else:
        df["timestamp"] = pd.to_datetime(ts, utc=True)
    return df


def _save(df: pd.DataFrame):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PATH, index=False)
    size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    print(f"\n  [OK] Saved: {OUTPUT_PATH.relative_to(BASE_DIR)}")
    print(f"       {len(df):,} rows  |  {size_mb:.1f} MB")


def _print_summary(df: pd.DataFrame):
    span = df["timestamp"].max() - df["timestamp"].min()
    print(f"  Rows : {len(df):,}")
    print(f"  Range: {df['timestamp'].min():%Y-%m-%d} -> {df['timestamp'].max():%Y-%m-%d} UTC")
    print(f"  Span : {span.days:,} days  (~{span.days / 365.25:.1f} years)")


# ---------------------------------------------------------------------------
# Full collection
# ---------------------------------------------------------------------------


def collect(force: bool = False):
    print(f"\n{'=' * 70}")
    print(f"Dukascopy US30 1-min — Full Collection")
    print(f"Started : {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"From    : {DATA_START:%Y-%m-%d}")
    print(f"Output  : {OUTPUT_PATH.relative_to(BASE_DIR)}")
    print(f"{'=' * 70}")

    if OUTPUT_PATH.exists() and not force:
        print(f"\n  [SKIP] File already exists: {OUTPUT_PATH.name}")
        print(f"         Use --force to re-download or --update to append new bars.")
        return

    end_date = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0)
    chunks = _month_chunks(DATA_START, end_date)

    print(f"\n  Fetching {len(chunks)} monthly chunks ...\n")

    frames = []
    for i, (cs, ce) in enumerate(chunks, 1):
        label = f"{cs:%Y-%m}  [{i}/{len(chunks)}]"
        chunk = _fetch_chunk(cs, ce, label)
        if not chunk.empty:
            frames.append(_normalise(chunk))

    if not frames:
        print("\n  [ERROR] No data returned — aborting.")
        sys.exit(1)

    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["timestamp"], keep="last")
    df = df.sort_values("timestamp").reset_index(drop=True)

    print()
    _print_summary(df)
    _save(df)
    print(f"\n  Done.\n")


# ---------------------------------------------------------------------------
# Incremental update
# ---------------------------------------------------------------------------


def update(days: int = 7, force: bool = False):
    print(f"\n{'=' * 70}")
    print(f"Dukascopy US30 1-min — Incremental Update  (last {days} days)")
    print(f"Started : {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"{'=' * 70}")

    if not OUTPUT_PATH.exists():
        print(f"\n  [WARN] No existing file found — running full collection instead.")
        collect(force=True)
        return

    existing = _load_existing()
    latest = existing["timestamp"].max()
    age_h = (datetime.now(tz=timezone.utc) - latest).total_seconds() / 3600

    print(
        f"\n  Existing: {len(existing):,} rows, latest bar {latest:%Y-%m-%d %H:%M} UTC ({age_h:.1f}h ago)"
    )

    if age_h < FRESHNESS_THRESHOLD_HOURS and not force:
        print(f"  [SKIP] Data is fresh — skipping (use --force to override).")
        return

    fetch_from = min(
        latest - timedelta(hours=1),
        datetime.now(tz=timezone.utc) - timedelta(days=days),
    )
    fetch_to = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0)

    print(f"  Fetching: {fetch_from:%Y-%m-%d %H:%M} -> {fetch_to:%Y-%m-%d %H:%M} UTC\n")

    chunks = _month_chunks(fetch_from, fetch_to)
    frames = []
    for i, (cs, ce) in enumerate(chunks, 1):
        label = f"{cs:%Y-%m}  [{i}/{len(chunks)}]"
        chunk = _fetch_chunk(cs, ce, label)
        if not chunk.empty:
            frames.append(_normalise(chunk))

    if not frames:
        print(f"\n  [WARN] No new data returned — file unchanged.")
        return

    new_df = pd.concat(frames, ignore_index=True)

    combined = pd.concat([existing, new_df], ignore_index=True)
    before = len(combined)
    combined = combined.drop_duplicates(subset=["timestamp"], keep="last")
    combined = combined.sort_values("timestamp").reset_index(drop=True)
    net_new = len(combined) - len(existing)
    dupes = before - len(combined)

    print(
        f"\n  Merged: {len(existing):,} + {len(new_df):,} -> {len(combined):,}  "
        f"({net_new:+,} new bars, {dupes} dupes removed)"
    )

    if net_new <= 0:
        print(f"  [INFO] No new bars added — file unchanged.")
        return

    backup = OUTPUT_PATH.with_suffix(".parquet.backup")
    OUTPUT_PATH.rename(backup)
    try:
        _save(combined)
        backup.unlink()
    except Exception as exc:
        print(f"\n  [ERROR] Save failed: {exc} — restoring backup.")
        backup.rename(OUTPUT_PATH)
        sys.exit(1)

    print(f"\n  Done.\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Collect or update Dukascopy US30 1-minute OHLCV data",
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
        help="(--update only) Days of recent data to fetch (default: 7)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing file on full collect / skip freshness check on update",
    )
    args = parser.parse_args()

    if args.update:
        update(days=args.days, force=args.force)
    else:
        collect(force=args.force)


if __name__ == "__main__":
    main()
