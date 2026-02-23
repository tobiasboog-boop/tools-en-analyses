"""
Zenith Werkbon Rapportage v2.0
===============================
Complete export met locatie-afhankelijke SLA KPIs (Classificatie-matrix)

Laatste update: 2026-02-23
"""
import streamlit as st
import pandas as pd
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import re
from io import BytesIO
import numpy as np
from pandas.tseries.offsets import BDay

# Load environment
try:
    from dotenv import load_dotenv
    env_path = Path('.env')
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# SDK import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '_sdk'))
from notifica_sdk import NotificaClient

# CSV BLOB helper
from csv_blob_helper import get_blob_notities_from_csv, get_latest_csv_batch

# Page config
st.set_page_config(
    page_title="Zenith Werkbon Rapportage",
    page_icon="📊",
    layout="wide"
)

KLANTNUMMER = 1229  # Zenith

# ============================================================================
# KPI CLASSIFICATIE-MATRIX (uit Zenith Classificatie tab)
# ============================================================================
# Response en Restore tijden per locatie soort + prioriteit
# Waarden: uren (int), "NBD" (Next Business Day), "BE" (Best Effort), None (n.v.t.)

LOCATIE_SOORTEN = ['Warehouse', 'Store', 'Depot', 'Fietshub', 'Office']

KPI_RESPONSE = {
    'Warehouse': {'Urgent': 4,  'Medium': 12,   'Low': 'NBD'},
    'Store':     {'Urgent': 12, 'Medium': None,  'Low': 'NBD'},
    'Depot':     {'Urgent': 12, 'Medium': None,  'Low': 'NBD'},
    'Fietshub':  {'Urgent': 24, 'Medium': None,  'Low': 'NBD'},
    'Office':    {'Urgent': 12, 'Medium': None,  'Low': 'NBD'},
}

KPI_RESTORE = {
    'Warehouse': {'Urgent': 12,   'Medium': 'NBD', 'Low': 'BE'},
    'Store':     {'Urgent': 24,   'Medium': 'NBD', 'Low': 'NBD'},
    'Depot':     {'Urgent': 24,   'Medium': 'NBD', 'Low': 'NBD'},
    'Fietshub':  {'Urgent': 'BE', 'Medium': 'BE',  'Low': 'BE'},
    'Office':    {'Urgent': 24,   'Medium': 24,    'Low': 'NBD'},
}

# Bekende contactpersonen Coolblue (uit Classificatie tab)
BEKENDE_CONTACTEN = ['Carlo', 'Ricardo', 'Rick', 'Sven', 'Giorno', 'Mariska']

# ============================================================================
# PASSWORD AUTHENTICATION
# ============================================================================

def check_password():
    """Returns True if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["password_correct"] = False

    # First run, show input for password
    if "password_correct" not in st.session_state:
        st.text_input(
            "🔒 Wachtwoord",
            type="password",
            on_change=password_entered,
            key="password",
            help="Voer het wachtwoord in om toegang te krijgen"
        )
        st.info("ℹ️ Deze applicatie is beveiligd. Voer het wachtwoord in om verder te gaan.")
        return False
    # Password incorrect, show input + error
    elif not st.session_state["password_correct"]:
        st.text_input(
            "🔒 Wachtwoord",
            type="password",
            on_change=password_entered,
            key="password",
            help="Voer het wachtwoord in om toegang te krijgen"
        )
        st.error("❌ Incorrect wachtwoord. Probeer opnieuw.")
        return False
    # Password correct
    else:
        return True

# Check authentication before showing app
if not check_password():
    st.stop()  # Stop here if not authenticated

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def strip_rtf(text):
    """
    Strip RTF formatting and escape sequences from BLOB text.

    CSV data is already clean, so we skip processing if no RTF detected.
    """
    if not text or not isinstance(text, str):
        return ''

    # Fast path: Check if text contains RTF codes
    # If no RTF found, return original text (for CSV data)
    if not ('\\rtf' in text or '\\ansi' in text or (text.count('\\') > 2)):
        return text.strip()

    # RTF detected - proceed with stripping
    original_text = text

    # Remove RTF header patterns
    text = re.sub(r'\\rtf[0-9]+', '', text)
    text = re.sub(r'\\ansi\\ansicpg[0-9]+', '', text)
    text = re.sub(r'\\deff[0-9]+', '', text)

    # Remove font table
    text = re.sub(r'\{\\fonttbl[^}]*\}', '', text)
    text = re.sub(r'\{\\colortbl[^}]*\}', '', text)

    # Remove specific fonts and formatting
    text = re.sub(r'Arial;?', '', text)
    text = re.sub(r'Symbol;?', '', text)
    text = re.sub(r'Riched20 [0-9\.]+', '', text)
    text = re.sub(r'\\f[0-9]+', '', text)
    text = re.sub(r'\\fs[0-9]+', '', text)

    # Convert common Unicode/RTF character escapes BEFORE removing control words
    unicode_map = {
        r"\'e9": "é",  # é
        r"\'e8": "è",  # è
        r"\'ea": "ê",  # ê
        r"\'eb": "ë",  # ë
        r"\'e0": "à",  # à
        r"\'e1": "á",  # á
        r"\'e2": "â",  # â
        r"\'e4": "ä",  # ä
        r"\'f3": "ó",  # ó
        r"\'f4": "ô",  # ô
        r"\'f6": "ö",  # ö
        r"\'fc": "ü",  # ü
        r"\'e7": "ç",  # ç
        r"\'ef": "ï",  # ï
        r"\'2019": "'",  # right single quote
        r"\'2013": "–",  # en dash
        r"\'2014": "—",  # em dash
    }
    for escape, char in unicode_map.items():
        text = text.replace(escape, char)

    # Remove ALL standalone backslashes (escape characters)
    # This MUST happen BEFORE removing RTF control words (which also start with \)
    # Handles: "\ Vervolg", "\ Jos", etc.
    text = re.sub(r'\\\s', ' ', text)  # Backslash followed by any whitespace
    text = re.sub(r'\\(?=[^\w])', '', text)  # Backslash before non-word char (except already handled)

    # Remove RTF control words (backslash + letters/numbers)
    text = re.sub(r'\\[a-z]+[0-9]*\s?', ' ', text)

    # Remove braces and asterisks
    text = re.sub(r'[{}*]', '', text)

    # Replace \par with newline
    text = re.sub(r'\\par', '\n', text)

    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s*;\s*', '', text)

    return text.strip()

def map_priority(prio_raw):
    """Map DWH priority to Excel format"""
    if pd.isna(prio_raw):
        return 'Medium'
    prio_str = str(prio_raw).upper()
    if '12UUR' in prio_str or '4UUR' in prio_str:
        return 'Urgent'
    elif 'LOW' in prio_str or 'NBD' in prio_str:
        return 'Low'
    else:
        return 'Medium'

def map_installatie_soort(inst_raw):
    """Map DWH installation type to Excel format"""
    if pd.isna(inst_raw):
        return ''
    if inst_raw == 'Camerasysteem':
        return 'Camera'
    elif inst_raw == 'Inbraaksysteem':
        return 'Inbraak'
    else:
        return inst_raw

def guess_location_type(location_name):
    """Heuristic to guess location type based on name (Coolblue/Zenith specific)"""
    if pd.isna(location_name):
        return 'Store'  # Default fallback

    name_lower = str(location_name).lower()

    # Fietshub (Coolblue specific)
    if 'fietshub' in name_lower or 'fiets hub' in name_lower:
        return 'Fietshub'

    # Depot (Coolblue specific)
    if 'depot' in name_lower:
        return 'Depot'

    # Warehouse / DC
    if any(kw in name_lower for kw in ['dc', 'distributie', 'warehouse', 'magazijn', 'fulfilment']):
        return 'Warehouse'

    # Office
    if any(kw in name_lower for kw in ['kantoor', 'office', 'hoofdkantoor', 'hq']):
        return 'Office'

    # Explicit store keywords
    if any(kw in name_lower for kw in ['winkel', 'store', 'shop', 'filiaal']):
        return 'Store'

    # Default: Store (most common, safest SLA assumption)
    return 'Store'

def extract_storing_omschrijving(notitie_text):
    """Extract storing description from BLOB notitie - intelligente extractie"""
    if not notitie_text:
        return ''

    # Strip RTF first
    clean = strip_rtf(notitie_text)

    # Split in zinnen (op . ! ? of newlines)
    sentences = []
    for line in clean.replace('!', '.').replace('?', '.').split('.'):
        line = line.strip()
        if line:
            sentences.append(line)

    # Filter: skip metadata zinnen (namen + datums, vervolg op, etc.)
    metadata_patterns = [
        r'^\w+\s+\w+\s+\d{2}-\d{2}-\d{4}',  # "Patrick Dutour Geerling 16-07-2024"
        r'^Vervolg op:?\s*\[',               # "Vervolg op: [werkbon://..."
        r'^\[werkbon://',                    # "[werkbon://WB123]"
        r'^(Jos[eé] van der Pool|Patrick Dutour|Werner|Roy Post)',  # Specifieke namen
        r'^(Remote|Code gemaild|Opvolging|LET OP)',  # Metadata keywords
    ]

    meaningful_sentences = []
    for sentence in sentences:
        # Skip if matches metadata pattern
        is_metadata = False
        for pattern in metadata_patterns:
            if re.search(pattern, sentence, re.IGNORECASE):
                is_metadata = True
                break

        # Skip very short sentences (< 20 chars)
        if len(sentence) < 20:
            is_metadata = True

        if not is_metadata:
            meaningful_sentences.append(sentence)

    # Return first meaningful sentence, max 200 chars
    if meaningful_sentences:
        description = meaningful_sentences[0]
        if len(description) > 200:
            return description[:197] + "..."
        return description

    # Fallback: return first 200 chars if no meaningful sentence found
    if len(clean) > 200:
        return clean[:197] + "..."
    return clean

def get_kpi(prio, locatie_soort):
    """
    Get KPI values based on priority + location type (Classificatie-matrix).

    Returns dict with 'response' and 'restore' values:
    - int: hours (e.g. 4, 12, 24)
    - "NBD": Next Business Day
    - "BE": Best Effort (always passes)
    - None: combination doesn't exist
    """
    loc = locatie_soort if locatie_soort in KPI_RESPONSE else 'Store'
    prio_key = prio if prio in ('Urgent', 'Medium', 'Low') else 'Medium'

    return {
        'response': KPI_RESPONSE.get(loc, KPI_RESPONSE['Store']).get(prio_key),
        'restore': KPI_RESTORE.get(loc, KPI_RESTORE['Store']).get(prio_key),
    }


def next_business_day_end(dt):
    """Calculate end of next business day (23:59:59) after given datetime."""
    if pd.isna(dt):
        return None
    next_bd = (pd.Timestamp(dt) + BDay(1)).normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)
    return next_bd


def check_sla(actual_hours, actual_dt, start_dt, kpi_value):
    """
    Check SLA against a KPI value.

    Returns: "Behaald", "Niet Behaald", "BE" (Best Effort), or "" (n.v.t.)
    """
    if kpi_value is None:
        return ''  # combination doesn't exist
    if kpi_value == 'BE':
        return 'BE'
    if kpi_value == 'NBD':
        if pd.isna(actual_dt) or pd.isna(start_dt):
            return ''
        nbd_end = next_business_day_end(start_dt)
        return 'Behaald' if pd.Timestamp(actual_dt) <= nbd_end else 'Niet Behaald'
    # Numeric hours
    if pd.isna(actual_hours):
        return ''
    return 'Behaald' if actual_hours <= kpi_value else 'Niet Behaald'


def check_nbd(start_dt, end_dt):
    """Check if end_dt falls within the next business day after start_dt."""
    if pd.isna(start_dt) or pd.isna(end_dt):
        return ''
    nbd_end = next_business_day_end(start_dt)
    return 'Ja' if pd.Timestamp(end_dt) <= nbd_end else 'Nee'


def extract_contact_cb(notitie_text):
    """Try to extract contact person name from BLOB notes (best-effort)."""
    if not notitie_text or not isinstance(notitie_text, str):
        return ''
    for naam in BEKENDE_CONTACTEN:
        if naam.lower() in notitie_text.lower():
            return naam
    return ''


def categorize_response_time(hours):
    """Categorize response time into ranges"""
    if pd.isna(hours):
        return ''
    if hours <= 4:
        return '0-4u'
    elif hours <= 8:
        return '4-8u'
    elif hours <= 12:
        return '8-12u'
    elif hours <= 24:
        return '12-24u'
    else:
        return '>24u'

# ============================================================================
# STREAMLIT APP
# ============================================================================

st.title("Zenith Werkbon Rapportage v2.0")
st.markdown("**Werkbonnen export met locatie-afhankelijke SLA KPIs (Classificatie-matrix)**")

# Filters
with st.sidebar:
    st.header("Filters")
    default_start = datetime.now() - timedelta(days=30)
    default_end = datetime.now()
    start_date = st.date_input("Van", default_start)
    end_date = st.date_input("Tot", default_end)

    # Haal opdrachtgever/klant lijsten op voor filters
    if st.button("🔄 Ververs filters", help="Haal beschikbare opdrachtgevers en klanten op"):
        with st.spinner("Opdrachtgevers en klanten ophalen..."):
            try:
                client = NotificaClient()

                # Haal opdrachtgevers (debiteuren) op
                opdrachtgevers_query = client.query(KLANTNUMMER, f'''
                    SELECT DISTINCT wb."Debiteur"
                    FROM werkbonnen."Werkbonnen" wb
                    WHERE wb."MeldDatum" >= '{start_date}'
                      AND wb."MeldDatum" <= '{end_date}'
                      AND wb."Debiteur" IS NOT NULL
                    ORDER BY wb."Debiteur"
                ''')
                st.session_state.opdrachtgevers_lijst = opdrachtgevers_query['Debiteur'].tolist()

                # Haal klanten op
                klanten_query = client.query(KLANTNUMMER, f'''
                    SELECT DISTINCT wb."Klant"
                    FROM werkbonnen."Werkbonnen" wb
                    WHERE wb."MeldDatum" >= '{start_date}'
                      AND wb."MeldDatum" <= '{end_date}'
                      AND wb."Klant" IS NOT NULL
                    ORDER BY wb."Klant"
                ''')
                st.session_state.klanten_lijst = klanten_query['Klant'].tolist()

                st.success(f"✓ {len(st.session_state.opdrachtgevers_lijst)} opdrachtgevers en {len(st.session_state.klanten_lijst)} klanten gevonden")
            except Exception as e:
                st.error(f"Fout bij ophalen filters: {e}")

    # Toon opdrachtgever filter (altijd zichtbaar)
    opdrachtgever_options = st.session_state.get('opdrachtgevers_lijst', [])
    opdrachtgever_filter = st.multiselect(
        "Filter op opdrachtgever (debiteur)",
        options=opdrachtgever_options,
        default=st.session_state.get('selected_opdrachtgevers', []),
        help="Type om te zoeken op hoofdniveau (bijv. 'Coolblue B.V.')",
        disabled=len(opdrachtgever_options) == 0
    )
    if opdrachtgever_filter:
        st.session_state.selected_opdrachtgevers = opdrachtgever_filter

    # Bulk selectie voor klanten
    if len(st.session_state.get('klanten_lijst', [])) > 0:
        col1, col2 = st.columns([3, 1])
        with col1:
            bulk_search = st.text_input(
                "🔍 Bulk selectie klanten",
                placeholder="Type bijv. 'Zeeman' om alle filialen te selecteren",
                help="Selecteert automatisch alle klanten die deze tekst bevatten"
            )
        with col2:
            if st.button("➕ Selecteer", disabled=not bulk_search):
                if bulk_search:
                    klant_options = st.session_state.get('klanten_lijst', [])
                    matches = [k for k in klant_options if bulk_search.lower() in k.lower()]
                    current = st.session_state.get('selected_klanten', [])
                    # Voeg matches toe aan huidige selectie (geen duplicaten)
                    st.session_state.selected_klanten = list(set(current + matches))
                    st.success(f"✓ {len(matches)} klanten toegevoegd")
                    st.rerun()

    # Toon klantfilter (altijd zichtbaar)
    klant_options = st.session_state.get('klanten_lijst', [])
    klant_filter = st.multiselect(
        "Filter op klant (locatie)",
        options=klant_options,
        default=st.session_state.get('selected_klanten', []),
        help="Type om te zoeken op locatieniveau (bijv. 'Coolblue Winkel Rotterdam')",
        disabled=len(klant_options) == 0
    )
    if klant_filter:
        st.session_state.selected_klanten = klant_filter

    if len(opdrachtgever_options) == 0 and len(klant_options) == 0:
        st.info("💡 Klik 'Ververs filters' om filters te laden")

    st.markdown("---")
    st.markdown("**Kleurcodering in Excel:**")
    st.markdown("🔴 Rood = Niet in database (handmatig invullen)")
    st.markdown("🟡 Geel = Automatisch afgeleid (controleren)")

# Guard: opdrachtgever moet geselecteerd zijn
if not opdrachtgever_filter:
    st.warning("⬅️ Selecteer eerst een opdrachtgever (debiteur) in de sidebar. Klik 'Ververs filters' als de lijst nog leeg is.")

# Main button (disabled als geen opdrachtgever geselecteerd)
if st.button("📥 Data Ophalen & Exporteren", type="primary", disabled=not opdrachtgever_filter):
    client = NotificaClient()

    # Compacte status indicator (update in plaats van nieuwe messages)
    status_container = st.empty()

    with st.spinner("Data ophalen uit DWH..."):

        # ====================================================================
        # STAP 1: BASIS WERKBONNEN OPHALEN
        # ====================================================================
        status_container.info("Stap 1/6: Basis werkbonnen ophalen...")

        werkbonnen_basis = client.query(KLANTNUMMER, f'''
            SELECT
                wb."WerkbonDocumentKey",
                wb."Werkbon",
                wb."Debiteur",
                wb."Klant",
                wb."MeldDatum",
                wb."MeldTijd",
                wb."Prioriteit",
                wb."Betreft onderaannemer",
                wb."Onderaannemer",
                wb."ParentWerkbonDocumentKey",
                wb."Status",
                ssm."Werkboncode",
                ssm."Werkbon titel"
            FROM werkbonnen."Werkbonnen" wb
            JOIN notifica."SSM Werkbonnen" ssm
              ON wb."WerkbonDocumentKey" = ssm."WerkbonDocumentKey"
            WHERE wb."MeldDatum" >= '{start_date}'
              AND wb."MeldDatum" <= '{end_date}'
            ORDER BY wb."MeldDatum" DESC
        ''')

        if werkbonnen_basis.empty:
            st.warning("Geen werkbonnen gevonden in deze periode.")
            st.stop()

        status_container.success(f"✓ {len(werkbonnen_basis)} werkbonnen gevonden")

        # Pas opdrachtgever filter toe indien ingesteld
        if opdrachtgever_filter:
            werkbonnen_basis = werkbonnen_basis[werkbonnen_basis['Debiteur'].isin(opdrachtgever_filter)]
            st.info(f"📌 Gefilterd op {len(opdrachtgever_filter)} opdrachtgever(s) - {len(werkbonnen_basis)} werkbonnen")

        # Pas klantfilter toe indien ingesteld
        if klant_filter:
            werkbonnen_basis = werkbonnen_basis[werkbonnen_basis['Klant'].isin(klant_filter)]
            st.info(f"📌 Gefilterd op {len(klant_filter)} klant(en) - {len(werkbonnen_basis)} werkbonnen")

        if werkbonnen_basis.empty:
            st.warning("Geen werkbonnen gevonden na filtering.")
            st.stop()

        # ====================================================================
        # STAP 2: PARAGRAFEN & INSTALLATIES
        # ====================================================================
        status_container.info("Stap 2/6: Paragrafen en installaties ophalen...")

        wb_keys = werkbonnen_basis['WerkbonDocumentKey'].tolist()
        wb_keys_str = ','.join(str(k) for k in wb_keys)

        paragrafen = client.query(KLANTNUMMER, f'''
            SELECT
                para."WerkbonDocumentKey",
                para."Uitgevoerd op" AS datum_oplossing,
                para."TijdstipUitgevoerd" AS tijd_oplossing,
                para."InstallatieKey",
                inst."Installatiesoort"
            FROM werkbonnen."Werkbonparagrafen" para
            LEFT JOIN notifica."SSM Installaties" inst
              ON para."InstallatieKey" = inst."InstallatieKey"
            WHERE para."WerkbonDocumentKey" IN ({wb_keys_str})
        ''')

        status_container.success(f"✓ {len(paragrafen)} paragrafen gevonden")

        # ====================================================================
        # STAP 3: REACTIE TIJDEN (LOGBOEK)
        # ====================================================================
        status_container.info("Stap 3/6: Reactie tijden ophalen...")

        logboek = client.query(KLANTNUMMER, f'''
            SELECT
                log."WerkbonDocumentKey",
                MIN(log."Datum en tijd") AS reactie_datetime
            FROM notifica."SSM Logboek werkbonfases" log
            WHERE log."WerkbonDocumentKey" IN ({wb_keys_str})
              AND log."Waarde" LIKE '%In uitvoering%'
            GROUP BY log."WerkbonDocumentKey"
        ''')

        status_container.success(f"✓ {len(logboek)} reactie tijden gevonden")

        # ====================================================================
        # STAP 4: BLOB NOTITIES (VIA CSV EXPORT)
        # ====================================================================
        status_container.info("Stap 4/6: BLOB monteur notities ophalen (via CSV)...")

        # Eerst sessies ophalen (nog steeds via SQL)
        sessies = client.query(KLANTNUMMER, f'''
            SELECT
                s."DocumentKey" AS "WerkbonDocumentKey",
                s."MobieleuitvoersessieRegelKey"
            FROM werkbonnen."Mobiele uitvoersessies" s
            WHERE s."DocumentKey" IN ({wb_keys_str})
        ''')

        blob_notities = pd.DataFrame()
        if not sessies.empty:
            sessie_keys = sessies['MobieleuitvoersessieRegelKey'].tolist()

            # Haal meest recente CSV batch op
            batch_info = get_latest_csv_batch(client, KLANTNUMMER, days=7)

            if batch_info:
                # Toon welke CSV batch gebruikt wordt
                st.info(f"📅 CSV Export: {batch_info['date']} (meest recente nachtelijke export)")
                # Download BLOB CSV bestanden en filter op sessie keys
                blob_raw = get_blob_notities_from_csv(
                    client,
                    KLANTNUMMER,
                    sessie_keys,
                    batch_info
                )

                # Merge met sessies om WerkbonDocumentKey te krijgen
                if not blob_raw.empty:
                    blob_notities = sessies.merge(
                        blob_raw,
                        on='MobieleuitvoersessieRegelKey',
                        how='inner'
                    )
                    # Als er meerdere notities zijn voor dezelfde werkbon, combineer ze
                    blob_notities = blob_notities.groupby('WerkbonDocumentKey').agg({
                        'notitie': lambda x: '\n\n'.join(x.dropna().astype(str))
                    }).reset_index()
            else:
                status_container.warning("⚠️ Geen recente CSV batch gevonden (laatste 7 dagen)")

        status_container.success(f"✓ {len(blob_notities)} BLOB notities gevonden (via CSV)")

        # ====================================================================
        # STAP 5: DATA COMBINEREN
        # ====================================================================
        status_container.info("Stap 5/6: Data samenvoegen en transformeren...")

        # Merge alles
        df = werkbonnen_basis.copy()
        df = df.merge(paragrafen, on='WerkbonDocumentKey', how='left')
        df = df.merge(logboek, on='WerkbonDocumentKey', how='left')

        # Filter 1: alleen werkbonnen met reactie data (= werkbonnen die zijn gestart)
        before_filter = len(df)
        df = df[df['reactie_datetime'].notna()]
        after_filter = len(df)
        if before_filter > after_filter:
            status_container.info(f"ℹ️ {before_filter - after_filter} niet-gestarte werkbonnen uitgefilterd")

        # Filter 2: alleen werkbonnen met oplossing data (= werkbonnen die zijn afgerond)
        # Dit voorkomt werkbonnen met 11-13 lege velden (wel gestart, niet afgerond)
        before_filter2 = len(df)
        df = df[df['datum_oplossing'].notna()]
        after_filter2 = len(df)
        if before_filter2 > after_filter2:
            status_container.info(f"ℹ️ {before_filter2 - after_filter2} niet-afgeronde werkbonnen uitgefilterd")

        # Merge BLOB notities alleen als er data is
        if not blob_notities.empty and 'notitie' in blob_notities.columns:
            df = df.merge(
                blob_notities[['WerkbonDocumentKey', 'notitie']].drop_duplicates(subset=['WerkbonDocumentKey']),
                on='WerkbonDocumentKey',
                how='left'
            )
        else:
            # Voeg lege notitie kolom toe
            df['notitie'] = None

        # Info: werkbonnen zonder BLOB notities (Storing omschrijving en Toelichting zijn dan leeg)
        zonder_blob = df['notitie'].isna() | (df['notitie'] == '')
        if zonder_blob.sum() > 0:
            st.info(f"ℹ️ {zonder_blob.sum()} werkbonnen zonder BLOB notities (Storing omschrijving en Toelichting zijn leeg)")

        if df.empty:
            st.warning("Geen werkbonnen over na filtering. Verlaag de filters.")
            st.stop()

        # ====================================================================
        # STAP 6: KOLOMMEN TRANSFORMEREN
        # ====================================================================

        result_df = pd.DataFrame()

        # --- Basisgegevens ---
        result_df['Werkbon nummer'] = df['Werkboncode']
        result_df['Week'] = pd.to_datetime(df['MeldDatum']).dt.isocalendar().week.values
        result_df['Datum aanmaak'] = pd.to_datetime(df['MeldDatum']).dt.date
        result_df['Tijd aanmaak'] = pd.to_datetime(df['MeldTijd']).dt.time
        result_df['Maand'] = pd.to_datetime(df['MeldDatum']).dt.month

        # Locatie naam - extract na ' - '
        result_df['Locatie naam'] = df['Klant'].apply(
            lambda x: x.split(' - ', 1)[1].strip() if pd.notna(x) and ' - ' in x else x
        )

        # Locatie soort - heuristic (bewerkbaar in UI na data ophalen)
        result_df['Locatie soort'] = result_df['Locatie naam'].apply(guess_location_type)

        # Installatie soort
        result_df['Installatie soort'] = df['Installatiesoort'].apply(map_installatie_soort)

        # Categorie Melding - LEEG (handmatig, A-E)
        result_df['Categorie Melding'] = ''

        result_df['Titel'] = df['Werkbon titel']
        result_df['Storing omschrijving'] = df['notitie'].apply(extract_storing_omschrijving)

        # --- SLA & Reactie ---
        result_df['Prio volgens SLA'] = df['Prioriteit'].apply(map_priority)
        result_df['Reactie datum'] = pd.to_datetime(df['reactie_datetime']).dt.date
        result_df['Reactie tijd'] = pd.to_datetime(df['reactie_datetime']).dt.time

        # Contact CB - best-effort uit BLOB notities
        result_df['Contact CB'] = df['notitie'].apply(extract_contact_cb)

        # Prio na overleg CB - LEEG (handmatig)
        result_df['Prio na overleg CB'] = ''

        # --- Quickfix / Definitief (leeg, toekomst) ---
        result_df['Restore quickfix datum'] = ''
        result_df['Restore quickfix tijd'] = ''

        # Datum/tijd oplossing (= restore definitief)
        result_df['Datum oplossing'] = pd.to_datetime(df['datum_oplossing']).dt.date
        result_df['Tijd oplossing'] = pd.to_datetime(df['tijd_oplossing']).dt.time

        result_df['Restore definitief datum'] = ''
        result_df['Restore definitief tijd'] = ''

        # --- Overige ---
        result_df['Onderaannemer'] = df['Betreft onderaannemer']

        def fill_onderaannemer(onderaannemer, betreft_onderaannemer):
            if pd.isna(onderaannemer) or onderaannemer == '' or '000000 - Zenith' in str(onderaannemer):
                if pd.notna(betreft_onderaannemer) and str(betreft_onderaannemer).lower() == 'nee':
                    return 'Niet van toepassing'
                return ''
            return onderaannemer

        result_df['Welke onderaannemer?'] = df.apply(
            lambda row: fill_onderaannemer(row['Onderaannemer'], row['Betreft onderaannemer']), axis=1
        )

        result_df['Geannuleerd?'] = df['Status'].apply(
            lambda x: 'Ja' if pd.notna(x) and 'Geannuleerd' in str(x) else 'Nee'
        )
        result_df['Toelichting'] = df['notitie'].apply(strip_rtf)
        result_df['Ouderdom systeem'] = ''
        result_df['Gerelateerde werkbon'] = df['ParentWerkbonDocumentKey'].fillna('-').replace('', '-')

        # Sla basis data op in session_state voor bewerkbare locatie soort
        st.session_state['result_df'] = result_df
        st.session_state['data_ready'] = True

        status_container.success(f"Data opgehaald - {len(result_df)} werkbonnen klaar")

# ============================================================================
# LOCATIE SOORT BEWERKBAAR (na data ophalen)
# ============================================================================

if st.session_state.get('data_ready', False) and 'result_df' in st.session_state:
    result_df = st.session_state['result_df']

    st.subheader("Locatie soort toewijzing")
    st.markdown("Controleer en pas de locatie soorten aan. **Dit bepaalt de SLA-normen.**")

    # Bouw bewerkbare tabel met unieke locaties + telling
    loc_counts = result_df.groupby(['Locatie naam', 'Locatie soort']).size().reset_index(name='Aantal')
    loc_counts = loc_counts.sort_values('Locatie naam')

    # Bewerkbare tabel met dropdown voor Locatie soort
    edited_locs = st.data_editor(
        loc_counts,
        column_config={
            "Locatie naam": st.column_config.TextColumn("Locatie", disabled=True),
            "Locatie soort": st.column_config.SelectboxColumn(
                "Locatie soort",
                options=LOCATIE_SOORTEN,
                required=True,
            ),
            "Aantal": st.column_config.NumberColumn("Aantal", disabled=True),
        },
        hide_index=True,
        use_container_width=True,
        key="locatie_editor",
    )

    # Sla de mapping op
    st.session_state['locatie_mapping'] = dict(zip(edited_locs['Locatie naam'], edited_locs['Locatie soort']))

    # ====================================================================
    # EXPORT KNOP (na locatie soort bewerkbaar)
    # ====================================================================

    if st.button("Exporteren naar Excel", type="primary"):

        # Pas bewerkbare locatie soorten toe
        result_df['Locatie soort'] = result_df['Locatie naam'].map(st.session_state['locatie_mapping'])

        # ====================================================================
        # BEREKENDE VELDEN
        # ====================================================================

        # Datetimes combineren
        result_df['aanmaak d+t'] = pd.to_datetime(
            result_df['Datum aanmaak'].astype(str) + ' ' + result_df['Tijd aanmaak'].astype(str),
            errors='coerce'
        )
        result_df['reactie d+t'] = pd.to_datetime(
            result_df['Reactie datum'].astype(str) + ' ' + result_df['Reactie tijd'].astype(str),
            errors='coerce'
        )
        result_df['response d+t'] = pd.to_datetime(
            result_df['Datum oplossing'].astype(str) + ' ' + result_df['Tijd oplossing'].astype(str),
            errors='coerce'
        )

        # Tijdsverschillen
        result_df['reactietijd'] = result_df['reactie d+t'] - result_df['aanmaak d+t']
        result_df['response tijd'] = result_df['response d+t'] - result_df['aanmaak d+t']

        # Prio numeriek
        prio_map = {'Urgent': 1, 'Medium': 2, 'Low': 3}
        result_df['Prio'] = result_df['Prio volgens SLA'].map(prio_map)

        # Uren (ceiling)
        result_df['responsetijd uren'] = result_df['reactietijd'].apply(
            lambda x: np.ceil(x.total_seconds() / 3600) if pd.notna(x) else None
        )
        result_df['restoretijd uren'] = result_df['response tijd'].apply(
            lambda x: np.ceil(x.total_seconds() / 3600) if pd.notna(x) else None
        )

        # KPI lookup (locatie-afhankelijk)
        result_df['KPI response'] = result_df.apply(
            lambda row: get_kpi(row['Prio volgens SLA'], row['Locatie soort'])['response'], axis=1
        )
        result_df['KPI restore'] = result_df.apply(
            lambda row: get_kpi(row['Prio volgens SLA'], row['Locatie soort'])['restore'], axis=1
        )

        # SLA check (ondersteunt uren, NBD en BE)
        result_df['SLA response'] = result_df.apply(
            lambda row: check_sla(row['responsetijd uren'], row['reactie d+t'], row['aanmaak d+t'], row['KPI response']),
            axis=1
        )
        result_df['SLA restore'] = result_df.apply(
            lambda row: check_sla(row['restoretijd uren'], row['response d+t'], row['aanmaak d+t'], row['KPI restore']),
            axis=1
        )

        # NBD check
        result_df['Controle NBD'] = result_df.apply(
            lambda row: check_nbd(row['aanmaak d+t'], row['response d+t']), axis=1
        )

        # Overige berekende velden
        result_df['responsetijd range'] = result_df['responsetijd uren'].apply(categorize_response_time)
        result_df['Dag binnenkomst'] = pd.to_datetime(result_df['Datum aanmaak']).dt.dayofweek + 1
        result_df['Toelichting bij Niet Behaald'] = result_df.apply(
            lambda row: '-' if row['SLA response'] == 'Behaald' and row['SLA restore'] == 'Behaald' else '',
            axis=1
        )

        st.success(f"Data getransformeerd - {len(result_df)} werkbonnen")

        # ====================================================================
        # EXCEL EXPORT MET KLEURCODERING
        # ====================================================================

        output = BytesIO()
        columns = list(result_df.columns)

        with pd.ExcelWriter(output, engine='xlsxwriter', engine_kwargs={'options': {'strings_to_urls': False}}) as writer:
            result_df.to_excel(writer, sheet_name='Werkbonnen', index=False)

            workbook = writer.book
            worksheet = writer.sheets['Werkbonnen']

            # Formaten
            red_format = workbook.add_format({'bg_color': '#FEE2E2'})
            yellow_format = workbook.add_format({'bg_color': '#FEF3C7'})
            date_format = workbook.add_format({'num_format': 'dd-mm-yyyy'})
            time_format = workbook.add_format({'num_format': 'hh:mm:ss'})
            datetime_format = workbook.add_format({'num_format': 'dd-mm-yyyy hh:mm:ss'})

            # Kolom indexen dynamisch opzoeken
            def col_idx(name):
                return columns.index(name) if name in columns else -1

            # Rode kolommen (handmatig invullen)
            red_cols = [
                'Categorie Melding', 'Prio na overleg CB',
                'Restore quickfix datum', 'Restore quickfix tijd',
                'Restore definitief datum', 'Restore definitief tijd',
                'Ouderdom systeem', 'Toelichting bij Niet Behaald',
            ]

            # Gele kolommen (automatisch afgeleid, controleren)
            yellow_cols = ['Locatie soort', 'Contact CB']

            # Datum kolommen
            date_cols = ['Datum aanmaak', 'Reactie datum', 'Datum oplossing']
            time_cols = ['Tijd aanmaak', 'Reactie tijd', 'Tijd oplossing']
            datetime_cols = ['aanmaak d+t', 'reactie d+t', 'response d+t']

            for row_num in range(1, len(result_df) + 1):
                row_data = result_df.iloc[row_num - 1]

                # Datum/tijd opmaak
                for col_name in date_cols:
                    idx = col_idx(col_name)
                    if idx >= 0:
                        worksheet.write(row_num, idx, row_data[col_name], date_format)

                for col_name in time_cols:
                    idx = col_idx(col_name)
                    if idx >= 0:
                        worksheet.write(row_num, idx, row_data[col_name], time_format)

                for col_name in datetime_cols:
                    idx = col_idx(col_name)
                    if idx >= 0:
                        worksheet.write(row_num, idx, row_data[col_name], datetime_format)

                # Rode kolommen
                for col_name in red_cols:
                    idx = col_idx(col_name)
                    if idx >= 0:
                        worksheet.write(row_num, idx, row_data.get(col_name, ''), red_format)

                # Gele kolommen
                for col_name in yellow_cols:
                    idx = col_idx(col_name)
                    if idx >= 0:
                        val = row_data.get(col_name, '')
                        if val:
                            worksheet.write(row_num, idx, val, yellow_format)

            # ====================================================================
            # INSTRUCTIES SHEET
            # ====================================================================
            instr_data = [
                ('Categorie Melding', 'ROOD', 'Handmatig: A=Technische storing, B=Operationele spoed, C=Bouwkundig, D=Wijzigingsverzoek, E=Gebruikerssupport'),
                ('Locatie soort', 'GEEL', 'Automatisch afgeleid, bewerkbaar in app. Bepaalt SLA-normen.'),
                ('Contact CB', 'GEEL', 'Best-effort uit notities. Controleer en vul aan indien nodig.'),
                ('Prio na overleg CB', 'ROOD', 'Handmatig invullen na overleg met Coolblue'),
                ('Restore quickfix datum/tijd', 'ROOD', 'Handmatig: tijdelijke oplossing. Later via Syntess Externe Notitie.'),
                ('Restore definitief datum/tijd', 'ROOD', 'Handmatig: definitieve oplossing. Later via Syntess Externe Notitie.'),
                ('Ouderdom systeem', 'ROOD', 'Voorlopig leeg. Later: datum oplevering uit Syntess.'),
                ('Toelichting bij Niet Behaald', 'ROOD', 'Handmatig: toelichting als SLA niet behaald. "-" als beide SLAs behaald.'),
            ]
            instructies = pd.DataFrame(instr_data, columns=['Kolom', 'Kleur', 'Toelichting'])

            # Classificatie info
            classificatie = pd.DataFrame([
                ('Prioriteit 1', 'Urgent', ''),
                ('Prioriteit 2', 'Medium', 'Alleen Warehouse'),
                ('Prioriteit 3', 'Low', ''),
            ], columns=['Prioriteit', 'Naam', 'Opmerking'])

            sla_response_info = pd.DataFrame([
                ('Warehouse', '4 uur', '12 uur', 'NBD'),
                ('Store', '12 uur', 'n.v.t.', 'NBD'),
                ('Depot', '12 uur', 'n.v.t.', 'NBD'),
                ('Fietshub', '24 uur', 'n.v.t.', 'NBD'),
                ('Office', '12 uur', 'n.v.t.', 'NBD'),
            ], columns=['Locatie', 'Urgent', 'Medium', 'Low'])

            sla_restore_info = pd.DataFrame([
                ('Warehouse', '12 uur', 'NBD', 'BE'),
                ('Store', '24 uur', 'NBD', 'NBD'),
                ('Depot', '24 uur', 'NBD', 'NBD'),
                ('Fietshub', 'BE', 'BE', 'BE'),
                ('Office', '24 uur', '24 uur', 'NBD'),
            ], columns=['Locatie', 'Urgent', 'Medium', 'Low'])

            instructies.to_excel(writer, sheet_name='Instructies', index=False, startrow=0)
            row_offset = len(instructies) + 3
            writer.sheets['Instructies'].write(row_offset - 1, 0, 'SLA RESPONSE TIJDEN (uren)')
            sla_response_info.to_excel(writer, sheet_name='Instructies', index=False, startrow=row_offset)
            row_offset += len(sla_response_info) + 2
            writer.sheets['Instructies'].write(row_offset - 1, 0, 'SLA RESTORE TIJDEN (uren)')
            sla_restore_info.to_excel(writer, sheet_name='Instructies', index=False, startrow=row_offset)
            row_offset += len(sla_restore_info) + 2
            writer.sheets['Instructies'].write(row_offset - 1, 0, 'NBD = Next Business Day | BE = Best Effort (geen harde norm)')

        output.seek(0)

        # ====================================================================
        # PREVIEW & DOWNLOAD
        # ====================================================================

        # Preview eerste 10 rijen
        st.subheader("Preview (eerste 10 werkbonnen)")
        preview_cols = [c for c in columns if c not in ('aanmaak d+t', 'reactie d+t', 'response d+t', 'reactietijd', 'response tijd')]
        st.dataframe(result_df[preview_cols].head(10))

        # Stats
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Totaal werkbonnen", len(result_df))
        with col2:
            sla_response_ok = (result_df['SLA response'] == 'Behaald').sum()
            st.metric("SLA response behaald", f"{sla_response_ok}/{len(result_df)}")
        with col3:
            sla_restore_ok = (result_df['SLA restore'] == 'Behaald').sum()
            st.metric("SLA restore behaald", f"{sla_restore_ok}/{len(result_df)}")
        with col4:
            geannuleerd = (result_df['Geannuleerd?'] == 'Ja').sum()
            st.metric("Geannuleerd", geannuleerd)

        # Download button
        filename = f"zenith_werkbonnen_{start_date}_{end_date}.xlsx"
        st.download_button(
            label="Download Excel",
            data=output,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.info("**Let op:** Rode cellen = handmatig invullen. Gele cellen = automatisch afgeleid (controleren). Zie tabblad 'Instructies' voor details.")
