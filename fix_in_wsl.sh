#!/bin/bash
# Fix line endings and format code in WSL2

set -e

echo "🚀 Fixing code in WSL2..."

# Navigate to project
cd /mnt/c/Github/KR-Lead-Scraper

# Check if we're in the right place
echo "📂 Current directory: $(pwd)"

# Check Python version
echo "🐍 Python version: $(python3 --version)"

# Install black and ruff if not present
echo "📦 Installing black and ruff..."
python3 -m pip install --user --quiet black ruff 2>/dev/null || echo "⚠️  Could not install, trying existing..."

# Use Windows venv tools
echo "🎨 Running Black from Windows venv..."
./venv/Scripts/black.exe .

# Fix with ruff
echo "🔧 Running Ruff from Windows venv..."
./venv/Scripts/ruff.exe check --fix .

# Show git status
echo "📊 Git status:"
git status --short

echo ""
echo "✅ Done! Now commit and push:"
echo "   git add -A"
echo "   git commit -m 'fix: Format code in WSL2 (native LF)'"
echo "   git push origin fix/config-extra-fields"
