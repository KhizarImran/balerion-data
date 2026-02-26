# Balerion Data Collection - Project Details

## Project Overview

**Purpose:** Automated MT5 (MetaTrader 5) data collection system for the Balerion quantitative hedge fund. Collects and maintains clean, deduplicated 1-minute OHLCV data for FX pairs and indices.

**Created:** February 25, 2026  
**Version:** 1.0.0  
**Language:** Python 3.11+  
**Package Manager:** uv (with pip fallback)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     MT5 (MetaTrader 5)                      │
│              Live/Demo Trading Account                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ API Connection
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Data Collection Scripts                         │
│  ┌──────────────────┐  ┌─────────────────────────────┐     │
│  │ Initial          │  │ Weekly Update               │     │
│  │ Historical       │  │ (Incremental)               │     │
│  │ Collection       │  │ - Fetch last 7 days         │     │
│  │ - 2-3 years      │  │ - Merge & deduplicate       │     │
│  │ - 100k bars max  │  │ - Backup & update           │     │
│  └──────────────────┘  └─────────────────────────────┘     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ Save as Parquet
                     ▼
┌─────────────────────────────────────────────────────────────┐
│               Local Parquet Storage                          │
│  ┌──────────────┐         ┌─────────────────┐              │
│  │  data/fx/    │         │  data/indices/  │              │
│  │  - eurusd    │         │  - us30         │              │
│  │  - usdjpy    │         │  - xauusd       │              │
│  │  - gbpusd    │         │                 │              │
│  │  - eurgbp    │         └─────────────────┘              │
│  │  - usdcad    │                                           │
│  │  - audnzd    │                                           │
│  └──────────────┘                                           │
└─────────────────────────────────────────────────────────────┘
```

## Data Coverage

### FX Pairs (6)
- **EURUSD** - Euro vs US Dollar
- **USDJPY** - US Dollar vs Japanese Yen
- **GBPUSD** - Great Britain Pound vs US Dollar
- **EURGBP** - Euro vs Great Britain Pound
- **USDCAD** - US Dollar vs Canadian Dollar
- **AUDNZD** - Australian Dollar vs New Zealand Dollar

### Indices (2)
- **US30** - Dow Jones Industrial Average
- **XAUUSD** - Gold vs US Dollar

### Data Specifications
- **Timeframe:** 1 minute (M1)
- **Format:** Parquet (snappy compression)
- **Columns:** timestamp, open, high, low, close, volume, spread, real_volume
- **History:** 2-3 years (depending on broker availability)
- **Size per symbol:** ~1.5-1.7 MB per 100k rows (parquet)
- **Total dataset:** ~12-15 MB for all 8 symbols

## Directory Structure

```
balerion-data/
├── data/                          # Data storage (gitignored)
│   ├── fx/                        # FX pair parquet files
│   │   ├── eurusd_1m.parquet
│   │   ├── usdjpy_1m.parquet
│   │   ├── gbpusd_1m.parquet
│   │   ├── eurgbp_1m.parquet
│   │   ├── usdcad_1m.parquet
│   │   └── audnzd_1m.parquet
│   └── indices/                   # Index parquet files
│       ├── us30_1m.parquet
│       └── xauusd_1m.parquet
│
├── scripts/                       # Python scripts
│   ├── config.py                  # Configuration (symbols, settings)
│   ├── mt5_utils.py               # Reusable MT5 utility functions
│   ├── collect_historical_data.py # Initial collection (run once)
│   ├── update_weekly_data.py      # Weekly updates (run weekly)
│   ├── check_data.py              # Data quality checker
│   ├── requirements.txt           # Pip dependencies
│   ├── setup.ps1                  # Windows setup script
│   └── setup.sh                   # Linux/Mac setup script
│
├── docs/                          # Documentation
│   ├── README.md                  # Documentation index
│   ├── QUICKSTART.md              # Quick start guide
│   ├── SCRIPTS.md                 # Detailed script documentation
│   └── CHANGELOG.md               # Version history
│
├── .venv/                         # Virtual environment (created by uv)
├── pyproject.toml                 # Project config (uv/pip)
├── .python-version                # Python 3.11
├── .gitignore                     # Git ignore rules
├── README.md                      # Main README
└── CLAUDE.md                      # This file

```

## Key Scripts

### 1. collect_historical_data.py
**Purpose:** Initial data collection (run once)

**What it does:**
- Connects to MT5
- Fetches maximum available historical data (typically 2-3 years)
- Collects data in chunks (99,999 bars per request)
- Attempts to fetch earlier data in 10 iterations
- Removes duplicates
- Saves to parquet

**Usage:**
```bash
python scripts/collect_historical_data.py
```

**Runtime:** 5-15 minutes  
**Output:** 8 parquet files (6 FX + 2 indices)

### 2. update_weekly_data.py
**Purpose:** Weekly incremental updates

**What it does:**
- Loads existing parquet files
- Fetches last 7 days of data from MT5
- Merges with existing data
- Removes duplicates (by timestamp)
- Creates backup (.parquet.backup)
- Saves updated parquet file
- Deletes backup after successful save

**Usage:**
```bash
# Standard weekly update
python scripts/update_weekly_data.py

# Force update (ignore 12-hour check)
python scripts/update_weekly_data.py --force

# Fetch more days (useful if you missed weeks)
python scripts/update_weekly_data.py --days 14
```

**Runtime:** 1-3 minutes  
**Smart skip:** Won't update if data is <12 hours old (unless --force)

### 3. check_data.py
**Purpose:** Data quality verification

**What it does:**
- Loads all parquet files
- Displays statistics (rows, date range, file size)
- Checks for duplicates
- Checks for missing values
- Detects large gaps (>2 hours)
- Reports price ranges

**Usage:**
```bash
python scripts/check_data.py
```

## Configuration

### config.py
Central configuration for all scripts.

**Key settings:**
```python
# Symbols to collect
FX_SYMBOLS = ["EURUSD", "USDJPY", "GBPUSD", "EURGBP", "USDCAD", "AUDNZD"]
INDEX_SYMBOLS = ["US30", "XAUUSD"]

# Symbol alternatives (if primary name not found)
SYMBOL_ALTERNATIVES = {
    "EURUSD": ["EURUSD", "EURUSD.a", "EURUSDm", "EURUSD."],
    "US30": ["US30", "US30.cash", "US30Cash", "USA30", "DJ30"],
    # ... etc
}

# MT5 settings
TIMEFRAME = "M1"                   # 1-minute
MAX_BARS_PER_REQUEST = 99999       # MT5 maximum
MAX_HISTORICAL_ATTEMPTS = 10       # Chunks to fetch backwards

# Data settings
REMOVE_DUPLICATES = True
SAVE_FORMAT = "parquet"            # or "csv" or "both"

# Output columns
OUTPUT_COLUMNS = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
OPTIONAL_COLUMNS = ['spread', 'real_volume']
```

### mt5_utils.py
Reusable utility functions.

**Key functions:**
- `initialize_mt5()` - Connect to MT5
- `shutdown_mt5()` - Disconnect from MT5
- `find_symbol()` - Find symbol with alternatives
- `collect_maximum_data()` - Fetch maximum historical data
- `save_dataframe()` - Save to parquet/csv
- `load_existing_data()` - Load parquet file
- `append_new_data()` - Merge and deduplicate
- `get_data_filepath()` - Get file path for symbol

## Dependencies

### Core Dependencies
```
MetaTrader5>=5.0.45    # MT5 API
pandas>=2.0.0          # Data manipulation
pyarrow>=12.0.0        # Parquet support
pytz>=2023.3           # Timezone handling
```

### Development Dependencies (optional)
```
pytest>=7.0.0          # Testing
black>=23.0.0          # Code formatting
ruff>=0.1.0            # Linting
ipython>=8.0.0         # Interactive shell
```

## Installation & Setup

### Option 1: Using uv (Recommended)
```bash
# Install uv
irm https://astral.sh/uv/install.ps1 | iex  # Windows
# OR
curl -LsSf https://astral.sh/uv/install.sh | sh  # Linux/Mac

# Install dependencies
cd balerion-data
uv sync
```

### Option 2: Using pip
```bash
cd balerion-data
pip install -r scripts/requirements.txt
```

### Option 3: Automated Setup
```bash
# Windows
.\scripts\setup.ps1

# Linux/Mac
chmod +x scripts/setup.sh
./scripts/setup.sh
```

## Workflow

### Initial Setup (One-Time)
1. Install dependencies (`uv sync`)
2. Ensure MT5 is running and logged in
3. Run initial collection: `python scripts/collect_historical_data.py`
4. Verify data: `python scripts/check_data.py`

### Weekly Maintenance
1. Run update script: `python scripts/update_weekly_data.py`
2. (Optional) Check data: `python scripts/check_data.py`

### Automation (Recommended)
Set up Windows Task Scheduler or cron job:
- **Schedule:** Weekly (e.g., Sundays at 2 AM)
- **Program:** `python`
- **Arguments:** `scripts\update_weekly_data.py`
- **Start in:** `C:\Users\khiz2\devlab\balerion-data`

## Data Quality Features

### Deduplication
- Removes duplicate timestamps automatically
- Uses `drop_duplicates(subset=['timestamp'], keep='last')`
- Applied during both initial collection and updates

### Validation
- Ensures all OHLCV columns present
- Validates timestamp format (UTC datetime64[ns])
- Sorts data by timestamp
- Checks for missing values

### Backup System
- Creates `.parquet.backup` before updating
- Only deletes backup after successful save
- Allows rollback if update fails

### Gap Detection
- Identifies large gaps (>2 hours)
- Reports in `check_data.py`
- Expected gaps: weekends, holidays, market closures

## Reading Data

### Python Example
```python
import pandas as pd

# Load data
df = pd.read_parquet('data/fx/eurusd_1m.parquet')

# Display info
print(f"Rows: {len(df):,}")
print(f"Columns: {df.columns.tolist()}")
print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

# First few rows
print(df.head())

# Calculate returns
df['returns'] = df['close'].pct_change()

# Resample to hourly
df_hourly = df.set_index('timestamp').resample('1H').agg({
    'open': 'first',
    'high': 'max',
    'low': 'min',
    'close': 'last',
    'volume': 'sum'
})
```

## Performance Characteristics

### Storage
- **Parquet compression:** ~70% smaller than CSV
- **Memory usage:** ~100 MB RAM per 1M rows
- **Storage per symbol/year:** ~5-10 MB (parquet)

### Collection Speed
- **Initial collection:** 5-15 minutes for all 8 symbols
- **Weekly update:** 1-3 minutes for all 8 symbols
- **Limited by:** MT5 API rate limits, network speed

### Data Retrieval Limits
- **MT5 max bars per request:** 99,999
- **Historical depth:** 2-3 years (broker dependent)
- **Update granularity:** 1 minute

## Error Handling

### Connection Errors
- Graceful MT5 initialization failure
- Clear error messages with error codes
- Automatic cleanup (shutdown MT5 on exit)

### Symbol Not Found
- Tries alternative symbol names from config
- Reports which alternative was used
- Fails gracefully if all alternatives fail

### Data Issues
- Skips symbols with no data
- Continues processing other symbols
- Displays summary of successes/failures

## Security & Privacy

### Data Storage
- All data stored locally (no cloud)
- Data directory gitignored
- No sensitive information in parquet files

### MT5 Connection
- Uses read-only API (copy_rates_*)
- No trading operations
- No account modification

### Credentials
- No API keys or passwords in code
- MT5 login handled by MT5 terminal
- Scripts connect to already-logged-in MT5

## Future Enhancements

### Potential Features
- [ ] Support for multiple timeframes (5m, 15m, 1h, daily)
- [ ] Additional FX pairs and indices
- [ ] Email notifications on errors
- [ ] Data validation and anomaly detection
- [ ] REST API for data access
- [ ] Real-time streaming collection
- [ ] Integration with macro/economic indicators
- [ ] Automated data quality reports
- [ ] Data export to CSV/JSON on demand
- [ ] Historical data gap filling

### Scalability
- Current design supports up to ~50 symbols
- Each symbol independent (parallel collection possible)
- Parquet format scales well to millions of rows

## Troubleshooting

### MT5 Connection Failed
- Ensure MT5 is running and logged in
- Check: Tools > Options > Expert Advisors > Allow automated trading
- Verify account has data permissions

### Symbol Not Found
- Check symbol name in MT5 Market Watch
- Add alternative names to `config.py`
- Some symbols may be broker-specific

### Unicode Errors
- All emoji characters replaced with [OK], [ERROR], [INFO], [WARN]
- Should not occur in current version
- If it does, check for remaining emoji in script files

### Data Gaps
- Normal for weekends and holidays
- Check MT5 data availability
- Use `--days` flag to fetch more data

### Duplicate Data
- Automatic deduplication enabled
- If manual cleanup needed, see `docs/SCRIPTS.md`

## Contact & Support

**Project:** Balerion Quant Hedge Fund  
**Repository:** balerion-data  
**Documentation:** See `docs/` folder  
**Issues:** Check `docs/SCRIPTS.md` troubleshooting section

## License

Private - All rights reserved.

---

**Last Updated:** February 25, 2026  
**Maintained By:** Balerion Fund Development Team
