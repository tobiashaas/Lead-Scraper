"""
Create Test Database
Erstellt die Test-Datenbank für Integration Tests
"""

import psycopg
from app.core.config import settings
from urllib.parse import urlparse

def create_test_database():
    """Erstellt die Test-Datenbank"""
    # Parse DATABASE_URL
    parsed = urlparse(settings.database_url)
    
    # Verbinde mit postgres (default database)
    conn_string = f"host={parsed.hostname} port={parsed.port or 5432} dbname=postgres user={parsed.username} password={parsed.password}"
    
    print("Erstelle Test-Datenbank...")
    print(f"Host: {parsed.hostname}")
    print(f"Port: {parsed.port or 5432}")
    
    try:
        with psycopg.connect(conn_string, autocommit=True) as conn:
            with conn.cursor() as cur:
                # Prüfe ob Test-DB existiert
                cur.execute("""
                    SELECT 1 FROM pg_database WHERE datname = 'kr_leads_test'
                """)
                exists = cur.fetchone()
                
                if exists:
                    print("✅ Test-Datenbank existiert bereits")
                else:
                    # Erstelle Test-DB
                    cur.execute("CREATE DATABASE kr_leads_test")
                    print("✅ Test-Datenbank 'kr_leads_test' erstellt")
                
    except Exception as e:
        print(f"❌ Fehler: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("Create Test Database")
    print("=" * 60)
    print()
    
    if create_test_database():
        print("\n✅ Erfolgreich!")
    else:
        print("\n❌ Fehler beim Erstellen der Test-Datenbank")
