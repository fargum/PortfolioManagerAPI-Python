"""Test database connection and inspect schema."""
import asyncio
from sqlalchemy import text, inspect
from src.db.session import engine
from src.core.config import settings


async def test_connection():
    """Test database connection and list tables."""
    print(f"Testing connection to: {settings.database_url}")
    print(f"Database: {settings.database_url.split('/')[-1]}")
    
    try:
        async with engine.connect() as conn:
            # Test connection
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✓ Connected to PostgreSQL!")
            print(f"  Version: {version}\n")
            
            # List all schemas
            result = await conn.execute(text("""
                SELECT schema_name 
                FROM information_schema.schemata
                ORDER BY schema_name
            """))
            schemas = result.fetchall()
            print(f"Available schemas: {[s[0] for s in schemas]}\n")
            
            # List all tables in all schemas
            result = await conn.execute(text("""
                SELECT table_schema, table_name 
                FROM information_schema.tables 
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY table_schema, table_name
            """))
            tables = result.fetchall()
            
            print(f"Found {len(tables)} tables:")
            for table in tables:
                print(f"  - {table[0]}.{table[1]}")
            
            # Check if holdings table exists
            print("\n" + "="*50)
            holdings_schema = None
            for t in tables:
                if t[1] == 'holdings':
                    holdings_schema = t[0]
                    break
            
            if holdings_schema:
                print(f"✓ 'holdings' table found in schema '{holdings_schema}'!")
                
                # Get holdings table structure
                result = await conn.execute(text("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = :schema AND table_name = 'holdings'
                    ORDER BY ordinal_position
                """), {"schema": holdings_schema})
                columns = result.fetchall()
                
                print("\nHoldings table structure:")
                for col in columns:
                    nullable = "NULL" if col[2] == 'YES' else "NOT NULL"
                    print(f"  - {col[0]}: {col[1]} ({nullable})")
            else:
                print("✗ 'holdings' table NOT found!")
                print("  Available tables:", [t[0] for t in tables])
            
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False
    
    return True


if __name__ == "__main__":
    asyncio.run(test_connection())
