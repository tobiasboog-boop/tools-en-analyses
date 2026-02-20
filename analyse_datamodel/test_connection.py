"""Test DWH connecties."""
from db_connection import syntess_connection, ctrack_connection, KLANTEN


def test_syntess(klantnummer=1264):
    """Test Syntess DWH connectie."""
    naam = KLANTEN.get(klantnummer, "Onbekend")
    print(f"=== Syntess DWH: {naam} ({klantnummer}) ===\n")
    try:
        conn = syntess_connection(klantnummer)
        cur = conn.cursor()

        cur.execute("SELECT version();")
        print(f"PostgreSQL: {cur.fetchone()[0][:40]}...")

        cur.execute("""SELECT schema_name FROM information_schema.schemata
                       WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
                       ORDER BY schema_name""")
        schemas = [r[0] for r in cur.fetchall()]
        print(f"Schema's: {', '.join(schemas)}\n")

        cur.close()
        conn.close()
        print("Connectie OK!\n")
        return True
    except Exception as e:
        print(f"FOUT: {e}\n")
        return False


def test_ctrack():
    """Test C-Track DWH connectie."""
    print("=== C-Track DWH (Wassink 1225) ===\n")
    try:
        conn = ctrack_connection()
        cur = conn.cursor()

        cur.execute("SELECT version();")
        print(f"PostgreSQL: {cur.fetchone()[0][:40]}...")

        cur.execute("""SELECT table_name FROM information_schema.tables
                       WHERE table_schema = 'stg' LIMIT 5""")
        tables = [r[0] for r in cur.fetchall()]
        print(f"Eerste tabellen in stg: {', '.join(tables)}\n")

        cur.close()
        conn.close()
        print("Connectie OK!\n")
        return True
    except Exception as e:
        print(f"FOUT: {e}\n")
        return False


if __name__ == "__main__":
    test_syntess(1264)
    test_ctrack()
