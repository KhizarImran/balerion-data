# Quick Start Guide - Balerion Data Collection

## Setup (One-Time)

### 1. Install uv

**Windows (PowerShell):**
```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

**Linux/Mac:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Install Dependencies

```bash
cd balerion-data
uv sync
```

This creates a virtual environment and installs all dependencies.

## Daily Workflow

### Initial Collection (Run Once)

```bash
uv run python scripts/collect_historical_data.py
```

**What it does:**
- Collects 2-3 years of 1-minute OHLCV data
- Saves to `data/fx/` and `data/indices/`
- Takes 5-15 minutes

**Symbols collected:**
- FX: EURUSD, USDJPY, GBPUSD, EURGBP, USDCAD, AUDNZD
- Indices: US30, XAUUSD

### Weekly Updates

```bash
uv run python scripts/update_weekly_data.py
```

**What it does:**
- Fetches last 7 days of data
- Merges with existing data
- Removes duplicates
- Updates parquet files

**Options:**
```bash
# Fetch 14 days instead of 7
uv run python scripts/update_weekly_data.py --days 14

# Force update even if data is recent
uv run python scripts/update_weekly_data.py --force
```

### Check Data Quality

```bash
uv run python scripts/check_data.py
```

Shows statistics for all collected data files.

## Why uv?

**Speed:** 10-100x faster than pip
**Deterministic:** Lock file ensures reproducible installs
**Simple:** One command to set up everything
**Modern:** Built-in virtual environment management

## File Structure

```
balerion-data/
├── data/
│   ├── fx/              # FX pairs (6 files)
│   │   ├── eurusd_1m.parquet
│   │   ├── usdjpy_1m.parquet
│   │   └── ...
│   └── indices/         # Indices (2 files)
│       ├── us30_1m.parquet
│       └── xauusd_1m.parquet
├── scripts/
│   ├── collect_historical_data.py
│   ├── update_weekly_data.py
│   └── check_data.py
└── pyproject.toml       # uv configuration
```

## Common Tasks

### Add New Symbol

1. Edit `scripts/config.py`:
```python
FX_SYMBOLS = [..., "NZDUSD"]
```

2. Run collection:
```bash
uv run python scripts/collect_historical_data.py
```

### Read Data in Python

```python
import pandas as pd

# Load data
df = pd.read_parquet('data/fx/eurusd_1m.parquet')

# Check info
print(f"Rows: {len(df):,}")
print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

# First few rows
print(df.head())
```

### Automate Weekly Updates

**Windows Task Scheduler:**
- Program: `uv`
- Arguments: `run python scripts/update_weekly_data.py`
- Start in: `C:\path\to\balerion-data`

**Linux/Mac Cron:**
```bash
0 2 * * 0 cd /path/to/balerion-data && uv run python scripts/update_weekly_data.py
```

## Troubleshooting

### MT5 Connection Failed
- Ensure MT5 is running and logged in
- Check: Tools > Options > Expert Advisors > Allow automated trading

### Symbol Not Found
- Check symbol name in MT5 Market Watch
- Add alternative names to `scripts/config.py`

### uv Command Not Found
- Restart terminal after installing uv
- Check PATH includes `~/.cargo/bin` (Linux/Mac) or `%USERPROFILE%\.cargo\bin` (Windows)

## More Information

- **Detailed docs:** `scripts/README.md`
- **Main README:** `README.md`
- **Changelog:** `CHANGELOG.md`
