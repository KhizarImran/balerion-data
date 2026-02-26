"""
Pytest configuration for balerion-data tests.
Adds the scripts/ directory to sys.path so config.py and mt5_utils.py
can be imported without package installation.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
