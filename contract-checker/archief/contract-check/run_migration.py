"""
Database Migration Script: 1190 -> 1210
Migrates the contract_checker schema using Python and psycopg2
"""
import psycopg2
from psycopg2 import sql
from datetime import datetime
import sys
import os

# Fix Windows console encoding
if sys.platform == "win32":
    os.system("chcp 65001 > nul")
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Database credentials
DB_HOST = "10.3.152.9"
DB_PORT = 5432
DB_USER = "postgres"
DB_PASSWORD = "TQwSTtLM9bSaLD"
DB_SOURCE = "1190"
DB_TARGET = "1210"
SCHEMA = "contract_checker"


def connect_db(database):
    """Connect to a PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=database,
            user=DB_USER,
            password=DB_PASSWORD
        )
        conn.autocommit = False
        return conn
    except Exception as e:
        print(f"Error connecting to database {database}: {e}")
        sys.exit(1)


def check_schema_exists(conn, schema):
    """Check if schema exists."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.schemata
                WHERE schema_name = %s
            )
        """, (schema,))
        return cur.fetchone()[0]


def get_record_count(conn, schema, table):
    """Get record count for a table."""
    with conn.cursor() as cur:
        cur.execute(sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
            sql.Identifier(schema),
            sql.Identifier(table)
        ))
        return cur.fetchone()[0]


def ensure_target_schema(conn):
    """Ensure target schema exists with all tables."""
    print("\n=== Checking target schema ===")
    with conn.cursor() as cur:
        # Create schema if not exists
        cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
            sql.Identifier(SCHEMA)
        ))
        print(f"✓ Schema {SCHEMA} exists")

        # Check if tables exist
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
            ORDER BY table_name
        """, (SCHEMA,))
        tables = [row[0] for row in cur.fetchall()]

        if tables:
            print(f"✓ Found tables: {', '.join(tables)}")
        else:
            print("⚠ No tables found - will need to run setup.sql first")
            return False

    conn.commit()
    return True


def copy_table_data(source_conn, target_conn, table_name, columns):
    """Copy data from source to target table."""
    print(f"\n=== Copying {table_name} ===")

    # Count source records
    source_count = get_record_count(source_conn, SCHEMA, table_name)
    print(f"Source records: {source_count}")

    if source_count == 0:
        print("No records to copy")
        return

    # Fetch all data from source
    with source_conn.cursor() as src_cur:
        src_cur.execute(sql.SQL("SELECT {} FROM {}.{} ORDER BY id").format(
            sql.SQL(", ").join(map(sql.Identifier, columns)),
            sql.Identifier(SCHEMA),
            sql.Identifier(table_name)
        ))
        rows = src_cur.fetchall()

    print(f"Fetched {len(rows)} records from source")

    # Insert into target (with conflict handling)
    with target_conn.cursor() as tgt_cur:
        # Build insert statement with ON CONFLICT
        if table_name == "contracts":
            insert_sql = sql.SQL("""
                INSERT INTO {}.{} ({})
                VALUES ({})
                ON CONFLICT (filename, client_id) DO NOTHING
            """).format(
                sql.Identifier(SCHEMA),
                sql.Identifier(table_name),
                sql.SQL(", ").join(map(sql.Identifier, columns)),
                sql.SQL(", ").join([sql.Placeholder()] * len(columns))
            )
        else:
            insert_sql = sql.SQL("""
                INSERT INTO {}.{} ({})
                VALUES ({})
                ON CONFLICT (id) DO NOTHING
            """).format(
                sql.Identifier(SCHEMA),
                sql.Identifier(table_name),
                sql.SQL(", ").join(map(sql.Identifier, columns)),
                sql.SQL(", ").join([sql.Placeholder()] * len(columns))
            )

        # Insert in batches
        batch_size = 100
        inserted = 0
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            for row in batch:
                tgt_cur.execute(insert_sql, row)
            inserted += len(batch)
            if inserted % 500 == 0:
                print(f"Inserted {inserted}/{len(rows)} records...")

        target_conn.commit()
        print(f"✓ Inserted {inserted} records")

    # Verify target count
    target_count = get_record_count(target_conn, SCHEMA, table_name)
    print(f"Target records after migration: {target_count}")


def update_sequences(conn):
    """Update sequence values to match max IDs."""
    print("\n=== Updating sequences ===")

    sequences = [
        ("contracts_id_seq", "contracts"),
        ("contract_changes_id_seq", "contract_changes"),
        ("classifications_id_seq", "classifications")
    ]

    with conn.cursor() as cur:
        for seq_name, table_name in sequences:
            cur.execute(sql.SQL("""
                SELECT setval('{}.{}',
                    COALESCE((SELECT MAX(id) FROM {}.{}), 1))
            """).format(
                sql.Identifier(SCHEMA),
                sql.Identifier(seq_name),
                sql.Identifier(SCHEMA),
                sql.Identifier(table_name)
            ))
            new_val = cur.fetchone()[0]
            print(f"✓ {seq_name} set to {new_val}")

    conn.commit()


def verify_migration(source_conn, target_conn):
    """Verify the migration results."""
    print("\n=== Verification ===")

    tables = ["contracts", "classifications", "contract_changes"]
    all_ok = True

    for table in tables:
        source_count = get_record_count(source_conn, SCHEMA, table)
        target_count = get_record_count(target_conn, SCHEMA, table)

        status = "✓" if source_count == target_count else "✗"
        print(f"{status} {table}: {source_count} (source) -> {target_count} (target)")

        if source_count != target_count:
            all_ok = False

    return all_ok


def main():
    """Main migration process."""
    print("="*60)
    print("DATABASE MIGRATION: 1190 -> 1210")
    print(f"Schema: {SCHEMA}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    # Connect to both databases
    print("\nConnecting to databases...")
    source_conn = connect_db(DB_SOURCE)
    target_conn = connect_db(DB_TARGET)
    print("✓ Connected to source (1190)")
    print("✓ Connected to target (1210)")

    try:
        # Check source schema
        if not check_schema_exists(source_conn, SCHEMA):
            print(f"\n✗ ERROR: Schema {SCHEMA} does not exist in source database {DB_SOURCE}")
            sys.exit(1)
        print(f"✓ Source schema exists")

        # Ensure target schema and tables exist
        if not ensure_target_schema(target_conn):
            print("\n⚠ Target schema needs tables. Running setup first...")
            # Read and execute setup.sql
            with open("sql/setup.sql", "r", encoding="utf-8") as f:
                setup_sql = f.read()
            with target_conn.cursor() as cur:
                cur.execute(setup_sql)
            target_conn.commit()
            print("✓ Setup completed")

        # Copy data (order matters for foreign keys!)
        # 1. Contracts (parent table)
        copy_table_data(
            source_conn, target_conn, "contracts",
            ["id", "filename", "client_id", "client_name", "contract_number",
             "start_date", "end_date", "contract_type", "notes", "filepath",
             "created_at", "updated_at", "file_modified_at", "last_synced_at",
             "active", "deleted_at", "version", "checksum"]
        )

        # 2. Contract changes (references contracts)
        copy_table_data(
            source_conn, target_conn, "contract_changes",
            ["id", "contract_id", "filename", "change_type",
             "old_client_id", "new_client_id", "changed_fields",
             "changed_at", "changed_by"]
        )

        # 3. Classifications (references contracts)
        copy_table_data(
            source_conn, target_conn, "classifications",
            ["id", "werkbon_id", "contract_id", "timestamp", "classificatie",
             "mapping_score", "contract_referentie", "toelichting",
             "werkbon_bedrag", "werkelijke_classificatie", "created_at"]
        )

        # Update sequences
        update_sequences(target_conn)

        # Verify
        success = verify_migration(source_conn, target_conn)

        print("\n" + "="*60)
        if success:
            print("✓ MIGRATION COMPLETED SUCCESSFULLY")
        else:
            print("⚠ MIGRATION COMPLETED WITH WARNINGS")
            print("  Please review the verification results above")
        print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)

    except Exception as e:
        print(f"\n✗ ERROR during migration: {e}")
        import traceback
        traceback.print_exc()
        target_conn.rollback()
        sys.exit(1)
    finally:
        source_conn.close()
        target_conn.close()


if __name__ == "__main__":
    main()
