#!/usr/bin/env python3
"""Fix line endings to LF for specific files"""
import pathlib

files = [
    'alembic/versions/2025_10_18_1836-d5a50d72e841_add_performance_indexes.py',
    'app/api/scoring.py',
    'migrate_test_db.py',
]

for file_path in files:
    path = pathlib.Path(file_path)
    if path.exists():
        content = path.read_text(encoding='utf-8')
        # Convert CRLF to LF
        content = content.replace('\r\n', '\n')
        # Write with LF line endings
        path.write_text(content, encoding='utf-8', newline='\n')
        print(f"✅ Fixed: {file_path}")
    else:
        print(f"❌ Not found: {file_path}")

print("\n🎉 All line endings fixed!")
