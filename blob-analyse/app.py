"""
Zenith Werkbon Rapportage v2.1
===============================
Complete export met locatie-afhankelijke SLA KPIs (Classificatie-matrix)
+ AI use case tabs (Notitie-analyse, Contract Check, Storingspatronen)

Laatste update: 2026-03-10
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
# AI USE CASE TABS — RENDER FUNCTIONS
# ============================================================================

def render_notitie_analyse_tab():
    """Tab 2: AI Notitie-analyse — gestructureerde extractie uit BLOB-tekst"""

    st.header("AI Notitie-analyse")
    st.markdown("""
    **Het probleem:** Monteurs schrijven vrije tekst in het systeem. Rommelig, afkortingen, halve zinnen.
    De huidige tool stript alleen de RTF-opmaak, maar haalt geen **gestructureerde informatie** uit de inhoud.

    **De oplossing:** AI leest elke monteurnotitie en extraheert automatisch:
    """)

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown("🔍 **Probleem**")
        st.caption("Wat was de oorzaak?")
    with col2:
        st.markdown("🔧 **Actie**")
        st.caption("Wat is er gedaan?")
    with col3:
        st.markdown("✅ **Oplossing**")
        st.caption("Definitief of tijdelijk?")
    with col4:
        st.markdown("📦 **Materialen**")
        st.caption("Welke onderdelen?")
    with col5:
        st.markdown("⚠️ **Derden**")
        st.caption("Schade door externen?")

    st.markdown("---")
    st.subheader("Voorbeeld: van ruwe notitie naar gestructureerde data")

    # Mockup data — realistische Zenith/Coolblue werkbonnen
    mockup_data = pd.DataFrame([
        {
            "Werkbon": "WB-2025-001847",
            "Locatie": "Warehouse Tilburg",
            "Ruwe monteurnotitie": "Patrick Dutour 12-01-2025\nBrandmelder gang 3 defect rookmelder reageert niet meer. Detector vervangen type Siemens FDO241. Carlo gebeld voor toegang magazijn. Vervolg op: [werkbon://WB-2025-001700]",
            "→ Probleem": "Defecte rookmelder (reageert niet)",
            "→ Actie": "Detector vervangen",
            "→ Materiaal": "Siemens FDO241",
            "→ Definitief?": "Ja",
            "→ Derden?": "Nee",
        },
        {
            "Werkbon": "WB-2025-002103",
            "Locatie": "Store Amsterdam",
            "Ruwe monteurnotitie": "Roy Post 28-01-2025 Klant wil extra cam bijplaatsen boven kassa 4 ivm diefstal. Offerte gemaakt en doorgestuurd naar Ricardo. Geen storing - uitbreiding.",
            "→ Probleem": "Geen storing (uitbreidingsverzoek)",
            "→ Actie": "Offerte opgesteld",
            "→ Materiaal": "n.v.t.",
            "→ Definitief?": "n.v.t.",
            "→ Derden?": "Nee",
        },
        {
            "Werkbon": "WB-2025-002251",
            "Locatie": "Depot Rotterdam",
            "Ruwe monteurnotitie": "Werner 03-02-2025\nKabel inbraakdet beschadigd door lekkage plafond. Water druppelt op PIR sensor. Tijdelijk gerepareerd met krimpkous, moet terug voor definitief. Bouwkundig issue melden bij CB.",
            "→ Probleem": "Waterschade aan inbraakdetectie-kabel",
            "→ Actie": "Tijdelijke reparatie (krimpkous)",
            "→ Materiaal": "Krimpkous",
            "→ Definitief?": "Nee — retourbezoek nodig",
            "→ Derden?": "Ja — bouwkundig (lekkage plafond)",
        },
        {
            "Werkbon": "WB-2025-001955",
            "Locatie": "Fietshub Utrecht",
            "Ruwe monteurnotitie": "José v/d Pool 18-01-2025 vals alarm inbraak systeem. Spinnenwebben op sensor hal 2. Sensor schoongemaakt en gevoeligheid aangepast. Geen onderdelen.",
            "→ Probleem": "Vals alarm door spinnenwebben",
            "→ Actie": "Sensor gereinigd + gevoeligheid aangepast",
            "→ Materiaal": "Geen",
            "→ Definitief?": "Ja",
            "→ Derden?": "Nee",
        },
        {
            "Werkbon": "WB-2025-002087",
            "Locatie": "Store Den Haag",
            "Ruwe monteurnotitie": "Patrick Dutour 25-01-2025 Camera parkeerplaats draait niet meer, pan/tilt motor defect. Motor vervangen Dahua SD6AL245. Sven gebeld ivm parkeerplaats afsluiting.",
            "→ Probleem": "Defecte pan/tilt motor camera",
            "→ Actie": "Motor vervangen",
            "→ Materiaal": "Dahua SD6AL245",
            "→ Definitief?": "Ja",
            "→ Derden?": "Nee",
        },
        {
            "Werkbon": "WB-2025-002190",
            "Locatie": "Warehouse Eindhoven",
            "Ruwe monteurnotitie": "Roy Post 05-02-2025\nVerzoek nw toegangscontrole dock 7. Niet in scope oorspronkelijke install. Offerte nodig. Overleg met Giorno over planning Q2.",
            "→ Probleem": "Geen storing (uitbreidingsverzoek)",
            "→ Actie": "Offerte vereist",
            "→ Materiaal": "Toegangscontrole (nader te bepalen)",
            "→ Definitief?": "n.v.t.",
            "→ Derden?": "Nee",
        },
    ])

    st.dataframe(
        mockup_data,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Ruwe monteurnotitie": st.column_config.TextColumn(width="large"),
            "→ Probleem": st.column_config.TextColumn(width="medium"),
            "→ Actie": st.column_config.TextColumn(width="medium"),
        }
    )

    st.markdown("---")

    # Value proposition
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Tijdsbesparing per werkbon", "~5 min", help="Handmatig notities lezen en interpreteren vs. automatische extractie")
    with col2:
        st.metric("Velden automatisch ingevuld", "5", help="Probleem, actie, materiaal, definitief/tijdelijk, derden")
    with col3:
        st.metric("Nauwkeurigheid", "~90%", help="Op basis van vergelijkbare pilots bij andere klanten")

    st.info("""
    **Hoe werkt het?** De AI leest de volledige monteurnotitie — inclusief afkortingen, typefouten en ongestructureerde tekst — en
    extraheert de kerninfo. Dit vervangt het handmatig doorlezen van elke notitie. De medewerker valideert alleen nog de output.
    """)


def render_contract_check_tab():
    """Tab 3: Contract Check — binnen/buiten SLA classificatie"""

    st.header("AI Contract Check")
    st.markdown("""
    **Het probleem:** Per werkbon moet iemand beoordelen of het werk onder het SLA-contract valt of meerwerk is
    dat doorbelast mag worden. Dit kost tijd, is foutgevoelig, en leidt tot gemiste omzet.

    **De oplossing:** AI leest de werkbonomschrijving, monteurnotities én contractvoorwaarden, en geeft per werkbon een classificatie:
    """)

    # Drie classificaties visueel
    col1, col2, col3 = st.columns(3)
    with col1:
        st.success("**✅ BINNEN CONTRACT**")
        st.markdown("Werkzaamheden vallen onder de SLA-overeenkomst. Geen actie nodig.")
    with col2:
        st.error("**❌ MEERWERK**")
        st.markdown("Valt buiten het contract. Mag worden doorbelast aan de opdrachtgever.")
    with col3:
        st.warning("**⚠️ TWIJFEL**")
        st.markdown("Grensgebied. Vereist menselijke beoordeling door een medewerker.")

    st.markdown("---")
    st.subheader("Voorbeeld: AI-classificatie van Zenith werkbonnen")

    mockup_data = pd.DataFrame([
        {
            "Werkbon": "WB-2025-001847",
            "Locatie": "Warehouse Tilburg",
            "Omschrijving": "Brandmelder gang 3 defect, detector vervangen preventief",
            "Classificatie": "✅ Binnen contract",
            "AI-toelichting": "Vervanging defecte rookmelder is preventief onderhoud conform SLA art. 4.2 — onderdeel van reguliere service.",
            "Confidence": "96%",
        },
        {
            "Werkbon": "WB-2025-002103",
            "Locatie": "Store Amsterdam",
            "Omschrijving": "Extra camera bijplaatsen boven kassa 4",
            "Classificatie": "❌ Meerwerk",
            "AI-toelichting": "Bijplaatsen van camera is een uitbreiding, geen onderhoud of storing. Niet gedekt onder SLA-scope.",
            "Confidence": "98%",
        },
        {
            "Werkbon": "WB-2025-002251",
            "Locatie": "Depot Rotterdam",
            "Omschrijving": "Kabel inbraakdetectie beschadigd door lekkage plafond",
            "Classificatie": "⚠️ Twijfel",
            "AI-toelichting": "Schade door waterschade (derden/bouwkundig). Installatie valt onder SLA, maar oorzaak is extern. Menselijke beoordeling nodig.",
            "Confidence": "62%",
        },
        {
            "Werkbon": "WB-2025-001955",
            "Locatie": "Fietshub Utrecht",
            "Omschrijving": "Vals alarm inbraaksysteem door spinnenwebben, sensor schoongemaakt",
            "Classificatie": "✅ Binnen contract",
            "AI-toelichting": "Reiniging sensor en herkalibratie is regulier onderhoud. Vals alarm verhelpen valt onder SLA art. 4.1.",
            "Confidence": "94%",
        },
        {
            "Werkbon": "WB-2025-002087",
            "Locatie": "Store Den Haag",
            "Omschrijving": "Camera parkeerplaats draait niet meer, motor vervangen",
            "Classificatie": "✅ Binnen contract",
            "AI-toelichting": "Defect aan bestaande installatie. Vervanging motor is correctief onderhoud conform SLA art. 4.3.",
            "Confidence": "95%",
        },
        {
            "Werkbon": "WB-2025-002190",
            "Locatie": "Warehouse Eindhoven",
            "Omschrijving": "Verzoek nieuwe toegangscontrole dock 7, niet in oorspronkelijke scope",
            "Classificatie": "❌ Meerwerk",
            "AI-toelichting": "Nieuwe installatie buiten oorspronkelijke scope. Expliciete uitbreiding — niet gedekt onder bestaand SLA.",
            "Confidence": "99%",
        },
    ])

    st.dataframe(
        mockup_data,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Omschrijving": st.column_config.TextColumn(width="medium"),
            "Classificatie": st.column_config.TextColumn(width="small"),
            "AI-toelichting": st.column_config.TextColumn(width="large"),
            "Confidence": st.column_config.TextColumn(width="small"),
        }
    )

    st.markdown("---")

    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Nauwkeurigheid", "~90%", help="Gebaseerd op pilots bij vergelijkbare installatiebedrijven")
    with col2:
        st.metric("Tijdsbesparing", "85%", help="Van ~7 min handmatig naar ~1 min valideren per werkbon")
    with col3:
        st.metric("Benchmark gemist meerwerk", "10-15%", help="Percentage meerwerk dat niet wordt gefactureerd bij handmatige controle")
    with col4:
        st.metric("Human in the loop", "Altijd", help="De AI adviseert, de medewerker beslist")

    st.info("""
    **Belangrijk:** De medewerker blijft altijd in de lead. De AI geeft een advies met toelichting en confidence score.
    Bij twijfelgevallen (confidence < 80%) wordt de werkbon altijd voorgelegd aan een medewerker.
    Het eindoordeel is altijd menselijk — de AI bespaart tijd, niet verantwoordelijkheid.
    """)


def render_patronen_tab():
    """Tab 4: Storingspatronen — AI-gedreven patroonherkenning"""
    import plotly.express as px
    import plotly.graph_objects as go

    NAVY = '#16136F'
    NAVY_LIGHT = '#3636A2'
    NAVY_PALE = '#E8E7F5'
    ACCENT = '#5B59C2'

    st.header("Storingspatronen")

    result_df = st.session_state.get('result_df')
    has_data = result_df is not None and not result_df.empty

    if not has_data:
        st.info(
            "**Laad eerst data** in de **Storingslijst Export** tab. "
            "Hieronder een voorbeeld met demo data."
        )

        # --- Demo data ---
        demo_locaties = pd.DataFrame({
            'Locatie': ['Warehouse Tilburg', 'Store Amsterdam', 'Store Den Haag', 'Depot Rotterdam',
                        'Warehouse Eindhoven', 'Fietshub Utrecht', 'Store Rotterdam', 'Store Breda',
                        'Depot Tilburg', 'Store Groningen'],
            'Storingen': [34, 27, 22, 19, 16, 14, 11, 9, 8, 5],
        })
        demo_installatie = pd.DataFrame({
            'Type': ['Brandmelding', 'Camerasysteem', 'Inbraakdetectie', 'Toegangscontrole', 'Intercom'],
            'Storingen': [52, 41, 34, 24, 14],
        })
        maanden = ['Jan', 'Feb', 'Mrt', 'Apr', 'Mei', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dec']
        demo_trend = pd.DataFrame({
            'Maand': maanden,
            'Storingen': [11, 14, 18, 15, 12, 16, 13, 10, 17, 21, 19, 14],
            'idx': range(12),
        })
        demo_prio = pd.DataFrame({
            'Prioriteit': ['Prio 1 (4 uur)', 'Prio 2 (8 uur)', 'Prio 3 (24 uur)', 'Prio 4 (NBD)', 'Best Effort'],
            'Storingen': [18, 35, 62, 38, 12],
        })

        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Totaal werkbonnen", "165")
        col2.metric("Unieke locaties", "10")
        col3.metric("Installatietypes", "5")
        col4.metric("Periode", "Jan — Dec 2025")

        st.markdown("---")

        # Charts row 1: locaties + installatietype
        col1, col2 = st.columns([3, 2])
        with col1:
            fig = px.bar(
                demo_locaties.sort_values('Storingen'),
                x='Storingen', y='Locatie', orientation='h',
                color_discrete_sequence=[NAVY],
            )
            fig.update_layout(
                title='Top 10 locaties',
                xaxis_title='', yaxis_title='',
                height=380, margin=dict(l=0, r=20, t=40, b=20),
                plot_bgcolor='white', paper_bgcolor='white',
                font=dict(size=13),
            )
            fig.update_traces(texttemplate='%{x}', textposition='outside')
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig2 = px.pie(
                demo_installatie, values='Storingen', names='Type',
                color_discrete_sequence=[NAVY, NAVY_LIGHT, ACCENT, NAVY_PALE, '#9896D6'],
                hole=0.45,
            )
            fig2.update_layout(
                title='Verdeling per installatietype',
                height=380, margin=dict(l=0, r=0, t=40, b=20),
                paper_bgcolor='white',
                font=dict(size=13),
                legend=dict(orientation='h', yanchor='bottom', y=-0.15, xanchor='center', x=0.5),
            )
            fig2.update_traces(textinfo='percent+label', textposition='inside')
            st.plotly_chart(fig2, use_container_width=True)

        # Charts row 2: trend + prioriteit
        col1, col2 = st.columns([3, 2])
        with col1:
            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(
                x=demo_trend['Maand'], y=demo_trend['Storingen'],
                mode='lines+markers+text', text=demo_trend['Storingen'],
                textposition='top center',
                line=dict(color=NAVY, width=3),
                marker=dict(size=8, color=NAVY),
                fill='tozeroy', fillcolor='rgba(22,19,111,0.08)',
            ))
            fig3.update_layout(
                title='Storingen per maand (trend)',
                xaxis_title='', yaxis_title='Aantal',
                height=340, margin=dict(l=0, r=20, t=40, b=20),
                plot_bgcolor='white', paper_bgcolor='white',
                font=dict(size=13),
            )
            st.plotly_chart(fig3, use_container_width=True)

        with col2:
            fig4 = px.bar(
                demo_prio, x='Prioriteit', y='Storingen',
                color_discrete_sequence=[NAVY_LIGHT],
            )
            fig4.update_layout(
                title='Verdeling per prioriteit',
                xaxis_title='', yaxis_title='',
                height=340, margin=dict(l=0, r=20, t=40, b=20),
                plot_bgcolor='white', paper_bgcolor='white',
                font=dict(size=13),
                xaxis_tickangle=-25,
            )
            fig4.update_traces(texttemplate='%{y}', textposition='outside')
            st.plotly_chart(fig4, use_container_width=True)

        # AI inzichten
        st.markdown("---")
        st.subheader("AI-inzichten (voorbeeld)")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(
                '<div style="background:#F0F0FB; border-left:4px solid #16136F; padding:16px; border-radius:6px;">'
                '<strong>Probleemlocatie</strong><br>'
                'Warehouse Tilburg heeft <strong>2.5x</strong> meer storingen dan gemiddeld, '
                'voornamelijk bij brandmeldinstallaties (gang 3).'
                '</div>', unsafe_allow_html=True
            )
        with col2:
            st.markdown(
                '<div style="background:#F0F0FB; border-left:4px solid #3636A2; padding:16px; border-radius:6px;">'
                '<strong>Seizoenspatroon</strong><br>'
                'Oktober-november toont een <strong>piek (+45%)</strong>. '
                'Mogelijk verband met herfststormen en vochtschade aan buitensensoren.'
                '</div>', unsafe_allow_html=True
            )
        with col3:
            st.markdown(
                '<div style="background:#F0F0FB; border-left:4px solid #5B59C2; padding:16px; border-radius:6px;">'
                '<strong>Aanbeveling</strong><br>'
                'Preventief onderhoudsplan voor <strong>3 locaties</strong> kan '
                'naar schatting <strong>30%</strong> van de terugkerende storingen voorkomen.'
                '</div>', unsafe_allow_html=True
            )
        return

    # ========================================================================
    # ECHTE DATA ANALYSE
    # ========================================================================

    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Totaal werkbonnen", f"{len(result_df):,}".replace(',', '.'))
    with col2:
        st.metric("Unieke locaties", result_df['Locatie naam'].nunique())
    with col3:
        n_types = result_df['Installatie soort'].replace('', pd.NA).dropna().nunique()
        st.metric("Installatietypes", n_types)
    with col4:
        d_min = result_df['Datum aanmaak'].min()
        d_max = result_df['Datum aanmaak'].max()
        st.metric("Periode", f"{d_min} — {d_max}")

    st.markdown("---")

    # --- Charts row 1: locaties + installatietype ---
    loc_counts = result_df['Locatie naam'].value_counts().head(12)
    inst_counts = result_df['Installatie soort'].replace('', pd.NA).dropna().value_counts()

    col1, col2 = st.columns([3, 2])
    with col1:
        df_loc = pd.DataFrame({'Locatie': loc_counts.index, 'Storingen': loc_counts.values})
        fig = px.bar(
            df_loc.sort_values('Storingen'),
            x='Storingen', y='Locatie', orientation='h',
            color_discrete_sequence=[NAVY],
        )
        fig.update_layout(
            title=f'Top {len(df_loc)} locaties (meeste storingen)',
            xaxis_title='', yaxis_title='',
            height=max(350, len(df_loc) * 35 + 80),
            margin=dict(l=0, r=20, t=40, b=20),
            plot_bgcolor='white', paper_bgcolor='white',
            font=dict(size=13),
        )
        fig.update_traces(texttemplate='%{x}', textposition='outside')
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        if not inst_counts.empty:
            df_inst = pd.DataFrame({'Type': inst_counts.index, 'Storingen': inst_counts.values})
            fig2 = px.pie(
                df_inst, values='Storingen', names='Type',
                color_discrete_sequence=[NAVY, NAVY_LIGHT, ACCENT, NAVY_PALE, '#9896D6', '#C4C3E8'],
                hole=0.45,
            )
            fig2.update_layout(
                title='Verdeling per installatietype',
                height=max(350, len(df_loc) * 35 + 80),
                margin=dict(l=0, r=0, t=40, b=20),
                paper_bgcolor='white',
                font=dict(size=13),
                legend=dict(orientation='h', yanchor='bottom', y=-0.2, xanchor='center', x=0.5),
            )
            fig2.update_traces(textinfo='percent+label', textposition='inside')
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.caption("Geen installatiesoort data beschikbaar.")

    # --- Charts row 2: trend + prioriteit ---
    maand_labels = {1: 'Jan', 2: 'Feb', 3: 'Mrt', 4: 'Apr', 5: 'Mei', 6: 'Jun',
                    7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Okt', 11: 'Nov', 12: 'Dec'}

    maand_counts = result_df['Maand'].value_counts().sort_index()
    trend_df = pd.DataFrame({
        'Maand': [maand_labels.get(m, str(m)) for m in maand_counts.index],
        'Storingen': maand_counts.values,
        'idx': range(len(maand_counts)),
    })

    prio_col = 'Prio volgens SLA / input CB'
    has_prio = prio_col in result_df.columns

    col1, col2 = st.columns([3, 2])
    with col1:
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=trend_df['Maand'], y=trend_df['Storingen'],
            mode='lines+markers+text', text=trend_df['Storingen'],
            textposition='top center',
            line=dict(color=NAVY, width=3),
            marker=dict(size=8, color=NAVY),
            fill='tozeroy', fillcolor='rgba(22,19,111,0.08)',
        ))
        fig3.update_layout(
            title='Storingen per maand (trend)',
            xaxis_title='', yaxis_title='Aantal',
            height=340, margin=dict(l=0, r=20, t=40, b=20),
            plot_bgcolor='white', paper_bgcolor='white',
            font=dict(size=13),
        )
        st.plotly_chart(fig3, use_container_width=True)

    with col2:
        if has_prio:
            prio_counts = result_df[prio_col].replace('', pd.NA).dropna().value_counts()
            if not prio_counts.empty:
                df_prio = pd.DataFrame({'Prioriteit': prio_counts.index, 'Storingen': prio_counts.values})
                fig4 = px.bar(
                    df_prio, x='Prioriteit', y='Storingen',
                    color_discrete_sequence=[NAVY_LIGHT],
                )
                fig4.update_layout(
                    title='Verdeling per prioriteit',
                    xaxis_title='', yaxis_title='',
                    height=340, margin=dict(l=0, r=20, t=40, b=20),
                    plot_bgcolor='white', paper_bgcolor='white',
                    font=dict(size=13),
                    xaxis_tickangle=-25,
                )
                fig4.update_traces(texttemplate='%{y}', textposition='outside')
                st.plotly_chart(fig4, use_container_width=True)
            else:
                st.caption("Geen prioriteit data beschikbaar.")
        else:
            st.caption("Prioriteit kolom niet gevonden in data.")

    # --- Heatmap: locatietype x maand ---
    if 'Locatie soort' in result_df.columns:
        cross = pd.crosstab(
            result_df['Locatie soort'].replace('', 'Onbekend'),
            result_df['Maand']
        )
        cross.columns = [maand_labels.get(m, str(m)) for m in cross.columns]
        if not cross.empty and len(cross) > 1:
            fig5 = px.imshow(
                cross.values,
                x=cross.columns.tolist(),
                y=cross.index.tolist(),
                color_continuous_scale=[[0, '#F0F0FB'], [0.5, '#9896D6'], [1, NAVY]],
                aspect='auto',
                text_auto=True,
            )
            fig5.update_layout(
                title='Heatmap: storingen per locatietype per maand',
                xaxis_title='', yaxis_title='',
                height=max(250, len(cross) * 50 + 100),
                margin=dict(l=0, r=20, t=40, b=20),
                paper_bgcolor='white',
                font=dict(size=13),
            )
            st.plotly_chart(fig5, use_container_width=True)

    # --- SLA performance ---
    if 'SLA response' in result_df.columns:
        sla_data = result_df[result_df['SLA response'].replace('', pd.NA).notna()]
        if not sla_data.empty:
            st.markdown("---")
            st.subheader("SLA Performance")
            total_resp = len(sla_data)
            resp_ok = (sla_data['SLA response'] == 'Behaald').sum()
            resp_pct = round(resp_ok / total_resp * 100, 1) if total_resp > 0 else 0

            col1, col2, col3 = st.columns(3)
            col1.metric("Response SLA behaald", f"{resp_pct}%", f"{resp_ok} van {total_resp}")

            if 'SLA restore' in sla_data.columns:
                rest_data = sla_data[sla_data['SLA restore'].replace('', pd.NA).notna()]
                if not rest_data.empty:
                    rest_ok = (rest_data['SLA restore'] == 'Behaald').sum()
                    rest_pct = round(rest_ok / len(rest_data) * 100, 1)
                    col2.metric("Restore SLA behaald", f"{rest_pct}%", f"{rest_ok} van {len(rest_data)}")

            # SLA per locatietype tabel
            if 'Locatie soort' in sla_data.columns:
                sla_by_loc = sla_data.groupby('Locatie soort').apply(
                    lambda x: pd.Series({
                        'Werkbonnen': len(x),
                        'Response behaald': f"{round((x['SLA response'] == 'Behaald').sum() / len(x) * 100)}%",
                    })
                ).reset_index()
                col3.dataframe(sla_by_loc, use_container_width=True, hide_index=True)

    # --- AI inzichten ---
    st.markdown("---")
    st.subheader("AI-inzichten")

    insights = []

    # Inzicht 1: probleemlocatie
    loc_vc = result_df['Locatie naam'].value_counts()
    avg_count = loc_vc.mean()
    if not loc_vc.empty:
        top_name = loc_vc.index[0]
        top_count = loc_vc.values[0]
        ratio = round(top_count / avg_count, 1) if avg_count > 0 else 0
        top_loc_data = result_df[result_df['Locatie naam'] == top_name]
        top_inst = top_loc_data['Installatie soort'].replace('', pd.NA).dropna().value_counts()
        inst_txt = f", voornamelijk bij <strong>{top_inst.index[0]}</strong>" if not top_inst.empty else ""
        if ratio >= 1.5:
            insights.append((
                "Probleemlocatie",
                f"<strong>{top_name}</strong> heeft <strong>{ratio}x</strong> meer storingen "
                f"dan gemiddeld ({top_count} vs. {round(avg_count, 1)} gem.){inst_txt}."
            ))

    # Inzicht 2: seizoenspatroon
    if len(maand_counts) >= 4:
        peak_month_num = maand_counts.idxmax()
        peak_val = maand_counts.max()
        avg_val = maand_counts.mean()
        if peak_val > avg_val * 1.3:
            peak_name = maand_labels.get(peak_month_num, str(peak_month_num))
            pct_above = round((peak_val / avg_val - 1) * 100)
            insights.append((
                "Seizoenspatroon",
                f"<strong>{peak_name}</strong> toont een piek van <strong>+{pct_above}%</strong> "
                f"boven het maandgemiddelde ({int(peak_val)} vs. {round(avg_val, 1)} gem.). "
                f"Overweeg extra capaciteit in deze periode."
            ))

    # Inzicht 3: concentratie
    if len(loc_vc) >= 5:
        top3_sum = loc_vc.head(3).sum()
        total = loc_vc.sum()
        top3_pct = round(top3_sum / total * 100)
        if top3_pct >= 30:
            top3_names = ', '.join(loc_vc.head(3).index.tolist())
            insights.append((
                "Concentratie",
                f"<strong>{top3_pct}%</strong> van alle storingen komt van slechts 3 locaties: "
                f"<strong>{top3_names}</strong>. Gericht preventief onderhoud hier kan "
                f"het totaal aantal storingen significant reduceren."
            ))

    # Inzicht 4: installatie aanbeveling
    if not inst_counts.empty and len(inst_counts) >= 2:
        top_inst_name = inst_counts.index[0]
        top_inst_count = inst_counts.values[0]
        total_inst = inst_counts.sum()
        inst_pct = round(top_inst_count / total_inst * 100)
        if inst_pct >= 25:
            insights.append((
                "Dominante storingscategorie",
                f"<strong>{top_inst_name}</strong> is verantwoordelijk voor <strong>{inst_pct}%</strong> "
                f"van alle storingen ({top_inst_count} van {total_inst}). "
                f"Focus verbetertrajecten op dit installatietype voor het grootste effect."
            ))

    if not insights:
        insights.append((
            "Analyse",
            "De dataset is relatief klein of gelijkmatig verdeeld. "
            "Laad meer werkbonnen voor diepere patroonherkenning."
        ))

    # Render inzichten in kaarten
    cols = st.columns(min(len(insights), 3))
    colors = [NAVY, NAVY_LIGHT, ACCENT, '#9896D6']
    for i, (title, text) in enumerate(insights):
        with cols[i % len(cols)]:
            c = colors[i % len(colors)]
            st.markdown(
                f'<div style="background:#F0F0FB; border-left:4px solid {c}; '
                f'padding:16px; border-radius:6px; margin-bottom:12px;">'
                f'<strong>{title}</strong><br>{text}</div>',
                unsafe_allow_html=True
            )


# ============================================================================
# STREAMLIT APP — MAIN
# ============================================================================

st.title("Zenith Werkbon Rapportage v2.1")
st.markdown("**Werkbonnen export met SLA KPIs + AI-gedreven analyses**")

# Sidebar filters (globaal — buiten tabs)
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


# ============================================================================
# TABS
# ============================================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Storingslijst Export",
    "🤖 AI Notitie-analyse",
    "📋 Contract Check",
    "🔍 Storingspatronen",
])


# ============================================================================
# TAB 1: STORINGSLIJST EXPORT (bestaande functionaliteit)
# ============================================================================

with tab1:

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
            # Kolomvolgorde matcht Zenith Storingslijst (24 kolommen)
            # ====================================================================

            result_df = pd.DataFrame()

            # --- STORINGSLIJST KOLOMMEN (1-24, exact matching Zenith) ---

            # 1. Werkbonnummer
            result_df['Werkbonnummer'] = df['Werkboncode']

            # 2. Gerelateerde werkbon
            result_df['Gerelateerde werkbon'] = df['ParentWerkbonDocumentKey'].fillna('')

            # 3-4. Datum/tijd aanmaak
            result_df['Datum aanmaak'] = pd.to_datetime(df['MeldDatum']).dt.date
            result_df['Tijd aanmaak'] = pd.to_datetime(df['MeldTijd']).dt.time

            # 5. Locatie naam (extract na ' - ')
            result_df['Locatie naam'] = df['Klant'].apply(
                lambda x: x.split(' - ', 1)[1].strip() if pd.notna(x) and ' - ' in x else x
            )

            # 6. Storing omschrijving (uit BLOB notities)
            result_df['Storing omschrijving'] = df['notitie'].apply(extract_storing_omschrijving)

            # 7. Locatie soort (heuristic, bewerkbaar in UI)
            result_df['Locatie soort'] = result_df['Locatie naam'].apply(guess_location_type)

            # 8. Installatie soort
            result_df['Installatie soort'] = df['Installatiesoort'].apply(map_installatie_soort)

            # 9. Onderaannemer (Ja/Nee)
            result_df['Onderaannemer'] = df['Betreft onderaannemer']

            # 10. Welke onder aannemer?
            def fill_onderaannemer(onderaannemer, betreft_onderaannemer):
                if pd.isna(onderaannemer) or onderaannemer == '' or '000000 - Zenith' in str(onderaannemer):
                    if pd.notna(betreft_onderaannemer) and str(betreft_onderaannemer).lower() == 'nee':
                        return 'Niet van toepassing'
                    return ''
                return onderaannemer

            result_df['Welke onder aannemer?'] = df.apply(
                lambda row: fill_onderaannemer(row['Onderaannemer'], row['Betreft onderaannemer']), axis=1
            )

            # 11. Categorie Melding (leeg, handmatig A-E)
            result_df['Categorie Melding'] = ''

            # 12. Prio volgens SLA / input CB
            result_df['Prio volgens SLA / input CB'] = df['Prioriteit'].apply(map_priority)

            # 13-14. Reactie datum/tijd
            result_df['Reactie datum'] = pd.to_datetime(df['reactie_datetime']).dt.date
            result_df['Reactie tijd'] = pd.to_datetime(df['reactie_datetime']).dt.time

            # 15. Contact CB (best-effort uit BLOB notities)
            result_df['Contact CB'] = df['notitie'].apply(extract_contact_cb)

            # 16-17. Tijdelijke oplossing (leeg, handmatig/toekomst)
            result_df['Tijdelijke oplossing datum (indien van toepassing)'] = ''
            result_df['Tijdelijke oplossing tijd (indien van toepassing)'] = ''

            # 18-19. Datum/tijd oplossing (definitief)
            result_df['Datum oplossing'] = pd.to_datetime(df['datum_oplossing']).dt.date
            result_df['Tijd oplossing'] = pd.to_datetime(df['tijd_oplossing']).dt.time

            # 20. Geannuleerd?
            result_df['Geannuleerd?'] = df['Status'].apply(
                lambda x: 'Ja' if pd.notna(x) and 'Geannuleerd' in str(x) else 'Nee'
            )

            # 21. Toelichting (volledige BLOB notitie)
            result_df['Toelichting'] = df['notitie'].apply(strip_rtf)

            # 22. Ouderdom systeem / Garantie (leeg)
            result_df['Ouderdom systeem / Garantie'] = ''

            # 23. Maand
            result_df['Maand'] = pd.to_datetime(df['MeldDatum']).dt.month

            # 24. Toelichting bij Niet Behaald (wordt gevuld na SLA berekening)
            result_df['Toelichting bij Niet Behaald'] = ''

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
            # BEREKENDE VELDEN (matching Syntess kolommen 39-57)
            # ====================================================================

            # Week
            result_df['Week'] = pd.to_datetime(result_df['Datum aanmaak']).dt.isocalendar().week.values

            # Datetimes combineren
            result_df['aanmaak d+t'] = pd.to_datetime(
                result_df['Datum aanmaak'].astype(str) + ' ' + result_df['Tijd aanmaak'].astype(str),
                errors='coerce'
            )
            result_df['Response d+t'] = pd.to_datetime(
                result_df['Reactie datum'].astype(str) + ' ' + result_df['Reactie tijd'].astype(str),
                errors='coerce'
            )
            result_df['Restore quickfix'] = ''
            result_df['Restore definitief'] = pd.to_datetime(
                result_df['Datum oplossing'].astype(str) + ' ' + result_df['Tijd oplossing'].astype(str),
                errors='coerce'
            )

            # Tijdsverschillen
            result_df['Response tijd'] = result_df['Response d+t'] - result_df['aanmaak d+t']
            result_df['Restore tijd'] = result_df['Restore definitief'] - result_df['aanmaak d+t']
            result_df['Def fix tijd'] = ''

            # NBD check
            result_df['Controle NBD'] = result_df.apply(
                lambda row: check_nbd(row['aanmaak d+t'], row['Restore definitief']), axis=1
            )

            # Prio numeriek
            prio_map = {'Urgent': 1, 'Medium': 2, 'Low': 3}
            result_df['Prio'] = result_df['Prio volgens SLA / input CB'].map(prio_map)

            # Uren (ceiling)
            result_df['responsetijd uren'] = result_df['Response tijd'].apply(
                lambda x: np.ceil(x.total_seconds() / 3600) if pd.notna(x) else None
            )
            result_df['restoretijd uren'] = result_df['Restore tijd'].apply(
                lambda x: np.ceil(x.total_seconds() / 3600) if pd.notna(x) else None
            )
            result_df['Restore def uren'] = ''

            # KPI lookup (locatie-afhankelijk)
            result_df['KPI response'] = result_df.apply(
                lambda row: get_kpi(row['Prio volgens SLA / input CB'], row['Locatie soort'])['response'], axis=1
            )
            result_df['KPI restore'] = result_df.apply(
                lambda row: get_kpi(row['Prio volgens SLA / input CB'], row['Locatie soort'])['restore'], axis=1
            )

            # SLA check (ondersteunt uren, NBD en BE)
            result_df['SLA response'] = result_df.apply(
                lambda row: check_sla(row['responsetijd uren'], row['Response d+t'], row['aanmaak d+t'], row['KPI response']),
                axis=1
            )
            result_df['SLA restore'] = result_df.apply(
                lambda row: check_sla(row['restoretijd uren'], row['Restore definitief'], row['aanmaak d+t'], row['KPI restore']),
                axis=1
            )

            # Toelichting bij Niet Behaald - vullen na SLA berekening
            result_df['Toelichting bij Niet Behaald'] = result_df.apply(
                lambda row: '-' if row['SLA response'] == 'Behaald' and row['SLA restore'] == 'Behaald' else '',
                axis=1
            )

            # Update session state met berekende velden
            st.session_state['result_df'] = result_df

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
                header_format = workbook.add_format({'bg_color': '#D6E4F0', 'bold': True, 'border': 1})
                date_format = workbook.add_format({'num_format': 'dd-mm-yyyy'})
                time_format = workbook.add_format({'num_format': 'hh:mm:ss'})
                datetime_format = workbook.add_format({'num_format': 'dd-mm-yyyy hh:mm:ss'})

                # Lichtblauwe headers
                for col_num, col_name in enumerate(columns):
                    worksheet.write(0, col_num, col_name, header_format)

                # Kolom indexen dynamisch opzoeken
                def col_idx(name):
                    return columns.index(name) if name in columns else -1

                # Rode kolommen (handmatig invullen)
                red_cols = [
                    'Categorie Melding',
                    'Tijdelijke oplossing datum (indien van toepassing)',
                    'Tijdelijke oplossing tijd (indien van toepassing)',
                    'Ouderdom systeem / Garantie',
                    'Toelichting bij Niet Behaald',
                    'Restore quickfix',
                    'Def fix tijd',
                    'Restore def uren',
                ]

                # Gele kolommen (automatisch afgeleid, controleren)
                yellow_cols = ['Locatie soort', 'Contact CB']

                # Datum kolommen
                date_cols = ['Datum aanmaak', 'Reactie datum', 'Datum oplossing']
                time_cols = ['Tijd aanmaak', 'Reactie tijd', 'Tijd oplossing']
                datetime_cols = ['aanmaak d+t', 'Response d+t', 'Restore definitief']

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
                    ('Tijdelijke oplossing datum/tijd', 'ROOD', 'Handmatig: quickfix. Later via Syntess Externe Notitie timestamps.'),
                    ('Ouderdom systeem / Garantie', 'ROOD', 'Voorlopig leeg. Later: datum oplevering uit Syntess.'),
                    ('Toelichting bij Niet Behaald', 'ROOD', 'Handmatig: toelichting als SLA niet behaald. "-" als beide SLAs behaald.'),
                ]
                instructies = pd.DataFrame(instr_data, columns=['Kolom', 'Kleur', 'Toelichting'])

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

            # Preview eerste 10 rijen (storingslijst kolommen)
            st.subheader("Preview (eerste 10 werkbonnen)")
            storingslijst_cols = columns[:24]  # Eerste 24 = storingslijst
            st.dataframe(result_df[storingslijst_cols].head(10))

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


# ============================================================================
# TAB 2: AI NOTITIE-ANALYSE
# ============================================================================

with tab2:
    render_notitie_analyse_tab()


# ============================================================================
# TAB 3: CONTRACT CHECK
# ============================================================================

with tab3:
    render_contract_check_tab()


# ============================================================================
# TAB 4: STORINGSPATRONEN
# ============================================================================

with tab4:
    render_patronen_tab()
