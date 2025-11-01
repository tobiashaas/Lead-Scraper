"""Simple script to verify the full-text search index exists."""
import os
import sys

from sqlalchemy import create_engine, text

# Build database URL from environment or use default
db_url = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://kr_user:kr_password@localhost:5432/kr_scraper"
)

print(f"Connecting to database...")

try:
    engine = create_engine(db_url)
    
    query = text("""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'companies'
        ORDER BY indexname;
    """)
    
    print("\n📊 Indexes on 'companies' table:\n")
    print(f"{'Index Name':<45} {'Type/Definition'}")
    print("=" * 120)
    
    with engine.connect() as conn:
        result = conn.execute(query)
        indexes = list(result)
        
        if not indexes:
            print("❌ No indexes found on 'companies' table!")
            sys.exit(1)
        
        fts_index_found = False
        for row in indexes:
            index_name = row[0]
            index_def = row[1]
            
            # Truncate long definitions
            display_def = index_def if len(index_def) <= 75 else index_def[:72] + "..."
            print(f"{index_name:<45} {display_def}")
            
            if index_name == "idx_companies_name_fts":
                fts_index_found = True
                if "to_tsvector" in index_def and "german" in index_def:
                    print("  ✅ Full-text search index with German language config VERIFIED")
                else:
                    print("  ⚠️  Index found but definition unexpected")
        
        print("\n" + "=" * 120)
        print(f"\nTotal indexes: {len(indexes)}")
        
        if fts_index_found:
            print("\n✅ SUCCESS: Full-text search index 'idx_companies_name_fts' is present!")
            sys.exit(0)
        else:
            print("\n❌ FAILED: Full-text search index 'idx_companies_name_fts' NOT FOUND!")
            print("   Expected: GIN index on to_tsvector('german', company_name)")
            sys.exit(1)

except Exception as e:
    print(f"\n❌ Error connecting to database or querying indexes:")
    print(f"   {type(e).__name__}: {e}")
    sys.exit(1)
