# Balerion Data Collection - Documentation

Complete documentation for the MT5 data collection system.

## Table of Contents

### Getting Started

- **[Quick Start Guide](QUICKSTART.md)** - Get up and running in minutes
  - Installation with uv
  - Initial data collection
  - Weekly updates
  - Common tasks

### Reference

- **[Scripts Documentation](SCRIPTS.md)** - Detailed documentation
  - Prerequisites and setup
  - Configuration options
  - Script usage and arguments
  - Data format specifications
  - Troubleshooting guide
  - Automation setup
  - Advanced usage examples

### Project Information

- **[Changelog](CHANGELOG.md)** - Version history
  - Features added
  - Technical details
  - Future enhancements

## Quick Links

### Common Tasks

#### First Time Setup
```bash
# Install uv
irm https://astral.sh/uv/install.ps1 | iex  # Windows
# OR
curl -LsSf https://astral.sh/uv/install.sh | sh  # Linux/Mac

# Install dependencies
uv sync
```

#### Run Initial Collection
```bash
uv run python scripts/collect_historical_data.py
```

#### Update Weekly
```bash
uv run python scripts/update_weekly_data.py
```

#### Check Data Quality
```bash
uv run python scripts/check_data.py
```

## Project Structure

```
balerion-data/
├── docs/                   # Documentation (you are here)
│   ├── README.md          # This file
│   ├── QUICKSTART.md      # Quick start guide
│   ├── SCRIPTS.md         # Detailed script docs
│   └── CHANGELOG.md       # Version history
├── data/                   # Data storage (gitignored)
│   ├── fx/                # FX pair parquet files
│   └── indices/           # Index parquet files
├── scripts/                # Python scripts
│   ├── config.py          # Configuration
│   ├── mt5_utils.py       # Utility functions
│   ├── collect_historical_data.py
│   ├── update_weekly_data.py
│   ├── check_data.py
│   ├── setup.ps1          # Windows setup
│   └── setup.sh           # Linux/Mac setup
├── pyproject.toml          # Project config (uv/pip)
├── .python-version         # Python 3.11
├── .gitignore             # Git ignore rules
└── README.md              # Main README
```

## Symbols Collected

### FX Pairs (6)
- EURUSD
- USDJPY
- GBPUSD
- EURGBP
- USDCAD
- AUDNZD

### Indices (2)
- US30 (Dow Jones Industrial Average)
- XAUUSD (Gold vs USD)

## Data Format

All data is stored as Parquet files with the following schema:

| Column    | Type     | Description           |
|-----------|----------|-----------------------|
| timestamp | datetime | UTC timestamp         |
| open      | float64  | Opening price         |
| high      | float64  | Highest price         |
| low       | float64  | Lowest price          |
| close     | float64  | Closing price         |
| volume    | int64    | Tick volume           |

**File naming:** `{symbol}_1m.parquet` (e.g., `eurusd_1m.parquet`)

## Support

For issues or questions:

1. Check the [Scripts Documentation](SCRIPTS.md) troubleshooting section
2. Review the [Quick Start Guide](QUICKSTART.md) for common tasks
3. Check the [Changelog](CHANGELOG.md) for recent updates

## License

Private - All rights reserved.
