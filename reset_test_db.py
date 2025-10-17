"""
Reset Test Database
Löscht alle Daten aus der Test-Datenbank
"""

import psycopg
from app.core.config import settings
from urllib.parse import urlparse

def reset_test_database():
    """Löscht alle Daten aus der Test-Datenbank"""
    # Parse DATABASE_URL
    parsed = urlparse(settings.database_url)
    
    # Verbinde mit Test-DB
    conn_string = f"host={parsed.hostname} port={parsed.port or 5432} dbname=kr_leads_test user={parsed.username} password={parsed.password}"
    
    print("Lösche alle Daten aus Test-Datenbank...")
    
    try:
        with psycopg.connect(conn_string, autocommit=True) as conn:
            with conn.cursor() as cur:
                # Prüfe welche Tabellen existieren
                cur.execute("""
                    SELECT tablename FROM pg_tables 
                    WHERE schemaname = 'public'
                """)
                tables = [row[0] for row in cur.fetchall()]
                print(f"Gefundene Tabellen: {tables}")
                
                if not tables:
                    print("⚠️  Keine Tabellen gefunden - DB ist leer oder nicht migriert")
                    return True
                
                # Lösche alle Daten
                for table in tables:
                    if table != 'alembic_version':
                        try:
                            cur.execute(f"TRUNCATE TABLE {table} CASCADE")
                            print(f"  ✓ {table} geleert")
                        except Exception as e:
                            print(f"  ✗ {table}: {e}")
                
                print("✅ Alle Daten gelöscht")
                
    except Exception as e:
        print(f"❌ Fehler: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("Reset Test Database")
    print("=" * 60)
    print()
    
    if reset_test_database():
        print("\n✅ Erfolgreich!")
    else:
        print("\n❌ Fehler beim Zurücksetzen der Test-Datenbank")
