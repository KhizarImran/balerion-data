"""
Utility functions for MT5 data collection
"""

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import pytz
from typing import Optional, Tuple, List
from pathlib import Path
import config


def get_timeframe_constant(timeframe_str: str):
    """Convert timeframe string to MT5 constant"""
    timeframe_map = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
        "W1": mt5.TIMEFRAME_W1,
        "MN1": mt5.TIMEFRAME_MN1,
    }
    return timeframe_map.get(timeframe_str, mt5.TIMEFRAME_M1)


def initialize_mt5() -> bool:
    """Initialize MT5 connection"""
    if not mt5.initialize():
        print(f"[ERROR] MT5 initialization failed, error code: {mt5.last_error()}")
        return False
    print("[OK] MT5 initialized successfully")
    return True


def shutdown_mt5():
    """Shutdown MT5 connection"""
    mt5.shutdown()
    print("[OK] MT5 connection closed")


def find_symbol(symbol: str) -> Optional[str]:
    """
    Find the correct symbol name from alternatives

    Args:
        symbol: Primary symbol name

    Returns:
        Actual symbol name if found, None otherwise
    """
    alternatives = config.SYMBOL_ALTERNATIVES.get(symbol, [symbol])

    for alt_symbol in alternatives:
        symbol_info = mt5.symbol_info(alt_symbol)
        if symbol_info is not None:
            # Enable symbol in Market Watch if needed
            if not symbol_info.visible:
                if mt5.symbol_select(alt_symbol, True):
                    print(f"  [OK] Enabled symbol: {alt_symbol}")
                else:
                    continue
            return alt_symbol

    return None


def collect_maximum_data(symbol: str, timeframe) -> Optional[pd.DataFrame]:
    """
    Collect maximum available historical data for a symbol

    Args:
        symbol: Trading symbol
        timeframe: MT5 timeframe constant

    Returns:
        DataFrame with OHLCV data or None if failed
    """
    print(f"\n{'=' * 80}")
    print(f"Collecting data for: {symbol}")
    print(f"{'=' * 80}")

    # Find the actual symbol name
    actual_symbol = find_symbol(symbol)
    if actual_symbol is None:
        print(f"[ERROR] Symbol {symbol} not found in MT5")
        return None

    if actual_symbol != symbol:
        print(f"  [INFO] Using symbol: {actual_symbol} (mapped from {symbol})")

    symbol_info = mt5.symbol_info(actual_symbol)
    print(f"  Symbol: {symbol_info.name}")
    print(f"  Description: {symbol_info.description}")

    # Step 1: Get initial batch of data
    print(f"\n  Fetching initial data ({config.MAX_BARS_PER_REQUEST} bars)...")
    rates = mt5.copy_rates_from_pos(actual_symbol, timeframe, 0, config.MAX_BARS_PER_REQUEST)

    if rates is None or len(rates) == 0:
        print(f"  [ERROR] Failed to get initial data, error: {mt5.last_error()}")
        return None

    print(f"  [OK] Retrieved {len(rates):,} bars")

    all_rates = list(rates)
    df_temp = pd.DataFrame(rates)
    earliest_time = df_temp["time"].min()
    earliest_datetime = datetime.fromtimestamp(earliest_time, tz=pytz.utc)

    print(
        f"  Initial range: {earliest_datetime} to {datetime.fromtimestamp(df_temp['time'].max(), tz=pytz.utc)}"
    )

    # Step 2: Try to fetch earlier historical data
    print(f"\n  Attempting to fetch earlier historical data...")
    chunk_size = config.MAX_BARS_PER_REQUEST
    max_attempts = config.MAX_HISTORICAL_ATTEMPTS

    for attempt in range(max_attempts):
        earlier_datetime = earliest_datetime - timedelta(minutes=1)

        earlier_rates = mt5.copy_rates_from(actual_symbol, timeframe, earlier_datetime, chunk_size)

        if earlier_rates is None or len(earlier_rates) == 0:
            print(
                f"  [OK] No more historical data available (reached limit at attempt {attempt + 1})"
            )
            break

        df_earlier = pd.DataFrame(earlier_rates)
        new_earliest_time = df_earlier["time"].min()

        if new_earliest_time >= earliest_time:
            print(f"  [OK] Reached earliest available data at attempt {attempt + 1}")
            break

        # Add new data to our collection
        new_data = [r for r in earlier_rates if r["time"] < earliest_time]
        all_rates = new_data + all_rates

        # Update earliest time
        earliest_time = new_earliest_time
        earliest_datetime = datetime.fromtimestamp(earliest_time, tz=pytz.utc)

        if (attempt + 1) % 2 == 0:  # Print every 2 attempts
            print(
                f"    Attempt {attempt + 1}: {len(all_rates):,} bars total, earliest: {earliest_datetime}"
            )

    print(f"\n  [OK] Collection complete: {len(all_rates):,} total bars")

    # Convert to DataFrame from structured array
    # MT5 returns numpy structured arrays, convert properly
    import numpy as np

    if isinstance(all_rates, list) and len(all_rates) > 0:
        # Convert list of numpy void objects to DataFrame
        df = pd.DataFrame(np.array(all_rates))
    else:
        df = pd.DataFrame(all_rates)

    # Convert time column to datetime and rename to timestamp
    if "time" in df.columns:
        df["timestamp"] = pd.to_datetime(df["time"], unit="s")
        df = df.drop(columns=["time"])
    else:
        df["timestamp"] = pd.to_datetime([r["time"] for r in all_rates], unit="s")

    # Remove duplicates
    if config.REMOVE_DUPLICATES:
        original_len = len(df)
        df = df.drop_duplicates(subset=["timestamp"], keep="first")
        duplicates_removed = original_len - len(df)
        if duplicates_removed > 0:
            print(f"  [OK] Removed {duplicates_removed:,} duplicate timestamps")

    # Sort by timestamp
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Rename tick_volume to volume
    if "tick_volume" in df.columns:
        df = df.rename(columns={"tick_volume": "volume"})

    # Select output columns - keep only the ones that exist
    columns_to_keep = config.OUTPUT_COLUMNS.copy()
    if "spread" in df.columns and "spread" in config.OPTIONAL_COLUMNS:
        columns_to_keep.append("spread")
    if "real_volume" in df.columns and "real_volume" in config.OPTIONAL_COLUMNS:
        columns_to_keep.append("real_volume")

    # Only filter if we have the expected columns, otherwise keep all
    existing_cols = [col for col in columns_to_keep if col in df.columns]
    if len(existing_cols) >= 5:  # At least timestamp, O, H, L, C
        df = df[existing_cols]

    # Display summary
    print(f"\n  Final dataset:")
    print(f"    Rows: {len(df):,}")
    print(f"    Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    time_span = df["timestamp"].max() - df["timestamp"].min()
    print(f"    Time span: {time_span.days} days ({time_span.days / 365.25:.2f} years)")

    return df


def save_dataframe(df: pd.DataFrame, filepath: Path, save_format: str = "parquet"):
    """
    Save dataframe to file

    Args:
        df: DataFrame to save
        filepath: Path without extension
        save_format: "parquet", "csv", or "both"
    """
    import os

    # Ensure the parent directory exists
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if save_format in ["parquet", "both"]:
        parquet_path = filepath.with_suffix(".parquet")
        df.to_parquet(parquet_path, index=False)
        size_mb = os.path.getsize(parquet_path) / (1024 * 1024)
        print(f"  [OK] Saved parquet: {parquet_path} ({size_mb:.2f} MB)")

    if save_format in ["csv", "both"]:
        csv_path = filepath.with_suffix(".csv")
        df.to_csv(csv_path, index=False)
        size_mb = os.path.getsize(csv_path) / (1024 * 1024)
        print(f"  [OK] Saved CSV: {csv_path} ({size_mb:.2f} MB)")


def load_existing_data(filepath: Path) -> Optional[pd.DataFrame]:
    """
    Load existing parquet file if it exists

    Args:
        filepath: Path to parquet file

    Returns:
        DataFrame or None if file doesn't exist
    """
    if filepath.exists():
        df = pd.read_parquet(filepath)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        print(f"  [OK] Loaded existing data: {len(df):,} rows")
        print(f"    Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        return df
    return None


def append_new_data(existing_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
    """
    Append new data to existing data, removing duplicates

    Args:
        existing_df: Existing DataFrame
        new_df: New DataFrame to append

    Returns:
        Combined DataFrame without duplicates
    """
    # Combine dataframes
    combined = pd.concat([existing_df, new_df], ignore_index=True)

    # Remove duplicates based on timestamp
    original_len = len(combined)
    combined = combined.drop_duplicates(subset=["timestamp"], keep="last")
    duplicates_removed = original_len - len(combined)

    # Sort by timestamp
    combined = combined.sort_values("timestamp").reset_index(drop=True)

    print(
        f"  [OK] Merged data: {len(existing_df):,} existing + {len(new_df):,} new = {len(combined):,} total"
    )
    if duplicates_removed > 0:
        print(f"    Removed {duplicates_removed:,} duplicates")

    return combined


def get_symbol_category(symbol: str) -> str:
    """
    Determine if symbol is FX or Index

    Args:
        symbol: Symbol name

    Returns:
        "fx" or "indices"
    """
    if symbol in config.FX_SYMBOLS:
        return "fx"
    elif symbol in config.INDEX_SYMBOLS:
        return "indices"
    else:
        # Default to fx
        return "fx"


def get_data_filepath(symbol: str, category: str = None) -> Path:
    """
    Get the filepath for a symbol's data

    Args:
        symbol: Symbol name
        category: "fx" or "indices" (auto-detected if None)

    Returns:
        Path to parquet file
    """
    if category is None:
        category = get_symbol_category(symbol)

    if category == "fx":
        base_dir = config.FX_DIR
    else:
        base_dir = config.INDICES_DIR

    return base_dir / f"{symbol.lower()}_1m.parquet"
