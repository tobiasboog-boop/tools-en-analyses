#!/usr/bin/env python3
"""Contract Check - Publieke Demo Versie

Deze versie werkt met lokale Parquet data bestanden (historische werkbonnen).
Geschikt voor demo's en externe deployment naar klanten.
"""
import streamlit as st
from pathlib import Path
import json
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.auth import require_auth

st.set_page_config(
    page_title="Contract Check Demo",
    page_icon="📋",
    layout="wide"
)

# Wachtwoord check
require_auth()


# === LOGO HELPER ===
def get_logo_path():
    """Get logo path for embedding."""
    logo_path = Path(__file__).parent / "assets" / "notifica-logo-kleur.svg"
    if logo_path.exists():
        return str(logo_path)
    return None


# === SIDEBAR ===
with st.sidebar:
    # Logo
    logo_path = get_logo_path()
    if logo_path:
        st.image(logo_path, width=140)
        st.divider()

    # Navigation links
    st.markdown("### Navigatie")
    st.page_link("Home.py", label="🏠 Home", icon=None)
    st.page_link("pages/1_Werkbon_Selectie.py", label="📋 Werkbon Selectie")
    st.page_link("pages/2_Classificatie.py", label="🤖 Classificatie")

    st.divider()

    # Link to Notifica
    st.markdown("### Links")
    st.markdown("[📖 Handleiding](https://notifica.nl/tools/contract-checker)")
    st.markdown("[🌐 notifica.nl](https://notifica.nl)")


# ============================================
# MAIN APP
# ============================================
st.title("Contract Check Demo")
st.caption("AI-gedreven classificatie van werkbonnen - Publieke demo versie")

# Check of data beschikbaar is (use absolute path relative to this script)
data_path = Path(__file__).parent / "data"
if not data_path.exists() or not (data_path / "werkbonnen.parquet").exists():
    st.error("""
    **Data niet gevonden!**

    Deze app verwacht Parquet bestanden in de `data/` map.
    Zorg dat de volgende bestanden aanwezig zijn:
    - data/werkbonnen.parquet
    - data/werkbonparagrafen.parquet
    - data/kosten.parquet
    - data/kostenregels.parquet
    - data/oplossingen.parquet
    - data/opvolgingen.parquet
    """)
    st.stop()

# Laad metadata
metadata_file = data_path / "metadata.json"
if metadata_file.exists():
    with open(metadata_file) as f:
        metadata = json.load(f)
else:
    metadata = {}

# ============================================
# DEMO DATA BANNER
# ============================================
st.markdown("""
<div style="background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%); padding: 15px 20px; border-radius: 8px; border-left: 4px solid #3b82f6; margin-bottom: 20px;">
    <strong style="color: #1e40af;">📊 DEMO VERSIE - Historische Data</strong>
    <p style="color: #1e3a8a; margin: 8px 0 0 0; font-size: 0.9rem;">
        Deze tool werkt met een <strong>historische dataset</strong> van werkbonnen (status: Uitgevoerd + Historisch).
        De data is een snapshot voor demonstratie- en validatiedoeleinden.
    </p>
</div>
""", unsafe_allow_html=True)

st.divider()

# ============================================
# KPI METRICS
# ============================================
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "📋 Hoofdwerkbonnen",
        f"{metadata.get('aantal_hoofdwerkbonnen', '?'):,}",
        help="Aantal werkbon-trajecten in de demo dataset"
    )

with col2:
    st.metric(
        "📄 Werkbonnen",
        f"{metadata.get('aantal_werkbonnen', '?'):,}",
        help="Incl. vervolgbonnen"
    )

with col3:
    st.metric(
        "📑 Paragrafen",
        f"{metadata.get('aantal_paragrafen', '?'):,}",
        help="Werkbonparagrafen met werkzaamheden"
    )

with col4:
    st.metric(
        "💰 Kostenregels",
        f"{metadata.get('aantal_kosten', '?'):,}",
        help="Geregistreerde kosten"
    )

# Debiteuren info
debiteuren = metadata.get("debiteuren", {})
if debiteuren:
    st.caption(f"**Debiteuren:** {' | '.join([f'{code} - {naam}' for code, naam in debiteuren.items()])}")

st.divider()

# ============================================
# WORKFLOW UITLEG
# ============================================
st.markdown("## Hoe werkt het systeem?")

st.markdown("""
Dit systeem helpt om automatisch te bepalen of werkbonkosten **binnen** of **buiten**
een servicecontract vallen. De AI analyseert werkbonnen en vergelijkt ze met contractvoorwaarden.
""")

# Workflow diagram
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("""
    <div style="padding: 1.5rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 0.5rem; color: white; height: 180px;">
        <div style="font-size: 2rem; margin-bottom: 0.5rem;">1</div>
        <div style="font-weight: bold; font-size: 1.1rem; margin-bottom: 0.5rem;">Classificatie Context</div>
        <div style="font-size: 0.85rem; opacity: 0.9;">
            Definieer wat de AI moet beoordelen en welke contractregels gelden.
        </div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div style="padding: 1.5rem; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); border-radius: 0.5rem; color: white; height: 180px;">
        <div style="font-size: 2rem; margin-bottom: 0.5rem;">2</div>
        <div style="font-weight: bold; font-size: 1.1rem; margin-bottom: 0.5rem;">Werkbon Selectie</div>
        <div style="font-size: 0.85rem; opacity: 0.9;">
            Selecteer werkbonnen uit de dataset. Filter op debiteur, datum, type.
        </div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div style="padding: 1.5rem; background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); border-radius: 0.5rem; color: white; height: 180px;">
        <div style="font-size: 2rem; margin-bottom: 0.5rem;">3</div>
        <div style="font-weight: bold; font-size: 1.1rem; margin-bottom: 0.5rem;">AI Classificatie</div>
        <div style="font-size: 0.85rem; opacity: 0.9;">
            Claude AI beoordeelt elke werkbon: JA (binnen), NEE (buiten), of TWIJFEL.
        </div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown("""
    <div style="padding: 1.5rem; background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); border-radius: 0.5rem; color: white; height: 180px;">
        <div style="font-size: 2rem; margin-bottom: 0.5rem;">4</div>
        <div style="font-weight: bold; font-size: 1.1rem; margin-bottom: 0.5rem;">Resultaten</div>
        <div style="font-size: 0.85rem; opacity: 0.9;">
            Bekijk resultaten met confidence scores, exporteer naar CSV.
        </div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# ============================================
# NAVIGATIE
# ============================================
st.markdown("## Aan de slag")

col_a, col_b = st.columns(2)

with col_a:
    st.markdown("""
    <div style="padding: 2rem; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); border-radius: 1rem; color: white;">
        <div style="font-size: 1.5rem; font-weight: bold; margin-bottom: 0.5rem;">Werkbon Selectie</div>
        <div style="font-size: 0.95rem; opacity: 0.9; margin-bottom: 1rem;">
            Bekijk werkbonnen uit de demo dataset.<br>
            Filter op debiteur en selecteer voor classificatie.
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("▶️ Naar Werkbon Selectie", key="btn_selectie", type="primary"):
        st.switch_page("pages/1_Werkbon_Selectie.py")

with col_b:
    st.markdown("""
    <div style="padding: 2rem; background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); border-radius: 1rem; color: white;">
        <div style="font-size: 1.5rem; font-weight: bold; margin-bottom: 0.5rem;">Quick Classificatie</div>
        <div style="font-size: 0.95rem; opacity: 0.9; margin-bottom: 1rem;">
            Snelle classificatie van geselecteerde werkbonnen.<br>
            Laat de AI bepalen: binnen of buiten contract?
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("▶️ Naar Classificatie", key="btn_classificatie", type="primary"):
        st.switch_page("pages/2_Classificatie.py")

st.divider()

# ============================================
# DEMO INFO
# ============================================
with st.expander("ℹ️ Over deze demo"):
    st.markdown(f"""
    ### Contract Check Demo

    Deze demo versie bevat een **vooraf geëxporteerde subset** van werkbonnen
    voor demonstratie- en trainingsdoeleinden.

    **Dataset specificaties:**
    | Eigenschap | Waarde |
    |------------|--------|
    | Export datum | {metadata.get('export_timestamp', 'Onbekend')[:10] if metadata.get('export_timestamp') else 'Onbekend'} |
    | Status filter | {metadata.get('status_filter', 'Uitgevoerd + Historisch')} |
    | Debiteuren | {', '.join(metadata.get('debiteur_codes', ['Onbekend']))} |
    | Aantal hoofdwerkbonnen | {metadata.get('aantal_hoofdwerkbonnen', '?')} |
    | Aantal werkbonnen | {metadata.get('aantal_werkbonnen', '?')} |

    **Verschil met productie:**
    - Demo: Statische dataset, geen live data
    - Demo: Historische werkbonnen (facturatie al bekend)
    - Demo: Beperkt aantal werkbonnen

    **Validatie mogelijkheid:**
    Omdat dit historische werkbonnen zijn, kunnen we de AI classificatie vergelijken
    met de werkelijke facturatiestatus om de nauwkeurigheid (hit rate) te meten.
    """)

# Footer
st.divider()
st.markdown("""
<div style="text-align: center; color: #666;">
    Contract Check Demo | <a href="https://notifica.nl" target="_blank">Notifica</a> | Powered by Claude AI
</div>
""", unsafe_allow_html=True)
