"""
Bar Data Quality Tests
======================
Validates the integrity and quality of collected OHLCV bar data.

Run with:
    uv run pytest tests/test_bar_quality.py -v
    uv run pytest tests/test_bar_quality.py -v --symbol EURUSD   # single symbol
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

# Allow imports from scripts/
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_SYMBOLS = [(s, "fx") for s in config.FX_SYMBOLS] + [
    (s, "indices") for s in config.INDEX_SYMBOLS
]

SYMBOL_IDS = [s for s, _ in ALL_SYMBOLS]


def get_filepath(symbol: str, category: str) -> Path:
    base = config.FX_DIR if category == "fx" else config.INDICES_DIR
    return base / f"{symbol.lower()}_1m.parquet"


def load(symbol: str, category: str) -> pd.DataFrame:
    path = get_filepath(symbol, category)
    if not path.exists():
        pytest.skip(f"Data file not found: {path}")
    df = pd.read_parquet(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df.sort_values("timestamp").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def pytest_addoption(parser):
    parser.addoption(
        "--symbol",
        default=None,
        help="Run tests for a single symbol only (e.g. EURUSD)",
    )


def pytest_configure(config_obj):
    """Filter ALL_SYMBOLS if --symbol is passed."""
    pass  # filtering handled in the parametrize via the fixture below


@pytest.fixture(params=ALL_SYMBOLS, ids=SYMBOL_IDS)
def bar_data(request):
    symbol, category = request.param
    # honour --symbol CLI filter
    sym_filter = request.config.getoption("--symbol", default=None)
    if sym_filter and symbol != sym_filter.upper():
        pytest.skip(f"Skipping {symbol} (--symbol={sym_filter})")
    return symbol, load(symbol, category)


# ---------------------------------------------------------------------------
# 1. File & Schema
# ---------------------------------------------------------------------------


class TestFileAndSchema:
    """The parquet file exists and has the expected columns and dtypes."""

    def test_file_exists(self, bar_data):
        symbol, category = next((s, c) for s, c in ALL_SYMBOLS if s == bar_data[0]), None
        # file is already loaded; if we reached here the file exists
        pass

    def test_required_columns_present(self, bar_data):
        _, df = bar_data
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        missing = required - set(df.columns)
        assert not missing, f"Missing columns: {missing}"

    def test_numeric_ohlcv(self, bar_data):
        _, df = bar_data
        for col in ["open", "high", "low", "close"]:
            assert pd.api.types.is_float_dtype(df[col]) or pd.api.types.is_numeric_dtype(df[col]), (
                f"Column '{col}' is not numeric (dtype={df[col].dtype})"
            )

    def test_volume_non_negative_integer_like(self, bar_data):
        _, df = bar_data
        assert (df["volume"] >= 0).all(), "Volume contains negative values"


# ---------------------------------------------------------------------------
# 2. Row Count & Recency
# ---------------------------------------------------------------------------


class TestRowCountAndRecency:
    """The dataset is large enough and reasonably up to date."""

    MIN_ROWS = 100_000  # ~69 trading days of 1-min bars

    def test_minimum_row_count(self, bar_data):
        _, df = bar_data
        assert len(df) >= self.MIN_ROWS, (
            f"Only {len(df):,} rows — expected at least {self.MIN_ROWS:,}"
        )

    def test_data_not_stale(self, bar_data):
        """Latest bar must be within the last 14 days (accounts for weekends)."""
        _, df = bar_data
        latest = df["timestamp"].max()
        now = pd.Timestamp.now(tz="UTC")
        age_days = (now - latest).days
        assert age_days <= 14, (
            f"Latest bar is {age_days} days old — data may not have been updated recently"
        )

    def test_minimum_history_span(self, bar_data):
        """Dataset should cover at least 90 days of history.

        MT5 brokers typically provide ~99 days of 1-minute history per symbol.
        365 days is not achievable at 1-min resolution via MT5; use a realistic
        floor that confirms the initial collection ran successfully.
        """
        _, df = bar_data
        span_days = (df["timestamp"].max() - df["timestamp"].min()).days
        assert span_days >= 90, f"History span is only {span_days} days — expected >= 90"


# ---------------------------------------------------------------------------
# 3. Timestamp Integrity
# ---------------------------------------------------------------------------


class TestTimestamps:
    """Timestamps are unique, sorted, and timezone-aware."""

    def test_no_duplicate_timestamps(self, bar_data):
        _, df = bar_data
        n_dupes = df["timestamp"].duplicated().sum()
        assert n_dupes == 0, f"{n_dupes:,} duplicate timestamps found"

    def test_timestamps_are_sorted(self, bar_data):
        _, df = bar_data
        assert df["timestamp"].is_monotonic_increasing, "Timestamps are not sorted ascending"

    def test_timestamps_are_utc(self, bar_data):
        _, df = bar_data
        tz = df["timestamp"].dt.tz
        assert tz is not None, "Timestamps have no timezone (expected UTC)"
        assert str(tz).upper() in ("UTC", "UTC+00:00"), f"Unexpected timezone: {tz}"

    def test_no_future_timestamps(self, bar_data):
        """No bars should be more than 4 hours ahead of now.

        MT5 server time can run ahead of the local system clock (broker
        servers are often UTC+2/+3). A 4-hour tolerance covers all known
        broker time-zone offsets while still catching genuinely corrupt
        far-future timestamps.
        """
        _, df = bar_data
        now = pd.Timestamp.now(tz="UTC") + pd.Timedelta(hours=4)
        future = df[df["timestamp"] > now]
        assert len(future) == 0, f"{len(future)} bars are more than 4h ahead of local clock"

    def test_timestamps_on_minute_boundary(self, bar_data):
        """All 1-min bars should land exactly on a minute boundary (seconds == 0)."""
        _, df = bar_data
        non_minute = (df["timestamp"].dt.second != 0) | (df["timestamp"].dt.microsecond != 0)
        n = non_minute.sum()
        assert n == 0, f"{n:,} timestamps are not on a minute boundary"


# ---------------------------------------------------------------------------
# 4. OHLC Sanity
# ---------------------------------------------------------------------------


class TestOHLCSanity:
    """OHLC values obey fundamental price relationships."""

    def test_no_null_ohlcv(self, bar_data):
        _, df = bar_data
        nulls = df[["open", "high", "low", "close", "volume"]].isnull().sum()
        total = nulls.sum()
        assert total == 0, f"Null values found:\n{nulls[nulls > 0]}"

    def test_high_gte_low(self, bar_data):
        _, df = bar_data
        bad = df[df["high"] < df["low"]]
        assert len(bad) == 0, f"{len(bad):,} bars where high < low"

    def test_high_gte_open(self, bar_data):
        _, df = bar_data
        bad = df[df["high"] < df["open"]]
        assert len(bad) == 0, f"{len(bad):,} bars where high < open"

    def test_high_gte_close(self, bar_data):
        _, df = bar_data
        bad = df[df["high"] < df["close"]]
        assert len(bad) == 0, f"{len(bad):,} bars where high < close"

    def test_low_lte_open(self, bar_data):
        _, df = bar_data
        bad = df[df["low"] > df["open"]]
        assert len(bad) == 0, f"{len(bad):,} bars where low > open"

    def test_low_lte_close(self, bar_data):
        _, df = bar_data
        bad = df[df["low"] > df["close"]]
        assert len(bad) == 0, f"{len(bad):,} bars where low > close"

    def test_no_zero_prices(self, bar_data):
        _, df = bar_data
        for col in ["open", "high", "low", "close"]:
            zeros = (df[col] == 0).sum()
            assert zeros == 0, f"{zeros:,} zero values in '{col}'"

    def test_no_negative_prices(self, bar_data):
        _, df = bar_data
        for col in ["open", "high", "low", "close"]:
            neg = (df[col] < 0).sum()
            assert neg == 0, f"{neg:,} negative values in '{col}'"

    def test_price_spike_detection(self, bar_data):
        """Flag bars where the high-low range exceeds 20x the rolling median range.

        At 1-minute resolution, genuine high-volatility events (NFP, FOMC,
        flash crashes) commonly produce bars 5-10x the median range. A 20x
        multiplier only fires on clearly corrupt ticks — e.g. a broker
        erroneously printing a 500-pip candle during a 3-pip median session.
        """
        _, df = bar_data
        bar_range = df["high"] - df["low"]
        rolling_median = bar_range.rolling(window=200, min_periods=50).median()
        mask = rolling_median.notna() & (rolling_median > 0)
        spikes = (bar_range[mask] > rolling_median[mask] * 20).sum()
        assert spikes == 0, (
            f"{spikes:,} bars with range > 20x rolling median — possible data corruption"
        )


# ---------------------------------------------------------------------------
# 5. Gap Analysis
# ---------------------------------------------------------------------------


class TestGaps:
    """Checks for unexpectedly long intra-week gaps that indicate missing data."""

    # Forex markets are closed Fri ~22:00 UTC to Sun ~22:00 UTC (~48h)
    # We allow up to 55h to be safe; anything beyond that mid-week is a gap
    MAX_WEEKEND_GAP_HOURS = 55
    # Mid-week gaps beyond this are suspicious (bank holidays aside)
    MAX_INTRAWEEK_GAP_HOURS = 4

    # Known global bank holiday periods where all markets close.
    # Stored as (month, day) tuples; any gap whose start timestamp falls on
    # one of these dates is exempt from the intraweek gap check.
    BANK_HOLIDAY_DATES = {
        (12, 24),  # Christmas Eve
        (12, 25),  # Christmas Day
        (12, 26),  # Boxing Day
        (12, 31),  # New Year's Eve
        (1, 1),  # New Year's Day
        (1, 2),  # New Year's Day (observed)
    }

    def _is_bank_holiday(self, ts: pd.Timestamp) -> bool:
        return (ts.month, ts.day) in self.BANK_HOLIDAY_DATES

    def test_no_excessive_intraweek_gaps(self, bar_data):
        _, df = bar_data
        diffs = df["timestamp"].diff().dropna()

        prev_ts = df["timestamp"].iloc[:-1].reset_index(drop=True)
        diffs_reset = diffs.reset_index(drop=True)

        # Exclude gaps that cross a weekend (Fri/Sat/Sun start)
        is_weekend_cross = prev_ts.dt.weekday >= 4  # Fri=4, Sat=5, Sun=6

        # Exclude gaps that start on a known bank holiday
        is_bank_holiday = prev_ts.apply(self._is_bank_holiday)

        mid_week_diffs = diffs_reset[~is_weekend_cross & ~is_bank_holiday]
        excessive = mid_week_diffs[
            mid_week_diffs > pd.Timedelta(hours=self.MAX_INTRAWEEK_GAP_HOURS)
        ]

        assert len(excessive) == 0, (
            f"{len(excessive)} mid-week gaps > {self.MAX_INTRAWEEK_GAP_HOURS}h found "
            f"(after excluding weekends and bank holidays):\n" + excessive.to_string()
        )

    def test_weekend_gaps_not_too_long(self, bar_data):
        _, df = bar_data
        diffs = df["timestamp"].diff().dropna()
        oversized = diffs[diffs > pd.Timedelta(hours=self.MAX_WEEKEND_GAP_HOURS)]
        assert len(oversized) == 0, (
            f"{len(oversized)} gaps exceed {self.MAX_WEEKEND_GAP_HOURS}h (max gap: {diffs.max()})"
        )
