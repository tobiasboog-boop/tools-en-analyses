"""Test application database connection."""
import sys
import os

# Fix Windows console encoding
if sys.platform == "win32":
    os.system("chcp 65001 > nul")
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from src.config import config
from src.models.database import engine, SessionLocal
from src.models.contract import Contract
from sqlalchemy import text

print("="*60)
print("APPLICATION DATABASE CONNECTION TEST")
print("="*60)

print(f"\nConfiguration:")
print(f"  Host: {config.DB_HOST}")
print(f"  Port: {config.DB_PORT}")
print(f"  Database: {config.DB_NAME}")
print(f"  Schema: {config.DB_SCHEMA}")
print(f"  User: {config.DB_USER}")

# Test connection
print(f"\nTesting connection...")
try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version()"))
        version = result.fetchone()[0]
        print(f"✓ Connected to PostgreSQL")
        print(f"  Version: {version.split(',')[0]}")

        # Test schema access
        result = conn.execute(text(f"""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = '{config.DB_SCHEMA}'
        """))
        table_count = result.fetchone()[0]
        print(f"✓ Schema '{config.DB_SCHEMA}' has {table_count} tables")

except Exception as e:
    print(f"✗ Connection failed: {e}")
    exit(1)

# Test ORM
print(f"\nTesting SQLAlchemy ORM...")
try:
    db = SessionLocal()
    contracts = db.query(Contract).all()
    print(f"✓ Successfully queried Contract model")
    print(f"  Found {len(contracts)} contracts:")
    for contract in contracts:
        print(f"    - {contract.filename} (Client: {contract.client_id} - {contract.client_name})")
    db.close()
except Exception as e:
    print(f"✗ ORM query failed: {e}")
    exit(1)

print(f"\n{'='*60}")
print("✓ ALL TESTS PASSED")
print("The application is ready to use database 1210!")
print("="*60)
