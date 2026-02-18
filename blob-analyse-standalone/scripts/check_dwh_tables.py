"""
Check welke tabellen er in de DWH zitten voor de sessie-werkbon koppeling.
Run dit script met: python scripts/check_dwh_tables.py
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor

# Configuratie - zet NOTIFICA_DWH_PASSWORD als environment variable
DWH_CONFIG = {
    "host": os.environ.get("NOTIFICA_DWH_HOST", "10.3.152.9"),
    "port": int(os.environ.get("NOTIFICA_DWH_PORT", "5432")),
    "database": os.environ.get("NOTIFICA_DWH_DATABASE", "1229"),
    "user": os.environ.get("NOTIFICA_DWH_USER", "postgres"),
    "password": os.environ.get("NOTIFICA_DWH_PASSWORD")
}


def main():
    if not DWH_CONFIG["password"]:
        print("ERROR: Zet NOTIFICA_DWH_PASSWORD environment variable")
        print("Bijvoorbeeld: set NOTIFICA_DWH_PASSWORD=jouw_wachtwoord")
        return

    print("Verbinden met DWH...")
    conn = psycopg2.connect(**DWH_CONFIG)

    with conn.cursor() as cur:
        # 1. Toon alle schema's
        print("\n=== BESCHIKBARE SCHEMA'S ===")
        cur.execute("""
            SELECT schema_name FROM information_schema.schemata
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
            ORDER BY schema_name
        """)
        schemas = [r[0] for r in cur.fetchall()]
        for s in schemas:
            print(f"  - {s}")

        # 2. Toon tabellen per schema
        print("\n=== TABELLEN PER SCHEMA ===")
        for schema in schemas:
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = %s
                ORDER BY table_name
            """, (schema,))
            tables = [r[0] for r in cur.fetchall()]
            if tables:
                print(f"\n{schema}:")
                for t in tables:
                    print(f"  - {t}")

        # 3. Zoek specifiek naar sessie-gerelateerde tabellen/kolommen
        print("\n=== KOLOMMEN MET 'SESSIE' OF 'MWBSESS' ===")
        cur.execute("""
            SELECT table_schema, table_name, column_name
            FROM information_schema.columns
            WHERE column_name ILIKE '%sessie%'
               OR column_name ILIKE '%mwbsess%'
               OR table_name ILIKE '%sessie%'
            ORDER BY table_schema, table_name
        """)
        for row in cur.fetchall():
            print(f"  {row[0]}.{row[1]}.{row[2]}")

        # 4. Check de werkbonnen schema voor sessie data
        print("\n=== WERKBONNEN SCHEMA - ALLE TABELLEN ===")
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'werkbonnen'
            ORDER BY table_name
        """)
        for row in cur.fetchall():
            print(f"  - werkbonnen.{row[0]}")

    conn.close()
    print("\n=== KLAAR ===")


if __name__ == "__main__":
    main()
