#!/usr/bin/env python3
"""Test database connection"""

import psycopg2
from dotenv import load_dotenv
import os
import sys

# Load environment variables
load_dotenv()

def test_connection():
    """Test PostgreSQL connection"""

    print("Testing database connection...")
    print("=" * 70)

    # Get credentials from environment
    db_config = {
        'host': os.getenv("DB_HOST", "localhost"),
        'port': os.getenv("DB_PORT", 5432),
        'database': os.getenv("DB_NAME", "edgar_financial_metrics"),
        'user': os.getenv("DB_USER", "edgar_user"),
        'password': os.getenv("DB_PASSWORD", "")
    }

    print(f"Host:     {db_config['host']}")
    print(f"Port:     {db_config['port']}")
    print(f"Database: {db_config['database']}")
    print(f"User:     {db_config['user']}")
    print("=" * 70)

    try:
        # Attempt connection
        conn = psycopg2.connect(**db_config)

        print("✓ Connection successful!")

        # Test query
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM companies;")
        count = cursor.fetchone()[0]

        print(f"✓ Query successful!")
        print(f"  Companies in database: {count}")

        # List all tables
        cursor.execute("""
            SELECT tablename
            FROM pg_catalog.pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename;
        """)
        tables = cursor.fetchall()

        print(f"\n✓ Database has {len(tables)} tables:")
        for table in tables:
            print(f"  - {table[0]}")

        cursor.close()
        conn.close()

        print("\n" + "=" * 70)
        print("SUCCESS: Database connection test passed!")
        print("=" * 70)
        return True

    except psycopg2.OperationalError as e:
        print(f"\n✗ Connection failed!")
        print(f"  Error: {e}")
        print("\nTroubleshooting:")
        print("  1. Check PostgreSQL is running: pg_isready")
        print("  2. Verify credentials in .env file")
        print("  3. Ensure database exists: psql -l | grep edgar")
        print("  4. Try: createdb edgar_financial_metrics")
        return False

    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
