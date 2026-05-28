# balerion-data

Data ingestion pipeline for the Balerion quant hedge fund. Collects, normalises, and persists OHLCV market data and economic calendar events as local Parquet files.

---

## Overview

Two primary data sources feed the pipeline:

| Source | Coverage | History | Best for |
|--------|----------|---------|---------|
| **Dukascopy** | 28 FX pairs, 6 indices, BTCUSD | ~10 years | Backtesting — clean bid bars, deep history |
| **MT5** | 26 FX pairs, 6 indices | ~3 months M1 / years at higher TFs | Live system — broker-accurate, multi-TF |

All data is stored locally as Parquet files. No database, no cloud dependency.

---

## Architecture

```
┌──────────────────────────┐   ┌─────────────────────────────┐
│   Dukascopy Bank API     │   │   MetaTrader 5 Terminal     │
│  (via dukascopy-python)  │   │   (local, logged-in)        │
└────────────┬─────────────┘   └──────────────┬──────────────┘
             │                                │
             ▼                                ▼
┌────────────────────────────────────────────────────────────┐
│                     Ingestion Scripts                       │
│  collect_dukascopy.py         collect_historical_data.py   │
│  (full + incremental update)  collect_mt5_multitf.py       │
│                               update_mt5_m1_incremental.py │
│                               ff_calendar.py               │
└────────────────────────────────────────────────────────────┘
                              │
                              ▼
              data/  (Parquet, snappy compression)
              ├── fx/<symbol>/
              ├── indices/<symbol>/
              ├── crypto/<symbol>/
              └── calendar/weekly/
```

---

## Data Coverage

### FX Pairs (28)

| Category | Pairs |
|----------|-------|
| Majors | EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, USDCHF, NZDUSD |
| EUR crosses | EURGBP, EURJPY, EURAUD, EURCAD, EURCHF, EURNZD |
| GBP crosses | GBPJPY, GBPAUD, GBPCAD, GBPCHF, GBPNZD |
| AUD crosses | AUDJPY, AUDCAD, AUDCHF, AUDNZD |
| Other crosses | CADJPY, CADCHF, CHFJPY, NZDJPY, NZDCAD, NZDCHF |

### Indices & Metals (6)

US30 (Dow Jones), SPX500 (S&P 500), NAS100 (Nasdaq 100), GER40 (DAX), UK100 (FTSE 100), XAUUSD (Gold)

### Crypto (1 — Dukascopy only)

BTCUSD

### Supported Timeframes

| Source | Timeframes |
|--------|-----------|
| Dukascopy | `1min` `5min` `10min` `15min` `30min` `1h` `4h` `1d` `1w` `1mo` |
| MT5 | `M1` `M5` `M15` `M30` `H1` `H4` `D1` `W1` `MN1` |

---

## Directory Structure

```
balerion-data/
├── data/                          # gitignored
│   ├── fx/
│   │   └── <symbol>/              # e.g. eurusd/
│   │       ├── eurusd_dukascopy_15min.parquet
│   │       ├── eurusd_dukascopy_1h.parquet
│   │       ├── eurusd_mt5_5min.parquet
│   │       ├── eurusd_mt5_1h.parquet
│   │       └── eurusd_mt5_1d.parquet
│   ├── indices/
│   │   └── <symbol>/              # e.g. us30/
│   ├── crypto/
│   │   └── btcusd/
│   └── calendar/
│       └── weekly/                # ForexFactory high-impact events
│           └── 2026-W09_high_impact.parquet
│
├── scripts/
│   ├── collect_dukascopy.py       # ⭐ Primary Dukascopy collector
│   ├── collect_historical_data.py # MT5 initial collection (M5, H1, D1)
│   ├── collect_mt5_multitf.py     # MT5 flexible multi-TF collector
│   ├── update_mt5_m1_incremental.py  # MT5 M1 incremental updater
│   ├── ff_calendar.py             # ForexFactory economic calendar
│   ├── check_data.py              # Data quality checker
│   ├── config.py                  # Symbols, paths, MT5 settings
│   ├── mt5_utils.py               # Shared MT5 utilities
│   ├── collect_dukascopy_h1.py    # Legacy — use collect_dukascopy.py
│   └── update_weekly_data.py      # Legacy — use update_mt5_m1_incremental.py
│
├── docs/
├── pyproject.toml
├── .python-version                # 3.11
└── CLAUDE.md
```

---

## Installation

**Requires:** Python 3.11+, [uv](https://github.com/astral-sh/uv)

```powershell
# Install uv (Windows)
irm https://astral.sh/uv/install.ps1 | iex

# Install dependencies
uv sync
```

```bash
# Linux / Mac
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

---

## Scripts Reference

### collect_dukascopy.py — Dukascopy collector ⭐

Full collection (~10 years) or incremental update for any symbol and timeframe.

```bash
# Full collection — all symbols at 15min
uv run python scripts/collect_dukascopy.py --tf 15min

# Specific symbols
uv run python scripts/collect_dukascopy.py --symbols EURUSD GBPUSD --tf 1h

# Incremental update — top up last 7 days
uv run python scripts/collect_dukascopy.py --tf 15min --update --days 7

# Force re-download (overwrite existing)
uv run python scripts/collect_dukascopy.py --symbols USDJPY --tf 30min --force
```

**Output:** `data/<category>/<symbol>/<symbol>_dukascopy_<tf>.parquet`

**Notes:**
- Offer side is bid (standard for FX backtesting)
- Skips symbols that already have a file unless `--force` is passed
- `--update` falls back to a full collection if no existing file is found

---

### collect_historical_data.py — MT5 initial collection

Fetches maximum available history from MT5 at M5, H1, and D1 for all configured symbols. Run once to seed the dataset.

```bash
uv run python scripts/collect_historical_data.py
```

**Output:** `data/<category>/<symbol>/<symbol>_mt5_<tf>.parquet`

**Runtime:** 5–15 minutes for all 32 symbols × 3 timeframes. MT5 must be running and logged in.

---

### collect_mt5_multitf.py — MT5 flexible multi-TF collector

Collect or update MT5 data at any combination of timeframes and symbols.

```bash
# Collect all symbols at default TFs (M15, H4)
uv run python scripts/collect_mt5_multitf.py

# Specific symbols and timeframes
uv run python scripts/collect_mt5_multitf.py --symbols USDJPY XAUUSD --tfs M5 H1 D1

# Incremental update — merge last 14 days
uv run python scripts/collect_mt5_multitf.py --update

# Update with a longer lookback
uv run python scripts/collect_mt5_multitf.py --update --days 30

# Force full re-collect
uv run python scripts/collect_mt5_multitf.py --force
```

Valid `--tfs` values: `M1 M5 M15 M30 H1 H4 D1 W1 MN1`

---

### update_mt5_m1_incremental.py — MT5 M1 updater

Efficiently appends only missing 1-minute bars since the last saved timestamp.

```bash
# Update all FX pairs (default)
uv run python scripts/update_mt5_m1_incremental.py

# Update specific symbols
uv run python scripts/update_mt5_m1_incremental.py --symbols EURUSD GBPUSD

# Update index symbols
uv run python scripts/update_mt5_m1_incremental.py --indices

# Update everything (FX + indices)
uv run python scripts/update_mt5_m1_incremental.py --all

# Preview without writing
uv run python scripts/update_mt5_m1_incremental.py --dry-run
```

Bootstraps a full M1 history automatically if no existing file is found.

---

### ff_calendar.py — ForexFactory economic calendar

Fetches high-impact economic events from the ForexFactory XML feed.

```bash
# Fetch and save current week's high-impact events
uv run python scripts/ff_calendar.py

# Refresh end-of-week (updates previous/actual values)
uv run python scripts/ff_calendar.py --refresh
```

**Output:** `data/calendar/weekly/YYYY-W<nn>_high_impact.parquet`

**Schema:**

| Column | Description |
|--------|-------------|
| `event_datetime` | Event time in UTC |
| `title` | Event name |
| `country` | Currency code (USD, EUR, GBP, …) |
| `impact` | Low / Medium / High |
| `forecast` | Analyst estimate |
| `previous` | Prior period's result (becomes the actual after release) |

---

### check_data.py — Data quality

Validates all parquet files: row counts, date ranges, duplicates, missing values, large gaps.

```bash
uv run python scripts/check_data.py
```

---

## Parquet Schema — OHLCV

| Column | Type | Notes |
|--------|------|-------|
| `timestamp` | `datetime64[ns, UTC]` | Bar open time, UTC |
| `open` | `float64` | |
| `high` | `float64` | |
| `low` | `float64` | |
| `close` | `float64` | |
| `volume` | `float64` | Tick volume (MT5) or Dukascopy volume |
| `spread` | `float64` | MT5 only, optional |
| `real_volume` | `float64` | MT5 only, optional |

---

## Reading Data

```python
import pandas as pd

df = pd.read_parquet("data/fx/eurusd/eurusd_dukascopy_1h.parquet")

print(f"Rows      : {len(df):,}")
print(f"Date range: {df['timestamp'].min()} -> {df['timestamp'].max()}")

# Resample to 4H
df_4h = df.set_index("timestamp").resample("4h").agg({
    "open":   "first",
    "high":   "max",
    "low":    "min",
    "close":  "last",
    "volume": "sum",
}).dropna()
```

---

## Typical Workflows

### First-time setup

```bash
# 1. Seed Dukascopy data (all pairs, all TFs you want — takes a while)
uv run python scripts/collect_dukascopy.py --tf 15min
uv run python scripts/collect_dukascopy.py --tf 1h
uv run python scripts/collect_dukascopy.py --tf 1d

# 2. Seed MT5 data (M5, H1, D1 for all symbols)
uv run python scripts/collect_historical_data.py

# 3. Verify
uv run python scripts/check_data.py
```

### Regular updates

```bash
# Dukascopy — top up last 7 days
uv run python scripts/collect_dukascopy.py --tf 15min --update
uv run python scripts/collect_dukascopy.py --tf 1h --update

# MT5 M1 — append missing bars since last timestamp
uv run python scripts/update_mt5_m1_incremental.py --all

# MT5 other TFs — merge last 14 days
uv run python scripts/collect_mt5_multitf.py --update
```

### Economic calendar

```bash
# Monday: fetch the week's schedule
uv run python scripts/ff_calendar.py

# Friday: refresh to capture any updated actuals
uv run python scripts/ff_calendar.py --refresh
```

---

## Configuration

All symbol lists and MT5 settings live in `scripts/config.py`.

```python
FX_SYMBOLS     = ["EURUSD", "GBPUSD", ...]  # 26 pairs
INDEX_SYMBOLS  = ["US30", "SPX500", ...]    # 6 indices

SYMBOL_ALTERNATIVES = {
    "US30": ["US30", "US30.cash", "USA30", ...],  # broker name variants
    ...
}

MAX_BARS_PER_REQUEST = 99999   # MT5 API limit
SAVE_FORMAT          = "parquet"
```

---

## Troubleshooting

**MT5 connection fails**
- Ensure MetaTrader 5 is open and logged in
- Enable automated trading: Tools → Options → Expert Advisors → Allow automated trading

**Symbol not found**
- Check the symbol name shown in MT5's Market Watch
- Add the variant to `SYMBOL_ALTERNATIVES` in `config.py`

**Dukascopy returns no data**
- The feed occasionally has gaps or rate limits — re-run with `--force`
- Crypto (BTCUSD) history is shallower than FX

**Large gaps in MT5 M1 data**
- M1 depth is broker-dependent (~3 months typical); use Dukascopy for deep history
- Weekend and holiday gaps are expected

---

## License

Private — all rights reserved.
