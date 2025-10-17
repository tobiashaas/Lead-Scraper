"""
Create Alembic Migration
"""

import subprocess
import sys

message = sys.argv[1] if len(sys.argv) > 1 else "migration"

result = subprocess.run(
    ["python", "-m", "alembic", "revision", "--autogenerate", "-m", message],
    capture_output=True,
    text=True,
)

print(result.stdout)
if result.stderr:
    print(result.stderr)

sys.exit(result.returncode)
