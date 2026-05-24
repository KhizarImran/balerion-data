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
    # Majors
    "EURUSD", "GBPUSD", "USDJPY", "USDCAD", "USDCHF", "AUDUSD", "NZDUSD",
    # EUR crosses
    "EURGBP", "EURJPY", "EURAUD", "EURCAD", "EURCHF", "EURNZD",
    # GBP crosses
    "GBPJPY", "GBPAUD", "GBPCAD", "GBPCHF", "GBPNZD",
    # AUD crosses
    "AUDJPY", "AUDCAD", "AUDCHF", "AUDNZD",
    # Other crosses
    "CADJPY", "CADCHF", "CHFJPY", "NZDJPY", "NZDCAD", "NZDCHF",
]

INDEX_SYMBOLS = [
    "US30",     # Dow Jones
    "XAUUSD",   # Gold
    "NAS100",   # Nasdaq 100
    "SPX500",   # S&P 500
    "UK100",    # FTSE 100
    "GER40",    # DAX 40
]

# Alternative symbol names to try if primary fails
SYMBOL_ALTERNATIVES = {
    # FX Majors
    "EURUSD": ["EURUSD", "EURUSD.a", "EURUSDm", "EURUSD."],
    "GBPUSD": ["GBPUSD", "GBPUSD.a", "GBPUSDm", "GBPUSD."],
    "USDJPY": ["USDJPY", "USDJPY.a", "USDJPYm", "USDJPY."],
    "USDCAD": ["USDCAD", "USDCAD.a", "USDCADm", "USDCAD."],
    "USDCHF": ["USDCHF", "USDCHF.a", "USDCHFm", "USDCHF."],
    "AUDUSD": ["AUDUSD", "AUDUSD.a", "AUDUSDm", "AUDUSD."],
    "NZDUSD": ["NZDUSD", "NZDUSD.a", "NZDUSDm", "NZDUSD."],
    # EUR crosses
    "EURGBP": ["EURGBP", "EURGBP.a", "EURGBPm", "EURGBP."],
    "EURJPY": ["EURJPY", "EURJPY.a", "EURJPYm", "EURJPY."],
    "EURAUD": ["EURAUD", "EURAUD.a", "EURAUDm", "EURAUD."],
    "EURCAD": ["EURCAD", "EURCAD.a", "EURCADm", "EURCAD."],
    "EURCHF": ["EURCHF", "EURCHF.a", "EURCHFm", "EURCHF."],
    "EURNZD": ["EURNZD", "EURNZD.a", "EURNZDm", "EURNZD."],
    # GBP crosses
    "GBPJPY": ["GBPJPY", "GBPJPY.a", "GBPJPYm", "GBPJPY."],
    "GBPAUD": ["GBPAUD", "GBPAUD.a", "GBPAUDm", "GBPAUD."],
    "GBPCAD": ["GBPCAD", "GBPCAD.a", "GBPCADm", "GBPCAD."],
    "GBPCHF": ["GBPCHF", "GBPCHF.a", "GBPCHFm", "GBPCHF."],
    "GBPNZD": ["GBPNZD", "GBPNZD.a", "GBPNZDm", "GBPNZD."],
    # AUD crosses
    "AUDJPY": ["AUDJPY", "AUDJPY.a", "AUDJPYm", "AUDJPY."],
    "AUDCAD": ["AUDCAD", "AUDCAD.a", "AUDCADm", "AUDCAD."],
    "AUDCHF": ["AUDCHF", "AUDCHF.a", "AUDCHFm", "AUDCHF."],
    "AUDNZD": ["AUDNZD", "AUDNZD.a", "AUDNZDm", "AUDNZD."],
    # Other crosses
    "CADJPY": ["CADJPY", "CADJPY.a", "CADJPYm", "CADJPY."],
    "CADCHF": ["CADCHF", "CADCHF.a", "CADCHFm", "CADCHF."],
    "CHFJPY": ["CHFJPY", "CHFJPY.a", "CHFJPYm", "CHFJPY."],
    "NZDJPY": ["NZDJPY", "NZDJPY.a", "NZDJPYm", "NZDJPY."],
    "NZDCAD": ["NZDCAD", "NZDCAD.a", "NZDCADm", "NZDCAD."],
    "NZDCHF": ["NZDCHF", "NZDCHF.a", "NZDCHFm", "NZDCHF."],
    # Indices
    "US30":   ["US30", "US30.cash", "US30Cash", "USA30", "DJ30", "US30.", "USTEC30"],
    "XAUUSD": ["XAUUSD", "XAUUSD.a", "XAUUSDm", "GOLD", "XAUUSD.", "XAU/USD"],
    "NAS100": ["NAS100", "NAS100.cash", "NASDAQ", "US100", "NAS100.", "USATEC", "NDX100"],
    "SPX500": ["SPX500", "SPX500.cash", "SP500", "US500", "SPX500.", "S&P500"],
    "UK100":  ["UK100", "UK100.cash", "FTSE100", "FTSE", "UK100.", "UKX"],
    "GER40":  ["GER40", "GER40.cash", "DAX40", "DAX", "GER40.", "DE40", "GER30"],
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
