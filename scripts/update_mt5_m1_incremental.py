"""
Incrementally update MT5 1-minute FX parquet files.

For each configured FX pair:
1. Find an existing 1-minute parquet file.
2. If none exists, collect the maximum available MT5 M1 history.
3. If one exists, read its latest timestamp.
4. Fetch only MT5 M1 bars after that timestamp.
5. Merge, deduplicate, and save back to the same parquet file.

Usage:
    uv run python scripts/update_mt5_m1_incremental.py
    uv run python scripts/update_mt5_m1_incremental.py --symbols EURUSD GBPUSD
    uv run python scripts/update_mt5_m1_incremental.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

import config
import mt5_utils


TF_LABEL = "1m"


def _data_dir_for(category: str, symbol: str) -> Path:
    base_dir = config.FX_DIR if category == "fx" else config.INDICES_DIR
    return base_dir / symbol.lower()


def candidate_paths(symbol: str, category: str = "fx") -> list[Path]:
    """Return 1-minute parquet naming variants, newest convention first."""
    folder = _data_dir_for(category, symbol)
    sym = symbol.lower()
    return [
        folder / f"{sym}_mt5_1m.parquet",
        folder / f"{sym}_1m.parquet",
        folder / f"{sym}_mt5_1min.parquet",
    ]


def find_existing_path(symbol: str, category: str = "fx") -> Path | None:
    for path in candidate_paths(symbol, category):
        if path.exists():
            return path
    return None


def normalise_rates(rates) -> pd.DataFrame:
    df = pd.DataFrame(rates)
    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["time"], unit="s")
    df = df.drop(columns=["time"])

    if "tick_volume" in df.columns:
        df = df.rename(columns={"tick_volume": "volume"})

    columns = config.OUTPUT_COLUMNS.copy()
    if "spread" in df.columns and "spread" in config.OPTIONAL_COLUMNS:
        columns.append("spread")
    if "real_volume" in df.columns and "real_volume" in config.OPTIONAL_COLUMNS:
        columns.append("real_volume")

    return df[[col for col in columns if col in df.columns]]


def _as_utc_timestamp(value) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def latest_closed_mt5_timestamp(actual_symbol: str) -> pd.Timestamp | None:
    rates = mt5.copy_rates_from_pos(actual_symbol, mt5.TIMEFRAME_M1, 1, 1)
    if rates is None or len(rates) == 0:
        print(f"  [ERROR] Could not read latest closed MT5 bar: {mt5.last_error()}")
        return None
    return _as_utc_timestamp(pd.to_datetime(pd.DataFrame(rates)["time"].iloc[-1], unit="s"))


def fetch_missing_by_position(
    actual_symbol: str,
    latest_existing_utc: pd.Timestamp,
    latest_existing_naive: pd.Timestamp,
) -> pd.DataFrame | None:
    """Fallback path: fetch recent closed bars and keep only missing rows."""
    chunks = []
    offset = 1  # skip current forming bar
    chunk_size = config.MAX_BARS_PER_REQUEST

    while True:
        rates = mt5.copy_rates_from_pos(actual_symbol, mt5.TIMEFRAME_M1, offset, chunk_size)
        if rates is None:
            print(f"  [ERROR] copy_rates_from_pos failed: {mt5.last_error()}")
            return None
        if len(rates) == 0:
            break

        df = normalise_rates(rates)
        if df.empty:
            break

        chunks.append(df[df["timestamp"] > latest_existing_naive])
        earliest_utc = _as_utc_timestamp(df["timestamp"].min())
        if earliest_utc <= latest_existing_utc:
            break

        offset += len(df)

    if not chunks:
        return pd.DataFrame(columns=config.OUTPUT_COLUMNS)

    combined = pd.concat(chunks, ignore_index=True)
    combined = combined.drop_duplicates(subset=["timestamp"], keep="last")
    combined = combined.sort_values("timestamp").reset_index(drop=True)
    return combined


def fetch_missing_m1(symbol: str, latest_timestamp: pd.Timestamp) -> pd.DataFrame | None:
    actual_symbol = mt5_utils.find_symbol(symbol)
    if actual_symbol is None:
        print(f"  [ERROR] Symbol {symbol} not found in MT5")
        return None

    if actual_symbol != symbol:
        print(f"  [INFO] Using symbol: {actual_symbol} (mapped from {symbol})")

    latest_existing_utc = _as_utc_timestamp(latest_timestamp)
    latest_existing_naive = latest_existing_utc.tz_localize(None)
    latest_mt5_utc = latest_closed_mt5_timestamp(actual_symbol)
    if latest_mt5_utc is None:
        return None

    print(f"  Latest closed MT5 bar: {latest_mt5_utc.tz_localize(None)}")
    if latest_mt5_utc <= latest_existing_utc:
        print(f"  [INFO] Already current through {latest_existing_naive}")
        return pd.DataFrame(columns=config.OUTPUT_COLUMNS)

    from_dt = latest_existing_utc.to_pydatetime() + timedelta(minutes=1)
    to_dt = latest_mt5_utc.to_pydatetime()

    if from_dt >= to_dt:
        print(f"  [INFO] Already current through {latest_existing_naive}")
        return pd.DataFrame(columns=config.OUTPUT_COLUMNS)

    print(f"  Fetching missing M1 bars: {from_dt} -> {to_dt}")
    rates = mt5.copy_rates_range(actual_symbol, mt5.TIMEFRAME_M1, from_dt, to_dt)
    if rates is None:
        print(f"  [WARN] copy_rates_range failed: {mt5.last_error()}")
        print("  [INFO] Falling back to recent-bar fetch and timestamp filtering")
        df = fetch_missing_by_position(
            actual_symbol, latest_existing_utc, latest_existing_naive
        )
        if df is None:
            return None
        print(f"  [OK] Retrieved {len(df):,} new bars")
        if not df.empty:
            print(f"       New range: {df['timestamp'].min()} -> {df['timestamp'].max()}")
        return df
    if len(rates) == 0:
        print("  [INFO] MT5 returned no new bars")
        return pd.DataFrame(columns=config.OUTPUT_COLUMNS)

    df = normalise_rates(rates)
    df = df[df["timestamp"] > latest_existing_naive]
    print(f"  [OK] Retrieved {len(df):,} new bars")
    if not df.empty:
        print(f"       New range: {df['timestamp'].min()} -> {df['timestamp'].max()}")
    return df


def update_symbol(symbol: str, dry_run: bool = False, category: str = "fx") -> bool:
    print("\n" + "=" * 80)
    print(f"Updating {symbol} M1")
    print("=" * 80)

    path = find_existing_path(symbol, category)
    if path is None:
        print("  [WARN] No existing M1 parquet found. Checked:")
        for candidate in candidate_paths(symbol, category):
            print(f"         {candidate}")
        path = candidate_paths(symbol, category)[0]
        print(f"  [INFO] Bootstrapping maximum MT5 M1 history to: {path}")
        if dry_run:
            print("  [DRY RUN] Would collect maximum MT5 M1 history")
            return True

        df = mt5_utils.collect_maximum_data(symbol, mt5.TIMEFRAME_M1)
        if df is None or df.empty:
            print("  [ERROR] Failed to collect initial MT5 M1 history")
            return False

        mt5_utils.save_dataframe(df, path.with_suffix(""), config.SAVE_FORMAT)
        print(f"  [OK] Bootstrapped {len(df):,} rows")
        return True

    existing = mt5_utils.load_existing_data(path)
    if existing is None or existing.empty:
        print(f"  [ERROR] Existing file is empty or unreadable: {path}")
        return False

    latest = pd.to_datetime(existing["timestamp"]).max()
    print(f"  File: {path}")
    print(f"  Latest existing timestamp: {latest}")

    new_df = fetch_missing_m1(symbol, latest)
    if new_df is None:
        return False
    if new_df.empty:
        print("  [OK] No append needed")
        return True

    merged = mt5_utils.append_new_data(existing, new_df)
    added_rows = len(merged) - len(existing)
    if added_rows <= 0:
        print("  [OK] No new unique rows after merge")
        return True

    print(f"  [OK] Will append {added_rows:,} unique rows")
    print(f"       Updated range: {merged['timestamp'].min()} -> {merged['timestamp'].max()}")

    if dry_run:
        print("  [DRY RUN] Not writing parquet")
        return True

    backup_path = path.with_suffix(".parquet.backup")
    if backup_path.exists():
        backup_path.unlink()
    path.rename(backup_path)
    print(f"  [OK] Backup created: {backup_path.name}")

    try:
        mt5_utils.save_dataframe(merged, path.with_suffix(""), config.SAVE_FORMAT)
    except Exception:
        if path.exists():
            path.unlink()
        backup_path.rename(path)
        print("  [ERROR] Save failed; restored backup")
        raise

    backup_path.unlink()
    print("  [OK] Update complete")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Incrementally append missing MT5 M1 bars to existing FX/indices parquet files."
    )
    parser.add_argument("--symbols", nargs="+", default=None)
    parser.add_argument("--indices", action="store_true", help="Update index symbols instead of FX")
    parser.add_argument("--all", action="store_true", help="Update both FX and index symbols")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.symbols:
        index_set = set(config.INDEX_SYMBOLS)
        symbol_categories = [
            (s, "indices" if s in index_set else "fx") for s in args.symbols
        ]
    elif args.all:
        symbol_categories = [(s, "fx") for s in config.FX_SYMBOLS] + \
                            [(s, "indices") for s in config.INDEX_SYMBOLS]
    elif args.indices:
        symbol_categories = [(s, "indices") for s in config.INDEX_SYMBOLS]
    else:
        symbol_categories = [(s, "fx") for s in config.FX_SYMBOLS]

    all_symbols = [s for s, _ in symbol_categories]

    print("=" * 80)
    print("MT5 M1 INCREMENTAL UPDATE")
    print("=" * 80)
    print(f"Started: {datetime.now()}")
    print(f"Symbols ({len(all_symbols)}): {', '.join(all_symbols)}")
    print(f"Dry run: {args.dry_run}")

    if not mt5_utils.initialize_mt5():
        sys.exit(1)

    results: list[tuple[str, bool]] = []
    try:
        for symbol, category in symbol_categories:
            try:
                results.append((symbol, update_symbol(symbol, dry_run=args.dry_run, category=category)))
            except Exception as exc:
                print(f"  [ERROR] {symbol} failed: {exc}")
                results.append((symbol, False))
    finally:
        mt5_utils.shutdown_mt5()

    ok = [symbol for symbol, success in results if success]
    failed = [symbol for symbol, success in results if not success]

    print("\n" + "=" * 80)
    print("UPDATE SUMMARY")
    print("=" * 80)
    print(f"Success: {len(ok)}/{len(results)}")
    if ok:
        print(f"  [OK] {', '.join(ok)}")
    if failed:
        print(f"  [FAIL] {', '.join(failed)}")
    print(f"Completed: {datetime.now()}")

    if failed:
        sys.exit(2)


if __name__ == "__main__":
    main()
