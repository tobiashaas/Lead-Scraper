#!/usr/bin/env python3
"""Fix the 3 problematic files with LF line endings"""
import subprocess
import pathlib

files = [
    "alembic/versions/2025_10_18_1836-d5a50d72e841_add_performance_indexes.py",
    "app/api/scoring.py",
    "migrate_test_db.py",
]

print("🚀 Fixing 3 files with LF line endings...")
print()

for file_path in files:
    print(f"📝 Processing: {file_path}")

    # Read file
    path = pathlib.Path(file_path)
    if not path.exists():
        print(f"  ❌ File not found!")
        continue

    # Read with universal newlines, then write with LF
    content = path.read_text(encoding="utf-8")

    # Ensure LF line endings
    content = content.replace("\r\n", "\n")

    # Write back with LF
    path.write_text(content, encoding="utf-8", newline="\n")
    print(f"  ✅ Converted to LF")

print()
print("🎨 Running Black...")

# Run black on all files
result = subprocess.run(["venv/Scripts/black.exe"] + files, capture_output=True, text=True)

print(result.stdout)
if result.stderr:
    print(result.stderr)

print()
print("✅ Done! Now commit:")
print("   git add -A")
print("   git commit -m 'fix: Ensure LF line endings for 3 files'")
print("   git push")
