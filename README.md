# balerion-data

Data ingestion pipeline for the Balerion quant hedge fund. This repository handles all market data acquisition and storage into the home server.

## Overview

This service is responsible for fetching, normalizing, and persisting financial data used downstream by the strategy and execution layers. All data is stored locally as Parquet files, keeping the stack lean and dependency-free from a managed database.

## Scope

**Asset classes**
- Forex (currency pairs)

**Data types**
- OHLCV market data (open, high, low, close, volume)
- Macroeconomic / economic indicators (Fed data, interest rates, economic releases)

## Architecture

```
External Sources
      │
      ▼
 Ingestion Layer       ← fetch, validate, normalize
      │
      ▼
  Parquet Store        ← local filesystem on home server
  data/
  ├── fx/
  │   ├── ohlcv/
  │   │   └── <pair>/<year>/<month>.parquet
  │   └── tick/
  └── macro/
      └── <indicator>/<year>.parquet
```

## Repository Structure

```
balerion-data/
├── ingestion/          # Data fetchers per source
│   ├── fx/             # Forex OHLCV ingestion
│   └── macro/          # Macro/economic indicator ingestion
├── storage/            # Parquet read/write utilities
├── pipeline/           # Orchestration and scheduling
├── tests/              # Unit and integration tests
├── config/             # Source configs, symbols, intervals
└── data/               # Local Parquet store (gitignored)
```

## Data Sources (planned)

| Data Type | Source | Notes |
|-----------|--------|-------|
| Forex OHLCV | TBD (e.g. OANDA, Dukascopy, Alpha Vantage) | M1 to D1 bars |
| Macro indicators | FRED (Federal Reserve Economic Data) | Free API |
| Macro indicators | BLS, BEA | Economic releases |

## Storage Format

Data is persisted as **Parquet files** partitioned by asset and time period. This provides:

- Columnar compression with no database overhead
- Fast reads via pandas / polars / DuckDB
- Simple backup — just copy the `data/` directory
- No network dependency for reads

### Schema — OHLCV

| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | `datetime64[ns, UTC]` | Bar open time, UTC |
| `open` | `float64` | Open price |
| `high` | `float64` | High price |
| `low` | `float64` | Low price |
| `close` | `float64` | Close price |
| `volume` | `float64` | Volume (where available) |

### Schema — Macro

| Column | Type | Description |
|--------|------|-------------|
| `release_date` | `datetime64[ns, UTC]` | Official release date |
| `period` | `str` | Period the observation covers |
| `value` | `float64` | Indicator value |
| `revised` | `bool` | Whether this is a revised print |

## Quick Start - MT5 Data Collection

The MT5 data collection system is ready to use. It collects 1-minute OHLCV data for FX pairs and indices.

### Prerequisites

1. MetaTrader 5 installed and logged in
2. Python 3.11+ 
3. uv package manager (or pip)

### Installation

**Option 1: Using uv (Recommended)**

```bash
# Windows
.\scripts\setup.ps1

# Linux/Mac
chmod +x scripts/setup.sh
./scripts/setup.sh
```

The setup script will:
- Install uv if not present
- Create a virtual environment
- Install all dependencies

**Option 2: Manual installation with uv**

```bash
# Install uv (if not installed)
# Windows: irm https://astral.sh/uv/install.ps1 | iex
# Linux/Mac: curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync
```

**Option 3: Using pip**

```bash
pip install -r scripts/requirements.txt
```

### Initial Data Collection

Collect maximum available historical data (run once):

```bash
# Using uv (recommended)
uv run python scripts/collect_historical_data.py

# Or using standard Python
python scripts/collect_historical_data.py
```

This will fetch 2-3 years of 1-minute data for:
- **FX**: EURUSD, USDJPY, GBPUSD, EURGBP, USDCAD, AUDNZD
- **Indices**: US30, XAUUSD

Data is saved to `data/fx/` and `data/indices/` as Parquet files.

### Weekly Updates

Keep your data current (run weekly):

```bash
# Using uv (recommended)
uv run python scripts/update_weekly_data.py

# Or using standard Python
python scripts/update_weekly_data.py
```

This automatically:
- Fetches the last 7 days of data
- Merges with existing data
- Removes duplicates
- Updates the parquet files

### Check Data Quality

```bash
# Using uv (recommended)
uv run python scripts/check_data.py

# Or using standard Python
python scripts/check_data.py
```

### Quick Reference

```bash
# Install dependencies
uv sync

# Run initial collection (once)
uv run python scripts/collect_historical_data.py

# Update weekly
uv run python scripts/update_weekly_data.py

# Check data quality
uv run python scripts/check_data.py
```

## Documentation

- **[Quick Start Guide](docs/QUICKSTART.md)** - Fast setup and common tasks
- **[Scripts Documentation](docs/SCRIPTS.md)** - Detailed script usage and configuration
- **[Changelog](docs/CHANGELOG.md)** - Version history and updates

## Configuration

Key settings live in `.env` and `config/`:

```
DATA_DIR=/path/to/data          # Root of the Parquet store
FRED_API_KEY=your_key_here      # FRED API key (free at fred.stlouisfed.org)
FX_API_KEY=your_key_here        # Forex data provider API key
LOG_LEVEL=INFO
```

## Development

This is a solo-developer project. Conventions:

- Python 3.11+
- `pandas` / `pyarrow` for Parquet I/O
- `pytest` for testing
- Type hints throughout
- Each ingestion module is independently runnable for easy debugging

## Roadmap

- [ ] Forex OHLCV backfill (multi-pair, multi-timeframe)
- [ ] FRED macro indicator ingestion
- [ ] Incremental daily updates + scheduler
- [ ] Data quality checks (gap detection, outlier flagging)
- [ ] Parquet partitioning and compaction utilities
- [ ] CLI for ad-hoc queries against the local store

## License

Private — all rights reserved.
