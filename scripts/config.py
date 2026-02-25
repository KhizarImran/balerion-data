"""
Configuration file for MT5 data collection
"""

from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
FX_DIR = DATA_DIR / "fx"
INDICES_DIR = DATA_DIR / "indices"

# Symbols to collect - categorized by type
FX_SYMBOLS = [
    "EURUSD",
    "USDJPY",
    "GBPUSD",
    "EURGBP",
    "USDCAD",
    "AUDNZD",
]

INDEX_SYMBOLS = [
    "US30",    # Dow Jones
    "XAUUSD",  # Gold
]

# Alternative symbol names to try if primary fails
SYMBOL_ALTERNATIVES = {
    "EURUSD": ["EURUSD", "EURUSD.a", "EURUSDm", "EURUSD."],
    "USDJPY": ["USDJPY", "USDJPY.a", "USDJPYm", "USDJPY."],
    "GBPUSD": ["GBPUSD", "GBPUSD.a", "GBPUSDm", "GBPUSD."],
    "EURGBP": ["EURGBP", "EURGBP.a", "EURGBPm", "EURGBP."],
    "USDCAD": ["USDCAD", "USDCAD.a", "USDCADm", "USDCAD."],
    "AUDNZD": ["AUDNZD", "AUDNZD.a", "AUDNZDm", "AUDNZD."],
    "US30": ["US30", "US30.cash", "US30Cash", "USA30", "DJ30", "US30."],
    "XAUUSD": ["XAUUSD", "XAUUSD.a", "XAUUSDm", "GOLD", "XAUUSD."],
}

# MT5 settings
TIMEFRAME = "M1"  # 1-minute timeframe
MAX_BARS_PER_REQUEST = 99999  # MT5 maximum
MAX_HISTORICAL_ATTEMPTS = 10  # Number of chunks to fetch going backwards

# Data collection settings
REMOVE_DUPLICATES = True
SAVE_FORMAT = "parquet"  # Options: "parquet", "csv", "both"

# Column mappings for output
OUTPUT_COLUMNS = ['timestamp', 'open', 'high', 'low', 'close', 'volume']

# Optional columns (can be included if needed)
OPTIONAL_COLUMNS = ['spread', 'real_volume']
