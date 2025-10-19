#!/bin/bash
# Fix the 3 specific problematic files in WSL2

set -e

echo "🚀 Fixing 3 specific files in WSL2..."

cd /mnt/c/Github/KR-Lead-Scraper

# The 3 problematic files
FILES=(
    "alembic/versions/2025_10_18_1836-d5a50d72e841_add_performance_indexes.py"
    "app/api/scoring.py"
    "migrate_test_db.py"
)

echo "📝 Files to fix:"
for file in "${FILES[@]}"; do
    echo "  - $file"
done

# Format each file explicitly with black from Windows venv
echo ""
echo "🎨 Running Black on each file..."
for file in "${FILES[@]}"; do
    echo "Formatting: $file"
    ./venv/Scripts/black.exe "$file"
done

echo ""
echo "✅ Done! Files formatted with native LF line endings"
echo ""
echo "📊 Git status:"
git status --short

echo ""
echo "🚀 Now commit and push:"
echo "   git add -A"
echo "   git commit -m 'fix: Format 3 problematic files in WSL2'"
echo "   git push origin fix/config-extra-fields"
