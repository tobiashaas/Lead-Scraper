"""
Reset Alembic Version Table
Löscht die alembic_version Tabelle für einen Neustart
"""

from urllib.parse import urlparse

import psycopg

from app.core.config import settings


def reset_alembic():
    """Löscht die alembic_version Tabelle"""
    # Parse DATABASE_URL
    parsed = urlparse(settings.database_url)

    # Erstelle psycopg3 Connection String
    db_url = f"host={parsed.hostname} port={parsed.port or 5432} dbname={parsed.path[1:]} user={parsed.username} password={parsed.password}"

    print("Verbinde mit Datenbank...")
    print(f"URL: {db_url.replace(settings.database_url.split('@')[0].split('//')[1], '***')}")

    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                # Lösche ALLE Tabellen für kompletten Neustart
                print("Lösche ALLE Tabellen...")
                cur.execute("DROP SCHEMA public CASCADE;")
                cur.execute("CREATE SCHEMA public;")
                cur.execute("GRANT ALL ON SCHEMA public TO public;")
                conn.commit()
                print("✅ Alle Tabellen gelöscht")

                # Zeige alle Tabellen
                cur.execute(
                    """
                    SELECT tablename
                    FROM pg_tables
                    WHERE schemaname = 'public'
                    ORDER BY tablename;
                """
                )
                tables = cur.fetchall()

                if tables:
                    print(f"\nVorhandene Tabellen ({len(tables)}):")
                    for table in tables:
                        print(f"  - {table[0]}")
                else:
                    print("\nKeine Tabellen vorhanden")

    except Exception as e:
        print(f"❌ Fehler: {e}")
        return False

    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Reset Alembic Version Table")
    print("=" * 60)
    print()

    if reset_alembic():
        print("\n✅ Erfolgreich! Du kannst jetzt 'alembic revision --autogenerate' ausführen")
    else:
        print("\n❌ Fehler beim Zurücksetzen")
