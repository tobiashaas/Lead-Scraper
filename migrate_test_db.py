"""
Migrate Test Database
Führt Alembic Migrations auf Test-Datenbank aus
"""

import os
import subprocess

# Set environment variable for test database
os.environ[
    "DATABASE_URL"
] = "postgresql://kr_admin:uxu*rkj2yap7EWT-ubu@localhost:5432/kr_leads_test"

print("=" * 60)
print("Migrate Test Database")
print("=" * 60)
print()
print(f"DATABASE_URL: {os.environ['DATABASE_URL']}")
print()

# Run alembic upgrade
result = subprocess.run(["alembic", "upgrade", "head"], capture_output=True, text=True)

print(result.stdout)
if result.stderr:
    print(result.stderr)

if result.returncode == 0:
    print("\n✅ Migration erfolgreich!")
else:
    print(f"\n❌ Migration fehlgeschlagen (Exit Code: {result.returncode})")
