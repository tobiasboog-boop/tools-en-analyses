"""
Inspect CLOB Tables

Script om de structuur van CLOB tabellen te inspecteren.
Dit helpt bij het begrijpen van welke kolommen beschikbaar zijn voor de rapportage.
"""

import psycopg2
import pandas as pd
from tabulate import tabulate

DB_CONFIG = {
    "host": "217.160.16.105",
    "port": 5432,
    "database": "1229",
    "user": "steamlit_1229",
    "password": "steamlit_1229"
}


def inspect_table(conn, schema, table):
    """Inspecteer een tabel en toon structuur + sample data."""
    print(f"\n{'='*80}")
    print(f"TABEL: {schema}.{table}")
    print(f"{'='*80}\n")

    # Haal kolommen op
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT column_name, data_type, character_maximum_length
        FROM information_schema.columns
        WHERE table_schema = '{schema}'
        AND table_name = '{table}'
        ORDER BY ordinal_position
    """)

    columns = cursor.fetchall()

    print("KOLOMMEN:")
    print(tabulate(columns, headers=['Kolom', 'Type', 'Max Lengte'], tablefmt='grid'))

    # Haal aantal rijen op
    cursor.execute(f'SELECT COUNT(*) FROM {schema}.{table}')
    row_count = cursor.fetchone()[0]
    print(f"\nAantal rijen: {row_count:,}")

    # Haal sample data op
    if row_count > 0:
        print("\nSAMPLE DATA (eerste 3 rijen):")
        df = pd.read_sql(f"SELECT * FROM {schema}.{table} LIMIT 3", conn)
        print(df.to_string(index=False))

        # Toon CLOB kolom inhoud (vaak een specifieke kolom)
        clob_col_candidates = [col for col in df.columns if 'tekst' in col.lower() or 'clob' in col.lower() or 'text' in col.lower()]
        if clob_col_candidates:
            print(f"\n CLOB INHOUD (kolom: {clob_col_candidates[0]}):")
            for idx, row in df.iterrows():
                clob_value = row[clob_col_candidates[0]]
                if pd.notna(clob_value):
                    preview = str(clob_value)[:200] + "..." if len(str(clob_value)) > 200 else str(clob_value)
                    print(f"  Rij {idx+1}: {preview}")
                else:
                    print(f"  Rij {idx+1}: <NULL>")

    cursor.close()


def main():
    """Inspecteer alle CLOB tabellen."""
    print("=" * 80)
    print("DATABASE CLOB TABLE INSPECTOR")
    print("=" * 80)
    print(f"\nConnecting to: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("✅ Connectie succesvol!\n")

        # Inspecteer alle CLOB tabellen
        clob_tables = [
            ("maatwerk", "stg_AT_DOCUMENT_CLOBS"),
            ("maatwerk", "stg_AT_UITVBEST_CLOBS"),
            ("maatwerk", "stg_AT_WERK_CLOBS"),
            ("maatwerk", "stg_AT_MWBSESS_CLOBS")
        ]

        for schema, table in clob_tables:
            try:
                inspect_table(conn, schema, table)
            except Exception as e:
                print(f"\n❌ Fout bij {schema}.{table}: {e}")

        # Inspecteer ook de koppeltabel
        print(f"\n{'='*80}")
        print("KOPPELTABEL: werkbonnen.Mobiele uitvoersessies")
        print(f"{'='*80}\n")

        try:
            inspect_table(conn, "werkbonnen", "Mobiele uitvoersessies")
        except Exception as e:
            print(f"❌ Fout: {e}")

        conn.close()
        print("\n✅ Inspectie voltooid!")

    except Exception as e:
        print(f"❌ Database connectie fout: {e}")


if __name__ == "__main__":
    main()
