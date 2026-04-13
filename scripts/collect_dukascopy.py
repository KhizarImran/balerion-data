"""
Dukascopy multi-timeframe collector — FX, indices, crypto.

Downloads up to 10 years of OHLCV bars from Dukascopy Bank for any supported
timeframe and saves to data/<subfolder>/<symbol>/<symbol>_dukascopy_<tf>.parquet.

Supported timeframes
--------------------
    1min  5min  10min  15min  30min  1h  4h  1d  1w  1mo

Usage
-----
    # Download USDJPY 15-min (full history)
    uv run python scripts/collect_dukascopy.py --symbols USDJPY --tf 15min

    # Download EURUSD and GBPUSD at 30-min
    uv run python scripts/collect_dukascopy.py --symbols EURUSD GBPUSD --tf 30min

    # Download all symbols at 1h (equivalent to collect_dukascopy_h1.py)
    uv run python scripts/collect_dukascopy.py --tf 1h

    # Force re-download (overwrite existing file)
    uv run python scripts/collect_dukascopy.py --symbols USDJPY --tf 15min --force

    # Incremental update — merge the last N days
    uv run python scripts/collect_dukascopy.py --symbols USDJPY --tf 15min --update --days 7
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

SYMBOLS: dict[str, tuple[str, str]] = {
    # --- FX majors ---
    "EURUSD": (I.INSTRUMENT_FX_MAJORS_EUR_USD, "fx"),
    "GBPUSD": (I.INSTRUMENT_FX_MAJORS_GBP_USD, "fx"),
    "USDJPY": (I.INSTRUMENT_FX_MAJORS_USD_JPY, "fx"),
    "AUDUSD": (I.INSTRUMENT_FX_MAJORS_AUD_USD, "fx"),
    "USDCAD": (I.INSTRUMENT_FX_MAJORS_USD_CAD, "fx"),
    "USDCHF": (I.INSTRUMENT_FX_MAJORS_USD_CHF, "fx"),
    "NZDUSD": (I.INSTRUMENT_FX_MAJORS_NZD_USD, "fx"),
    # --- FX crosses ---
    "EURGBP": (I.INSTRUMENT_FX_CROSSES_EUR_GBP, "fx"),
    "AUDNZD": (I.INSTRUMENT_FX_CROSSES_AUD_NZD, "fx"),
    "EURCHF": (I.INSTRUMENT_FX_CROSSES_EUR_CHF, "fx"),
    "EURCAD": (I.INSTRUMENT_FX_CROSSES_EUR_CAD, "fx"),
    "EURAUD": (I.INSTRUMENT_FX_CROSSES_EUR_AUD, "fx"),
    "EURNZD": (I.INSTRUMENT_FX_CROSSES_EUR_NZD, "fx"),
    "GBPCHF": (I.INSTRUMENT_FX_CROSSES_GBP_CHF, "fx"),
    "GBPCAD": (I.INSTRUMENT_FX_CROSSES_GBP_CAD, "fx"),
    "GBPAUD": (I.INSTRUMENT_FX_CROSSES_GBP_AUD, "fx"),
    "GBPNZD": (I.INSTRUMENT_FX_CROSSES_GBP_NZD, "fx"),
    "GBPJPY": (I.INSTRUMENT_FX_CROSSES_GBP_JPY, "fx"),
    "EURJPY": (I.INSTRUMENT_FX_CROSSES_EUR_JPY, "fx"),
    "AUDJPY": (I.INSTRUMENT_FX_CROSSES_AUD_JPY, "fx"),
    "CADJPY": (I.INSTRUMENT_FX_CROSSES_CAD_JPY, "fx"),
    "CHFJPY": (I.INSTRUMENT_FX_CROSSES_CHF_JPY, "fx"),
    "NZDJPY": (I.INSTRUMENT_FX_CROSSES_NZD_JPY, "fx"),
    "AUDCAD": (I.INSTRUMENT_FX_CROSSES_AUD_CAD, "fx"),
    "AUDCHF": (I.INSTRUMENT_FX_CROSSES_AUD_CHF, "fx"),
    "NZDCAD": (I.INSTRUMENT_FX_CROSSES_NZD_CAD, "fx"),
    "NZDCHF": (I.INSTRUMENT_FX_CROSSES_NZD_CHF, "fx"),
    "CADCHF": (I.INSTRUMENT_FX_CROSSES_CAD_CHF, "fx"),
    # --- Indices / metals ---
    "US30": (I.INSTRUMENT_IDX_AMERICA_E_D_J_IND, "indices"),
    "SPX500": (I.INSTRUMENT_IDX_AMERICA_E_SANDP_500, "indices"),
    "NAS100": (I.INSTRUMENT_IDX_AMERICA_E_NQ_100, "indices"),
    "GER40": (I.INSTRUMENT_IDX_EUROPE_E_DAAX, "indices"),
    "UK100": (I.INSTRUMENT_IDX_EUROPE_E_FUTSEE_100, "indices"),
    "XAUUSD": (I.INSTRUMENT_FX_METALS_XAU_USD, "indices"),
    # --- Crypto ---
    "BTCUSD": (I.INSTRUMENT_VCCY_BTC_USD, "crypto"),
}

# ---------------------------------------------------------------------------
# Timeframe registry
# ---------------------------------------------------------------------------
# Maps the user-facing label → (dukascopy interval constant, chunk size in days)
# Smaller timeframes produce far more rows, so use shorter annual chunks to
# keep each request manageable and progress readable.

TF_MAP: dict[str, tuple[object, int]] = {
    "1min": (dukascopy_python.INTERVAL_MIN_1, 7),
    "5min": (dukascopy_python.INTERVAL_MIN_5, 30),
    "10min": (dukascopy_python.INTERVAL_MIN_10, 60),
    "15min": (dukascopy_python.INTERVAL_MIN_15, 90),
    "30min": (dukascopy_python.INTERVAL_MIN_30, 180),
    "1h": (dukascopy_python.INTERVAL_HOUR_1, 365),
    "4h": (dukascopy_python.INTERVAL_HOUR_4, 365),
    "1d": (dukascopy_python.INTERVAL_DAY_1, 365),
    "1w": (dukascopy_python.INTERVAL_WEEK_1, 365),
    "1mo": (dukascopy_python.INTERVAL_MONTH_1, 365),
}

# How many years back to request on a full collection run
TARGET_YEARS = 10

# Offer side — bid is standard for FX backtesting
OFFER_SIDE = dukascopy_python.OFFER_SIDE_BID

# Freshness threshold for --update smart-skip
FRESHNESS_THRESHOLD_HOURS = 1

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"


# ---------------------------------------------------------------------------
# Path helper
# ---------------------------------------------------------------------------


def output_path(ticker: str, tf_label: str) -> Path:
    _, subfolder = SYMBOLS[ticker]
    sym = ticker.lower()
    return DATA_DIR / subfolder / sym / f"{sym}_dukascopy_{tf_label}.parquet"


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def _fetch_chunk(
    instrument: str,
    interval,
    start: datetime,
    end: datetime,
    label: str,
) -> pd.DataFrame:
    try:
        df = dukascopy_python.fetch(
            instrument,
            interval,
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


def _print_summary(df: pd.DataFrame):
    span = df["timestamp"].max() - df["timestamp"].min()
    print(f"    Rows : {len(df):,}")
    print(f"    Range: {df['timestamp'].min():%Y-%m-%d} -> {df['timestamp'].max():%Y-%m-%d} UTC")
    print(f"    Span : {span.days:,} days  (~{span.days / 365.25:.1f} years)")


# ---------------------------------------------------------------------------
# Per-symbol collect
# ---------------------------------------------------------------------------


def collect_symbol(ticker: str, tf_label: str, force: bool = False) -> bool:
    """Full collection for one symbol + timeframe. Returns True on success."""
    instrument, _ = SYMBOLS[ticker]
    interval, chunk_days = TF_MAP[tf_label]
    path = output_path(ticker, tf_label)

    if path.exists() and not force:
        print(f"  [SKIP] {ticker} {tf_label}: {path.name} already exists (--force to re-collect)")
        return True

    end_date = datetime.now(tz=timezone.utc).replace(minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=TARGET_YEARS * 365 + 5)

    print(f"\n  {ticker} {tf_label}  ({instrument})")
    print(f"  From: {start_date:%Y-%m-%d}  To: {end_date:%Y-%m-%d}  chunk={chunk_days}d")

    # Build date chunks
    chunks, cs = [], start_date
    while cs < end_date:
        ce = min(cs + timedelta(days=chunk_days), end_date)
        chunks.append((cs, ce))
        cs = ce

    frames = []
    for i, (cs, ce) in enumerate(chunks, 1):
        label = f"{cs:%Y-%m-%d} -> {ce:%Y-%m-%d}  [{i}/{len(chunks)}]"
        chunk = _fetch_chunk(instrument, interval, cs, ce, label)
        if not chunk.empty:
            frames.append(_normalise(chunk))

    if not frames:
        print(f"  [ERROR] {ticker} {tf_label}: no data returned — skipping")
        return False

    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["timestamp"], keep="last")
    df = df.sort_values("timestamp").reset_index(drop=True)

    _print_summary(df)
    _save(df, path)
    return True


# ---------------------------------------------------------------------------
# Per-symbol update
# ---------------------------------------------------------------------------


def update_symbol(ticker: str, tf_label: str, days: int = 7, force: bool = False) -> bool:
    """Incremental update for one symbol + timeframe. Returns True on success."""
    instrument, _ = SYMBOLS[ticker]
    interval, _ = TF_MAP[tf_label]
    path = output_path(ticker, tf_label)

    if not path.exists():
        print(f"  [WARN] {ticker} {tf_label}: no existing file — running full collection")
        return collect_symbol(ticker, tf_label, force=True)

    existing = _load_existing(path)
    latest = existing["timestamp"].max()
    age_h = (datetime.now(tz=timezone.utc) - latest).total_seconds() / 3600

    print(
        f"  {ticker} {tf_label}: {len(existing):,} rows, "
        f"latest {latest:%Y-%m-%d %H:%M} UTC ({age_h:.1f}h ago)"
    )

    if age_h < FRESHNESS_THRESHOLD_HOURS and not force:
        print(f"    [SKIP] Data is fresh — skipping (use --force to override)")
        return True

    fetch_from = min(
        latest - timedelta(hours=1),
        datetime.now(tz=timezone.utc) - timedelta(days=days),
    )
    fetch_to = datetime.now(tz=timezone.utc).replace(minute=0, second=0, microsecond=0)

    label = f"{fetch_from:%Y-%m-%d} -> {fetch_to:%Y-%m-%d}"
    new_df = _fetch_chunk(instrument, interval, fetch_from, fetch_to, label)
    if new_df.empty:
        print(f"    [WARN] {ticker} {tf_label}: no new data returned")
        return False

    new_df = _normalise(new_df)

    combined = pd.concat([existing, new_df], ignore_index=True)
    before = len(combined)
    combined = combined.drop_duplicates(subset=["timestamp"], keep="last")
    combined = combined.sort_values("timestamp").reset_index(drop=True)
    net_new = len(combined) - len(existing)
    dupes = before - len(combined)

    print(
        f"    Merged: {len(existing):,} + {len(new_df):,} → {len(combined):,}  "
        f"({net_new:+,} new, {dupes} dupes)"
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
# Orchestrators
# ---------------------------------------------------------------------------


def run_collect(tickers: list[str], tf_label: str, force: bool):
    print(f"\n{'=' * 70}")
    print(f"Dukascopy {tf_label.upper()} — Full Collection")
    print(f"Started : {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"Symbols : {', '.join(tickers)}")
    print(f"Target  : {TARGET_YEARS} years per symbol")
    print(f"{'=' * 70}")

    results = {}
    for ticker in tickers:
        results[ticker] = collect_symbol(ticker, tf_label, force=force)

    _print_run_summary(results)


def run_update(tickers: list[str], tf_label: str, days: int, force: bool):
    print(f"\n{'=' * 70}")
    print(f"Dukascopy {tf_label.upper()} — Incremental Update  (last {days} days)")
    print(f"Started : {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"Symbols : {', '.join(tickers)}")
    print(f"{'=' * 70}")

    results = {}
    for ticker in tickers:
        results[ticker] = update_symbol(ticker, tf_label, days=days, force=force)

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
    all_tfs = list(TF_MAP.keys())

    parser = argparse.ArgumentParser(
        description="Collect or update Dukascopy data at any supported timeframe",
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
        "--tf",
        metavar="TIMEFRAME",
        default="1h",
        help=f"Timeframe to download (default: 1h). Choices: {', '.join(all_tfs)}",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Incremental update: merge recent bars into existing file",
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

    # Validate timeframe
    tf_label = args.tf.lower()
    if tf_label not in TF_MAP:
        parser.error(f"Unknown timeframe: {args.tf!r}. Valid choices: {', '.join(all_tfs)}")

    # Validate symbols
    if args.symbols:
        unknown = [s for s in args.symbols if s.upper() not in SYMBOLS]
        if unknown:
            parser.error(f"Unknown symbols: {', '.join(unknown)}. Valid: {', '.join(all_tickers)}")
        tickers = [s.upper() for s in args.symbols]
    else:
        tickers = all_tickers

    if args.update:
        run_update(tickers, tf_label, days=args.days, force=args.force)
    else:
        run_collect(tickers, tf_label, force=args.force)


if __name__ == "__main__":
    main()
