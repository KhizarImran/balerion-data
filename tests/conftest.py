"""
Pytest configuration for balerion-data tests.
Adds the scripts/ directory to sys.path so config.py and mt5_utils.py
can be imported without package installation.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def pytest_addoption(parser):
    parser.addoption(
        "--symbol",
        default=None,
        help="Run tests for a single symbol from the default MT5 set (e.g. EURUSD)",
    )
    parser.addoption(
        "--file",
        default=None,
        help="Path to any parquet file to test directly (absolute or relative to repo root)",
    )
    parser.addoption(
        "--timeframe",
        default=None,
        type=int,
        help="Bar interval in minutes (e.g. 1, 60, 240). Auto-detected if omitted.",
    )
