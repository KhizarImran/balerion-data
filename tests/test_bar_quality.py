"""
Bar Data Quality Tests
======================
Validates the integrity and quality of collected OHLCV bar data.

Works with any timeframe parquet file — the timeframe is either detected
automatically from the median bar interval or supplied via --timeframe.

Usage
-----
# Run against all default MT5 symbols (auto-detects timeframe from filename)
uv run pytest tests/test_bar_quality.py -v

# Single symbol from the default set
uv run pytest tests/test_bar_quality.py -v --symbol EURUSD

# Point at any parquet file directly (timeframe auto-detected)
uv run pytest tests/test_bar_quality.py -v --file data/fx/gbpusd_dukascopy_1h.parquet

# Override the detected timeframe explicitly (minutes)
uv run pytest tests/test_bar_quality.py -v --file data/fx/gbpusd_dukascopy_1h.parquet --timeframe 60
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

# Allow imports from scripts/
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import config

# ---------------------------------------------------------------------------
# Timeframe detection
# ---------------------------------------------------------------------------

# Known timeframes: interval in minutes -> display label
_KNOWN_TIMEFRAMES_MIN = {
    1: "M1",
    5: "M5",
    10: "M10",
    15: "M15",
    30: "M30",
    60: "H1",
    240: "H4",
    1440: "D1",
    10080: "W1",
}


def _detect_timeframe_minutes(df: pd.DataFrame) -> int:
    """
    Infer the bar interval in minutes from the median gap between consecutive
    timestamps. Snaps to the nearest known timeframe; falls back to the raw
    median if nothing matches within 20%.
    """
    diffs_min = df["timestamp"].diff().dropna().dt.total_seconds() / 60
    # Use the mode-like approach: most common positive diff
    positive = diffs_min[diffs_min > 0]
    if positive.empty:
        return 1
    median_min = positive.median()

    best_match, best_delta = 1, float("inf")
    for known_min in _KNOWN_TIMEFRAMES_MIN:
        delta = abs(median_min - known_min) / known_min
        if delta < best_delta:
            best_delta = delta
            best_match = known_min

    # Accept the snap if within 20% of a known timeframe
    if best_delta <= 0.20:
        return best_match

    return max(1, round(median_min))


def _tf_label(tf_minutes: int) -> str:
    return _KNOWN_TIMEFRAMES_MIN.get(tf_minutes, f"{tf_minutes}min")


# ---------------------------------------------------------------------------
# Default symbols (MT5 parquet files)
# ---------------------------------------------------------------------------

ALL_SYMBOLS = [(s, "fx") for s in config.FX_SYMBOLS] + [
    (s, "indices") for s in config.INDEX_SYMBOLS
]
SYMBOL_IDS = [s for s, _ in ALL_SYMBOLS]


def _default_filepath(symbol: str, category: str) -> Path:
    base = config.FX_DIR if category == "fx" else config.INDICES_DIR
    return base / f"{symbol.lower()}_1m.parquet"


def _load_path(path: Path) -> pd.DataFrame:
    if not path.exists():
        pytest.skip(f"Data file not found: {path}")
    df = pd.read_parquet(path)
    # Normalise: timestamp may be index or column
    if "timestamp" not in df.columns:
        df = df.reset_index()
        if "timestamp" not in df.columns:
            df = df.rename(columns={df.columns[0]: "timestamp"})
    ts = df["timestamp"]
    if hasattr(ts.dtype, "tz") and ts.dtype.tz is not None:
        # Already tz-aware — just convert to UTC without re-parsing
        df["timestamp"] = ts.dt.tz_convert("UTC")
    else:
        df["timestamp"] = pd.to_datetime(ts, utc=True)
    return df.sort_values("timestamp").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _resolve_file_arg(raw: str) -> Path:
    """Accept absolute paths or paths relative to the repo root."""
    p = Path(raw)
    if p.is_absolute():
        return p
    # Try relative to repo root first, then cwd
    repo_root = Path(__file__).parent.parent
    candidate = repo_root / p
    if candidate.exists():
        return candidate
    return p  # let the caller handle missing


@pytest.fixture(params=ALL_SYMBOLS, ids=SYMBOL_IDS)
def bar_data(request):
    """
    Fixture used when running the default MT5 symbol suite OR a single --file.

    When --file is passed every parametrized symbol is skipped and the single
    file is tested once (attached to the first param so pytest still runs).
    """
    file_arg = request.config.getoption("--file", default=None)
    tf_override = request.config.getoption("--timeframe", default=None)

    if file_arg:
        # Only run once — skip all but the first param slot
        if request.param != ALL_SYMBOLS[0]:
            pytest.skip("--file mode: single file, skipping extra param slots")
        path = _resolve_file_arg(file_arg)
        df = _load_path(path)
        tf = tf_override if tf_override else _detect_timeframe_minutes(df)
        label = path.name
        return label, df, tf

    # Default mode: MT5 symbol suite
    symbol, category = request.param
    sym_filter = request.config.getoption("--symbol", default=None)
    if sym_filter and symbol != sym_filter.upper():
        pytest.skip(f"Skipping {symbol} (--symbol={sym_filter})")

    path = _default_filepath(symbol, category)
    df = _load_path(path)
    tf = tf_override if tf_override else _detect_timeframe_minutes(df)
    return symbol, df, tf


# ---------------------------------------------------------------------------
# Thresholds derived from timeframe
# ---------------------------------------------------------------------------


def _min_rows(tf_minutes: int) -> int:
    """
    Minimum acceptable row count.
    Target: at least 90 days of trading bars.
    FX trades ~16h/day on weekdays (~5/7 of the time).
    """
    trading_minutes_per_day = 16 * 60
    bars_per_day = trading_minutes_per_day / tf_minutes
    return max(500, int(bars_per_day * 90))


def _min_history_days(tf_minutes: int) -> int:
    """Minimum calendar-day span we expect in the dataset."""
    # For very long history sources (Dukascopy) we don't lower the bar —
    # just require at least 90 days regardless of timeframe.
    return 90


def _max_intraweek_gap_hours(tf_minutes: int) -> float:
    """
    Maximum tolerated mid-week gap.
    Rule: allow up to 3x the bar interval, floored at 2h, capped at 8h.
    """
    gap_hours = (tf_minutes * 3) / 60
    return max(2.0, min(gap_hours, 8.0))


def _max_weekend_gap_hours(tf_minutes: int) -> float:
    """
    FX weekend closure is ~48h (Fri 22:00 UTC -> Sun 22:00 UTC).
    For weekly bars the 'weekend' gap is a whole week — don't check it.
    """
    if tf_minutes >= 10080:  # W1
        return 24 * 14  # two weeks
    return 55.0


def _bar_interval_label(tf_minutes: int) -> str:
    return _tf_label(tf_minutes)


# ---------------------------------------------------------------------------
# 1. File & Schema
# ---------------------------------------------------------------------------


class TestFileAndSchema:
    """The parquet file exists and has the expected columns and dtypes."""

    def test_required_columns_present(self, bar_data):
        _, df, _ = bar_data
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        missing = required - set(df.columns)
        assert not missing, f"Missing columns: {missing}"

    def test_numeric_ohlcv(self, bar_data):
        _, df, _ = bar_data
        for col in ["open", "high", "low", "close"]:
            assert pd.api.types.is_numeric_dtype(df[col]), (
                f"Column '{col}' is not numeric (dtype={df[col].dtype})"
            )

    def test_volume_non_negative(self, bar_data):
        _, df, _ = bar_data
        assert (df["volume"] >= 0).all(), "Volume contains negative values"


# ---------------------------------------------------------------------------
# 2. Row Count & Recency
# ---------------------------------------------------------------------------


class TestRowCountAndRecency:
    """The dataset is large enough and reasonably up to date."""

    def test_minimum_row_count(self, bar_data):
        label, df, tf = bar_data
        min_rows = _min_rows(tf)
        assert len(df) >= min_rows, (
            f"[{_tf_label(tf)}] Only {len(df):,} rows — expected >= {min_rows:,} "
            f"(~90 trading days at {_tf_label(tf)})"
        )

    def test_data_not_stale(self, bar_data):
        """Latest bar must be within the last 14 days."""
        _, df, tf = bar_data
        latest = df["timestamp"].max()
        age_days = (pd.Timestamp.now(tz="UTC") - latest).days
        assert age_days <= 14, (
            f"[{_tf_label(tf)}] Latest bar is {age_days} days old — may need updating"
        )

    def test_minimum_history_span(self, bar_data):
        _, df, tf = bar_data
        min_days = _min_history_days(tf)
        span_days = (df["timestamp"].max() - df["timestamp"].min()).days
        assert span_days >= min_days, (
            f"[{_tf_label(tf)}] History span is only {span_days} days — expected >= {min_days}"
        )


# ---------------------------------------------------------------------------
# 3. Timestamp Integrity
# ---------------------------------------------------------------------------


class TestTimestamps:
    """Timestamps are unique, sorted, and timezone-aware."""

    def test_no_duplicate_timestamps(self, bar_data):
        _, df, tf = bar_data
        n_dupes = df["timestamp"].duplicated().sum()
        assert n_dupes == 0, f"[{_tf_label(tf)}] {n_dupes:,} duplicate timestamps found"

    def test_timestamps_are_sorted(self, bar_data):
        _, df, tf = bar_data
        assert df["timestamp"].is_monotonic_increasing, (
            f"[{_tf_label(tf)}] Timestamps are not sorted ascending"
        )

    def test_timestamps_are_utc(self, bar_data):
        _, df, tf = bar_data
        tz = df["timestamp"].dt.tz
        assert tz is not None, f"[{_tf_label(tf)}] Timestamps have no timezone (expected UTC)"
        assert str(tz).upper() in ("UTC", "UTC+00:00"), (
            f"[{_tf_label(tf)}] Unexpected timezone: {tz}"
        )

    def test_no_future_timestamps(self, bar_data):
        """No bar more than 4 hours ahead of local clock."""
        _, df, tf = bar_data
        horizon = pd.Timestamp.now(tz="UTC") + pd.Timedelta(hours=4)
        future = df[df["timestamp"] > horizon]
        assert len(future) == 0, (
            f"[{_tf_label(tf)}] {len(future)} bars are more than 4h ahead of local clock"
        )

    def test_timestamps_on_bar_boundary(self, bar_data):
        """
        Timestamps must fall on the expected bar boundary.
        - M1  : seconds == 0, microseconds == 0
        - H1  : minutes == 0, seconds == 0
        - D1  : hours == 0, minutes == 0, seconds == 0
        - etc.
        For sub-minute data or unusual timeframes we only check seconds == 0.
        """
        _, df, tf = bar_data
        ts = df["timestamp"]

        if tf < 1:
            # Sub-minute: just ensure no microsecond noise
            bad = ts.dt.microsecond != 0
        elif tf < 60:
            # M1–M30: on the minute
            bad = (ts.dt.second != 0) | (ts.dt.microsecond != 0)
        elif tf < 1440:
            # H1–H4: on the hour
            bad = (ts.dt.minute != 0) | (ts.dt.second != 0) | (ts.dt.microsecond != 0)
        elif tf < 10080:
            # D1: on midnight
            bad = (ts.dt.hour != 0) | (ts.dt.minute != 0) | (ts.dt.second != 0)
        else:
            # W1+: skip boundary check
            bad = pd.Series([False] * len(df))

        n = bad.sum()
        assert n == 0, (
            f"[{_tf_label(tf)}] {n:,} timestamps not on a {_tf_label(tf)} boundary\n"
            f"  Examples: {ts[bad].head(3).tolist()}"
        )


# ---------------------------------------------------------------------------
# 4. OHLC Sanity
# ---------------------------------------------------------------------------


class TestOHLCSanity:
    """OHLC values obey fundamental price relationships."""

    def test_no_null_ohlcv(self, bar_data):
        _, df, tf = bar_data
        nulls = df[["open", "high", "low", "close", "volume"]].isnull().sum()
        total = nulls.sum()
        assert total == 0, f"[{_tf_label(tf)}] Null values found:\n{nulls[nulls > 0]}"

    def test_high_gte_low(self, bar_data):
        _, df, tf = bar_data
        bad = df[df["high"] < df["low"]]
        assert len(bad) == 0, f"[{_tf_label(tf)}] {len(bad):,} bars where high < low"

    def test_high_gte_open(self, bar_data):
        _, df, tf = bar_data
        bad = df[df["high"] < df["open"]]
        assert len(bad) == 0, f"[{_tf_label(tf)}] {len(bad):,} bars where high < open"

    def test_high_gte_close(self, bar_data):
        _, df, tf = bar_data
        bad = df[df["high"] < df["close"]]
        assert len(bad) == 0, f"[{_tf_label(tf)}] {len(bad):,} bars where high < close"

    def test_low_lte_open(self, bar_data):
        _, df, tf = bar_data
        bad = df[df["low"] > df["open"]]
        assert len(bad) == 0, f"[{_tf_label(tf)}] {len(bad):,} bars where low > open"

    def test_low_lte_close(self, bar_data):
        _, df, tf = bar_data
        bad = df[df["low"] > df["close"]]
        assert len(bad) == 0, f"[{_tf_label(tf)}] {len(bad):,} bars where low > close"

    def test_no_zero_prices(self, bar_data):
        _, df, tf = bar_data
        for col in ["open", "high", "low", "close"]:
            zeros = (df[col] == 0).sum()
            assert zeros == 0, f"[{_tf_label(tf)}] {zeros:,} zero values in '{col}'"

    def test_no_negative_prices(self, bar_data):
        _, df, tf = bar_data
        for col in ["open", "high", "low", "close"]:
            neg = (df[col] < 0).sum()
            assert neg == 0, f"[{_tf_label(tf)}] {neg:,} negative values in '{col}'"

    def test_price_spike_detection(self, bar_data):
        """
        Flag bars where high-low range exceeds 20x the rolling median range.
        Window scales with timeframe so we always look back ~200 bars.
        """
        _, df, tf = bar_data
        bar_range = df["high"] - df["low"]
        rolling_median = bar_range.rolling(window=200, min_periods=50).median()
        mask = rolling_median.notna() & (rolling_median > 0)
        spikes = (bar_range[mask] > rolling_median[mask] * 20).sum()
        assert spikes == 0, (
            f"[{_tf_label(tf)}] {spikes:,} bars with range > 20x rolling median "
            f"— possible data corruption"
        )


# ---------------------------------------------------------------------------
# 5. Gap Analysis
# ---------------------------------------------------------------------------


BANK_HOLIDAY_DATES = {
    (12, 24),  # Christmas Eve
    (12, 25),  # Christmas Day
    (12, 26),  # Boxing Day
    (12, 31),  # New Year's Eve
    (1, 1),  # New Year's Day
    (1, 2),  # New Year's Day (observed)
}


def _is_bank_holiday(ts: pd.Timestamp) -> bool:
    return (ts.month, ts.day) in BANK_HOLIDAY_DATES


class TestGaps:
    """Checks for unexpectedly long gaps that indicate missing data."""

    def test_no_excessive_intraweek_gaps(self, bar_data):
        _, df, tf = bar_data
        max_gap_h = _max_intraweek_gap_hours(tf)

        diffs = df["timestamp"].diff().dropna()
        prev_ts = df["timestamp"].iloc[:-1].reset_index(drop=True)
        diffs_reset = diffs.reset_index(drop=True)

        # Exclude gaps that cross a weekend (Fri/Sat/Sun start)
        is_weekend_cross = prev_ts.dt.weekday >= 4  # Fri=4, Sat=5, Sun=6
        is_holiday = prev_ts.apply(_is_bank_holiday)

        mid_week_diffs = diffs_reset[~is_weekend_cross & ~is_holiday]
        excessive = mid_week_diffs[mid_week_diffs > pd.Timedelta(hours=max_gap_h)]

        assert len(excessive) == 0, (
            f"[{_tf_label(tf)}] {len(excessive)} mid-week gaps > {max_gap_h}h "
            f"(after excluding weekends/holidays):\n{excessive.to_string()}"
        )

    def test_weekend_gaps_not_too_long(self, bar_data):
        _, df, tf = bar_data
        max_gap_h = _max_weekend_gap_hours(tf)

        diffs = df["timestamp"].diff().dropna()
        oversized = diffs[diffs > pd.Timedelta(hours=max_gap_h)]
        assert len(oversized) == 0, (
            f"[{_tf_label(tf)}] {len(oversized)} gaps exceed {max_gap_h}h "
            f"(max gap found: {diffs.max()})"
        )
