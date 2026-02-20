"""Add missing contract_filename column to classifications table in source database 1190."""
import psycopg2
import sys
import os

# Fix Windows console encoding
if sys.platform == "win32":
    os.system("chcp 65001 > nul")
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

DB_HOST = "10.3.152.9"
DB_PORT = 5432
DB_USER = "postgres"
DB_PASSWORD = "TQwSTtLM9bSaLD"
DB_NAME = "1190"
SCHEMA = "contract_checker"

print("="*60)
print("FIXING CLASSIFICATIONS TABLE SCHEMA IN DATABASE 1190")
print("="*60)

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

    with conn.cursor() as cur:
        print("\nAdding contract_filename column...")
        cur.execute(f"""
            ALTER TABLE {SCHEMA}.classifications
            ADD COLUMN IF NOT EXISTS contract_filename VARCHAR(255)
        """)

        print("Creating index...")
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_classifications_contract_filename
            ON {SCHEMA}.classifications(contract_filename)
        """)

        conn.commit()
        print("✓ Column added successfully")

        # Verify
        print("\nVerifying columns in classifications table:")
        cur.execute("""
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = 'classifications'
            ORDER BY ordinal_position
        """, (SCHEMA,))

        for row in cur.fetchall():
            print(f"  - {row[0]:30} {row[1]:20} {row[2] if row[2] else ''}")

    conn.close()

    print("\n" + "="*60)
    print("✓ SCHEMA FIX COMPLETED FOR DATABASE 1190")
    print("="*60)

except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
