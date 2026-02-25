#!/bin/bash
# Setup script for Balerion Data Collection using uv
# This script installs uv and sets up the project dependencies

set -e

echo "================================================================================"
echo "Balerion Data Collection - Setup Script"
echo "================================================================================"
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "uv is not installed. Installing uv..."
    echo ""
    
    # Install uv using the official installer
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    echo ""
    echo "✓ uv installed successfully"
    echo "  Please restart your terminal and run this script again."
    echo ""
    exit 0
fi

echo "✓ uv is already installed"
echo ""

# Navigate to project root
cd "$(dirname "$0")/.."

echo "Installing project dependencies..."
echo ""

# Sync dependencies
uv sync

echo ""
echo "================================================================================"
echo "Setup Complete!"
echo "================================================================================"
echo ""
echo "Next steps:"
echo "  1. Ensure MT5 is running and logged in"
echo "  2. Run initial data collection:"
echo "     uv run python scripts/collect_historical_data.py"
echo ""
echo "  3. Set up weekly updates:"
echo "     uv run python scripts/update_weekly_data.py"
echo ""
echo "For more information, see scripts/README.md"
echo ""
