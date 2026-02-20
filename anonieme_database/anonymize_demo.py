"""
Anonimiseer een gekloonde Syntess DWH database voor demo-doeleinden.

Workflow:
1. Kloon database 1225 via GRIP naar een nieuwe demo-database (bijv. "demo_1225")
2. Draai dit script op de gekloonde database
3. Koppel Power BI semantisch model aan de endviews van de demo-database

Het script:
- Verbindt met de gekloonde demo-database
- Draait anonymization.sql (alle UPDATE-statements)
- Draait verify_anonymization.sql (steekproef)
- Toont een samenvatting van de anonimisatie

Gebruik:
    python anonymize_demo.py --host 10.3.152.9 --port 5432 --database demo_1225 --user postgres --password <wachtwoord>
    python anonymize_demo.py --env  (leest uit .env bestand)
"""

import argparse
import os
import sys
import time
from pathlib import Path

try:
    import psycopg2
    from psycopg2 import sql
except ImportError:
    print("psycopg2 niet gevonden. Installeer met: pip install psycopg2-binary")
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

SCRIPT_DIR = Path(__file__).parent
ANONYMIZATION_SQL = SCRIPT_DIR / "anonymization.sql"
VERIFICATION_SQL = SCRIPT_DIR / "verify_anonymization.sql"


def get_connection_params(args):
    """Haal connectie-parameters op uit argumenten of .env bestand."""
    if args.env:
        if load_dotenv is None:
            print("python-dotenv niet gevonden. Installeer met: pip install python-dotenv")
            sys.exit(1)
        load_dotenv(args.env)
        return {
            "host": os.getenv("SYNTESS_DB_HOST", "10.3.152.9"),
            "port": int(os.getenv("SYNTESS_DB_PORT", "5432")),
            "database": os.getenv("SYNTESS_DB_NAME", "demo_1225"),
            "user": os.getenv("SYNTESS_DB_USER", "postgres"),
            "password": os.getenv("SYNTESS_DB_PASSWORD", ""),
        }
    return {
        "host": args.host,
        "port": args.port,
        "database": args.database,
        "user": args.user,
        "password": args.password,
    }


def check_database_is_clone(conn, source_db="1225"):
    """Veiligheidscheck: waarschuw als de database op de brondatabase lijkt."""
    cur = conn.cursor()
    cur.execute("SELECT current_database()")
    db_name = cur.fetchone()[0]
    cur.close()

    if db_name == source_db:
        print(f"\n{'='*60}")
        print(f"  WAARSCHUWING: Je bent verbonden met database '{db_name}'!")
        print(f"  Dit lijkt de ORIGINELE klantdatabase te zijn.")
        print(f"  Anonimisatie is ONOMKEERBAAR.")
        print(f"{'='*60}\n")
        antwoord = input("Weet je ZEKER dat dit de gekloonde demo-database is? (ja/nee): ")
        if antwoord.lower() != "ja":
            print("Afgebroken. Kloon eerst de database via GRIP.")
            sys.exit(0)

    return db_name


def run_sql_file(conn, sql_file, description):
    """Voer een SQL-bestand uit op de database."""
    print(f"\n{'─'*60}")
    print(f"  {description}")
    print(f"  Bestand: {sql_file.name}")
    print(f"{'─'*60}")

    if not sql_file.exists():
        print(f"  FOUT: Bestand niet gevonden: {sql_file}")
        return False

    sql_content = sql_file.read_text(encoding="utf-8")

    # Splits op statement-niveau (dubbele newline + commentaar of direct statement)
    # We voeren het hele bestand in één keer uit
    start = time.time()
    cur = conn.cursor()
    try:
        cur.execute(sql_content)
        conn.commit()
        elapsed = time.time() - start
        print(f"  Voltooid in {elapsed:.1f} seconden")
        return True
    except Exception as e:
        conn.rollback()
        print(f"  FOUT: {e}")
        return False
    finally:
        cur.close()


def run_verification(conn, sql_file):
    """Voer verificatie-queries uit en toon resultaten."""
    print(f"\n{'='*60}")
    print(f"  VERIFICATIE - Steekproef geanonimiseerde data")
    print(f"{'='*60}")

    if not sql_file.exists():
        print(f"  Bestand niet gevonden: {sql_file}")
        return

    sql_content = sql_file.read_text(encoding="utf-8")

    # Splits individuele queries (gescheiden door --QUERY: label)
    queries = []
    current_label = ""
    current_sql = []

    for line in sql_content.split("\n"):
        if line.startswith("--QUERY:"):
            if current_sql:
                queries.append((current_label, "\n".join(current_sql)))
            current_label = line.replace("--QUERY:", "").strip()
            current_sql = []
        elif line.startswith("--"):
            continue
        else:
            current_sql.append(line)

    if current_sql:
        queries.append((current_label, "\n".join(current_sql)))

    cur = conn.cursor()
    for label, query in queries:
        query = query.strip()
        if not query:
            continue
        try:
            cur.execute(query)
            rows = cur.fetchall()
            colnames = [desc[0] for desc in cur.description] if cur.description else []

            print(f"\n  {label}")
            print(f"  {'─'*50}")
            if colnames:
                header = " | ".join(f"{c:<25}" for c in colnames[:4])
                print(f"  {header}")
                print(f"  {'─'*50}")
            for row in rows[:5]:
                vals = " | ".join(f"{str(v):<25}" for v in row[:4])
                print(f"  {vals}")
            if len(rows) > 5:
                print(f"  ... en {len(rows) - 5} meer rijen")
        except Exception as e:
            print(f"\n  {label}: FOUT - {e}")
            conn.rollback()

    cur.close()


def show_summary(conn):
    """Toon een samenvatting van de database na anonimisatie."""
    print(f"\n{'='*60}")
    print(f"  SAMENVATTING")
    print(f"{'='*60}")

    cur = conn.cursor()

    # Tel rijen in de belangrijkste tabellen
    tables = [
        "stamrelaties", "stammedewerkers", "stampersonen", "stamadressen",
        "stamadministraties", "dimobjecten", "dimwerkbonnen", "dimprojecten",
        "factverkoopfactuurtermijnen", "factinkoopfactuurtermijnen",
        "factopbrengsten", "factjournaalregels", "factkosten",
    ]

    print(f"\n  {'Tabel':<45} {'Rijen':>10}")
    print(f"  {'─'*55}")

    for table in tables:
        try:
            cur.execute(f'SELECT COUNT(*) FROM prepare."{table}"')
            count = cur.fetchone()[0]
            print(f"  prepare.{table:<36} {count:>10,}")
        except Exception:
            conn.rollback()

    cur.close()


def main():
    parser = argparse.ArgumentParser(
        description="Anonimiseer een gekloonde Syntess DWH database voor demo-doeleinden"
    )
    parser.add_argument("--host", default="10.3.152.9", help="Database host")
    parser.add_argument("--port", type=int, default=5432, help="Database port")
    parser.add_argument("--database", default="demo_1225", help="Database naam (de KLOON, niet het origineel!)")
    parser.add_argument("--user", default="postgres", help="Database gebruiker")
    parser.add_argument("--password", default="", help="Database wachtwoord")
    parser.add_argument("--env", default="", help="Pad naar .env bestand (alternatief voor losse parameters)")
    parser.add_argument("--skip-verify", action="store_true", help="Sla verificatie over")
    parser.add_argument("--force", action="store_true", help="Sla veiligheidscheck over")

    args = parser.parse_args()
    params = get_connection_params(args)

    print(f"\n{'='*60}")
    print(f"  SYNTESS DWH ANONIMISATIE TOOL")
    print(f"  Database: {params['database']} @ {params['host']}:{params['port']}")
    print(f"{'='*60}")

    # Verbind
    try:
        conn = psycopg2.connect(**params)
        conn.autocommit = False
        print(f"  Verbonden met database")
    except Exception as e:
        print(f"  Kan niet verbinden: {e}")
        sys.exit(1)

    # Veiligheidscheck
    if not args.force:
        db_name = check_database_is_clone(conn)
        print(f"  Database: {db_name}")

    # Stap 1: Anonimisatie
    success = run_sql_file(conn, ANONYMIZATION_SQL, "STAP 1: Anonimisatie uitvoeren")
    if not success:
        print("\nAnonimisatie mislukt. Database is NIET gewijzigd (rollback).")
        conn.close()
        sys.exit(1)

    # Stap 2: Samenvatting
    show_summary(conn)

    # Stap 3: Verificatie
    if not args.skip_verify:
        run_verification(conn, VERIFICATION_SQL)

    conn.close()

    print(f"\n{'='*60}")
    print(f"  KLAAR! Database '{params['database']}' is geanonimiseerd.")
    print(f"")
    print(f"  Volgende stappen:")
    print(f"  1. Maak een semantisch model (Power BI) op de endviews")
    print(f"  2. Koppel rapporten aan het semantisch model")
    print(f"  3. Test de rapporten met de demo-data")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
