"""Database connection helper voor Syntess DWH en C-Track DWH."""
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()


# === Syntess DWH (alle klanten) ===

def syntess_connection(klantnummer):
    """Maak connectie met Syntess DWH voor een specifieke klant.

    Args:
        klantnummer: Klantnummer als database naam (bijv. 1264 voor WETEC)
    """
    return psycopg2.connect(
        host=os.getenv('SYNTESS_HOST'),
        port=os.getenv('SYNTESS_PORT'),
        database=str(klantnummer),
        user=os.getenv('SYNTESS_USER'),
        password=os.getenv('SYNTESS_PASSWORD')
    )


def syntess_query(klantnummer, query, params=None):
    """Voer query uit op Syntess DWH en retourneer resultaten als dicts."""
    conn = syntess_connection(klantnummer)
    cur = conn.cursor()
    cur.execute(query, params)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


# === C-Track DWH (Wassink 1225) ===

def ctrack_connection():
    """Maak connectie met C-Track DWH."""
    return psycopg2.connect(
        host=os.getenv('CTRACK_HOST'),
        port=os.getenv('CTRACK_PORT'),
        database=os.getenv('CTRACK_DB'),
        user=os.getenv('CTRACK_USER'),
        password=os.getenv('CTRACK_PASSWORD')
    )


# === Bekende klanten ===

KLANTEN = {
    1264: "WETEC",
    1225: "Wassink",
    1241: "Liquiditeit Demo",
    1256: "Van den Buijs",
}
