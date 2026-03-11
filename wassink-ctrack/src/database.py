"""
Wassink C-Track — Database Layer
=================================
Data bronnen:
1. C-Track ritten: PostgreSQL DWH (stg.ods_vehicle_trips_detailed)
2. Medewerkerdata: Syntess DWH (Azure SQL, 1225DWH) → Notifica API → CSV fallback
"""

import os
import sys
import streamlit as st
import pandas as pd

# Notifica SDK import (voor API fallback)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_sdk'))
try:
    from notifica_sdk import NotificaClient
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

# dotenv laden
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
except ImportError:
    pass

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')


@st.cache_data(ttl=300)
def check_connections() -> dict:
    """Test of C-Track en Syntess DWH bereikbaar zijn. Geeft status dict terug."""
    status = {
        'ctrack': {'ok': False, 'bron': 'Parquet (fallback)', 'detail': ''},
        'syntess': {'ok': False, 'bron': 'CSV (fallback)', 'detail': ''},
    }

    # Test C-Track PostgreSQL
    try:
        conn = _get_ctrack_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM stg.ods_vehicle_trips_detailed")
        count = cur.fetchone()[0]
        cur.execute("SELECT MAX(tripstartutc) FROM stg.ods_vehicle_trips_detailed")
        latest = cur.fetchone()[0]
        conn.close()
        status['ctrack'] = {
            'ok': True,
            'bron': f'PostgreSQL (10.3.152.9)',
            'detail': f'{count:,} ritten, laatste: {str(latest)[:10]}',
        }
    except Exception as e:
        status['ctrack']['detail'] = str(e)[:80]

    # Test Syntess Azure SQL
    if os.getenv('SYNTESS_DB_PASSWORD'):
        try:
            conn = _get_syntess_connection()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM Notifica.[SSM Bedrijfsmedewerkers] WHERE [Status] = 'Actueel'")
            count = cur.fetchone()[0]
            conn.close()
            status['syntess'] = {
                'ok': True,
                'bron': 'Azure SQL (1225DWH)',
                'detail': f'{count} medewerkers',
            }
        except Exception as e:
            status['syntess']['detail'] = str(e)[:80]

    return status

# Functie-mapping: Syntess functie → werktijd-categorie voor controlevensters
FUNCTIE_CATEGORIE = {
    'Servicemonteur': 'Servicemonteur',
    'Monteur': 'Projectmonteur',
    'Elektromonteur': 'Projectmonteur',
    'Hulpmonteur': 'Projectmonteur',
    'Hulpmonteur IW': 'Projectmonteur',
}


def _fix_double_utf8(s):
    """Fix double-encoded UTF-8 strings (e.g. Ã© -> é)."""
    if pd.isna(s) or not isinstance(s, str):
        return s
    try:
        return s.encode('latin-1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


# =====================================================================
# C-TRACK DATA (PostgreSQL DWH)
# =====================================================================

def _get_ctrack_connection():
    """Maak PostgreSQL connectie voor C-Track data."""
    import psycopg
    return psycopg.connect(
        host=os.getenv('CTRACK_DB_HOST', '10.3.152.9'),
        port=int(os.getenv('CTRACK_DB_PORT', '5432')),
        dbname=os.getenv('CTRACK_DB_NAME', 'DATAWAREHOUSE'),
        user=os.getenv('CTRACK_DB_USER', 'ctrack_kijker'),
        password=os.getenv('CTRACK_DB_PASSWORD', 'ctrack_kijker'),
    )


def _query_ctrack(sql: str) -> pd.DataFrame:
    """Execute SQL query on C-Track PostgreSQL."""
    conn = _get_ctrack_connection()
    cur = conn.cursor()
    cur.execute(sql)
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    conn.close()
    return pd.DataFrame(rows, columns=columns)


@st.cache_data(ttl=600)
def load_vehicles() -> pd.DataFrame:
    """Load vehicle master data from DWH."""
    try:
        return _query_ctrack('SELECT * FROM stg.stg_ctrack_vehicles')
    except Exception as e:
        st.warning(f"DB niet bereikbaar, fallback naar Parquet: {e}")
        return pd.read_parquet(os.path.join(DATA_DIR, 'vehicles.parquet'))


@st.cache_data(ttl=600)
def load_trips() -> pd.DataFrame:
    """Load trips from DWH with unit conversions."""
    try:
        df = _query_ctrack("""
            SELECT t.*, v.vehicleregistration as kenteken
            FROM stg.ods_vehicle_trips_detailed t
            LEFT JOIN stg.stg_ctrack_vehicles v ON t.nodeid = v.nodeid
        """)
    except Exception as e:
        st.warning(f"DB niet bereikbaar, fallback naar Parquet: {e}")
        df = pd.read_parquet(os.path.join(DATA_DIR, 'trips.parquet'))

    # Parse timestamps (UTC -> Europe/Amsterdam)
    start_ts = pd.to_datetime(df['tripstartutc'], utc=True)
    end_ts = pd.to_datetime(df['tripendutc'], utc=True)
    df['start'] = start_ts.dt.tz_convert('Europe/Amsterdam')
    df['eind'] = end_ts.dt.tz_convert('Europe/Amsterdam')
    df['datum'] = df['start'].dt.date

    # Convert units: meters -> km, seconds -> minutes
    df['afstand_km'] = df['tripdistance'].fillna(0) / 1000.0
    df['rijtijd_min'] = df['drivingtime'].fillna(0) / 60.0
    df['km_stand_start'] = df['startodometerreading'].fillna(0) / 1000.0
    df['km_stand_eind'] = df['endodometerreading'].fillna(0) / 1000.0

    # Parse coordinates to float
    for col in ['startlatitude', 'startlongitude', 'endlatitude', 'endlongitude']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Idle time in minutes
    df['stationair_min'] = df.get('excessidletime', pd.Series(0)).fillna(0) / 60.0
    df['overspeed_min'] = df.get('overspeedduration', pd.Series(0)).fillna(0) / 60.0

    # Bestuurder kolom: ods tabel gebruikt 'drivername' i.p.v. 'bestuurder'
    if 'bestuurder' not in df.columns and 'drivername' in df.columns:
        df['bestuurder'] = df['drivername']

    # Kenteken: komt via JOIN, maar fallback voor Parquet
    if 'kenteken' not in df.columns and 'vehicleregistration' in df.columns:
        df['kenteken'] = df['vehicleregistration']
    if 'kenteken' not in df.columns:
        df['kenteken'] = ''

    # Fix double-encoded UTF-8 in text columns
    for col in ['startlocation', 'endlocation', 'bestuurder']:
        if col in df.columns:
            df[col] = df[col].apply(_fix_double_utf8)

    return df


# =====================================================================
# SYNTESS DWH (Azure SQL - directe connectie)
# =====================================================================

def _get_syntess_connection():
    """Maak Azure SQL connectie voor Syntess DWH (1225DWH)."""
    import pyodbc
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=bisqq.database.windows.net,1433;"
        "DATABASE=1225DWH;"
        "UID=server_admin;"
        f"PWD={os.getenv('SYNTESS_DB_PASSWORD', '')};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )


def _query_syntess(sql: str) -> pd.DataFrame:
    """Execute SQL query on Syntess Azure SQL DWH."""
    conn = _get_syntess_connection()
    cur = conn.cursor()
    cur.execute(sql)
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    conn.close()
    return pd.DataFrame(rows, columns=columns)


@st.cache_data(ttl=3600)
def _load_medewerkers_syntess_dwh() -> pd.DataFrame:
    """Haal medewerkerdata op via directe Syntess DWH connectie."""
    if not os.getenv('SYNTESS_DB_PASSWORD'):
        return pd.DataFrame()

    try:
        df = _query_syntess("""
            SELECT [Medewerker code] as medewerkercode,
                   [Volledige naam] as volledige_naam,
                   [Functie] as functie,
                   [Status] as status,
                   [Datum in dienst] as datum_in_dienst,
                   [plaats], [straat], [Huisnummer] as huisnummer, [postcode]
            FROM Notifica.[SSM Bedrijfsmedewerkers]
            WHERE [Status] = 'Actueel'
              AND [Volledige naam] IS NOT NULL
              AND LEN([Volledige naam]) > 3
              AND ([Datum in dienst] IS NOT NULL OR [Functie] IS NOT NULL)
        """)
        return df
    except Exception as e:
        print(f"[INFO] Syntess DWH niet bereikbaar: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def _load_verzuim_syntess_dwh() -> pd.DataFrame:
    """Haal verzuimdata op via directe Syntess DWH connectie."""
    if not os.getenv('SYNTESS_DB_PASSWORD'):
        return pd.DataFrame()

    try:
        return _query_syntess("""
            SELECT * FROM uren.[Medewerkers verzuim]
        """)
    except Exception as e:
        print(f"[INFO] Syntess verzuim niet bereikbaar: {e}")
        return pd.DataFrame()


# =====================================================================
# NOTIFICA DATA API (fallback als DWH niet bereikbaar)
# =====================================================================

@st.cache_data(ttl=3600)
def _load_medewerkers_api() -> pd.DataFrame:
    """Haal medewerkerdata op via Notifica Data API."""
    if not SDK_AVAILABLE:
        return pd.DataFrame()

    data_key = os.getenv('NOTIFICA_DATA_KEY', '')
    klantnummer = os.getenv('KLANTNUMMER', '1225')
    if not data_key:
        return pd.DataFrame()

    try:
        client = NotificaClient(data_key=data_key)
        df = client.query(int(klantnummer), """
            SELECT
                [Medewerker code] as medewerkercode,
                [Volledige naam] as volledige_naam,
                [Functie] as functie,
                [Status] as status,
                [Datum in dienst] as datum_in_dienst,
                [plaats], [straat], [Huisnummer] as huisnummer, [postcode]
            FROM Notifica.[SSM Bedrijfsmedewerkers]
            WHERE [Status] = 'Actueel'
              AND [Volledige naam] IS NOT NULL
              AND LEN([Volledige naam]) > 3
              AND ([Datum in dienst] IS NOT NULL OR [Functie] IS NOT NULL)
        """)
        return df
    except Exception as e:
        print(f"[INFO] Notifica API niet beschikbaar: {e}")
        return pd.DataFrame()


# =====================================================================
# MEDEWERKER MAPPING (Syntess DWH → API → CSV fallback)
# =====================================================================

def _load_medewerker_csv() -> pd.DataFrame:
    """Laad medewerker mapping uit CSV (fallback)."""
    csv_path = os.path.join(DATA_DIR, 'medewerker_mapping.csv')
    if os.path.exists(csv_path):
        return pd.read_csv(csv_path, dtype=str).fillna('')
    return pd.DataFrame(columns=['bestuurder', 'personeelsnummer', 'functie'])


def _match_bestuurder_to_medewerker(bestuurder: str, medewerkers: pd.DataFrame) -> dict:
    """Match C-Track bestuurder naam aan Syntess medewerker (achternaam + voornaam)."""
    if medewerkers.empty or pd.isna(bestuurder):
        return {}

    parts = bestuurder.lower().strip().split()
    if not parts:
        return {}

    achternaam = parts[-1]
    voornaam = parts[0] if len(parts) > 1 else ''

    for _, row in medewerkers.iterrows():
        mdw_naam = str(row.get('volledige_naam', '')).lower()
        if achternaam in mdw_naam.split():
            if voornaam and voornaam in mdw_naam:
                result = {
                    'personeelsnummer': str(row.get('medewerkercode', '')),
                    'functie': str(row.get('functie', '') or ''),
                }
                # Adresgegevens meenemen als beschikbaar
                for col in ['straat', 'huisnummer', 'postcode', 'plaats']:
                    if col in medewerkers.columns:
                        result[col] = str(row.get(col, '') or '')
                return result

    return {}


def _functie_categorie(functie: str) -> str:
    """Map Syntess functie naar werktijd-categorie (Projectmonteur/Servicemonteur)."""
    if not functie:
        return ''
    return FUNCTIE_CATEGORIE.get(functie, '')


@st.cache_data(ttl=3600)
def load_medewerker_mapping() -> pd.DataFrame:
    """Laad medewerker mapping: Syntess DWH → API → CSV fallback.

    Returns DataFrame met kolommen:
        bestuurder, personeelsnummer, functie, functie_categorie,
        straat, huisnummer, postcode, plaats
    """
    # CSV is altijd de basis (handmatige overrides + al gematcht)
    csv_data = _load_medewerker_csv()

    # Check of CSV al gevuld is (personeelsnummers aanwezig)
    csv_has_data = (
        not csv_data.empty
        and 'personeelsnummer' in csv_data.columns
        and csv_data['personeelsnummer'].str.strip().ne('').any()
    )

    if csv_has_data:
        # CSV is al gevuld (door Syntess-matching of handmatig)
        result = csv_data.copy()
        # Voeg functie_categorie toe
        result['functie_categorie'] = result['functie'].apply(_functie_categorie)
        return result

    # Probeer Syntess DWH direct, dan API, dan lege CSV
    syntess_data = _load_medewerkers_syntess_dwh()
    if syntess_data.empty:
        syntess_data = _load_medewerkers_api()

    if syntess_data.empty:
        csv_data['functie_categorie'] = ''
        return csv_data

    # Match bestuurders uit trips met Syntess medewerkers
    trips = load_trips()
    bestuurders = trips['bestuurder'].dropna().unique()

    mapping_rows = []
    for bestuurder in bestuurders:
        match = _match_bestuurder_to_medewerker(bestuurder, syntess_data)
        mapping_rows.append({
            'bestuurder': bestuurder,
            'personeelsnummer': match.get('personeelsnummer', ''),
            'functie': match.get('functie', ''),
            'straat': match.get('straat', ''),
            'huisnummer': match.get('huisnummer', ''),
            'postcode': match.get('postcode', ''),
            'plaats': match.get('plaats', ''),
        })

    result = pd.DataFrame(mapping_rows)
    result['functie_categorie'] = result['functie'].apply(_functie_categorie)
    return result
