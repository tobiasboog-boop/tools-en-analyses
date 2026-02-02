#!/usr/bin/env python3
"""Classificatie - Publieke versie

Classificeer geselecteerde werkbonnen met AI.
"""
import streamlit as st
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.auth import require_auth, get_secret
from src.services.parquet_data_service import ParquetDataService, WerkbonVerhaalBuilder

st.set_page_config(page_title="Classificatie", layout="wide")

# Wachtwoord check
require_auth()

st.title("Werkbon Classificatie")
st.caption("AI-gedreven beoordeling: binnen of buiten contract?")

# Check for API key (from secrets or env)
api_key = get_secret("ANTHROPIC_API_KEY", "")

# Session state
if "werkbonnen_for_beoordeling" not in st.session_state:
    st.session_state.werkbonnen_for_beoordeling = []
if "classificatie_resultaten" not in st.session_state:
    st.session_state.classificatie_resultaten = {}

# Sidebar
with st.sidebar:
    st.header("Instellingen")

    # API key input (if not in env)
    if not api_key:
        api_key = st.text_input(
            "Anthropic API Key",
            type="password",
            help="Nodig voor AI classificatie"
        )

    st.divider()

    # Confidence threshold
    confidence_threshold = st.slider(
        "Confidence drempel",
        min_value=0.5,
        max_value=0.95,
        value=0.85,
        step=0.05,
        help="Minimale confidence voor definitieve classificatie"
    )

    st.divider()

    # Selection info
    st.subheader("Geselecteerd")
    selected_count = len(st.session_state.werkbonnen_for_beoordeling)
    st.metric("Werkbonnen", selected_count)

    if selected_count == 0:
        st.warning("Selecteer eerst werkbonnen")
        if st.button("← Naar Selectie"):
            st.switch_page("pages/1_Werkbon_Selectie.py")

# Main content
if not st.session_state.werkbonnen_for_beoordeling:
    st.info("Geen werkbonnen geselecteerd. Ga naar **Werkbon Selectie** om werkbonnen te kiezen.")
    st.stop()

if not api_key:
    st.warning("Voer een Anthropic API key in via de sidebar om te classificeren.")
    st.stop()

# Load data service
@st.cache_resource
def get_data_service():
    return ParquetDataService(data_dir="data")

data_service = get_data_service()

# Contract context (simplified - no file loading in demo)
st.subheader("Contract Context")
contract_context = st.text_area(
    "Contract voorwaarden (optioneel)",
    height=150,
    placeholder="Voer hier relevante contractvoorwaarden in die de AI moet meewegen...",
    help="Beschrijf wat wel/niet onder het contract valt"
)

st.divider()

# Classify button
col_btn, col_info = st.columns([1, 3])

with col_btn:
    classify_clicked = st.button("🤖 Start Classificatie", type="primary")

with col_info:
    st.caption(f"Classificeer {len(st.session_state.werkbonnen_for_beoordeling)} werkbonnen")


def classify_werkbon(werkbon_key: int, contract_text: str, api_key: str) -> dict:
    """Classify a single werkbon using Claude API."""
    import anthropic

    # Get werkbon data
    keten = data_service.get_werkbon_keten(
        werkbon_key,
        include_kosten_details=True,
        include_oplossingen=True,
        include_opvolgingen=True
    )

    if not keten:
        return {"error": "Werkbon niet gevonden"}

    # Build verhaal
    builder = WerkbonVerhaalBuilder()
    verhaal = builder.build_verhaal(keten)

    # Build prompt
    system_prompt = """Je bent een expert in het beoordelen van werkbonnen voor een installatiebedrijf.
Je taak is om te bepalen of uitgevoerde werkzaamheden binnen of buiten een onderhoudscontract vallen.

BELANGRIJK:
- Analyseer de werkbon GRONDIG: bekijk type, storing, oorzaak, oplossing, kosten
- Vergelijk met de contractvoorwaarden
- Geef een duidelijk oordeel: JA (binnen contract), NEE (buiten contract), of ONZEKER
- Geef een confidence score (0-100%)
- Leg je redenering uit

Antwoord in het volgende formaat:
OORDEEL: [JA/NEE/ONZEKER]
CONFIDENCE: [0-100]%
REDENERING: [Korte uitleg van je beslissing]
"""

    user_prompt = f"""## Contract voorwaarden:
{contract_text if contract_text else "(Geen specifieke voorwaarden opgegeven)"}

## Werkbon informatie:
{verhaal}

## Vraag:
Valt deze werkbon BINNEN het contract (niet factureren) of BUITEN het contract (wel factureren)?
"""

    # Call Claude API
    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        response_text = response.content[0].text

        # Parse response
        result = {
            "werkbon_key": werkbon_key,
            "response": response_text,
            "oordeel": "ONZEKER",
            "confidence": 0,
            "redenering": ""
        }

        lines = response_text.split("\n")
        for line in lines:
            line_upper = line.upper()
            if "OORDEEL:" in line_upper:
                if "JA" in line_upper:
                    result["oordeel"] = "JA"
                elif "NEE" in line_upper:
                    result["oordeel"] = "NEE"
                else:
                    result["oordeel"] = "ONZEKER"
            elif "CONFIDENCE:" in line_upper:
                # Extract number
                import re
                match = re.search(r'(\d+)', line)
                if match:
                    result["confidence"] = int(match.group(1))
            elif "REDENERING:" in line_upper:
                result["redenering"] = line.split(":", 1)[1].strip() if ":" in line else ""

        return result

    except Exception as e:
        return {"error": str(e), "werkbon_key": werkbon_key}


# Run classification
if classify_clicked:
    progress_bar = st.progress(0)
    status_text = st.empty()

    werkbonnen = st.session_state.werkbonnen_for_beoordeling
    total = len(werkbonnen)

    for i, wb in enumerate(werkbonnen):
        status_text.text(f"Classificeren: {wb['werkbon_code']} ({i+1}/{total})")

        result = classify_werkbon(
            wb["hoofdwerkbon_key"],
            contract_context,
            api_key
        )

        st.session_state.classificatie_resultaten[wb["hoofdwerkbon_key"]] = result

        progress_bar.progress((i + 1) / total)

    status_text.text("Classificatie voltooid!")
    st.balloons()

# Show results
if st.session_state.classificatie_resultaten:
    st.divider()
    st.subheader("Resultaten")

    # Summary
    resultaten = st.session_state.classificatie_resultaten
    ja_count = sum(1 for r in resultaten.values() if r.get("oordeel") == "JA")
    nee_count = sum(1 for r in resultaten.values() if r.get("oordeel") == "NEE")
    onzeker_count = sum(1 for r in resultaten.values() if r.get("oordeel") == "ONZEKER")
    error_count = sum(1 for r in resultaten.values() if "error" in r)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("JA (binnen)", ja_count, help="Niet factureren")
    with col2:
        st.metric("NEE (buiten)", nee_count, help="Wel factureren")
    with col3:
        st.metric("ONZEKER", onzeker_count, help="Handmatige beoordeling nodig")
    with col4:
        st.metric("Errors", error_count)

    st.divider()

    # Detail per werkbon
    for wb in st.session_state.werkbonnen_for_beoordeling:
        key = wb["hoofdwerkbon_key"]
        result = resultaten.get(key, {})

        if "error" in result:
            st.error(f"**{wb['werkbon_code']}**: Error - {result['error']}")
            continue

        oordeel = result.get("oordeel", "?")
        confidence = result.get("confidence", 0)
        redenering = result.get("redenering", "")

        # Color based on oordeel
        if oordeel == "JA":
            color = "🟢"
        elif oordeel == "NEE":
            color = "🔴"
        else:
            color = "🟡"

        # Confidence warning
        conf_warning = " ⚠️" if confidence < confidence_threshold * 100 else ""

        with st.expander(f"{color} {wb['werkbon_code']} - {oordeel} ({confidence}%){conf_warning}"):
            st.markdown(f"**Oordeel:** {oordeel}")
            st.markdown(f"**Confidence:** {confidence}%")
            st.markdown(f"**Redenering:** {redenering}")

            st.divider()

            st.markdown("**Volledige AI response:**")
            st.text(result.get("response", ""))

    # Export button
    st.divider()
    if st.button("📥 Exporteer naar CSV"):
        import pandas as pd
        from io import StringIO

        rows = []
        for wb in st.session_state.werkbonnen_for_beoordeling:
            key = wb["hoofdwerkbon_key"]
            result = resultaten.get(key, {})
            rows.append({
                "werkbon_code": wb["werkbon_code"],
                "hoofdwerkbon_key": key,
                "oordeel": result.get("oordeel", "ERROR"),
                "confidence": result.get("confidence", 0),
                "redenering": result.get("redenering", result.get("error", ""))
            })

        df = pd.DataFrame(rows)
        csv = df.to_csv(index=False)
        st.download_button(
            "Download CSV",
            csv,
            file_name="classificatie_resultaten.csv",
            mime="text/csv"
        )
