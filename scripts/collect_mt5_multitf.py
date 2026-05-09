"""
MT5 multi-timeframe data collector.

Collects native MT5 bars at any supported timeframe for specified symbols
and saves to data/<category>/<symbol>/<symbol>_mt5_<tf>.parquet.

Usage:
    uv run python scripts/collect_mt5_multitf.py
    uv run python scripts/collect_mt5_multitf.py --symbols USDJPY XAUUSD US30 --tfs M15 H4
    uv run python scripts/collect_mt5_multitf.py --force   # overwrite existing
"""

import sys
import argparse
from pathlib import Path

import mt5_utils
import config

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_SYMBOLS   = config.FX_SYMBOLS + config.INDEX_SYMBOLS
DEFAULT_TIMEFRAMES = ["M15", "H4"]

# Map MT5 timeframe string → label used in filename
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


def _out_path(symbol: str, tf_str: str) -> Path:
    cat = mt5_utils.get_symbol_category(symbol)
    sym = symbol.lower()
    label = _TF_LABEL.get(tf_str, tf_str.lower())
    if cat == "fx":
        folder = config.FX_DIR / sym
    else:
        folder = config.INDICES_DIR / sym
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{sym}_mt5_{label}"   # save_dataframe appends .parquet


def main() -> None:
    parser = argparse.ArgumentParser(description="MT5 multi-timeframe collector")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS, metavar="SYM")
    parser.add_argument("--tfs",     nargs="+", default=DEFAULT_TIMEFRAMES, metavar="TF",
                        help="MT5 timeframe strings: M1 M5 M15 M30 H1 H4 D1")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()

    print("=" * 60)
    print("  MT5 Multi-Timeframe Collector")
    print(f"  Symbols    : {args.symbols}")
    print(f"  Timeframes : {args.tfs}")
    print("=" * 60)

    if not mt5_utils.initialize_mt5():
        sys.exit(1)

    try:
        for symbol in args.symbols:
            for tf_str in args.tfs:
                out = _out_path(symbol, tf_str)
                parquet = out.with_suffix(".parquet")

                if parquet.exists() and not args.force:
                    import pandas as pd
                    existing = pd.read_parquet(parquet)
                    print(f"\n[SKIP] {symbol} {tf_str}: {parquet.name} exists "
                          f"({len(existing):,} bars, last: {existing['timestamp'].iloc[-1]}) "
                          f"— use --force to re-collect")
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
