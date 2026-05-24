"""
Balerion Quant Terminal
=======================
Bloomberg-inspired quantitative analysis platform for strategy research.
"""

import datetime
import os
import warnings

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from pathlib import Path
from plotly.subplots import make_subplots
from scipy import stats
from statsmodels.tsa.stattools import acf, adfuller
from statsmodels.stats.diagnostic import acorr_ljungbox

warnings.filterwarnings("ignore")

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

DATA_DIR = Path(os.environ.get("DATA_DIR", str(Path(__file__).parent.parent / "data")))

C = {
    "bg":     "#080d16",
    "panel":  "#0c1524",
    "dark":   "#050a10",
    "border": "#172840",
    "cyan":   "#00c8f0",
    "orange": "#ff6b35",
    "green":  "#00e87a",
    "red":    "#ff3a5c",
    "text":   "#cdd9e5",
    "muted":  "#3d5a78",
    "grid":   "#0f2035",
    "yellow": "#f0c040",
}

ANN = {
    "1min":  252 * 24 * 60,
    "5min":  252 * 24 * 12,
    "15min": 252 * 24 * 4,
    "30min": 252 * 24 * 2,
    "1h":    252 * 24,
    "4h":    252 * 6,
    "1d":    252,
}

TF_ORDER = ["1min", "5min", "15min", "30min", "1h", "4h", "1d"]


def _rgba(hex_color: str, alpha: float) -> str:
    """Convert #rrggbb hex + float alpha to rgba() string (Plotly 6 compatible)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha:.3f})"


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG  (must be first Streamlit call)
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="BALERION | Quant Terminal",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOM CSS — Bloomberg-style dark terminal
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown(f"""
<style>
/* ── Base ── */
html, body, [class*="css"] {{
    font-family: 'Courier New', 'Consolas', 'JetBrains Mono', monospace !important;
}}
[data-testid="stAppViewContainer"] {{
    background: {C['bg']};
}}
[data-testid="stSidebar"] {{
    background: {C['dark']};
    border-right: 1px solid {C['border']};
}}
[data-testid="stHeader"] {{ background: transparent !important; }}
section.main > div.block-container {{
    padding-top: 0.5rem;
    padding-bottom: 1rem;
    max-width: 100%;
}}

/* ── Headings ── */
h1 {{
    color: {C['cyan']} !important;
    font-size: 13px !important;
    letter-spacing: 4px;
    text-transform: uppercase;
    border-bottom: 1px solid {C['border']};
    padding-bottom: 6px;
    margin-bottom: 12px !important;
}}
h2 {{
    color: {C['cyan']} !important;
    font-size: 11px !important;
    letter-spacing: 3px;
    text-transform: uppercase;
}}
h3 {{
    color: {C['orange']} !important;
    font-size: 10px !important;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 6px !important;
}}
h4 {{
    color: {C['yellow']} !important;
    font-size: 10px !important;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin: 14px 0 6px 0 !important;
}}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {{
    background: {C['dark']};
    border-bottom: 1px solid {C['border']};
    gap: 0;
}}
.stTabs [data-baseweb="tab"] {{
    color: {C['muted']};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    padding: 8px 16px;
    border-radius: 0 !important;
}}
.stTabs [aria-selected="true"] {{
    color: {C['cyan']} !important;
    background: {C['panel']} !important;
    border-bottom: 2px solid {C['cyan']} !important;
}}
.stTabs [data-baseweb="tab-panel"] {{
    background: {C['bg']};
    padding: 14px 0 0 0;
}}

/* ── Metrics ── */
[data-testid="stMetricValue"] {{
    color: {C['cyan']} !important;
    font-size: 18px !important;
    font-weight: 700 !important;
}}
[data-testid="stMetricLabel"] {{
    color: {C['muted']} !important;
    font-size: 9px !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
}}
[data-testid="metric-container"] {{
    background: {C['panel']};
    border: 1px solid {C['border']};
    border-top: 2px solid {C['cyan']};
    padding: 10px 14px !important;
    border-radius: 0 !important;
}}

/* ── Inputs ── */
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {{
    background: {C['panel']} !important;
    border: 1px solid {C['border']} !important;
    color: {C['text']} !important;
    border-radius: 0 !important;
}}
.stSlider [data-baseweb="slider"] {{ background: {C['border']}; }}
[data-testid="stCheckbox"] label {{ color: {C['text']} !important; font-size: 11px; }}

/* ── Buttons ── */
button[kind="secondary"] {{
    background: transparent !important;
    border: 1px solid {C['cyan']} !important;
    color: {C['cyan']} !important;
    border-radius: 0 !important;
    font-size: 10px !important;
    letter-spacing: 2px !important;
}}

/* ── Divider ── */
hr {{ border-color: {C['border']} !important; margin: 6px 0 !important; }}

/* ── Info ── */
[data-testid="stInfo"] {{
    background: {C['cyan']}11 !important;
    border-left: 3px solid {C['cyan']} !important;
    border-radius: 0 !important;
    font-size: 11px;
}}
[data-testid="stWarning"] {{
    background: {C['orange']}11 !important;
    border-left: 3px solid {C['orange']} !important;
    border-radius: 0 !important;
    font-size: 11px;
}}
[data-testid="stError"] {{
    background: {C['red']}11 !important;
    border-left: 3px solid {C['red']} !important;
    border-radius: 0 !important;
    font-size: 11px;
}}

/* ── Expander ── */
[data-testid="stExpander"] {{
    background: {C['panel']} !important;
    border: 1px solid {C['border']} !important;
    border-radius: 0 !important;
}}
[data-testid="stExpander"] summary {{ color: {C['muted']} !important; font-size: 10px; letter-spacing: 2px; }}

/* ── Scrollbar ── */
::-webkit-scrollbar {{ width: 3px; height: 3px; }}
::-webkit-scrollbar-track {{ background: {C['dark']}; }}
::-webkit-scrollbar-thumb {{ background: {C['border']}; }}
::-webkit-scrollbar-thumb:hover {{ background: {C['cyan']}44; }}

/* ── Radio buttons ── */
.stRadio label {{ color: {C['text']} !important; font-size: 11px !important; }}
.stRadio [data-testid="stMarkdownContainer"] p {{ color: {C['text']} !important; }}

/* ── Sidebar text ── */
.sidebar-section {{
    color: {C['muted']};
    font-size: 9px;
    letter-spacing: 3px;
    text-transform: uppercase;
    border-bottom: 1px solid {C['border']};
    padding-bottom: 3px;
    margin: 10px 0 6px 0;
}}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CATALOG & LOADING
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300, show_spinner=False)
def build_catalog() -> dict:
    catalog = {}
    if not DATA_DIR.exists():
        return catalog
    for cat_dir in sorted(DATA_DIR.iterdir()):
        if not cat_dir.is_dir() or cat_dir.name.startswith("."):
            continue
        category = cat_dir.name
        for sym_dir in sorted(cat_dir.iterdir()):
            if not sym_dir.is_dir():
                continue
            symbol = sym_dir.name.upper()
            for pq in sorted(sym_dir.glob("*.parquet")):
                stem = pq.stem
                tf = None
                for candidate in TF_ORDER:
                    if stem.endswith(candidate):
                        tf = candidate
                        break
                if tf is None:
                    if stem.endswith("_1m"):
                        tf = "1min"
                    elif stem.endswith("_1h"):
                        tf = "1h"
                if tf is None:
                    continue
                source = "DUKASCOPY" if "dukascopy" in stem else "MT5"
                label = f"{symbol}  {tf.upper()}  {source}  [{category.upper()}]"
                catalog[label] = {
                    "path": pq,
                    "symbol": symbol,
                    "tf": tf,
                    "source": source,
                    "category": category,
                }
    return catalog


@st.cache_data(ttl=60, show_spinner=False)
def load_data(path_str: str, max_rows: int = 200_000) -> pd.DataFrame:
    path = Path(path_str)
    df = pd.read_parquet(path)

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    elif "time" in df.columns:
        df = df.rename(columns={"time": "timestamp"})
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    else:
        df.index = pd.to_datetime(df.index, utc=True)
        df = df.reset_index().rename(columns={"index": "timestamp"})

    for col in ["open", "high", "low", "close"]:
        if col not in df.columns:
            return pd.DataFrame()

    if "volume" not in df.columns:
        df["volume"] = np.nan

    df = df.sort_values("timestamp").reset_index(drop=True)

    if len(df) > max_rows:
        df = df.tail(max_rows).reset_index(drop=True)

    return df


def apply_date_filter(df: pd.DataFrame, start, end) -> pd.DataFrame:
    if df.empty:
        return df
    ts = df["timestamp"]
    if start:
        df = df[ts >= pd.Timestamp(start, tz="UTC")]
    if end:
        df = df[ts < pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)]
    return df.reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════════════
# QUANT CALCULATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def add_log_returns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["log_ret"] = np.log(df["close"] / df["close"].shift(1))
    return df


def realized_vol(returns: pd.Series, window: int, ann: int) -> pd.Series:
    return returns.rolling(window, min_periods=window // 2).std() * np.sqrt(ann)


def parkinson_vol(df: pd.DataFrame, window: int, ann: int) -> pd.Series:
    hl = np.log(df["high"] / df["low"].replace(0, np.nan))
    pk = np.sqrt((hl ** 2) / (4 * np.log(2)))
    return pk.rolling(window, min_periods=window // 2).mean() * np.sqrt(ann)


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).rolling(period, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def hurst_exponent(ts: np.ndarray) -> float:
    ts = np.asarray(ts, dtype=float)
    ts = ts[~np.isnan(ts)]
    n = len(ts)
    if n < 50:
        return 0.5
    max_lag = min(n // 4, 200)
    lags = np.unique(np.logspace(1, np.log10(max_lag), 25).astype(int))
    rs_vals, valid_lags = [], []
    for lag in lags:
        chunks = [ts[i : i + lag] for i in range(0, n - lag + 1, lag)]
        rs_chunk = []
        for c in chunks:
            m, s = c.mean(), c.std()
            if s == 0:
                continue
            dev = np.cumsum(c - m)
            rs_chunk.append((dev.max() - dev.min()) / s)
        if rs_chunk:
            rs_vals.append(np.mean(rs_chunk))
            valid_lags.append(lag)
    if len(valid_lags) < 3:
        return 0.5
    poly = np.polyfit(np.log(valid_lags), np.log(rs_vals), 1)
    return float(np.clip(poly[0], 0.0, 1.0))


def half_life_ar1(returns: pd.Series) -> float:
    r = returns.dropna().values
    if len(r) < 30:
        return np.nan
    cov = np.cov(r[1:], r[:-1])
    var = np.var(r[:-1])
    if var == 0:
        return np.nan
    phi = cov[0, 1] / var
    if not (0 < phi < 1):
        return np.nan
    return float(-np.log(2) / np.log(phi))


def rolling_sharpe(returns: pd.Series, window: int, ann: int) -> pd.Series:
    r = returns.rolling(window, min_periods=window // 2)
    return (r.mean() / r.std().replace(0, np.nan)) * np.sqrt(ann)


def max_drawdown_series(equity: pd.Series) -> pd.Series:
    roll_max = equity.cummax()
    return (equity - roll_max) / roll_max.replace(0, np.nan)


def backtest(df: pd.DataFrame, signal: pd.Series, ann: int) -> dict:
    log_ret = df["log_ret"]
    fwd_ret = log_ret.shift(-1)
    strat_ret = (signal.shift(1) * fwd_ret).fillna(0)

    equity = (1 + strat_ret).cumprod()
    bh_equity = (1 + fwd_ret.fillna(0)).cumprod()
    dd = max_drawdown_series(equity)

    n = len(strat_ret)
    ann_ret = float(equity.iloc[-1] ** (ann / n) - 1) if n > 0 else 0.0
    sharpe = float((strat_ret.mean() / strat_ret.std()) * np.sqrt(ann)) if strat_ret.std() > 0 else 0.0
    long_ret = strat_ret[strat_ret > 0].sum()
    short_ret = abs(strat_ret[strat_ret < 0].sum())

    return {
        "equity":       equity,
        "bh_equity":    bh_equity,
        "drawdown":     dd,
        "returns":      strat_ret,
        "total_return": float(equity.iloc[-1] - 1),
        "ann_return":   ann_ret,
        "sharpe":       sharpe,
        "max_drawdown": float(dd.min()),
        "n_trades":     int(signal.diff().abs().fillna(0).sum() / 2),
        "win_rate":     float((strat_ret > 0).mean()),
        "profit_factor": long_ret / short_ret if short_ret > 0 else np.nan,
    }


def ma_crossover_signal(df: pd.DataFrame, fast: int, slow: int) -> pd.Series:
    return np.sign(df["close"].rolling(fast).mean() - df["close"].rolling(slow).mean()).fillna(0)


def rsi_mr_signal(df: pd.DataFrame, period: int, oversold: int, overbought: int) -> pd.Series:
    rsi = compute_rsi(df["close"], period)
    sig = pd.Series(0.0, index=df.index)
    sig[rsi < oversold] = 1.0
    sig[rsi > overbought] = -1.0
    return sig.ffill().fillna(0)


def momentum_signal(df: pd.DataFrame, lookback: int) -> pd.Series:
    return np.sign(df["log_ret"].rolling(lookback).sum()).fillna(0)


# ═══════════════════════════════════════════════════════════════════════════════
# CHART HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _layout(fig, title: str = "", height: int = 400, rows: int = 1):
    axis_style = dict(
        gridcolor=C["grid"],
        zerolinecolor=C["border"],
        tickfont=dict(size=9, color=C["muted"]),
        linecolor=C["border"],
    )
    updates = dict(
        title=dict(text=f"<span style='font-size:10px;letter-spacing:2px;color:{C['muted']}'>{title}</span>",
                   x=0.01, y=0.99, xanchor="left", yanchor="top") if title else None,
        paper_bgcolor=C["bg"],
        plot_bgcolor=C["panel"],
        font=dict(family="Courier New, Consolas, monospace", color=C["text"], size=10),
        height=height,
        margin=dict(l=55, r=15, t=30 if title else 10, b=40),
        legend=dict(bgcolor=C["dark"], bordercolor=C["border"],
                    font=dict(size=9), orientation="h", y=1.02, x=0),
        hoverlabel=dict(bgcolor=C["dark"], bordercolor=C["border"],
                        font=dict(size=9, family="Courier New")),
        xaxis=axis_style,
        yaxis=axis_style,
    )
    if rows >= 2:
        updates["xaxis2"] = axis_style
        updates["yaxis2"] = axis_style
    if rows >= 3:
        updates["xaxis3"] = axis_style
        updates["yaxis3"] = axis_style
    fig.update_layout(**{k: v for k, v in updates.items() if v is not None})
    return fig


CANDLE_LIMIT = 1000   # above this bar count switch to line chart
CHART_MAX_PTS = 3000  # max points sent to Plotly for any full-dataset chart


def _ds(df: pd.DataFrame, max_pts: int = CHART_MAX_PTS) -> pd.DataFrame:
    """Downsample a dataframe to at most max_pts rows for charting."""
    if len(df) <= max_pts:
        return df
    step = len(df) // max_pts
    return df.iloc[::step].copy()


def _vol_trace(df: pd.DataFrame, row: int = 2) -> go.Bar:
    vol_colors = [C["green"] if r >= 0 else C["red"]
                  for r in df["close"].diff().fillna(0)]
    return go.Bar(x=df["timestamp"], y=df["volume"],
                  name="Vol", marker_color=vol_colors, opacity=0.5)


def chart_candle(df: pd.DataFrame) -> go.Figure:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.02, row_heights=[0.78, 0.22])
    fig.add_trace(go.Candlestick(
        x=df["timestamp"],
        open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        name="OHLC",
        increasing=dict(line=dict(color=C["green"], width=1), fillcolor=_rgba(C["green"], 0.6)),
        decreasing=dict(line=dict(color=C["red"], width=1), fillcolor=_rgba(C["red"], 0.6)),
    ), row=1, col=1)
    fig.add_trace(_vol_trace(df), row=2, col=1)
    _layout(fig, "", height=520, rows=2)
    fig.update_layout(xaxis_rangeslider_visible=False)
    fig.update_yaxes(title_text="VOL", title_font=dict(size=8), row=2, col=1)
    return fig


def chart_line(df: pd.DataFrame) -> go.Figure:
    """Lightweight line chart — used when bar count exceeds CANDLE_LIMIT."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.02, row_heights=[0.78, 0.22])
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["close"],
        name="Close", mode="lines",
        line=dict(color=C["cyan"], width=1.2),
    ), row=1, col=1)
    fig.add_trace(_vol_trace(df), row=2, col=1)
    _layout(fig, "", height=520, rows=2)
    fig.update_yaxes(title_text="VOL", title_font=dict(size=8), row=2, col=1)
    return fig


def chart_price(df: pd.DataFrame) -> tuple[go.Figure, str]:
    """Return (figure, chart_type_label) — auto-selects candle vs line."""
    if len(df) <= CANDLE_LIMIT:
        return chart_candle(df), "CANDLESTICK"
    return chart_line(df), "LINE"


def chart_dist(returns: pd.Series) -> go.Figure:
    r = returns.dropna()
    counts, edges = np.histogram(r, bins=120)
    x_mid = (edges[:-1] + edges[1:]) / 2
    mu, sigma = r.mean(), r.std()
    nx = np.linspace(r.quantile(0.002), r.quantile(0.998), 400)
    ny = stats.norm.pdf(nx, mu, sigma) * len(r) * (edges[1] - edges[0])

    fig = go.Figure()
    bar_colors = [C["red"] if v < 0 else C["cyan"] for v in x_mid]
    fig.add_trace(go.Bar(x=x_mid, y=counts, name="Empirical",
                         marker_color=bar_colors, opacity=0.7))
    fig.add_trace(go.Scatter(x=nx, y=ny, name="Normal",
                             line=dict(color=C["orange"], width=2, dash="dash")))
    for pct, label, color in [(5, "VaR95", C["orange"]), (1, "VaR99", C["red"])]:
        v = np.percentile(r, pct)
        fig.add_vline(x=v, line_color=color, line_dash="dot", line_width=1.5,
                      annotation_text=label, annotation_font_size=8,
                      annotation_font_color=color)
    _layout(fig, "RETURNS DISTRIBUTION", height=330)
    return fig


def chart_qq(returns: pd.Series) -> go.Figure:
    r = returns.dropna().values
    (osm, osr), (slope, intercept, _) = stats.probplot(r)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=osm, y=osr, mode="markers",
                             marker=dict(color=C["cyan"], size=3, opacity=0.6),
                             name="Empirical"))
    xl = np.array([osm.min(), osm.max()])
    fig.add_trace(go.Scatter(x=xl, y=slope * xl + intercept, mode="lines",
                             line=dict(color=C["orange"], width=2, dash="dash"),
                             name="Normal"))
    _layout(fig, "Q-Q PLOT (vs Normal)", height=330)
    fig.update_xaxes(title="Theoretical Quantiles")
    fig.update_yaxes(title="Sample Quantiles")
    return fig


def chart_acf_bar(values: np.ndarray, ci: float, title: str, height: int = 270) -> go.Figure:
    lags = np.arange(1, len(values))
    v = values[1:]
    colors = [C["green"] if abs(x) > ci else C["muted"] for x in v]
    fig = go.Figure()
    fig.add_hrect(y0=-ci, y1=ci, fillcolor=C["cyan"], opacity=0.06, line_width=0)
    fig.add_hline(y=ci, line_color=_rgba(C["cyan"], 0.33), line_width=1, line_dash="dot")
    fig.add_hline(y=-ci, line_color=_rgba(C["cyan"], 0.33), line_width=1, line_dash="dot")
    fig.add_trace(go.Bar(x=lags, y=v, marker_color=colors, name="ACF"))
    _layout(fig, title, height=height)
    return fig


def chart_rolling_vol(df: pd.DataFrame, returns: pd.Series, ann: int) -> go.Figure:
    # Compute on full data, then downsample for rendering
    step = max(1, len(df) // CHART_MAX_PTS)
    ts = df["timestamp"].iloc[::step]
    fig = go.Figure()
    for w, color, label in [(20, C["cyan"], "RV-20"), (60, C["orange"], "RV-60"),
                            (120, C["green"], "RV-120")]:
        rv = realized_vol(returns, w, ann).iloc[::step] * 100
        fig.add_trace(go.Scatter(x=ts, y=rv, line=dict(color=color, width=1.2), name=label))
    pk = parkinson_vol(df, 60, ann).iloc[::step] * 100
    fig.add_trace(go.Scatter(x=ts, y=pk,
                             line=dict(color=C["red"], width=1, dash="dot"),
                             name="Parkinson-60"))
    _layout(fig, "REALIZED VOLATILITY — Annualized %", height=340)
    fig.update_yaxes(ticksuffix="%")
    return fig


def chart_equity(result: dict, timestamps: pd.Series) -> go.Figure:
    step = max(1, len(timestamps) // CHART_MAX_PTS)
    ts = timestamps.iloc[::step]
    eq  = result["equity"].iloc[::step]
    bh  = result["bh_equity"].iloc[::step]
    dd  = result["drawdown"].iloc[::step]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=[0.7, 0.3])
    fig.add_trace(go.Scatter(
        x=ts, y=(eq - 1) * 100,
        name="Strategy", line=dict(color=C["cyan"], width=1.5),
        fill="tozeroy", fillcolor=_rgba(C["cyan"], 0.07),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=ts, y=(bh - 1) * 100,
        name="Buy & Hold", line=dict(color=C["muted"], width=1, dash="dot"),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=ts, y=dd * 100,
        name="Drawdown", line=dict(color=C["red"], width=1),
        fill="tozeroy", fillcolor=_rgba(C["red"], 0.15),
    ), row=2, col=1)
    _layout(fig, "EQUITY CURVE & DRAWDOWN", height=440, rows=2)
    fig.update_yaxes(ticksuffix="%")
    return fig


def chart_seasonality_heatmap(df: pd.DataFrame) -> go.Figure:
    d = df.copy()
    d["hour"] = d["timestamp"].dt.hour
    d["dow"] = d["timestamp"].dt.dayofweek
    pivot = d.groupby(["hour", "dow"])["log_ret"].mean().unstack() * 10_000
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    cols = [day_names[c] for c in pivot.columns]
    fig = go.Figure(go.Heatmap(
        z=pivot.values, x=cols, y=pivot.index,
        colorscale=[[0, C["red"]], [0.5, C["dark"]], [1, C["green"]]],
        zmid=0,
        colorbar=dict(ticksuffix=" bps", len=0.85, tickfont=dict(size=8)),
        hovertemplate="Day: %{x}<br>Hour UTC: %{y}:00<br>Avg: %{z:.2f} bps<extra></extra>",
    ))
    _layout(fig, "RETURN SEASONALITY  (Hour UTC × Day of Week,  avg bps)", height=440)
    fig.update_yaxes(title="Hour (UTC)", ticksuffix=":00")
    return fig


def chart_corr_matrix(corr: pd.DataFrame) -> go.Figure:
    syms = corr.columns.tolist()
    fig = go.Figure(go.Heatmap(
        z=corr.values, x=syms, y=syms,
        zmin=-1, zmax=1, zmid=0,
        colorscale=[[0, C["red"]], [0.5, "#1a3050"], [1, C["green"]]],
        text=np.round(corr.values, 2),
        texttemplate="%{text}",
        textfont=dict(size=10),
        colorbar=dict(len=0.85, tickfont=dict(size=8)),
    ))
    _layout(fig, "CROSS-ASSET CORRELATION MATRIX", height=480)
    return fig


def chart_roll_corr(r1: pd.Series, r2: pd.Series, window: int, l1: str, l2: str) -> go.Figure:
    rc = r1.rolling(window).corr(r2)
    colors = rc.apply(lambda x: C["cyan"] if x >= 0 else C["red"])
    fig = go.Figure()
    fig.add_trace(go.Bar(x=r1.index, y=rc, marker_color=colors, name="Corr"))
    fig.add_hline(y=0, line_color=C["muted"], line_width=1)
    for level, color in [(0.5, C["green"]), (-0.5, C["red"])]:
        fig.add_hline(y=level, line_color=_rgba(color, 0.27), line_dash="dash", line_width=1)
    _layout(fig, f"ROLLING({window}) CORRELATION:  {l1}  vs  {l2}", height=300)
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# UI HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def stat_row(label: str, value: str, color: str = None):
    c = color or C["cyan"]
    st.markdown(
        f"""<div style="display:flex;justify-content:space-between;align-items:center;
        padding:5px 0;border-bottom:1px solid {C['grid']};font-size:11px;">
        <span style="color:{C['muted']};letter-spacing:1px;text-transform:uppercase;font-size:9px;">{label}</span>
        <span style="color:{c};font-weight:700;">{value}</span></div>""",
        unsafe_allow_html=True,
    )


def kpi_grid(items: list):
    cols = st.columns(len(items))
    for col, (label, value, color) in zip(cols, items):
        with col:
            c = color or C["cyan"]
            st.markdown(
                f"""<div style="background:{C['panel']};border:1px solid {C['border']};
                border-top:2px solid {c};padding:10px 12px;text-align:center;">
                <div style="color:{C['muted']};font-size:8px;letter-spacing:2px;
                text-transform:uppercase;margin-bottom:3px;">{label}</div>
                <div style="color:{c};font-size:17px;font-weight:700;">{value}</div></div>""",
                unsafe_allow_html=True,
            )


def info_box(text: str, color: str = None):
    c = color or C["cyan"]
    st.markdown(
        f"""<div style="background:{c}0f;border-left:3px solid {c};padding:10px 14px;
        margin:8px 0;font-size:10px;color:{C['text']};line-height:1.8;">{text}</div>""",
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════════════════════

def tab_overview(df: pd.DataFrame, tf: str):
    last = df["close"].iloc[-1]
    prev = df["close"].iloc[-2] if len(df) > 1 else last
    chg = last - prev
    pct = chg / prev * 100 if prev != 0 else 0

    today = df["timestamp"].dt.date.iloc[-1]
    today_mask = df["timestamp"].dt.date == today
    d_high = df.loc[today_mask, "high"].max() if today_mask.any() else last
    d_low  = df.loc[today_mask, "low"].min() if today_mask.any() else last

    ann = ANN.get(tf, 252)
    ret = df["log_ret"]
    short_vol = ret.tail(max(ann // 12, 20)).std() * np.sqrt(ann) * 100

    chg_color = C["green"] if chg >= 0 else C["red"]
    st.markdown(
        f"""<div style="background:{C['dark']};border:1px solid {C['border']};
        border-left:4px solid {C['cyan']};padding:10px 18px;margin-bottom:14px;
        display:flex;gap:40px;align-items:center;flex-wrap:wrap;">
        <div>
          <div style="color:{C['muted']};font-size:8px;letter-spacing:3px;">LAST CLOSE</div>
          <div style="color:{C['text']};font-size:24px;font-weight:700;">{last:.5f}</div>
        </div>
        <div>
          <div style="color:{C['muted']};font-size:8px;letter-spacing:3px;">CHANGE</div>
          <div style="color:{chg_color};font-size:18px;font-weight:600;">
            {'+' if chg>=0 else ''}{chg:.5f}&nbsp;&nbsp;{'+' if pct>=0 else ''}{pct:.3f}%
          </div>
        </div>
        <div>
          <div style="color:{C['muted']};font-size:8px;letter-spacing:3px;">DAY HIGH</div>
          <div style="color:{C['green']};font-size:16px;">{d_high:.5f}</div>
        </div>
        <div>
          <div style="color:{C['muted']};font-size:8px;letter-spacing:3px;">DAY LOW</div>
          <div style="color:{C['red']};font-size:16px;">{d_low:.5f}</div>
        </div>
        <div>
          <div style="color:{C['muted']};font-size:8px;letter-spacing:3px;">1M REAL VOL</div>
          <div style="color:{C['orange']};font-size:16px;">{short_vol:.2f}%</div>
        </div>
        <div>
          <div style="color:{C['muted']};font-size:8px;letter-spacing:3px;">BARS LOADED</div>
          <div style="color:{C['cyan']};font-size:16px;">{len(df):,}</div>
        </div>
        </div>""",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns([3, 1, 1])
    with c1:
        max_display = min(5_000, len(df))
        default_display = min(500, len(df))
        n_bars = st.slider("Bars to display", 50, max_display, default_display, 50,
                           help=f"≤{CANDLE_LIMIT} bars → candlestick  |  >{CANDLE_LIMIT} bars → line chart")
    with c2:
        show_ema = st.checkbox("EMA", value=True)
        ema_p = st.selectbox("EMA period", [20, 50, 100, 200], index=1) if show_ema else 50
    with c3:
        show_bb = st.checkbox("Bollinger Bands", value=True)

    plot_df = df.tail(n_bars).copy()
    fig, chart_type = chart_price(plot_df)

    # Chart-type badge
    badge_color = C["cyan"] if chart_type == "CANDLESTICK" else C["orange"]
    st.markdown(
        f"""<div style="font-size:9px;color:{badge_color};letter-spacing:2px;
        margin-bottom:4px;">▸ {chart_type} MODE &nbsp;·&nbsp; {n_bars:,} bars</div>""",
        unsafe_allow_html=True,
    )

    if show_ema:
        ema = plot_df["close"].ewm(span=ema_p).mean()
        fig.add_trace(go.Scatter(x=plot_df["timestamp"], y=ema,
                                 name=f"EMA{ema_p}",
                                 line=dict(color=C["orange"], width=1.5)), row=1, col=1)
    if show_bb:
        sma20 = plot_df["close"].rolling(20).mean()
        std20 = plot_df["close"].rolling(20).std()
        fig.add_trace(go.Scatter(x=plot_df["timestamp"], y=sma20 + 2 * std20,
                                 name="BB+2σ",
                                 line=dict(color=_rgba(C["cyan"], 0.33), width=1, dash="dot")),
                      row=1, col=1)
        fig.add_trace(go.Scatter(x=plot_df["timestamp"], y=sma20 - 2 * std20,
                                 name="BB-2σ",
                                 line=dict(color=_rgba(C["cyan"], 0.33), width=1, dash="dot"),
                                 fill="tonexty", fillcolor=_rgba(C["cyan"], 0.03)),
                      row=1, col=1)

    st.plotly_chart(fig, use_container_width=True)

    with st.expander("RAW DATA SAMPLE"):
        sample = df.tail(200).copy()
        sample["timestamp"] = sample["timestamp"].dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(sample[["timestamp", "open", "high", "low", "close", "volume"]],
                     use_container_width=True, height=300)


def tab_returns(df: pd.DataFrame, returns: pd.Series, ann: int):
    r = returns.dropna()
    if len(r) < 10:
        st.warning("Not enough data for return analysis.")
        return

    mu = r.mean()
    sigma = r.std()
    skew = float(r.skew())
    kurt = float(r.kurtosis())
    jb_stat, jb_p = stats.jarque_bera(r)
    var95 = float(np.percentile(r, 5))
    var99 = float(np.percentile(r, 1))
    cvar95 = float(r[r <= var95].mean())
    cvar99 = float(r[r <= var99].mean())
    ann_ret = mu * ann
    ann_vol = sigma * np.sqrt(ann)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0

    kpi_grid([
        ("Ann. Return",     f"{ann_ret*100:.2f}%",  C["green"] if ann_ret > 0 else C["red"]),
        ("Ann. Volatility", f"{ann_vol*100:.2f}%",  C["orange"]),
        ("Sharpe Ratio",    f"{sharpe:.3f}",         C["green"] if sharpe > 0 else C["red"]),
        ("Skewness",        f"{skew:.3f}",           C["orange"] if abs(skew) > 0.5 else C["cyan"]),
        ("Excess Kurtosis", f"{kurt:.2f}",           C["red"] if kurt > 3 else C["cyan"]),
        ("JB p-value",      f"{jb_p:.4f}",          C["red"] if jb_p < 0.05 else C["green"]),
    ])

    st.write("")
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(chart_dist(r), use_container_width=True)
    with col2:
        st.plotly_chart(chart_qq(r), use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        st.markdown("#### TAIL RISK")
        stat_row("VaR 95%",  f"{var95*10000:.3f} bps",  C["orange"])
        stat_row("VaR 99%",  f"{var99*10000:.3f} bps",  C["red"])
        stat_row("CVaR 95%", f"{cvar95*10000:.3f} bps", C["red"])
        stat_row("CVaR 99%", f"{cvar99*10000:.3f} bps", C["red"])
        stat_row("Worst bar", f"{r.min()*10000:.3f} bps", C["red"])
        stat_row("Best bar",  f"{r.max()*10000:.3f} bps", C["green"])

    with col4:
        st.markdown("#### DISTRIBUTION MOMENTS")
        stat_row("Mean (per bar)", f"{mu*10000:.4f} bps")
        stat_row("Std Dev (per bar)", f"{sigma*10000:.4f} bps")
        stat_row("Skewness", f"{skew:.4f}", C["orange"] if abs(skew) > 0.5 else C["cyan"])
        stat_row("Excess Kurtosis", f"{kurt:.4f}", C["red"] if kurt > 3 else C["cyan"])
        stat_row("Jarque-Bera stat", f"{jb_stat:.2f}")
        stat_row("JB p-value", f"{jb_p:.6f}", C["red"] if jb_p < 0.05 else C["green"])
        stat_row("Non-normal returns?",
                 "YES — fat tails" if jb_p < 0.05 else "No evidence",
                 C["red"] if jb_p < 0.05 else C["green"])

    st.markdown("#### CUMULATIVE RETURN & MAX DRAWDOWN")
    equity = (1 + returns.fillna(0)).cumprod()
    dd = max_drawdown_series(equity)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=[0.7, 0.3])
    _step = max(1, len(df) // CHART_MAX_PTS)
    _ts = df["timestamp"].iloc[::_step]
    fig.add_trace(go.Scatter(x=_ts, y=(equity.iloc[::_step] - 1) * 100,
                             line=dict(color=C["cyan"], width=1.5),
                             fill="tozeroy", fillcolor=_rgba(C["cyan"], 0.07), name="Cum Return"),
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=_ts, y=dd.iloc[::_step] * 100,
                             line=dict(color=C["red"], width=1),
                             fill="tozeroy", fillcolor=_rgba(C["red"], 0.13), name="Drawdown"),
                  row=2, col=1)
    _layout(fig, "", height=380, rows=2)
    fig.update_yaxes(ticksuffix="%")
    st.plotly_chart(fig, use_container_width=True)


def tab_volatility(df: pd.DataFrame, returns: pd.Series, ann: int):
    if len(returns.dropna()) < 30:
        st.warning("Not enough data.")
        return

    st.plotly_chart(chart_rolling_vol(df, returns, ann), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        # Volatility regimes — downsample before per-bar colouring
        rv21 = returns.rolling(21).std() * np.sqrt(ann) * 100
        rv21 = rv21.dropna()
        low_q, high_q = rv21.quantile(0.33), rv21.quantile(0.67)
        _sv = max(1, len(rv21) // CHART_MAX_PTS)
        rv21_ds = rv21.iloc[::_sv]
        vol_colors = [C["green"] if x <= low_q else (C["orange"] if x <= high_q else C["red"])
                      for x in rv21_ds]
        fig = go.Figure(go.Bar(x=rv21_ds.index, y=rv21_ds, marker_color=vol_colors, name="RV-21"))
        fig.add_hline(y=low_q, line_color=_rgba(C["green"], 0.4), line_dash="dash", line_width=1)
        fig.add_hline(y=high_q, line_color=_rgba(C["red"], 0.4), line_dash="dash", line_width=1)
        _layout(fig, "VOLATILITY REGIME  (Low / Med / High)", height=300)
        fig.update_yaxes(ticksuffix="%")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Vol of vol — compute on full data, render downsampled
        rv21_full = returns.rolling(21).std() * np.sqrt(ann)
        vov = rv21_full.rolling(21).std() * np.sqrt(ann) * 100
        _s = max(1, len(df) // CHART_MAX_PTS)
        fig = go.Figure(go.Scatter(x=df["timestamp"].iloc[::_s], y=vov.iloc[::_s],
                                   line=dict(color=C["orange"], width=1),
                                   fill="tozeroy", fillcolor=_rgba(C["orange"], 0.09),
                                   name="Vol-of-Vol"))
        _layout(fig, "VOLATILITY OF VOLATILITY", height=300)
        fig.update_yaxes(ticksuffix="%")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### ROLLING VOLATILITY COMPARISON")
    window = st.slider("Window (bars)", 5, 250, 21, key="vol_win")
    _s2 = max(1, len(df) // CHART_MAX_PTS)
    _ts2 = df["timestamp"].iloc[::_s2]
    fig2 = go.Figure()
    rv = realized_vol(returns, window, ann).iloc[::_s2] * 100
    pk = parkinson_vol(df, window, ann).iloc[::_s2] * 100
    fig2.add_trace(go.Scatter(x=_ts2, y=rv,
                              line=dict(color=C["cyan"], width=1.2), name="Close-to-Close"))
    fig2.add_trace(go.Scatter(x=_ts2, y=pk,
                              line=dict(color=C["orange"], width=1.2), name="Parkinson H/L"))
    _layout(fig2, f"REALIZED vs PARKINSON  —  {window}-bar window, Annualized %", height=300)
    fig2.update_yaxes(ticksuffix="%")
    st.plotly_chart(fig2, use_container_width=True)

    info_box(
        f"<b style='color:{C['cyan']}'>PARKINSON</b> uses High-Low range — more efficient for"
        " intraday volatility. <b style='color:{C['cyan']}'>CLOSE-TO-CLOSE</b> captures overnight"
        " gap risk. Parkinson > C2C usually signals intraday mean-reversion; C2C > Parkinson suggests"
        " gap-heavy regime.",
        C["muted"],
    )


def tab_structure(df: pd.DataFrame, returns: pd.Series, ann: int):
    r = returns.dropna()
    if len(r) < 50:
        st.warning("Need at least 50 observations for structure analysis.")
        return

    with st.spinner("Computing Hurst exponent..."):
        hurst = hurst_exponent(r.values)

    adf_stat, adf_p, *adf_rest = adfuller(r, maxlag=20, autolag="AIC")
    hl = half_life_ar1(r)

    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown("#### MARKET STRUCTURE METRICS")
        hurst_color = C["green"] if hurst < 0.45 else (C["red"] if hurst > 0.55 else C["yellow"])
        hurst_regime = "MEAN-REVERTING" if hurst < 0.45 else ("TRENDING" if hurst > 0.55 else "RANDOM WALK")
        stat_row("Hurst Exponent H", f"{hurst:.4f}", hurst_color)
        stat_row("Regime",           hurst_regime,   hurst_color)
        st.markdown("")
        stat_row("ADF Statistic", f"{adf_stat:.4f}")
        stat_row("ADF p-value",   f"{adf_p:.6f}",
                 C["green"] if adf_p < 0.05 else C["red"])
        stat_row("Returns Stationary?",
                 "YES" if adf_p < 0.05 else "NO",
                 C["green"] if adf_p < 0.05 else C["red"])
        st.markdown("")
        hl_str = f"{hl:.1f} bars" if not np.isnan(hl) else "N/A (not mean-reverting)"
        stat_row("AR(1) Half-Life", hl_str, C["orange"])

        info_box(
            f"<b style='color:{C['cyan']}'>HURST EXPONENT</b><br>"
            "H &lt; 0.45 → Anti-persistent (mean-reverting signal)<br>"
            "H ≈ 0.50 → Random walk (efficient market)<br>"
            "H &gt; 0.55 → Persistent (trend-following signal)<br><br>"
            f"<b style='color:{C['cyan']}'>HALF-LIFE</b><br>"
            "Bars for a return shock to halve. "
            "Low = fast mean-reversion.",
        )

    with col2:
        n_lags = st.slider("ACF lags", 10, 100, 40, key="acf_lags")
        ci = 1.96 / np.sqrt(len(r))

        acf_r  = acf(r, nlags=n_lags, fft=True)
        acf_r2 = acf(r**2, nlags=n_lags, fft=True)

        st.plotly_chart(chart_acf_bar(acf_r, ci, "ACF — LOG RETURNS  (autocorrelation)"),
                        use_container_width=True)
        st.plotly_chart(chart_acf_bar(acf_r2, ci,
                                      "ACF — SQUARED RETURNS  (volatility clustering)"),
                        use_container_width=True)

    # Ljung-Box
    lb = acorr_ljungbox(r, lags=[5, 10, 20, 40], return_df=True)
    lb.index.name = "Lags"
    lb.columns = ["LB Statistic", "p-value"]
    lb["Reject H₀ (no autocorr)?"] = lb["p-value"].apply(
        lambda p: "YES — serial correlation present" if p < 0.05 else "No"
    )
    st.markdown("#### LJUNG-BOX TEST — Serial Correlation in Returns")
    st.dataframe(lb.round(4), use_container_width=True)

    # Momentum factor (past return vs forward return)
    st.markdown("#### MOMENTUM DECAY PROFILE")
    info_box(
        "Shows avg forward N-bar return sorted by sign of past N-bar momentum. "
        "Positive bars = momentum effect; negative = mean-reversion effect.",
        C["muted"],
    )
    lb_opts = [5, 10, 20, 40, 60, 120]
    fig = go.Figure()
    for lookback in lb_opts:
        past = r.rolling(lookback).sum()
        fwd  = r.shift(-lookback).rolling(lookback).sum()
        mom_pos = fwd[past > 0].mean() * 10_000
        mom_neg = fwd[past < 0].mean() * 10_000
        fig.add_trace(go.Bar(name=str(lookback),
                             x=[f"Past+{lookback}", f"Past-{lookback}"],
                             y=[mom_pos, mom_neg],
                             marker_color=[C["green"] if mom_pos > 0 else C["red"],
                                           C["green"] if mom_neg > 0 else C["red"]]))
    _layout(fig, "AVG FORWARD RETURN by Past-Return Sign  (bps)", height=320)
    fig.update_yaxes(ticksuffix=" bps")
    st.plotly_chart(fig, use_container_width=True)


def tab_seasonality(df: pd.DataFrame, returns: pd.Series):
    if df.empty:
        return
    df2 = df.copy()
    df2["log_ret"] = returns.values
    df2["hour"] = df2["timestamp"].dt.hour
    df2["dow"]  = df2["timestamp"].dt.dayofweek

    st.plotly_chart(chart_seasonality_heatmap(df2), use_container_width=True)

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    col1, col2 = st.columns(2)
    with col1:
        hourly = df2.groupby("hour")["log_ret"].mean() * 10_000
        fig = go.Figure(go.Bar(
            x=hourly.index, y=hourly,
            marker_color=[C["green"] if v >= 0 else C["red"] for v in hourly],
            name="Avg Return"))
        _layout(fig, "AVG RETURN BY HOUR (UTC, bps)", height=300)
        fig.update_xaxes(ticksuffix=":00")
        fig.update_yaxes(ticksuffix=" bps")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        daily = df2.groupby("dow")["log_ret"].mean() * 10_000
        fig = go.Figure(go.Bar(
            x=[day_names[i] for i in daily.index], y=daily,
            marker_color=[C["green"] if v >= 0 else C["red"] for v in daily],
            name="Avg Return"))
        _layout(fig, "AVG RETURN BY DAY OF WEEK (bps)", height=300)
        fig.update_yaxes(ticksuffix=" bps")
        st.plotly_chart(fig, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        h_vol = df2.groupby("hour")["log_ret"].std() * 10_000
        fig = go.Figure(go.Bar(x=h_vol.index, y=h_vol,
                               marker_color=C["orange"], opacity=0.8, name="Std Dev"))
        _layout(fig, "RETURN STD DEV BY HOUR (UTC, bps)", height=280)
        fig.update_xaxes(ticksuffix=":00")
        fig.update_yaxes(ticksuffix=" bps")
        st.plotly_chart(fig, use_container_width=True)

    with col4:
        h_vol_by_vol = df2.groupby("hour")["log_ret"].apply(
            lambda x: (x**2).mean()**0.5 * 10_000
        )
        fig = go.Figure(go.Bar(x=h_vol_by_vol.index, y=h_vol_by_vol,
                               marker_color=C["yellow"], opacity=0.8, name="RMS Return"))
        _layout(fig, "RMS RETURN BY HOUR (UTC, bps)", height=280)
        fig.update_xaxes(ticksuffix=":00")
        fig.update_yaxes(ticksuffix=" bps")
        st.plotly_chart(fig, use_container_width=True)


def tab_correlation(catalog: dict):
    tradeable = {k: v for k, v in catalog.items()
                 if v["category"] in ("fx", "indices", "crypto")}
    if len(tradeable) < 2:
        st.info("Need at least 2 assets in the data directory for correlation analysis.")
        return

    selected = st.multiselect(
        "Select assets (2–8)",
        list(tradeable.keys()),
        default=list(tradeable.keys())[:min(6, len(tradeable))],
        max_selections=8,
    )
    if len(selected) < 2:
        st.warning("Select at least 2 assets.")
        return

    c1, c2 = st.columns(2)
    with c1:
        resample_tf = st.selectbox("Resample to", ["1h", "4h", "1D"], index=0)
    with c2:
        corr_window = st.slider("Rolling window (bars)", 20, 250, 60)

    returns_dict = {}
    prog = st.progress(0)
    for i, label in enumerate(selected):
        meta = tradeable[label]
        data = load_data(str(meta["path"]))
        prog.progress((i + 1) / len(selected))
        if data.empty:
            continue
        data = add_log_returns(data).set_index("timestamp")
        resampled = data["log_ret"].resample(resample_tf).sum()
        returns_dict[meta["symbol"]] = resampled
    prog.empty()

    if len(returns_dict) < 2:
        st.warning("Could not load sufficient data.")
        return

    ret_df = pd.DataFrame(returns_dict).dropna(how="all").fillna(0)
    corr = ret_df.corr()

    st.plotly_chart(chart_corr_matrix(corr), use_container_width=True)

    syms = list(returns_dict.keys())
    col3, col4 = st.columns(2)
    with col3:
        s1 = st.selectbox("Asset 1", syms, index=0, key="corr_s1")
    with col4:
        s2 = st.selectbox("Asset 2", syms, index=min(1, len(syms) - 1), key="corr_s2")

    if s1 != s2 and s1 in ret_df and s2 in ret_df:
        st.plotly_chart(chart_roll_corr(ret_df[s1], ret_df[s2], corr_window, s1, s2),
                        use_container_width=True)

        # Scatter
        valid = ret_df[[s1, s2]].dropna()
        fig = go.Figure(go.Scatter(
            x=valid[s1] * 10_000, y=valid[s2] * 10_000,
            mode="markers", marker=dict(color=C["cyan"], size=3, opacity=0.35),
            name="Returns",
        ))
        if len(valid) > 10:
            slope, intercept, r_val, *_ = stats.linregress(valid[s1], valid[s2])
            xl = np.array([valid[s1].min(), valid[s1].max()])
            fig.add_trace(go.Scatter(
                x=xl * 10_000, y=(slope * xl + intercept) * 10_000,
                mode="lines", line=dict(color=C["orange"], width=2),
                name=f"OLS β={slope:.3f}  R²={r_val**2:.3f}",
            ))
        _layout(fig, f"RETURN SCATTER:  {s1}  vs  {s2}  (bps)", height=360)
        fig.update_xaxes(title=f"{s1} (bps)")
        fig.update_yaxes(title=f"{s2} (bps)")
        st.plotly_chart(fig, use_container_width=True)

        # PCA if >3 assets
        if len(ret_df.columns) >= 3:
            st.markdown("#### PCA — VARIANCE EXPLAINED BY FACTOR")
            from numpy.linalg import eig
            cov = ret_df.cov()
            evals, evecs = eig(cov)
            evals = np.real(evals)
            evals_sorted = np.sort(evals)[::-1]
            pct_explained = evals_sorted / evals_sorted.sum() * 100
            cumulative = np.cumsum(pct_explained)
            fig_pca = make_subplots(specs=[[{"secondary_y": True}]])
            fig_pca.add_trace(go.Bar(
                x=[f"PC{i+1}" for i in range(len(pct_explained))],
                y=pct_explained,
                marker_color=C["cyan"], name="% Variance",
            ))
            fig_pca.add_trace(go.Scatter(
                x=[f"PC{i+1}" for i in range(len(cumulative))],
                y=cumulative,
                line=dict(color=C["orange"], width=2),
                mode="lines+markers", name="Cumulative %",
            ), secondary_y=True)
            _layout(fig_pca, "PCA — Variance Explained per Principal Component", height=300)
            fig_pca.update_yaxes(title_text="% Variance", ticksuffix="%")
            fig_pca.update_yaxes(title_text="Cumulative %", ticksuffix="%", secondary_y=True)
            st.plotly_chart(fig_pca, use_container_width=True)


def tab_strategy(df: pd.DataFrame, returns: pd.Series, ann: int):
    strategy = st.radio(
        "Strategy type",
        ["Trend — MA Crossover", "Mean Reversion — RSI", "Time-Series Momentum"],
        horizontal=True,
    )

    col_p, col_r = st.columns([1, 3])
    with col_p:
        st.markdown("#### PARAMETERS")

        if strategy == "Trend — MA Crossover":
            fast = st.slider("Fast MA", 5, 100, 20, key="s_fast")
            slow = st.slider("Slow MA", 20, 500, 100, key="s_slow")
            signal = ma_crossover_signal(df, fast, slow)
            s_title = f"MA Crossover  {fast}/{slow}"

        elif strategy == "Mean Reversion — RSI":
            period   = st.slider("RSI Period", 5, 50, 14, key="s_rsi_p")
            oversold = st.slider("Oversold", 10, 45, 30, key="s_rsi_os")
            overbought = st.slider("Overbought", 55, 90, 70, key="s_rsi_ob")
            signal = rsi_mr_signal(df, period, oversold, overbought)
            s_title = f"RSI({period}) MR  {oversold}/{overbought}"

        else:
            lookback = st.slider("Momentum lookback", 5, 500, 60, key="s_mom")
            signal = momentum_signal(df, lookback)
            s_title = f"TS Momentum({lookback})"

        result = backtest(df, signal, ann)

        st.markdown("")
        st.markdown("#### BACKTEST RESULTS")
        tr = result["total_return"]
        sr = result["sharpe"]
        stat_row("Total Return",   f"{tr*100:.2f}%",
                 C["green"] if tr > 0 else C["red"])
        stat_row("Ann. Return",    f"{result['ann_return']*100:.2f}%",
                 C["green"] if result["ann_return"] > 0 else C["red"])
        stat_row("Sharpe Ratio",   f"{sr:.3f}",
                 C["green"] if sr > 0 else C["red"])
        stat_row("Max Drawdown",   f"{result['max_drawdown']*100:.2f}%", C["red"])
        stat_row("# Trades",       str(result["n_trades"]))
        stat_row("Win Rate",       f"{result['win_rate']*100:.1f}%",
                 C["green"] if result["win_rate"] > 0.5 else C["red"])
        if not np.isnan(result["profit_factor"]):
            stat_row("Profit Factor", f"{result['profit_factor']:.3f}",
                     C["green"] if result["profit_factor"] > 1 else C["red"])

    with col_r:
        # Signal + price
        tail_n = min(3_000, len(df))
        pf = df.tail(tail_n)
        ps = signal.tail(tail_n)
        fig_sig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                vertical_spacing=0.02, row_heights=[0.72, 0.28])
        fig_sig.add_trace(go.Scatter(x=pf["timestamp"], y=pf["close"],
                                     line=dict(color=C["text"], width=1), name="Close"),
                          row=1, col=1)
        long_x = pf["timestamp"][ps == 1]
        long_y = pf["close"][ps == 1]
        short_x = pf["timestamp"][ps == -1]
        short_y = pf["close"][ps == -1]
        if len(long_x):
            fig_sig.add_trace(go.Scatter(x=long_x, y=long_y, mode="markers",
                                         marker=dict(color=C["green"], size=3, opacity=0.6),
                                         name="Long"), row=1, col=1)
        if len(short_x):
            fig_sig.add_trace(go.Scatter(x=short_x, y=short_y, mode="markers",
                                         marker=dict(color=C["red"], size=3, opacity=0.6),
                                         name="Short"), row=1, col=1)
        sig_colors = [C["green"] if s > 0 else (C["red"] if s < 0 else C["muted"])
                      for s in ps]
        fig_sig.add_trace(go.Bar(x=pf["timestamp"], y=ps,
                                 marker_color=sig_colors, name="Signal", opacity=0.75),
                          row=2, col=1)
        _layout(fig_sig, f"SIGNAL:  {s_title}", height=360, rows=2)
        st.plotly_chart(fig_sig, use_container_width=True)

        st.plotly_chart(chart_equity(result, df["timestamp"]), use_container_width=True)

        # Rolling Sharpe — compute full, render downsampled
        win = max(20, min(252, len(result["returns"]) // 4))
        rs = rolling_sharpe(result["returns"], win, ann)
        _sr = max(1, len(df) // CHART_MAX_PTS)
        fig_rs = go.Figure()
        fig_rs.add_trace(go.Scatter(x=df["timestamp"].iloc[::_sr], y=rs.iloc[::_sr],
                                    line=dict(color=C["orange"], width=1),
                                    fill="tozeroy",
                                    fillcolor=_rgba(C["orange"], 0.08),
                                    name=f"Rolling Sharpe({win})"))
        fig_rs.add_hline(y=0, line_color=C["muted"], line_width=1)
        fig_rs.add_hline(y=1.0, line_color=_rgba(C["green"], 0.33), line_dash="dot", line_width=1,
                         annotation_text="SR=1", annotation_font_size=8,
                         annotation_font_color=C["green"])
        fig_rs.add_hline(y=-1.0, line_color=_rgba(C["red"], 0.33), line_dash="dot", line_width=1)
        _layout(fig_rs, f"ROLLING SHARPE RATIO  (window={win})", height=250)
        st.plotly_chart(fig_rs, use_container_width=True)

    # Momentum decile analysis
    st.markdown("#### MOMENTUM FACTOR DECILE ANALYSIS")
    info_box(
        "Ranks bars by past N-bar return into deciles. Shows avg forward return per decile. "
        "A monotone positive slope → momentum effect. Inverted slope → mean reversion.",
        C["muted"],
    )
    col_lb, col_fwd = st.columns(2)
    with col_lb:
        m_lb = st.slider("Past lookback (bars)", 5, 500, 60, key="mom_lb")
    with col_fwd:
        m_fwd = st.slider("Forward return (bars)", 1, 200, 20, key="mom_fwd")

    past_ret = returns.rolling(m_lb).sum()
    fwd_ret  = returns.shift(-m_fwd).rolling(m_fwd).sum()
    valid_mask = past_ret.notna() & fwd_ret.notna()
    if valid_mask.sum() > 20:
        try:
            quintiles = pd.qcut(past_ret[valid_mask], 10,
                                 labels=[f"D{i}" for i in range(1, 11)])
            decile_fwd = fwd_ret[valid_mask].groupby(quintiles).mean() * 10_000
            fig_mom = go.Figure(go.Bar(
                x=decile_fwd.index.astype(str), y=decile_fwd,
                marker_color=[C["green"] if v > 0 else C["red"] for v in decile_fwd],
                name="Avg Forward Return",
            ))
            fig_mom.add_hline(y=0, line_color=C["muted"], line_width=1)
            _layout(fig_mom,
                    f"AVG FORWARD RETURN BY PAST-RETURN DECILE  "
                    f"(lookback={m_lb}, fwd={m_fwd})  bps",
                    height=300)
            fig_mom.update_yaxes(ticksuffix=" bps")
            st.plotly_chart(fig_mom, use_container_width=True)
        except Exception:
            st.info("Not enough data variation for decile analysis.")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    # Header bar
    now_utc = datetime.datetime.utcnow().strftime("%Y-%m-%d  %H:%M:%S UTC")
    st.markdown(
        f"""<div style="background:{C['dark']};border-bottom:1px solid {C['border']};
        padding:8px 20px;margin-bottom:0;display:flex;justify-content:space-between;
        align-items:center;">
        <div style="display:flex;align-items:center;gap:16px;">
          <span style="color:{C['cyan']};font-size:16px;font-weight:700;letter-spacing:5px;">◈ BALERION</span>
          <span style="color:{C['border']};font-size:12px;">|</span>
          <span style="color:{C['muted']};font-size:9px;letter-spacing:3px;">QUANTITATIVE RESEARCH TERMINAL</span>
        </div>
        <span style="color:{C['muted']};font-size:9px;letter-spacing:2px;">{now_utc}</span>
        </div>""",
        unsafe_allow_html=True,
    )

    catalog = build_catalog()
    if not catalog:
        st.error("No parquet files found in data/  —  run the collection scripts first.")
        return

    # Sidebar
    with st.sidebar:
        st.markdown(
            f"""<div style="text-align:center;padding:14px 0 6px 0;">
            <div style="color:{C['cyan']};font-size:13px;font-weight:700;letter-spacing:5px;">◈ BALERION</div>
            <div style="color:{C['muted']};font-size:8px;letter-spacing:3px;margin-top:2px;">QUANT TERMINAL v2.0</div>
            </div><hr>""",
            unsafe_allow_html=True,
        )

        # ── Build symbol → source → tf index ────────────────────────────────
        sym_index: dict = {}
        for _lbl, _m in catalog.items():
            sym_index.setdefault(_m["symbol"], {}).setdefault(_m["source"], {})[_m["tf"]] = _m

        # ── PAIR ─────────────────────────────────────────────────────────────
        st.markdown('<div class="sidebar-section">PAIR</div>', unsafe_allow_html=True)
        all_symbols = sorted(sym_index.keys())
        # Default to EURUSD if available, else first
        default_sym_idx = all_symbols.index("EURUSD") if "EURUSD" in all_symbols else 0
        selected_sym = st.selectbox(
            "Pair", all_symbols, index=default_sym_idx,
            label_visibility="collapsed",
        )

        # ── SOURCE ────────────────────────────────────────────────────────────
        st.markdown('<div class="sidebar-section">SOURCE</div>', unsafe_allow_html=True)
        available_srcs = sorted(sym_index[selected_sym].keys())
        default_src = "DUKASCOPY" if "DUKASCOPY" in available_srcs else available_srcs[0]
        selected_src = st.selectbox(
            "Source", available_srcs, index=available_srcs.index(default_src),
            label_visibility="collapsed",
        )

        # ── TIMEFRAME ─────────────────────────────────────────────────────────
        st.markdown('<div class="sidebar-section">TIMEFRAME</div>', unsafe_allow_html=True)
        available_tfs = [tf for tf in TF_ORDER if tf in sym_index[selected_sym][selected_src]]
        tf_labels = {
            "1min": "1 MIN", "5min": "5 MIN", "15min": "15 MIN", "30min": "30 MIN",
            "1h": "1 HOUR", "4h": "4 HOUR", "1d": "DAILY",
        }
        default_tf = "1d" if "1d" in available_tfs else available_tfs[-1]
        selected_tf = st.selectbox(
            "Timeframe", available_tfs, index=available_tfs.index(default_tf),
            format_func=lambda t: tf_labels.get(t, t.upper()),
            label_visibility="collapsed",
        )

        meta = sym_index[selected_sym][selected_src][selected_tf]

        # ── DATE RANGE ────────────────────────────────────────────────────────
        st.markdown('<div class="sidebar-section">DATE RANGE</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            start_date = st.date_input("From", value=None, label_visibility="collapsed")
        with c2:
            end_date = st.date_input("To", value=None, label_visibility="collapsed")

        # ── LOOK-BACK PERIOD ──────────────────────────────────────────────────
        st.markdown('<div class="sidebar-section">LOOK-BACK</div>', unsafe_allow_html=True)
        _LOOKBACK = {
            "7 days": 7, "14 days": 14, "30 days": 30,
            "90 days": 90, "180 days": 180,
            "1 year": 365, "2 years": 730, "All": None,
        }
        _BARS_PER_DAY = {
            "1min": 1440, "5min": 288, "15min": 96, "30min": 48,
            "1h": 24, "4h": 6, "1d": 1,
        }
        lb_choice = st.selectbox(
            "Look-back", list(_LOOKBACK.keys()), index=4,
            label_visibility="collapsed",
        )
        lb_days = _LOOKBACK[lb_choice]
        if lb_days is None:
            max_rows = 1_000_000
        else:
            max_rows = max(500, int(lb_days * _BARS_PER_DAY.get(meta["tf"], 24) * 5 / 7))

        # ── INFO ──────────────────────────────────────────────────────────────
        st.markdown('<div class="sidebar-section">INFO</div>', unsafe_allow_html=True)
        file_mb = meta["path"].stat().st_size / 1_048_576
        st.markdown(
            f"""<div style="font-size:10px;color:{C['muted']};line-height:2.2;">
            Category:&nbsp;<span style="color:{C['cyan']}">{meta['category'].upper()}</span><br>
            File:&nbsp;<span style="color:{C['cyan']}">{meta['path'].name}</span><br>
            Size:&nbsp;<span style="color:{C['cyan']}">{file_mb:.1f} MB</span>
            </div>""",
            unsafe_allow_html=True,
        )

    # Load data
    with st.spinner(f"Loading {meta['symbol']} {meta['tf'].upper()} data..."):
        df = load_data(str(meta["path"]), max_rows=max_rows)

    if df.empty:
        st.error("Failed to load the selected file.")
        return

    df = apply_date_filter(df, start_date, end_date)
    if df.empty:
        st.warning("No data in selected date range.")
        return

    df = add_log_returns(df)
    returns = df["log_ret"]
    ann = ANN.get(meta["tf"], 252)

    # Info banner
    d0 = df["timestamp"].iloc[0].strftime("%Y-%m-%d")
    d1 = df["timestamp"].iloc[-1].strftime("%Y-%m-%d")
    st.markdown(
        f"""<div style="background:{C['panel']};border:1px solid {C['border']};
        border-left:3px solid {C['cyan']};padding:5px 16px;margin-bottom:12px;
        font-size:9px;display:flex;gap:28px;flex-wrap:wrap;">
        <span><span style="color:{C['muted']}">SYMBOL</span>&nbsp;
              <span style="color:{C['cyan']};font-weight:700;">{meta['symbol']}</span></span>
        <span><span style="color:{C['muted']}">TF</span>&nbsp;
              <span style="color:{C['cyan']}">{meta['tf'].upper()}</span></span>
        <span><span style="color:{C['muted']}">SOURCE</span>&nbsp;
              <span style="color:{C['cyan']}">{meta['source']}</span></span>
        <span><span style="color:{C['muted']}">BARS</span>&nbsp;
              <span style="color:{C['text']}">{len(df):,}</span></span>
        <span><span style="color:{C['muted']}">RANGE</span>&nbsp;
              <span style="color:{C['text']}">{d0}  →  {d1}</span></span>
        <span><span style="color:{C['muted']}">ANN FACTOR</span>&nbsp;
              <span style="color:{C['text']}">{ann:,}</span></span>
        </div>""",
        unsafe_allow_html=True,
    )

    # Tabs
    tabs = st.tabs([
        "OVERVIEW",
        "RETURNS",
        "VOLATILITY",
        "STRUCTURE",
        "SEASONALITY",
        "CORRELATION",
        "STRATEGY LAB",
    ])
    with tabs[0]: tab_overview(df, meta["tf"])
    with tabs[1]: tab_returns(df, returns, ann)
    with tabs[2]: tab_volatility(df, returns, ann)
    with tabs[3]: tab_structure(df, returns, ann)
    with tabs[4]: tab_seasonality(df, returns)
    with tabs[5]: tab_correlation(catalog)
    with tabs[6]: tab_strategy(df, returns, ann)


if __name__ == "__main__":
    main()
