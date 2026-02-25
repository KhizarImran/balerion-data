"""
Weekly Data Update Script
==========================
Updates existing datasets with the latest week's data.
Handles deduplication automatically.

This script should be run weekly to keep your datasets up to date.
It will:
1. Load existing parquet files
2. Fetch new data from the last known timestamp
3. Merge and deduplicate
4. Save back to parquet

Usage:
    python update_weekly_data.py

Optional arguments:
    --days N    Fetch last N days (default: 7)
    --force     Force update even if recent data exists

Examples:
    python update_weekly_data.py
    python update_weekly_data.py --days 14
"""

import sys
import argparse
from datetime import datetime, timedelta
import pandas as pd
import config
import mt5_utils
import MetaTrader5 as mt5
from pathlib import Path


def collect_recent_data(symbol: str, timeframe, days: int = 7) -> pd.DataFrame:
    """
    Collect recent data for a symbol
    
    Args:
        symbol: Trading symbol
        timeframe: MT5 timeframe constant
        days: Number of days to fetch (default: 7)
        
    Returns:
        DataFrame with recent OHLCV data or None if failed
    """
    print(f"\n{'='*80}")
    print(f"Updating: {symbol}")
    print(f"{'='*80}")
    
    # Find the actual symbol name
    actual_symbol = mt5_utils.find_symbol(symbol)
    if actual_symbol is None:
        print(f"  [ERROR] Symbol {symbol} not found in MT5")
        return None
    
    if actual_symbol != symbol:
        print(f"  [INFO] Using symbol: {actual_symbol} (mapped from {symbol})")
    
    # Calculate date range
    from_date = datetime.now() - timedelta(days=days)
    
    print(f"  Fetching data from last {days} days...")
    print(f"  Date range: {from_date} to {datetime.now()}")
    
    # Fetch data using copy_rates_from_pos (most reliable for recent data)
    # Calculate approximate number of bars (1 minute bars)
    # Account for weekends and market closures (assume ~70% uptime)
    bars_to_fetch = int(days * 24 * 60 * 0.7) + 100  # Add buffer
    
    rates = mt5.copy_rates_from_pos(actual_symbol, timeframe, 0, bars_to_fetch)
    
    if rates is None or len(rates) == 0:
        print(f"  [ERROR] Failed to get rates, error: {mt5.last_error()}")
        return None
    
    print(f"  [OK] Retrieved {len(rates):,} bars")
    
    # Convert to DataFrame
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Filter to requested date range
    df = df[df['time'] >= from_date]
    
    print(f"  [OK] Filtered to {len(df):,} bars in date range")
    print(f"    Actual range: {df['time'].min()} to {df['time'].max()}")
    
    # Rename columns
    df = df.rename(columns={
        'time': 'timestamp',
        'tick_volume': 'volume',
    })
    
    # Select output columns
    columns_to_keep = config.OUTPUT_COLUMNS.copy()
    if 'spread' in df.columns and 'spread' in config.OPTIONAL_COLUMNS:
        columns_to_keep.append('spread')
    if 'real_volume' in df.columns and 'real_volume' in config.OPTIONAL_COLUMNS:
        columns_to_keep.append('real_volume')
    
    df = df[[col for col in columns_to_keep if col in df.columns]]
    
    return df


def update_symbol(symbol: str, category: str, timeframe, days: int, force: bool = False):
    """
    Update data for a single symbol
    
    Args:
        symbol: Symbol to update
        category: "fx" or "indices"
        timeframe: MT5 timeframe constant
        days: Number of days to fetch
        force: Force update even if recent
        
    Returns:
        True if successful, False otherwise
    """
    filepath = mt5_utils.get_data_filepath(symbol, category)
    
    # Load existing data
    existing_df = mt5_utils.load_existing_data(filepath)
    
    if existing_df is None:
        print(f"  [WARN] No existing data found for {symbol}")
        print(f"  [INFO] Run 'collect_historical_data.py' first to create initial dataset")
        return False
    
    # Check if update is needed
    if not force:
        latest_timestamp = existing_df['timestamp'].max()
        hours_since_update = (datetime.now() - latest_timestamp).total_seconds() / 3600
        
        if hours_since_update < 12:  # Less than 12 hours old
            print(f"  [INFO] Data is recent (last update: {latest_timestamp})")
            print(f"  [INFO] Skipping update (use --force to override)")
            return True
    
    # Collect new data
    new_df = collect_recent_data(symbol, timeframe, days)
    
    if new_df is None or new_df.empty:
        print(f"  [ERROR] Failed to collect new data")
        return False
    
    # Merge with existing data
    print(f"\n  Merging data...")
    merged_df = mt5_utils.append_new_data(existing_df, new_df)
    
    # Check if there's actually new data
    new_rows = len(merged_df) - len(existing_df)
    if new_rows <= 0:
        print(f"  [INFO] No new data to add")
        return True
    
    print(f"  [OK] Added {new_rows:,} new rows")
    print(f"    New date range: {merged_df['timestamp'].min()} to {merged_df['timestamp'].max()}")
    
    # Backup old file
    if filepath.exists():
        backup_path = filepath.with_suffix('.parquet.backup')
        filepath.rename(backup_path)
        print(f"  [OK] Created backup: {backup_path.name}")
    
    # Save updated data
    mt5_utils.save_dataframe(merged_df, filepath, config.SAVE_FORMAT)
    
    # Remove backup after successful save
    if backup_path.exists():
        backup_path.unlink()
    
    return True


def update_all_symbols(days: int = 7, force: bool = False):
    """
    Update all configured symbols
    
    Args:
        days: Number of days to fetch (default: 7)
        force: Force update even if recent
    """
    print("\n" + "="*80)
    print("MT5 WEEKLY DATA UPDATE")
    print("="*80)
    print(f"Started at: {datetime.now()}")
    print(f"Fetching last {days} days")
    print(f"Force update: {force}")
    
    # Initialize MT5
    if not mt5_utils.initialize_mt5():
        return
    
    try:
        # Get MT5 info
        account_info = mt5.account_info()
        if account_info:
            print(f"Connected to: {account_info.server} (Account: {account_info.login})")
        
        timeframe = mt5_utils.get_timeframe_constant(config.TIMEFRAME)
        
        # Update FX symbols
        print("\n" + "="*80)
        print("UPDATING FX SYMBOLS")
        print("="*80)
        
        fx_success = []
        fx_failed = []
        
        for symbol in config.FX_SYMBOLS:
            try:
                if update_symbol(symbol, "fx", timeframe, days, force):
                    fx_success.append(symbol)
                else:
                    fx_failed.append(symbol)
            except Exception as e:
                print(f"  [ERROR] Error updating {symbol}: {e}")
                fx_failed.append(symbol)
        
        # Update Index symbols
        print("\n" + "="*80)
        print("UPDATING INDEX SYMBOLS")
        print("="*80)
        
        idx_success = []
        idx_failed = []
        
        for symbol in config.INDEX_SYMBOLS:
            try:
                if update_symbol(symbol, "indices", timeframe, days, force):
                    idx_success.append(symbol)
                else:
                    idx_failed.append(symbol)
            except Exception as e:
                print(f"  [ERROR] Error updating {symbol}: {e}")
                idx_failed.append(symbol)
        
        # Print summary
        print("\n" + "="*80)
        print("UPDATE SUMMARY")
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
        
        print(f"\nOverall: {total_success}/{total_symbols} symbols updated successfully")
        print(f"\nCompleted at: {datetime.now()}")
        
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        mt5_utils.shutdown_mt5()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Update MT5 data with recent weekly data",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Number of days to fetch (default: 7)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force update even if data is recent'
    )
    
    args = parser.parse_args()
    
    try:
        update_all_symbols(days=args.days, force=args.force)
    except KeyboardInterrupt:
        print("\n\n[WARN] Update interrupted by user")
        mt5_utils.shutdown_mt5()
        sys.exit(1)


if __name__ == "__main__":
    main()

