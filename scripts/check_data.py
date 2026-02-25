"""
Data Quality Checker
====================
Checks the quality and integrity of collected data.

Usage:
    python check_data.py
"""

import pandas as pd
from pathlib import Path
import config


def check_file(filepath: Path):
    """Check a single data file"""
    if not filepath.exists():
        print(f"  ❌ File not found: {filepath.name}")
        return False
    
    try:
        df = pd.read_parquet(filepath)
        
        # Basic stats
        print(f"  ✓ {filepath.name}")
        print(f"    Rows: {len(df):,}")
        print(f"    Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        time_span = (df['timestamp'].max() - df['timestamp'].min())
        print(f"    Time span: {time_span.days} days ({time_span.days/365.25:.2f} years)")
        
        # Check for duplicates
        duplicates = df['timestamp'].duplicated().sum()
        if duplicates > 0:
            print(f"    ⚠ Duplicates: {duplicates:,}")
        
        # Check for missing values
        missing = df.isnull().sum().sum()
        if missing > 0:
            print(f"    ⚠ Missing values: {missing:,}")
        
        # Check for gaps
        df_sorted = df.sort_values('timestamp').copy()
        df_sorted['time_diff'] = df_sorted['timestamp'].diff()
        
        # Gaps larger than 2 hours (accounting for weekends and market closures)
        large_gaps = df_sorted[df_sorted['time_diff'] > pd.Timedelta(hours=2)]
        if len(large_gaps) > 0:
            print(f"    ℹ Large gaps (>2h): {len(large_gaps)}")
        
        # File size
        file_size_mb = filepath.stat().st_size / (1024 * 1024)
        print(f"    File size: {file_size_mb:.2f} MB")
        
        # Price stats
        print(f"    Price range: {df['low'].min():.4f} - {df['high'].max():.4f}")
        
        print()
        return True
        
    except Exception as e:
        print(f"  ❌ Error reading {filepath.name}: {e}")
        print()
        return False


def check_all_data():
    """Check all data files"""
    print("\n" + "="*80)
    print("DATA QUALITY REPORT")
    print("="*80)
    
    # Check FX symbols
    print("\nFX SYMBOLS:")
    print("-" * 80)
    
    fx_checked = 0
    fx_ok = 0
    
    for symbol in config.FX_SYMBOLS:
        filepath = config.FX_DIR / f"{symbol.lower()}_1m.parquet"
        fx_checked += 1
        if check_file(filepath):
            fx_ok += 1
    
    # Check Index symbols
    print("\nINDEX SYMBOLS:")
    print("-" * 80)
    
    idx_checked = 0
    idx_ok = 0
    
    for symbol in config.INDEX_SYMBOLS:
        filepath = config.INDICES_DIR / f"{symbol.lower()}_1m.parquet"
        idx_checked += 1
        if check_file(filepath):
            idx_ok += 1
    
    # Summary
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print(f"FX: {fx_ok}/{fx_checked} files OK")
    print(f"Indices: {idx_ok}/{idx_checked} files OK")
    print(f"Overall: {fx_ok + idx_ok}/{fx_checked + idx_checked} files OK")
    print()


def main():
    """Main entry point"""
    check_all_data()


if __name__ == "__main__":
    main()

