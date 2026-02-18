"""
Fetch Sessie-Werkbon Koppeling uit DWH

Dit script haalt de koppeling op tussen:
- MedewerkerWerkbonSessie (blobveld bron)
- Werkbonnen (DWH data)

Zodat we blobvelden kunnen linken aan werkbonnen.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor

# Configuratie
DWH_CONFIG = {
    "host": os.environ.get("NOTIFICA_DWH_HOST", "10.3.152.9"),
    "port": int(os.environ.get("NOTIFICA_DWH_PORT", "5432")),
    "database": os.environ.get("NOTIFICA_DWH_DATABASE", "1229"),
    "user": os.environ.get("NOTIFICA_DWH_USER", "postgres"),
    "password": os.environ.get("NOTIFICA_DWH_PASSWORD")
}

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "sessie_werkbon_koppeling.json"


def get_connection():
    if not DWH_CONFIG["password"]:
        raise ValueError("NOTIFICA_DWH_PASSWORD environment variable niet gezet")
    return psycopg2.connect(**DWH_CONFIG)


def serialize_value(value):
    if value is None:
        return None
    elif isinstance(value, datetime):
        return value.isoformat()
    elif isinstance(value, Decimal):
        return float(value)
    return value


def list_available_schemas():
    """Toon beschikbare schema's in de database."""
    query = """
    SELECT schema_name
    FROM information_schema.schemata
    WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
    ORDER BY schema_name
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return [row[0] for row in cur.fetchall()]


def list_tables_in_schema(schema_name):
    """Toon tabellen in een schema."""
    query = """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = %s
    ORDER BY table_name
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (schema_name,))
            return [row[0] for row in cur.fetchall()]


def find_sessie_table():
    """Zoek naar sessie-gerelateerde tabellen."""
    print("Zoeken naar sessie tabellen...")

    schemas = list_available_schemas()
    print(f"Beschikbare schema's: {schemas}")

    sessie_tables = []
    for schema in schemas:
        tables = list_tables_in_schema(schema)
        for table in tables:
            if 'sessie' in table.lower() or 'mwbsess' in table.lower():
                sessie_tables.append(f"{schema}.{table}")
                print(f"  Gevonden: {schema}.{table}")

    return sessie_tables


def get_sessie_werkbon_mapping(limit=None):
    """
    Haal de koppeling op tussen sessies en werkbonnen.

    De MedewerkerWerkbonSessie tabel bevat typisch:
    - SessieKey (= blob ID)
    - WerkbonDocumentKey (= link naar werkbon)
    """

    # Probeer verschillende mogelijke queries
    queries_to_try = [
        # Optie 1: Directe sessie tabel in werkbonnen schema
        """
        SELECT * FROM werkbonnen."MedewerkerWerkbonSessies"
        ORDER BY "SessieKey" DESC
        """,
        # Optie 2: Uren tabel die sessies bevat
        """
        SELECT * FROM werkbonnen."Uren"
        ORDER BY "WerkbonDocumentKey" DESC
        """,
        # Optie 3: Zoek in alle tabellen naar sessie kolommen
        """
        SELECT table_schema, table_name, column_name
        FROM information_schema.columns
        WHERE column_name ILIKE '%sessie%'
        OR column_name ILIKE '%mwbsess%'
        """,
    ]

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for i, query in enumerate(queries_to_try):
                try:
                    print(f"\nProbeer query {i+1}...")
                    if limit:
                        query = query.rstrip().rstrip(';') + f" LIMIT {limit}"
                    cur.execute(query)
                    results = cur.fetchall()
                    if results:
                        print(f"  Succes! {len(results)} records gevonden")
                        return [
                            {k: serialize_value(v) for k, v in row.items()}
                            for row in results
                        ]
                except Exception as e:
                    print(f"  Query {i+1} failed: {e}")

    return []


def main():
    print("=" * 60)
    print("SESSIE-WERKBON KOPPELING OPHALEN")
    print("=" * 60)

    # Stap 1: Vind sessie tabellen
    sessie_tables = find_sessie_table()

    if not sessie_tables:
        print("\nGeen sessie tabellen gevonden. Zoeken naar kolommen...")

    # Stap 2: Probeer mapping op te halen
    mapping = get_sessie_werkbon_mapping(limit=100)

    if mapping:
        print(f"\nMapping gevonden: {len(mapping)} records")
        print("\nVoorbeeld record:")
        print(json.dumps(mapping[0], indent=2, ensure_ascii=False))

        # Opslaan
        output_data = {
            "metadata": {
                "extracted_at": datetime.now().isoformat(),
                "total_records": len(mapping)
            },
            "koppeling": mapping
        }

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"\nOpgeslagen naar: {OUTPUT_PATH}")
    else:
        print("\nGeen mapping data gevonden")
        print("\nBeschikbare tabellen per schema:")
        for schema in list_available_schemas():
            tables = list_tables_in_schema(schema)
            if tables:
                print(f"\n{schema}:")
                for t in tables[:20]:
                    print(f"  - {t}")
                if len(tables) > 20:
                    print(f"  ... en {len(tables) - 20} meer")


if __name__ == "__main__":
    main()
