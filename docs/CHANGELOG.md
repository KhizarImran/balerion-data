# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2026-02-25

### Added - MT5 Data Collection System

#### Core Features
- **Initial Historical Data Collection**: Automated collection of maximum available 1-minute OHLCV data
- **Weekly Incremental Updates**: Smart update system that fetches only new data and deduplicates automatically
- **Multi-Symbol Support**: Configured for 6 FX pairs and 2 indices
- **Efficient Storage**: Parquet format with ~70% compression vs CSV
- **uv Package Manager**: Modern, fast package management with lock file for reproducible builds

#### Project Structure
- `pyproject.toml` - Project configuration and dependencies (uv/pip compatible)
- `.python-version` - Python version specification (3.11)
- `scripts/setup.ps1` - Windows setup script with uv installation
- `scripts/setup.sh` - Linux/Mac setup script with uv installation
- `QUICKSTART.md` - Quick reference guide for common tasks

#### Scripts Created
- `scripts/config.py` - Centralized configuration for symbols and settings
- `scripts/mt5_utils.py` - Reusable utility functions for MT5 operations
- `scripts/collect_historical_data.py` - Initial data collection (run once)
- `scripts/update_weekly_data.py` - Weekly update with deduplication
- `scripts/check_data.py` - Data quality verification tool
- `scripts/requirements.txt` - Python dependencies (pip fallback)

#### Data Coverage
**FX Pairs:**
- EURUSD
- USDJPY
- GBPUSD
- EURGBP
- USDCAD
- AUDNZD

**Indices:**
- US30 (Dow Jones Industrial Average)
- XAUUSD (Gold vs USD)

#### Directory Structure
```
balerion-data/
├── data/
│   ├── fx/              # FX pair parquet files
│   └── indices/         # Index parquet files
└── scripts/
    ├── config.py
    ├── mt5_utils.py
    ├── collect_historical_data.py
    ├── update_weekly_data.py
    ├── check_data.py
    ├── requirements.txt
    └── README.md
```

#### Key Features
- **Automatic Symbol Mapping**: Tries alternative symbol names if primary not found
- **Chunked Historical Collection**: Fetches data in chunks to get maximum history
- **Smart Deduplication**: Removes duplicate timestamps automatically
- **Backup System**: Creates backups before overwriting data
- **Progress Reporting**: Clear console output with emojis and statistics
- **Error Handling**: Graceful handling of MT5 errors and connection issues

#### Data Quality
- Remove duplicate timestamps
- Sort data by timestamp
- Validate OHLCV columns
- Check for data gaps
- Report statistics and date ranges

#### Documentation
- Comprehensive README with usage examples
- Configuration guide
- Troubleshooting section
- Automation setup for Windows/Linux
- Python examples for reading data

### Changed
- Updated main README.md with MT5 quick start guide

### Technical Details
- Python 3.8+ compatible
- Dependencies: MetaTrader5, pandas, pyarrow, pytz
- Data format: Parquet with snappy compression
- Timestamp format: UTC datetime64[ns]
- Typical data size: 5-10 MB per symbol per year (parquet)
- Expected history: 2-3 years depending on broker

### Future Enhancements
- [ ] Add more FX pairs and indices
- [ ] Support for multiple timeframes (5m, 15m, 1h, etc.)
- [ ] Email notifications on collection completion/errors
- [ ] Data validation and anomaly detection
- [ ] Historical data export to CSV/JSON
- [ ] REST API for data access
- [ ] Real-time streaming data collection
- [ ] Integration with macro/economic indicators
