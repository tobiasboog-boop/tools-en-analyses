"""
Zenith Werkbon Rapportage
==========================
Complete versie met alle 37 kolommen en Excel export

Laatste update: 2026-02-19
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
    """Strip RTF formatting and escape sequences from BLOB text"""
    if not text or not isinstance(text, str):
        return ''

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
    """Heuristic to guess location type based on name"""
    if pd.isna(location_name):
        return ''

    name_lower = str(location_name).lower()

    # Retail ketens met nummers (bijv. "Zeeman 1234 Amsterdam") = Store
    retail_chains = ['zeeman', 'coolblue', 'hema', 'action', 'kruidvat', 'etos', 'ah', 'jumbo', 'aldi', 'lidl']
    for chain in retail_chains:
        if chain in name_lower:
            # Check of het een nummer bevat (winkel nummer) → Store
            if any(char.isdigit() for char in location_name):
                return 'Store'

    # Expliciete keywords
    if 'winkel' in name_lower or 'store' in name_lower or 'shop' in name_lower:
        return 'Store'
    elif 'dc' in name_lower or 'distributie' in name_lower or 'warehouse' in name_lower or 'magazijn' in name_lower:
        return 'Warehouse'
    elif 'kantoor' in name_lower or 'office' in name_lower or 'hoofdkantoor' in name_lower:
        return 'Office'
    elif 'hoofdkantoor' in name_lower or 'hq' in name_lower:
        return 'Office'

    # Default voor retail met plaatsnaam → Store
    if any(chain in name_lower for chain in retail_chains):
        return 'Store'

    return ''

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

def calculate_kpi_hours(prio):
    """Get KPI hours for priority"""
    if prio == 'Urgent':
        return {'response': 12, 'restore': 24}
    elif prio == 'Medium':
        return {'response': 24, 'restore': 48}
    elif prio == 'Low':
        return {'response': 48, 'restore': 72}
    else:
        return {'response': 24, 'restore': 48}

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

st.title("📊 Zenith Werkbon Rapportage - Complete Export")
st.markdown("**Status:** Alle 37 kolommen - Data ophalen en exporteren naar Excel met kleurcodering")

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

# Main button
if st.button("📥 Data Ophalen & Exporteren", type="primary"):
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

        # Filter 3: alleen werkbonnen met BLOB notities (voor >95% data kwaliteit)
        # Dit voorkomt werkbonnen met lege Storing omschrijving en Toelichting
        before_filter3 = len(df)
        df = df[df['notitie'].notna() & (df['notitie'] != '')]
        after_filter3 = len(df)
        if before_filter3 > after_filter3:
            status_container.info(f"ℹ️ {before_filter3 - after_filter3} werkbonnen zonder BLOB notities uitgefilterd")

        if df.empty:
            st.warning("Geen werkbonnen over na filtering. Verlaag de filters.")
            st.stop()

        # ====================================================================
        # STAP 6: KOLOMMEN TRANSFORMEREN (1-21)
        # ====================================================================

        result_df = pd.DataFrame()

        # 1. Werkbon nummer
        result_df['Werkbon nummer'] = df['Werkboncode']

        # 2. Gerelateerde werkbon (fill met "-" als leeg)
        result_df['Gerelateerde werkbon'] = df['ParentWerkbonDocumentKey'].fillna('-').replace('', '-')

        # 3. Datum aanmaak (alleen datum, geen tijd)
        result_df['Datum aanmaak'] = pd.to_datetime(df['MeldDatum']).dt.date

        # 4. Tijd aanmaak - extract tijd uit datetime
        result_df['Tijd aanmaak'] = pd.to_datetime(df['MeldTijd']).dt.time

        # 5. Locatie naam - extract na ' - '
        result_df['Locatie naam'] = df['Klant'].apply(
            lambda x: x.split(' - ', 1)[1].strip() if pd.notna(x) and ' - ' in x else x
        )

        # 6. Titel
        result_df['Titel'] = df['Werkbon titel']

        # 7. Storing omschrijving - eerste zin uit BLOB notitie
        result_df['Storing omschrijving'] = df['notitie'].apply(extract_storing_omschrijving)

        # 8. Locatie soort - NIET IN DATABASE (heuristic)
        result_df['Locatie soort'] = result_df['Locatie naam'].apply(guess_location_type)

        # 9. Installatie soort - mapping
        result_df['Installatie soort'] = df['Installatiesoort'].apply(map_installatie_soort)

        # 10. Onderaannemer
        result_df['Onderaannemer'] = df['Betreft onderaannemer']

        # 11. Welke onderaannemer? - filter Zenith, fill met "Niet van toepassing" als leeg
        def fill_onderaannemer(onderaannemer, betreft_onderaannemer):
            if pd.isna(onderaannemer) or onderaannemer == '' or '000000 - Zenith' in str(onderaannemer):
                # Check of het wel een onderaannemer betreft
                if pd.notna(betreft_onderaannemer) and str(betreft_onderaannemer).lower() == 'nee':
                    return 'Niet van toepassing'
                return ''
            return onderaannemer

        result_df['Welke onderaannemer? (indien bekend)'] = df.apply(
            lambda row: fill_onderaannemer(row['Onderaannemer'], row['Betreft onderaannemer']), axis=1
        )

        # 12. Prio volgens SLA - mapping
        result_df['Prio volgens SLA'] = df['Prioriteit'].apply(map_priority)

        # 13-14. Reactie datum & tijd - split logboek datetime
        result_df['Reactie datum'] = pd.to_datetime(df['reactie_datetime']).dt.date
        result_df['Reactie tijd'] = pd.to_datetime(df['reactie_datetime']).dt.time

        # 15. Contact CB - NIET IN DATABASE
        result_df['Contact CB'] = ''

        # 16. Prio na overleg CB - assumptie: zelfde
        result_df['Prio na overleg CB'] = result_df['Prio volgens SLA']

        # 17-18. Datum & tijd oplossing
        result_df['Datum oplossing'] = pd.to_datetime(df['datum_oplossing']).dt.date
        result_df['Tijd oplossing'] = pd.to_datetime(df['tijd_oplossing']).dt.time

        # 19. Geannuleerd?
        result_df['Geannuleerd?'] = df['Status'].apply(
            lambda x: 'Ja' if pd.notna(x) and 'Geannuleerd' in str(x) else 'Nee'
        )

        # 20. Toelichting - volledige BLOB notitie (RTF stripped)
        result_df['Toelichting'] = df['notitie'].apply(strip_rtf)

        # 21. Ouderdom systeem - VAAK LEEG
        result_df['Ouderdom systeem'] = ''

        # ====================================================================
        # BEREKENDE VELDEN (22-37)
        # ====================================================================

        # 22. Maand (extract from date object)
        result_df['Maand'] = pd.to_datetime(result_df['Datum aanmaak']).dt.month

        # 23. aanmaak d+t - combineer datum + tijd
        result_df['aanmaak d+t'] = pd.to_datetime(
            result_df['Datum aanmaak'].astype(str) + ' ' + result_df['Tijd aanmaak'].astype(str),
            errors='coerce'
        )

        # 24. reactie d+t - combineer reactie datum + tijd
        result_df['reactie d+t'] = pd.to_datetime(
            result_df['Reactie datum'].astype(str) + ' ' + result_df['Reactie tijd'].astype(str),
            errors='coerce'
        )

        # 25. response d+t - combineer oplossing datum + tijd
        result_df['response d+t'] = pd.to_datetime(
            result_df['Datum oplossing'].astype(str) + ' ' + result_df['Tijd oplossing'].astype(str),
            errors='coerce'
        )

        # 26. reactietijd - verschil tussen reactie en aanmaak
        result_df['reactietijd'] = result_df['reactie d+t'] - result_df['aanmaak d+t']

        # 27. response tijd - verschil tussen oplossing en aanmaak
        result_df['response tijd'] = result_df['response d+t'] - result_df['aanmaak d+t']

        # 28. Prio - mapping naar nummer
        prio_map = {'Urgent': 1, 'Medium': 2, 'Low': 3}
        result_df['Prio'] = result_df['Prio volgens SLA'].map(prio_map)

        # 29. reasponsetijd uren - ceiling van reactietijd in uren
        result_df['reasponsetijd uren'] = result_df['reactietijd'].apply(
            lambda x: np.ceil(x.total_seconds() / 3600) if pd.notna(x) else None
        )

        # 30. restoretijd uren - ceiling van response tijd in uren
        result_df['restoretijd uren'] = result_df['response tijd'].apply(
            lambda x: np.ceil(x.total_seconds() / 3600) if pd.notna(x) else None
        )

        # 31-32. KPI response & restore - lookup op basis van prio
        result_df['KPI response'] = result_df['Prio volgens SLA'].apply(
            lambda x: calculate_kpi_hours(x)['response']
        )
        result_df['KPI restore'] = result_df['Prio volgens SLA'].apply(
            lambda x: calculate_kpi_hours(x)['restore']
        )

        # 33-34. SLA response & restore - behaald/niet behaald
        result_df['SLA response'] = result_df.apply(
            lambda row: 'Behaald' if pd.notna(row['reasponsetijd uren']) and row['reasponsetijd uren'] <= row['KPI response'] else 'Niet Behaald',
            axis=1
        )
        result_df['SLA restore'] = result_df.apply(
            lambda row: 'Behaald' if pd.notna(row['restoretijd uren']) and row['restoretijd uren'] <= row['KPI restore'] else 'Niet Behaald',
            axis=1
        )

        # 35. responsetijd range - categorisering
        result_df['responsetijd range'] = result_df['reasponsetijd uren'].apply(categorize_response_time)

        # 36. Dag binnenkomst - weekday (1=Monday, 7=Sunday)
        result_df['Dag binnenkomst'] = pd.to_datetime(result_df['Datum aanmaak']).dt.dayofweek + 1

        # 37. Toelichting bij Niet Behaald - fill met "-" als beide SLA's behaald zijn
        result_df['Toelichting bij Niet Behaald'] = result_df.apply(
            lambda row: '-' if row['SLA response'] == 'Behaald' and row['SLA restore'] == 'Behaald' else '',
            axis=1
        )

        status_container.success(f"✓ Data getransformeerd - {len(result_df)} werkbonnen klaar")

        # ====================================================================
        # EXCEL EXPORT MET KLEURCODERING
        # ====================================================================
        status_container.info("Stap 6/6: Excel bestand maken met kleurcodering...")

        output = BytesIO()

        # Ensure proper UTF-8 encoding for special characters (é, ç, etc.)
        with pd.ExcelWriter(output, engine='xlsxwriter', engine_kwargs={'options': {'strings_to_urls': False}}) as writer:
            result_df.to_excel(writer, sheet_name='Werkbonnen', index=False)

            workbook = writer.book
            worksheet = writer.sheets['Werkbonnen']

            # Formaten
            red_format = workbook.add_format({'bg_color': '#FEE2E2'})  # Rood - niet in database
            yellow_format = workbook.add_format({'bg_color': '#FEF3C7'})  # Geel - automatisch afgeleid
            date_format = workbook.add_format({'num_format': 'dd-mm-yyyy'})  # Datum formaat
            time_format = workbook.add_format({'num_format': 'hh:mm:ss'})  # Tijd formaat
            datetime_format = workbook.add_format({'num_format': 'dd-mm-yyyy hh:mm:ss'})  # Datetime formaat

            # Kolom indexen (0-based)
            col_datum_aanmaak = 2  # Kolom C
            col_tijd_aanmaak = 3  # Kolom D
            col_locatie_soort = 7  # Kolom H - Locatie soort
            col_reactie_datum = 12  # Kolom M
            col_reactie_tijd = 13  # Kolom N
            col_contact_cb = 14  # Kolom O - Contact CB
            col_datum_oplossing = 16  # Kolom Q
            col_tijd_oplossing = 17  # Kolom R
            col_ouderdom = 20  # Kolom U - Ouderdom systeem
            col_aanmaak_dt = 22  # Kolom W
            col_reactie_dt = 23  # Kolom X
            col_response_dt = 24  # Kolom Y

            # Datum/tijd opmaak toepassen op alle rijen
            for row_num in range(1, len(result_df) + 1):
                # Datum kolommen
                worksheet.write(row_num, col_datum_aanmaak, result_df.iloc[row_num - 1]['Datum aanmaak'], date_format)
                worksheet.write(row_num, col_reactie_datum, result_df.iloc[row_num - 1]['Reactie datum'], date_format)
                worksheet.write(row_num, col_datum_oplossing, result_df.iloc[row_num - 1]['Datum oplossing'], date_format)

                # Tijd kolommen
                worksheet.write(row_num, col_tijd_aanmaak, result_df.iloc[row_num - 1]['Tijd aanmaak'], time_format)
                worksheet.write(row_num, col_reactie_tijd, result_df.iloc[row_num - 1]['Reactie tijd'], time_format)
                worksheet.write(row_num, col_tijd_oplossing, result_df.iloc[row_num - 1]['Tijd oplossing'], time_format)

                # Datetime kolommen
                worksheet.write(row_num, col_aanmaak_dt, result_df.iloc[row_num - 1]['aanmaak d+t'], datetime_format)
                worksheet.write(row_num, col_reactie_dt, result_df.iloc[row_num - 1]['reactie d+t'], datetime_format)
                worksheet.write(row_num, col_response_dt, result_df.iloc[row_num - 1]['response d+t'], datetime_format)

            # Kleurcodering toepassen
            for row_num in range(1, len(result_df) + 1):
                # Rood - niet in database
                worksheet.write(row_num, col_contact_cb, result_df.iloc[row_num - 1]['Contact CB'], red_format)
                worksheet.write(row_num, col_ouderdom, result_df.iloc[row_num - 1]['Ouderdom systeem'], red_format)

                # Geel - automatisch afgeleid (heuristic)
                loc_soort = result_df.iloc[row_num - 1]['Locatie soort']
                if loc_soort:  # Alleen als er een waarde is ingevuld
                    worksheet.write(row_num, col_locatie_soort, loc_soort, yellow_format)

            # Instructies sheet
            instructies = pd.DataFrame({
                'Kolom': [
                    'Contact CB',
                    'Locatie soort',
                    'Ouderdom systeem'
                ],
                'Status': [
                    'ROOD - Niet in database',
                    'GEEL - Automatisch afgeleid',
                    'ROOD - Niet in database'
                ],
                'Actie': [
                    'Handmatig invullen (bijv. Carlo, Emma)',
                    'Controleren en aanpassen indien nodig',
                    'Handmatig invullen indien bekend'
                ]
            })
            instructies.to_excel(writer, sheet_name='Instructies', index=False)

        output.seek(0)

        # ====================================================================
        # PREVIEW & DOWNLOAD
        # ====================================================================

        status_container.success("✅ Export klaar!")

        # Preview eerste 10 rijen
        st.subheader("Preview (eerste 10 werkbonnen)")
        st.dataframe(result_df.head(10))

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
            label="📥 Download Excel",
            data=output,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.info("💡 **Let op:** Rode cellen moeten handmatig worden ingevuld. Gele cellen zijn automatisch afgeleid en kunnen worden gecontroleerd.")
