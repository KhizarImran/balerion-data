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

## Getting Started

```bash
# Clone the repo
git clone <repo-url> balerion-data
cd balerion-data

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp config/example.env .env
# Edit .env with your API keys and data paths

# Run initial backfill
python -m pipeline.backfill --source fx --pair EURUSD --start 2020-01-01
```

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
