# MT5 Data Collection System

Production-ready scripts for collecting and maintaining 1-minute OHLCV data from MetaTrader 5.

## Overview

This system collects historical and ongoing 1-minute OHLCV (Open, High, Low, Close, Volume) data for:

**FX Pairs:**
- EURUSD
- USDJPY
- GBPUSD
- EURGBP
- USDCAD
- AUDNZD

**Indices:**
- US30 (Dow Jones)
- XAUUSD (Gold)

Data is stored in efficient Parquet format with automatic deduplication.

## Directory Structure

```
balerion-data/
├── data/
│   ├── fx/                    # FX pair data
│   │   ├── eurusd_1m.parquet
│   │   ├── usdjpy_1m.parquet
│   │   └── ...
│   └── indices/               # Index data
│       ├── us30_1m.parquet
│       └── xauusd_1m.parquet
└── scripts/
    ├── config.py              # Configuration settings
    ├── mt5_utils.py           # Utility functions
    ├── collect_historical_data.py  # Initial data collection
    └── update_weekly_data.py       # Weekly updates
```

## Prerequisites

1. **MetaTrader 5** installed and logged in
2. **Python 3.11+**
3. **uv** package manager (recommended) or pip

### Installing uv

**Windows (PowerShell):**
```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

**Linux/Mac:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Installing Dependencies

**Using uv (Recommended):**
```bash
# From project root
uv sync

# This will:
# - Create a virtual environment
# - Install all dependencies from pyproject.toml
# - Generate/update uv.lock
```

**Using pip (Alternative):**
```bash
pip install -r requirements.txt
```

## Usage

### Step 1: Initial Historical Data Collection

Run this **once** to collect all available historical data:

**Using uv (Recommended):**
```bash
uv run python scripts/collect_historical_data.py
```

**Using standard Python:**
```bash
python scripts/collect_historical_data.py
```

This will:
- Connect to MT5
- Fetch maximum available history for each symbol (typically 2-3 years)
- Save data to `data/fx/` and `data/indices/` folders
- Display collection summary

**Expected runtime:** 5-15 minutes depending on broker and data availability.

### Step 2: Weekly Updates

Run this **weekly** (or as needed) to update with recent data:

**Using uv (Recommended):**
```bash
uv run python scripts/update_weekly_data.py
```

**Using standard Python:**
```bash
python scripts/update_weekly_data.py
```

This will:
- Load existing parquet files
- Fetch last 7 days of data
- Merge with existing data
- Remove duplicates automatically
- Save updated files

**Optional arguments:**

```bash
# Update with last 14 days (useful if you missed a week)
uv run python scripts/update_weekly_data.py --days 14

# Force update even if data is recent
uv run python scripts/update_weekly_data.py --force
```

## Configuration

Edit `config.py` to customize:

```python
# Add or remove symbols
FX_SYMBOLS = ["EURUSD", "USDJPY", ...]
INDEX_SYMBOLS = ["US30", "XAUUSD", ...]

# Change save format
SAVE_FORMAT = "parquet"  # Options: "parquet", "csv", "both"

# Adjust data collection limits
MAX_BARS_PER_REQUEST = 99999
MAX_HISTORICAL_ATTEMPTS = 10
```

## Output Format

Each parquet file contains:

| Column    | Type      | Description           |
|-----------|-----------|-----------------------|
| timestamp | datetime  | Bar timestamp (UTC)   |
| open      | float     | Opening price         |
| high      | float     | Highest price         |
| low       | float     | Lowest price          |
| close     | float     | Closing price         |
| volume    | int       | Tick volume           |

Optional columns (if enabled in config):
- `spread`: Spread in points
- `real_volume`: Real traded volume (if available)

## Reading Data in Python

```python
import pandas as pd

# Load data
df = pd.read_parquet('data/fx/eurusd_1m.parquet')

# Display info
print(f"Rows: {len(df):,}")
print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
print(df.head())

# Example: Calculate daily returns
df['returns'] = df['close'].pct_change()
```

## Automation with Task Scheduler (Windows)

To automate weekly updates:

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger to weekly (e.g., Sunday 2 AM)
4. Action: Start a program
   - Program: `python`
   - Arguments: `C:\path\to\balerion-data\scripts\update_weekly_data.py`
   - Start in: `C:\path\to\balerion-data\scripts`

## Automation with Cron (Linux/Mac)

Add to crontab:

```bash
# Run every Sunday at 2 AM
0 2 * * 0 cd /path/to/balerion-data/scripts && python update_weekly_data.py
```

## Troubleshooting

### Symbol Not Found

If a symbol fails with "not found" error:

1. Check the symbol name in MT5 Market Watch
2. Add alternative names to `config.py`:

```python
SYMBOL_ALTERNATIVES = {
    "US30": ["US30", "US30.cash", "USA30", "DJ30"],
}
```

### MT5 Connection Failed

- Ensure MT5 is running and logged in
- Check that MT5 allows API connections (Tools > Options > Expert Advisors > Allow automated trading)

### Data Gaps

If you notice gaps in data:

```bash
# Fetch more days to fill gaps
python update_weekly_data.py --days 30 --force
```

### Duplicate Timestamps

The system automatically removes duplicates. If you encounter issues:

```python
# Manual deduplication
import pandas as pd
df = pd.read_parquet('data/fx/eurusd_1m.parquet')
df = df.drop_duplicates(subset=['timestamp'], keep='last')
df = df.sort_values('timestamp').reset_index(drop=True)
df.to_parquet('data/fx/eurusd_1m.parquet', index=False)
```

## Data Integrity Checks

Verify your data quality:

```python
import pandas as pd

df = pd.read_parquet('data/fx/eurusd_1m.parquet')

# Check for duplicates
print(f"Duplicates: {df['timestamp'].duplicated().sum()}")

# Check for missing values
print(f"Missing values:\n{df.isnull().sum()}")

# Check for gaps (should be ~1 minute apart when market is open)
df['time_diff'] = df['timestamp'].diff()
gaps = df[df['time_diff'] > pd.Timedelta(hours=2)]
print(f"Significant gaps: {len(gaps)}")
```

## Performance Notes

- **Parquet vs CSV**: Parquet files are ~70% smaller than CSV
- **Memory usage**: ~100MB RAM per 1M rows
- **Storage**: Expect ~5-10 MB per symbol per year (parquet)

## Advanced Usage

### Collecting Data for New Symbols

1. Add symbol to `config.py`:

```python
FX_SYMBOLS = [..., "NZDUSD"]
```

2. Run initial collection for just that symbol:

```python
import mt5_utils
import config

mt5_utils.initialize_mt5()
timeframe = mt5_utils.get_timeframe_constant("M1")
df = mt5_utils.collect_maximum_data("NZDUSD", timeframe)
filepath = mt5_utils.get_data_filepath("NZDUSD", "fx")
mt5_utils.save_dataframe(df, filepath, "parquet")
mt5_utils.shutdown_mt5()
```

### Exporting to CSV

```python
import pandas as pd

df = pd.read_parquet('data/fx/eurusd_1m.parquet')
df.to_csv('eurusd_1m.csv', index=False)
```

### Filtering Date Range

```python
import pandas as pd

df = pd.read_parquet('data/fx/eurusd_1m.parquet')

# Get last 30 days
cutoff = pd.Timestamp.now() - pd.Timedelta(days=30)
df_recent = df[df['timestamp'] >= cutoff]

print(f"Recent data: {len(df_recent):,} rows")
```

## Support

For issues related to:
- MT5 connectivity: Check MT5 documentation
- Symbol availability: Contact your broker
- Script bugs: Open an issue in the repository

## License

MIT License - Feel free to modify and use for your projects.
