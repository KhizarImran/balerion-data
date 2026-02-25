"""
Initial Historical Data Collection Script
==========================================
Collects maximum available 1-minute OHLCV data for all configured symbols.

This script should be run once to establish the initial dataset.
After this, use 'update_weekly_data.py' for incremental updates.

Usage:
    python collect_historical_data.py

Symbols collected:
    FX: EURUSD, USDJPY, GBPUSD, EURGBP, USDCAD, AUDNZD
    Indices: US30, XAUUSD
"""

import sys
from datetime import datetime
import config
import mt5_utils


def collect_all_symbols():
    """Collect historical data for all configured symbols"""
    
    print("\n" + "="*80)
    print("MT5 HISTORICAL DATA COLLECTION")
    print("="*80)
    print(f"Started at: {datetime.now()}")
    print(f"Timeframe: 1 Minute")
    print(f"Save format: {config.SAVE_FORMAT}")
    
    # Initialize MT5
    if not mt5_utils.initialize_mt5():
        return
    
    try:
        # Get MT5 info
        import MetaTrader5 as mt5
        account_info = mt5.account_info()
        if account_info:
            print(f"Connected to: {account_info.server} (Account: {account_info.login})")
        
        timeframe = mt5_utils.get_timeframe_constant(config.TIMEFRAME)
        
        # Collect FX symbols
        print("\n" + "="*80)
        print("COLLECTING FX SYMBOLS")
        print("="*80)
        
        fx_success = []
        fx_failed = []
        
        for symbol in config.FX_SYMBOLS:
            try:
                df = mt5_utils.collect_maximum_data(symbol, timeframe)
                
                if df is not None and not df.empty:
                    filepath = mt5_utils.get_data_filepath(symbol, "fx")
                    mt5_utils.save_dataframe(df, filepath, config.SAVE_FORMAT)
                    fx_success.append(symbol)
                else:
                    fx_failed.append(symbol)
                    
            except Exception as e:
                print(f"  [ERROR] Error collecting {symbol}: {e}")
                fx_failed.append(symbol)
        
        # Collect Index symbols
        print("\n" + "="*80)
        print("COLLECTING INDEX SYMBOLS")
        print("="*80)
        
        idx_success = []
        idx_failed = []
        
        for symbol in config.INDEX_SYMBOLS:
            try:
                df = mt5_utils.collect_maximum_data(symbol, timeframe)
                
                if df is not None and not df.empty:
                    filepath = mt5_utils.get_data_filepath(symbol, "indices")
                    mt5_utils.save_dataframe(df, filepath, config.SAVE_FORMAT)
                    idx_success.append(symbol)
                else:
                    idx_failed.append(symbol)
                    
            except Exception as e:
                print(f"  [ERROR] Error collecting {symbol}: {e}")
                idx_failed.append(symbol)
        
        # Print summary
        print("\n" + "="*80)
        print("COLLECTION SUMMARY")
        print("="*80)
        
        print(f"\nFX Symbols:")
        print(f"  [OK] Success: {len(fx_success)}/{len(config.FX_SYMBOLS)}")
        if fx_success:
            print(f"    {', '.join(fx_success)}")
        if fx_failed:
            print(f"  [ERROR] Failed: {len(fx_failed)}/{len(config.FX_SYMBOLS)}")
            print(f"    {', '.join(fx_failed)}")
        
        print(f"\nIndex Symbols:")
        print(f"  [OK] Success: {len(idx_success)}/{len(config.INDEX_SYMBOLS)}")
        if idx_success:
            print(f"    {', '.join(idx_success)}")
        if idx_failed:
            print(f"  [ERROR] Failed: {len(idx_failed)}/{len(config.INDEX_SYMBOLS)}")
            print(f"    {', '.join(idx_failed)}")
        
        total_success = len(fx_success) + len(idx_success)
        total_symbols = len(config.FX_SYMBOLS) + len(config.INDEX_SYMBOLS)
        
        print(f"\nOverall: {total_success}/{total_symbols} symbols collected successfully")
        print(f"\nData saved to:")
        print(f"  FX: {config.FX_DIR}")
        print(f"  Indices: {config.INDICES_DIR}")
        
        print(f"\nCompleted at: {datetime.now()}")
        
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        mt5_utils.shutdown_mt5()


def main():
    """Main entry point"""
    try:
        collect_all_symbols()
    except KeyboardInterrupt:
        print("\n\n[WARN] Collection interrupted by user")
        mt5_utils.shutdown_mt5()
        sys.exit(1)


if __name__ == "__main__":
    main()

