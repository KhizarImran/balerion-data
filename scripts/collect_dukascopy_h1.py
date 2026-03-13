"""
Dukascopy H1 bulk collector — major FX, US30, XAUUSD, BTCUSD.

Downloads 10 years of 1-hour bid OHLCV bars from Dukascopy Bank for every
symbol in the SYMBOLS table and saves each one to its respective data/ folder:

    data/fx/         — FX pairs  (eurusd_dukascopy_1h.parquet, …)
    data/indices/    — US30, XAUUSD
    data/crypto/     — BTCUSD

Files are named  <ticker_lower>_dukascopy_1h.parquet  to coexist cleanly
alongside any MT5-sourced files.

Usage
-----
    # Collect all symbols (skip any that already have a file)
    python scripts/collect_dukascopy_h1.py

    # Force re-collect everything, overwriting existing files
    python scripts/collect_dukascopy_h1.py --force

    # Collect specific symbols only
    python scripts/collect_dukascopy_h1.py --symbols EURUSD USDJPY BTCUSD

    # Incremental update — merge the last N days for all symbols
    python scripts/collect_dukascopy_h1.py --update

    # Update specific symbols and/or extend the lookback window
    python scripts/collect_dukascopy_h1.py --update --symbols US30 XAUUSD --days 14
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
# Symbol registry
# ---------------------------------------------------------------------------
# Each entry: ticker -> (dukascopy_instrument_string, output_subfolder)
# Subfolder is relative to data/.

SYMBOLS: dict[str, tuple[str, str]] = {
    # --- FX majors ---
    "EURUSD": (I.INSTRUMENT_FX_MAJORS_EUR_USD, "fx"),
    "GBPUSD": (I.INSTRUMENT_FX_MAJORS_GBP_USD, "fx"),
    "USDJPY": (I.INSTRUMENT_FX_MAJORS_USD_JPY, "fx"),
    "AUDUSD": (I.INSTRUMENT_FX_MAJORS_AUD_USD, "fx"),
    "USDCAD": (I.INSTRUMENT_FX_MAJORS_USD_CAD, "fx"),
    "USDCHF": (I.INSTRUMENT_FX_MAJORS_USD_CHF, "fx"),
    "NZDUSD": (I.INSTRUMENT_FX_MAJORS_NZD_USD, "fx"),
    # --- Indices / metals ---
    "US30": (I.INSTRUMENT_IDX_AMERICA_E_D_J_IND, "indices"),
    "XAUUSD": (I.INSTRUMENT_FX_METALS_XAU_USD, "indices"),
    # --- Crypto ---
    "BTCUSD": (I.INSTRUMENT_VCCY_BTC_USD, "crypto"),
}

# How many years of history to request on a full collection run.
# Dukascopy FX majors go back to ~2003; BTC to ~2013; US30 to ~2003.
# We target 10 years (≈3,650 days) as the minimum floor.
TARGET_YEARS = 10

# Annual chunks — keeps progress output readable and avoids large single requests
CHUNK_YEARS = 1

# Offer side — bid is standard for FX backtesting
OFFER_SIDE = dukascopy_python.OFFER_SIDE_BID

INTERVAL = dukascopy_python.INTERVAL_HOUR_1

# Freshness threshold for --update smart-skip (hours)
FRESHNESS_THRESHOLD_HOURS = 1

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"


# ---------------------------------------------------------------------------
# Path helper
# ---------------------------------------------------------------------------


def output_path(ticker: str) -> Path:
    _, subfolder = SYMBOLS[ticker]
    return DATA_DIR / subfolder / f"{ticker.lower()}_dukascopy_1h.parquet"


# ---------------------------------------------------------------------------
# Core helpers  (identical logic to collect_gbpusd_dukascopy.py)
# ---------------------------------------------------------------------------


def _fetch_chunk(instrument: str, start: datetime, end: datetime, label: str) -> pd.DataFrame:
    try:
        df = dukascopy_python.fetch(
            instrument,
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
    """Move timestamp from index → column, ensure UTC, keep OHLCV only."""
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


def _load_existing(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    ts = df["timestamp"]
    if hasattr(ts.dtype, "tz") and ts.dtype.tz is not None:
        df["timestamp"] = ts.dt.tz_convert("UTC")
    else:
        df["timestamp"] = pd.to_datetime(ts, utc=True)
    return df


def _save(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    size_mb = os.path.getsize(path) / (1024 * 1024)
    print(f"    [OK] Saved: {path.relative_to(BASE_DIR)}  ({size_mb:.2f} MB, {len(df):,} rows)")


def _print_summary(ticker: str, df: pd.DataFrame):
    span = df["timestamp"].max() - df["timestamp"].min()
    print(f"    Rows : {len(df):,}")
    print(f"    Range: {df['timestamp'].min():%Y-%m-%d} -> {df['timestamp'].max():%Y-%m-%d} UTC")
    print(f"    Span : {span.days:,} days  (~{span.days / 365.25:.1f} years)")


# ---------------------------------------------------------------------------
# Per-symbol collect
# ---------------------------------------------------------------------------


def collect_symbol(ticker: str, force: bool = False) -> bool:
    """Full collection for one symbol. Returns True on success."""
    instrument, _ = SYMBOLS[ticker]
    path = output_path(ticker)

    if path.exists() and not force:
        print(f"  [SKIP] {ticker}: {path.name} already exists (--force to re-collect)")
        return True

    # Determine start date: 10 years ago (floor), or known data availability
    end_date = datetime.now(tz=timezone.utc).replace(minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=TARGET_YEARS * 365 + 5)  # +5 day buffer

    print(f"\n  {ticker}  ({instrument})")
    print(f"  From: {start_date:%Y-%m-%d}  To: {end_date:%Y-%m-%d}")

    # Build annual chunks
    chunks, cs = [], start_date
    while cs < end_date:
        ce = min(datetime(cs.year + CHUNK_YEARS, cs.month, cs.day, tzinfo=timezone.utc), end_date)
        chunks.append((cs, ce))
        cs = ce

    frames = []
    for i, (cs, ce) in enumerate(chunks, 1):
        label = f"{cs:%Y-%m-%d} -> {ce:%Y-%m-%d}  [{i}/{len(chunks)}]"
        chunk = _fetch_chunk(instrument, cs, ce, label)
        if not chunk.empty:
            frames.append(_normalise(chunk))

    if not frames:
        print(f"  [ERROR] {ticker}: no data returned — skipping")
        return False

    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["timestamp"], keep="last")
    df = df.sort_values("timestamp").reset_index(drop=True)

    _print_summary(ticker, df)
    _save(df, path)
    return True


# ---------------------------------------------------------------------------
# Per-symbol update
# ---------------------------------------------------------------------------


def update_symbol(ticker: str, days: int = 7, force: bool = False) -> bool:
    """Incremental update for one symbol. Returns True on success."""
    instrument, _ = SYMBOLS[ticker]
    path = output_path(ticker)

    if not path.exists():
        print(f"  [WARN] {ticker}: no existing file — running full collection")
        return collect_symbol(ticker, force=True)

    existing = _load_existing(path)
    latest = existing["timestamp"].max()
    age_h = (datetime.now(tz=timezone.utc) - latest).total_seconds() / 3600

    print(
        f"  {ticker}: {len(existing):,} rows, latest {latest:%Y-%m-%d %H:%M} UTC ({age_h:.1f}h ago)"
    )

    if age_h < FRESHNESS_THRESHOLD_HOURS and not force:
        print(f"    [SKIP] Data is fresh — skipping (use --force to override)")
        return True

    fetch_from = min(
        latest - timedelta(hours=1), datetime.now(tz=timezone.utc) - timedelta(days=days)
    )
    fetch_to = datetime.now(tz=timezone.utc).replace(minute=0, second=0, microsecond=0)

    label = f"{fetch_from:%Y-%m-%d} -> {fetch_to:%Y-%m-%d}"
    new_df = _fetch_chunk(instrument, fetch_from, fetch_to, label)
    if new_df.empty:
        print(f"    [WARN] {ticker}: no new data returned")
        return False

    new_df = _normalise(new_df)

    combined = pd.concat([existing, new_df], ignore_index=True)
    before = len(combined)
    combined = combined.drop_duplicates(subset=["timestamp"], keep="last")
    combined = combined.sort_values("timestamp").reset_index(drop=True)
    net_new = len(combined) - len(existing)
    dupes = before - len(combined)

    print(
        f"    Merged: {len(existing):,} + {len(new_df):,} → {len(combined):,}  ({net_new:+,} new, {dupes} dupes)"
    )

    if net_new <= 0:
        print(f"    [INFO] No new bars — file unchanged")
        return True

    backup = path.with_suffix(".parquet.backup")
    path.rename(backup)
    try:
        _save(combined, path)
        backup.unlink()
    except Exception as exc:
        print(f"    [ERROR] Save failed ({exc}) — restoring backup")
        backup.rename(path)
        return False

    return True


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_collect(tickers: list[str], force: bool):
    print(f"\n{'=' * 70}")
    print(f"Dukascopy H1 — Full Collection")
    print(f"Started : {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"Symbols : {', '.join(tickers)}")
    print(f"Target  : {TARGET_YEARS} years of H1 bars per symbol")
    print(f"{'=' * 70}")

    results = {}
    for ticker in tickers:
        results[ticker] = collect_symbol(ticker, force=force)

    _print_run_summary(results)


def run_update(tickers: list[str], days: int, force: bool):
    print(f"\n{'=' * 70}")
    print(f"Dukascopy H1 — Incremental Update  (last {days} days)")
    print(f"Started : {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"Symbols : {', '.join(tickers)}")
    print(f"{'=' * 70}")

    results = {}
    for ticker in tickers:
        results[ticker] = update_symbol(ticker, days=days, force=force)

    _print_run_summary(results)


def _print_run_summary(results: dict[str, bool]):
    ok = [t for t, v in results.items() if v]
    err = [t for t, v in results.items() if not v]
    print(f"\n{'=' * 70}")
    print(f"  Done  : {len(ok)}/{len(results)} symbols succeeded")
    if ok:
        print(f"  OK    : {', '.join(ok)}")
    if err:
        print(f"  FAILED: {', '.join(err)}")
    print(f"{'=' * 70}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    all_tickers = list(SYMBOLS.keys())

    parser = argparse.ArgumentParser(
        description="Collect or update Dukascopy H1 data for major FX, indices, and crypto",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        metavar="TICKER",
        default=None,
        help=f"Symbols to process (default: all). Choices: {', '.join(all_tickers)}",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Incremental update: merge recent bars into existing files",
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
        help="Overwrite existing files / skip freshness check",
    )
    args = parser.parse_args()

    # Validate and resolve symbol list
    if args.symbols:
        unknown = [s for s in args.symbols if s.upper() not in SYMBOLS]
        if unknown:
            parser.error(f"Unknown symbols: {', '.join(unknown)}. Valid: {', '.join(all_tickers)}")
        tickers = [s.upper() for s in args.symbols]
    else:
        tickers = all_tickers

    if args.update:
        run_update(tickers, days=args.days, force=args.force)
    else:
        run_collect(tickers, force=args.force)


if __name__ == "__main__":
    main()
