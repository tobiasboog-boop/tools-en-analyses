"""
DWH Extract - Zenith Security Werkbonnen

Haalt werkbonnen data op uit de Notifica Data Warehouse voor klant 1229 (Zenith Security)
en slaat deze lokaal op voor koppeling met blobvelden.
"""

import json
import os
from pathlib import Path
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor

# Configuratie - wachtwoord via environment variable
DWH_CONFIG = {
    "host": os.environ.get("NOTIFICA_DWH_HOST", "10.3.152.9"),
    "port": int(os.environ.get("NOTIFICA_DWH_PORT", "5432")),
    "database": os.environ.get("NOTIFICA_DWH_DATABASE", "1229"),
    "user": os.environ.get("NOTIFICA_DWH_USER", "postgres"),
    "password": os.environ.get("NOTIFICA_DWH_PASSWORD")  # REQUIRED - set via .env
}

def check_config():
    """Check of de vereiste configuratie aanwezig is."""
    if not DWH_CONFIG["password"]:
        raise ValueError(
            "NOTIFICA_DWH_PASSWORD environment variable is niet gezet.\n"
            "Zet deze in een .env bestand of als environment variable."
        )

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "werkbonnen_zenith.json"


def get_connection():
    """Maak connectie met de DWH."""
    check_config()
    return psycopg2.connect(
        host=DWH_CONFIG["host"],
        port=DWH_CONFIG["port"],
        database=DWH_CONFIG["database"],
        user=DWH_CONFIG["user"],
        password=DWH_CONFIG["password"]
    )


def serialize_value(value):
    """Converteer waarde naar JSON-serializable formaat."""
    if value is None:
        return None
    elif isinstance(value, datetime):
        return value.isoformat()
    elif isinstance(value, date):
        return value.isoformat()
    elif isinstance(value, Decimal):
        return float(value)
    else:
        return value


def get_available_columns():
    """Haal beschikbare kolommen op uit de werkbonnen view."""
    query = """
    SELECT column_name
    FROM information_schema.columns
    WHERE table_schema = 'werkbonnen'
    AND table_name = 'Werkbonnen'
    ORDER BY ordinal_position
    """

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                columns = [row[0] for row in cur.fetchall()]
                return columns
    except Exception as e:
        print(f"Error getting columns: {e}")
        return []


def extract_werkbonnen(limit: Optional[int] = None) -> list:
    """
    Haal werkbonnen op uit de DWH.

    Args:
        limit: Optioneel - limiteer aantal records

    Returns:
        Lijst met werkbonnen dictionaries
    """
    # Basis query met alleen bestaande kolommen
    query = """
    SELECT *
    FROM werkbonnen."Werkbonnen" wb
    ORDER BY wb."MeldDatum" DESC NULLS LAST
    """

    if limit:
        query += f"\nLIMIT {limit}"

    werkbonnen = []

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                print(f"Executing query...")
                cur.execute(query)

                for row in cur.fetchall():
                    # Converteer alle waarden naar JSON-serializable
                    werkbon = {}
                    for key, value in row.items():
                        werkbon[key] = serialize_value(value)
                    werkbonnen.append(werkbon)

                print(f"Fetched {len(werkbonnen)} werkbonnen")

    except Exception as e:
        print(f"Error connecting to DWH: {e}")
        raise

    return werkbonnen


def extract_werkbonparagrafen(werkbon_ids: list) -> list:
    """
    Haal werkbonparagrafen op voor gegeven werkbonnen.

    Args:
        werkbon_ids: Lijst met werkbon document keys

    Returns:
        Lijst met paragraaf dictionaries
    """
    if not werkbon_ids:
        return []

    # Maak placeholder string voor IN clause
    placeholders = ','.join(['%s'] * len(werkbon_ids))

    query = f"""
    SELECT *
    FROM werkbonnen."Werkbonparagrafen" wbp
    WHERE wbp."WerkbonDocumentKey" IN ({placeholders})
    """

    paragrafen = []

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                print(f"Fetching paragrafen for {len(werkbon_ids)} werkbonnen...")
                cur.execute(query, werkbon_ids)

                for row in cur.fetchall():
                    paragraaf = {}
                    for key, value in row.items():
                        paragraaf[key] = serialize_value(value)
                    paragrafen.append(paragraaf)

                print(f"Fetched {len(paragrafen)} paragrafen")

    except Exception as e:
        print(f"Error fetching paragrafen: {e}")

    return paragrafen


def save_to_json(data: dict, path: Path):
    """Sla data op als JSON bestand."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    size_kb = path.stat().st_size / 1024
    print(f"Saved to {path} ({size_kb:.1f} KB)")


def main(limit: Optional[int] = 500, show_columns: bool = False):
    """
    Hoofdfunctie voor extractie.

    Args:
        limit: Max aantal werkbonnen (default 500 voor sample)
        show_columns: Toon beschikbare kolommen
    """
    print("=" * 60)
    print("DWH EXTRACT - ZENITH SECURITY WERKBONNEN")
    print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Database: {DWH_CONFIG['database']}")
    print("=" * 60)

    if show_columns:
        print("\nBeschikbare kolommen in werkbonnen.Werkbonnen:")
        columns = get_available_columns()
        for col in columns:
            print(f"  - {col}")
        return

    # Extract werkbonnen
    werkbonnen = extract_werkbonnen(limit=limit)

    if not werkbonnen:
        print("Geen werkbonnen gevonden!")
        return

    # Extract paragrafen
    werkbon_ids = [wb['WerkbonDocumentKey'] for wb in werkbonnen if wb.get('WerkbonDocumentKey')]
    paragrafen = extract_werkbonparagrafen(werkbon_ids)

    # Combineer data
    output_data = {
        "metadata": {
            "klant": "Zenith Security",
            "klant_id": "1229",
            "extracted_at": datetime.now().isoformat(),
            "source": "Notifica DWH",
            "totals": {
                "werkbonnen": len(werkbonnen),
                "paragrafen": len(paragrafen)
            }
        },
        "werkbonnen": werkbonnen,
        "paragrafen": paragrafen
    }

    # Sla op
    save_to_json(output_data, OUTPUT_PATH)

    # Toon sample van de kolommen
    if werkbonnen:
        print("\nBeschikbare kolommen in data:")
        sample_keys = list(werkbonnen[0].keys())[:15]
        for key in sample_keys:
            print(f"  - {key}")
        if len(werkbonnen[0].keys()) > 15:
            print(f"  ... en {len(werkbonnen[0].keys()) - 15} meer")

    print("\n" + "=" * 60)
    print("EXTRACTIE VOLTOOID")
    print(f"Werkbonnen: {len(werkbonnen)}")
    print(f"Paragrafen: {len(paragrafen)}")
    print("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract werkbonnen from DWH")
    parser.add_argument('--limit', type=int, default=500, help='Max aantal werkbonnen')
    parser.add_argument('--all', action='store_true', help='Haal alle werkbonnen op (geen limit)')
    parser.add_argument('--columns', action='store_true', help='Toon beschikbare kolommen')

    args = parser.parse_args()

    if args.columns:
        main(show_columns=True)
    elif args.all:
        main(limit=None)
    else:
        main(limit=args.limit)
