"""Verify database indexes, especially the full-text search index."""
import sys
from sqlalchemy import create_engine, text

from app.core.config import settings


def verify_indexes():
    """Check that all expected indexes exist on the companies table."""
    engine = create_engine(settings.database_url_psycopg3)
    
    query = text("""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'companies'
        ORDER BY indexname;
    """)
    
    print("📊 Indexes on 'companies' table:\n")
    print(f"{'Index Name':<40} {'Definition'}")
    print("=" * 120)
    
    with engine.connect() as conn:
        result = conn.execute(query)
        indexes = list(result)
        
        if not indexes:
            print("❌ No indexes found on 'companies' table!")
            return False
        
        fts_index_found = False
        for row in indexes:
            index_name = row[0]
            index_def = row[1]
            print(f"{index_name:<40} {index_def[:80]}")
            
            if index_name == "idx_companies_name_fts":
                fts_index_found = True
                print("  ✅ Full-text search index FOUND")
        
        print("\n" + "=" * 120)
        print(f"\nTotal indexes: {len(indexes)}")
        
        if fts_index_found:
            print("✅ Full-text search index 'idx_companies_name_fts' is present!")
            return True
        else:
            print("❌ Full-text search index 'idx_companies_name_fts' NOT FOUND!")
            print("   Expected: GIN index on to_tsvector('german', company_name)")
            return False


if __name__ == "__main__":
    try:
        success = verify_indexes()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
