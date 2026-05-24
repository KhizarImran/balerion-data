"""
Historical Data Collection Script
===================================
Collects maximum available OHLCV data for all configured symbols
at 5-minute, 1-hour, and daily timeframes from MT5.

Usage:
    python scripts/collect_historical_data.py
"""

import sys
from datetime import datetime
import config
import mt5_utils


TIMEFRAMES = [
    ("M5",  "5min"),
    ("H1",  "1h"),
    ("D1",  "1d"),
]


def collect_all_symbols():
    print("\n" + "=" * 80)
    print("MT5 HISTORICAL DATA COLLECTION")
    print("=" * 80)
    print(f"Started at: {datetime.now()}")
    print(f"Timeframes: {', '.join(label for _, label in TIMEFRAMES)}")

    if not mt5_utils.initialize_mt5():
        return

    try:
        import MetaTrader5 as mt5
        account_info = mt5.account_info()
        if account_info:
            print(f"Connected to: {account_info.server} (Account: {account_info.login})")

        all_symbols = [("fx", s) for s in config.FX_SYMBOLS] + \
                      [("indices", s) for s in config.INDEX_SYMBOLS]

        results = []

        for category, symbol in all_symbols:
            for mt5_tf, tf_label in TIMEFRAMES:
                timeframe = mt5_utils.get_timeframe_constant(mt5_tf)
                df = mt5_utils.collect_maximum_data(symbol, timeframe)
                if df is not None and not df.empty:
                    filepath = mt5_utils.get_data_filepath(symbol, category, tf_label)
                    mt5_utils.save_dataframe(df, filepath, config.SAVE_FORMAT)
                    results.append((symbol, tf_label, True))
                else:
                    results.append((symbol, tf_label, False))

        print("\n" + "=" * 80)
        print("COLLECTION SUMMARY")
        print("=" * 80)
        ok  = [(s, tf) for s, tf, success in results if success]
        err = [(s, tf) for s, tf, success in results if not success]
        print(f"Success: {len(ok)}/{len(results)}")
        for s, tf in ok:
            print(f"  [OK]    {s} {tf}")
        for s, tf in err:
            print(f"  [FAIL]  {s} {tf}")
        print(f"\nCompleted at: {datetime.now()}")

    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        mt5_utils.shutdown_mt5()


def main():
    try:
        collect_all_symbols()
    except KeyboardInterrupt:
        print("\n[WARN] Interrupted by user")
        mt5_utils.shutdown_mt5()
        sys.exit(1)


if __name__ == "__main__":
    main()
