# Setup script for Balerion Data Collection using uv
# This script installs uv and sets up the project dependencies

Write-Host "=" * 80
Write-Host "Balerion Data Collection - Setup Script"
Write-Host "=" * 80
Write-Host ""

# Check if uv is installed
$uvInstalled = Get-Command uv -ErrorAction SilentlyContinue

if (-not $uvInstalled) {
    Write-Host "uv is not installed. Installing uv..."
    Write-Host ""
    
    # Install uv using the official installer
    irm https://astral.sh/uv/install.ps1 | iex
    
    Write-Host ""
    Write-Host "✓ uv installed successfully"
    Write-Host "  Please restart your terminal and run this script again."
    Write-Host ""
    exit 0
}

Write-Host "✓ uv is already installed"
Write-Host ""

# Navigate to project root
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "Installing project dependencies..."
Write-Host ""

# Sync dependencies
uv sync

Write-Host ""
Write-Host "=" * 80
Write-Host "Setup Complete!"
Write-Host "=" * 80
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Ensure MT5 is running and logged in"
Write-Host "  2. Run initial data collection:"
Write-Host "     uv run python scripts/collect_historical_data.py"
Write-Host ""
Write-Host "  3. Set up weekly updates:"
Write-Host "     uv run python scripts/update_weekly_data.py"
Write-Host ""
Write-Host "For more information, see scripts/README.md"
Write-Host ""
