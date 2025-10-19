#!/usr/bin/env python3
"""Format files exactly as GitHub Actions would see them"""
import subprocess
import sys

# Run black with exact same settings as CI
result = subprocess.run(
    ["black", "--config", "pyproject.toml", "."], capture_output=True, text=True
)

print(result.stdout)
if result.stderr:
    print(result.stderr, file=sys.stderr)

sys.exit(result.returncode)
