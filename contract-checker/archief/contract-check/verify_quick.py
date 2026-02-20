"""Quick verification of migration results."""
import psycopg2
from psycopg2 import sql

DB_HOST = "10.3.152.9"
DB_PORT = 5432
DB_USER = "postgres"
DB_PASSWORD = "TQwSTtLM9bSaLD"
SCHEMA = "contract_checker"

def verify_database(db_name):
    """Verify database contents."""
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=db_name,
        user=DB_USER,
        password=DB_PASSWORD
    )

    print(f"\n{'='*50}")
    print(f"DATABASE: {db_name}")
    print('='*50)

    with conn.cursor() as cur:
        # Count records
        cur.execute(f"SELECT COUNT(*) FROM {SCHEMA}.contracts")
        contracts_count = cur.fetchone()[0]
        print(f"Contracts: {contracts_count}")

        cur.execute(f"SELECT COUNT(*) FROM {SCHEMA}.classifications")
        classifications_count = cur.fetchone()[0]
        print(f"Classifications: {classifications_count}")

        cur.execute(f"SELECT COUNT(*) FROM {SCHEMA}.contract_changes")
        changes_count = cur.fetchone()[0]
        print(f"Contract Changes: {changes_count}")

        # Show contract details
        if contracts_count > 0:
            print(f"\nContract details:")
            cur.execute(f"""
                SELECT id, filename, client_id, client_name, active
                FROM {SCHEMA}.contracts
                ORDER BY id
            """)
            for row in cur.fetchall():
                print(f"  ID {row[0]}: {row[1]} | Client: {row[2]} ({row[3]}) | Active: {row[4]}")

        # Check indexes
        print(f"\nIndexes:")
        cur.execute("""
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = %s
            ORDER BY indexname
        """, (SCHEMA,))
        for row in cur.fetchall():
            print(f"  - {row[0]}")

    conn.close()

if __name__ == "__main__":
    print("="*50)
    print("MIGRATION VERIFICATION")
    print("="*50)

    verify_database("1190")
    verify_database("1210")

    print(f"\n{'='*50}")
    print("VERIFICATION COMPLETE")
    print("="*50)
