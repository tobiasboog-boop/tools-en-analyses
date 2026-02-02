#!/usr/bin/env python3
"""Classificatie - Publieke versie

Classificeer geselecteerde werkbonnen met AI.
Inclusief drempelwaardes voor JA/NEE/TWIJFEL classificatie.
"""
import json
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


# === LOGO HELPER ===
def get_logo_path():
    """Get logo path for embedding."""
    logo_path = Path(__file__).parent.parent / "assets" / "notifica-logo-kleur.svg"
    if logo_path.exists():
        return str(logo_path)
    return None


# Check for API key (from secrets or env)
api_key = get_secret("ANTHROPIC_API_KEY", "")

# Session state
if "werkbonnen_for_beoordeling" not in st.session_state:
    st.session_state.werkbonnen_for_beoordeling = []
if "classificatie_resultaten" not in st.session_state:
    st.session_state.classificatie_resultaten = []


# === LOGO BOVEN NAVIGATIE ===
logo_path = get_logo_path()
if logo_path:
    st.logo(logo_path, size="large")

# === SIDEBAR ===
with st.sidebar:
    st.header("Status")

    # API key check and input
    if api_key:
        st.success("✅ Claude API")
        st.caption("Model: claude-sonnet-4-20250514")
    else:
        st.error("❌ Geen API key")
        api_key = st.text_input(
            "Anthropic API Key",
            type="password",
            help="Nodig voor AI classificatie"
        )
        if api_key:
            st.session_state.manual_api_key = api_key

    # Use manual API key if provided
    if "manual_api_key" in st.session_state and st.session_state.manual_api_key:
        api_key = st.session_state.manual_api_key

    st.divider()

    # Drempelwaardes
    st.header("Drempelwaardes")

    threshold_ja = st.slider("JA drempel", 0.5, 1.0, 0.85, 0.05)
    threshold_nee = st.slider("NEE drempel", 0.5, 1.0, 0.85, 0.05)

    st.info(f"""
    - JA + ≥{threshold_ja:.0%} → **JA**
    - NEE + ≥{threshold_nee:.0%} → **NEE**
    - Anders → **TWIJFEL**
    """)

    st.divider()

    # Selection info
    st.header("Geselecteerd")
    selected_count = len(st.session_state.werkbonnen_for_beoordeling)
    st.metric("Werkbonnen", selected_count)

    if selected_count == 0:
        st.warning("Selecteer eerst werkbonnen")
        if st.button("← Naar Selectie"):
            st.switch_page("pages/1_Werkbon_Selectie.py")

    st.divider()

    # Links
    st.markdown("### Links")
    st.markdown("[📖 Handleiding](https://notifica.nl/tools/contract-checker)")
    st.markdown("[🌐 notifica.nl](https://notifica.nl)")


# === MAIN CONTENT ===
st.title("Werkbon Classificatie")
st.caption("AI-gedreven beoordeling: binnen of buiten contract?")

if not st.session_state.werkbonnen_for_beoordeling:
    st.info("Geen werkbonnen geselecteerd. Ga naar **Werkbon Selectie** om werkbonnen te kiezen.")
    st.stop()

if not api_key:
    st.warning("Voer een Anthropic API key in via de sidebar om te classificeren.")
    st.stop()


# Load data service
@st.cache_resource
def get_data_service():
    data_dir = Path(__file__).parent.parent / "data"
    return ParquetDataService(data_dir=str(data_dir))

data_service = get_data_service()


# === CONTRACT CONTEXT ===
st.header("Contract voorwaarden")
contract_context = st.text_area(
    "Plak hier de relevante contractvoorwaarden",
    height=200,
    placeholder="Voer hier de contracttekst in die de AI moet gebruiken voor classificatie...",
    help="De AI vergelijkt elke werkbon met deze contractvoorwaarden"
)

if not contract_context:
    st.warning("⚠️ Voer contractvoorwaarden in om te kunnen classificeren")

st.divider()


# === WERKBONNEN PREVIEW ===
st.header(f"Te classificeren: {len(st.session_state.werkbonnen_for_beoordeling)} werkbonnen")

with st.expander("Bekijk geselecteerde werkbonnen", expanded=False):
    for i, wb in enumerate(st.session_state.werkbonnen_for_beoordeling[:20]):
        st.markdown(f"""
        **{i+1}. {wb.get('werkbon_code', 'N/A')}** - {wb.get('debiteur', 'Onbekend')}
        - Klant: {wb.get('klant', 'N/A')}
        """)
    if len(st.session_state.werkbonnen_for_beoordeling) > 20:
        st.caption(f"... en {len(st.session_state.werkbonnen_for_beoordeling) - 20} meer")


# === CLASSIFICATION FUNCTION ===
def classify_werkbon(werkbon_key: int, contract_text: str, api_key: str, threshold_ja: float, threshold_nee: float) -> dict:
    """Classify a single werkbon using Claude API with threshold-based final classification."""
    import anthropic

    # Get werkbon data
    keten = data_service.get_werkbon_keten(
        werkbon_key,
        include_kosten_details=True,
        include_oplossingen=True,
        include_opvolgingen=True
    )

    if not keten:
        return {"error": "Werkbon niet gevonden", "werkbon_key": werkbon_key}

    # Build verhaal
    builder = WerkbonVerhaalBuilder()
    verhaal = builder.build_verhaal(keten)

    # System prompt
    system_prompt = """Je bent een expert in het analyseren van servicecontracten voor verwarmingssystemen.

Je taak is om te bepalen of een werkbon binnen of buiten een servicecontract valt.

Analyseer het werkbon verhaal en vergelijk met de contractvoorwaarden. Let op:
- Type werkzaamheden (onderhoud, reparatie, storing, modificatie)
- Gebruikte materialen en onderdelen
- Arbeidsuren en kostenposten
- Specifieke uitsluitingen in het contract
- Storingscodes en oorzaken

Geef je antwoord ALLEEN in het volgende JSON formaat:
{
    "classificatie": "JA" of "NEE",
    "confidence": 0.0-1.0,
    "contract_referentie": "Verwijzing naar relevant contract artikel",
    "toelichting": "Korte uitleg van je redenering"
}

Classificatie:
- JA: Werkzaamheden vallen volledig binnen het contract (niet factureren aan klant)
- NEE: Werkzaamheden vallen buiten het contract (wel factureren aan klant)

confidence: Je zekerheid over de classificatie (0.0 = zeer onzeker, 1.0 = zeer zeker)

BELANGRIJK: Geef ALTIJD een classificatie (JA of NEE), ook als je onzeker bent.
De confidence score geeft aan hoe zeker je bent."""

    # Truncate contract if too long
    contract_truncated = contract_text[:15000] if len(contract_text) > 15000 else contract_text

    user_message = f"""### CONTRACT ###
{contract_truncated}

### WERKBON VERHAAL ###
{verhaal}

Classificeer deze werkbon. Geef je antwoord in JSON formaat."""

    # Call Claude API
    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )

        response_text = response.content[0].text

        # Parse JSON response
        try:
            text = response_text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            result = json.loads(text.strip())

            confidence = float(result.get("confidence", 0.5))
            base_classificatie = result.get("classificatie", "NEE").upper()

            # Apply thresholds
            if base_classificatie == "JA":
                final = "JA" if confidence >= threshold_ja else "TWIJFEL"
            else:
                final = "NEE" if confidence >= threshold_nee else "TWIJFEL"

            return {
                "werkbon_key": werkbon_key,
                "classificatie": final,
                "basis_classificatie": base_classificatie,
                "confidence": confidence,
                "contract_referentie": result.get("contract_referentie", ""),
                "toelichting": result.get("toelichting", ""),
                "verhaal": verhaal,
                "totaal_kosten": keten.totaal_kosten,
                "aantal_werkbonnen": keten.aantal_werkbonnen,
                "raw_response": response_text
            }

        except (json.JSONDecodeError, KeyError) as e:
            return {
                "werkbon_key": werkbon_key,
                "classificatie": "TWIJFEL",
                "basis_classificatie": "PARSE_ERROR",
                "confidence": 0.0,
                "contract_referentie": "",
                "toelichting": f"Kon response niet parsen: {str(e)}",
                "verhaal": verhaal,
                "totaal_kosten": keten.totaal_kosten if keten else 0,
                "raw_response": response_text
            }

    except Exception as e:
        return {
            "werkbon_key": werkbon_key,
            "error": str(e),
            "classificatie": "ERROR",
            "confidence": 0.0,
            "toelichting": f"API fout: {str(e)}"
        }


# === CLASSIFY BUTTON ===
if contract_context and st.button("🚀 Start Classificatie", type="primary", use_container_width=True):
    results = []
    progress = st.progress(0)
    status = st.empty()

    werkbonnen = st.session_state.werkbonnen_for_beoordeling

    for i, wb in enumerate(werkbonnen):
        status.text(f"Classificeren {i+1}/{len(werkbonnen)}: {wb.get('werkbon_code', '')}...")

        result = classify_werkbon(
            wb["hoofdwerkbon_key"],
            contract_context,
            api_key,
            threshold_ja,
            threshold_nee
        )

        # Add werkbon info to result
        result["werkbon_code"] = wb.get("werkbon_code", "")
        result["debiteur"] = wb.get("debiteur", "")
        result["klant"] = wb.get("klant", "")
        results.append(result)

        progress.progress((i + 1) / len(werkbonnen))

    status.empty()
    progress.empty()

    st.session_state.classificatie_resultaten = results
    st.success(f"✅ {len(results)} werkbonnen geclassificeerd!")


# === RESULTS ===
if st.session_state.classificatie_resultaten:
    results = st.session_state.classificatie_resultaten

    st.divider()
    st.header("Resultaten")

    # Summary
    ja = sum(1 for r in results if r.get("classificatie") == "JA")
    nee = sum(1 for r in results if r.get("classificatie") == "NEE")
    twijfel = sum(1 for r in results if r.get("classificatie") == "TWIJFEL")
    errors = sum(1 for r in results if r.get("classificatie") == "ERROR" or "error" in r)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div style="padding: 1.5rem; background: #dcfce7; border-radius: 0.5rem; text-align: center; border: 2px solid #22c55e;">
            <div style="font-size: 2.5rem; font-weight: bold; color: #166534;">{ja}</div>
            <div style="color: #166534;">✅ Binnen contract</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="padding: 1.5rem; background: #fee2e2; border-radius: 0.5rem; text-align: center; border: 2px solid #ef4444;">
            <div style="font-size: 2.5rem; font-weight: bold; color: #991b1b;">{nee}</div>
            <div style="color: #991b1b;">❌ Te factureren</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div style="padding: 1.5rem; background: #fed7aa; border-radius: 0.5rem; text-align: center; border: 2px solid #f97316;">
            <div style="font-size: 2.5rem; font-weight: bold; color: #9a3412;">{twijfel}</div>
            <div style="color: #9a3412;">❓ Handmatig checken</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        if errors > 0:
            st.markdown(f"""
            <div style="padding: 1.5rem; background: #f3f4f6; border-radius: 0.5rem; text-align: center; border: 2px solid #9ca3af;">
                <div style="font-size: 2.5rem; font-weight: bold; color: #4b5563;">{errors}</div>
                <div style="color: #4b5563;">⚠️ Errors</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="padding: 1.5rem; background: #f3f4f6; border-radius: 0.5rem; text-align: center; border: 2px solid #9ca3af;">
                <div style="font-size: 2.5rem; font-weight: bold; color: #4b5563;">{len(results)}</div>
                <div style="color: #4b5563;">📊 Totaal</div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # Detail per result
    for result in results:
        classificatie = result.get("classificatie", "ERROR")

        if classificatie == "JA":
            color, border, icon = "#dcfce7", "#22c55e", "✅"
        elif classificatie == "NEE":
            color, border, icon = "#fee2e2", "#ef4444", "❌"
        elif classificatie == "TWIJFEL":
            color, border, icon = "#fed7aa", "#f97316", "❓"
        else:
            color, border, icon = "#f3f4f6", "#9ca3af", "⚠️"

        confidence = result.get("confidence", 0)
        kosten_info = f" | €{result.get('totaal_kosten', 0):,.2f}" if result.get('totaal_kosten') else ""
        keten_info = f" | {result.get('aantal_werkbonnen', 1)} bon(nen)" if result.get('aantal_werkbonnen', 1) > 1 else ""

        st.markdown(f"""
        <div style="padding: 1rem; background: {color}; border-radius: 0.5rem; border-left: 4px solid {border}; margin-bottom: 0.5rem;">
            <strong>{icon} {result.get('werkbon_code', result.get('debiteur', '')[:40])}</strong>
            <span style="margin-left: 1rem; padding: 0.2rem 0.5rem; background: white; border-radius: 0.25rem;">
                {classificatie}
            </span>
            <span style="margin-left: 0.5rem; color: #666; font-size: 0.9rem;">
                ({confidence:.0%}){kosten_info}{keten_info}
            </span>
        </div>
        """, unsafe_allow_html=True)

        with st.expander(f"Details - {result.get('werkbon_code', 'Werkbon')}"):
            tab1, tab2 = st.tabs(["📋 Classificatie", "📄 Volledige Werkbon Keten"])

            with tab1:
                st.markdown(f"**Toelichting:** {result.get('toelichting', 'N/A')}")
                st.markdown(f"**Contract referentie:** {result.get('contract_referentie', 'N/A')}")
                st.markdown(f"**Klant:** {result.get('klant', 'N/A')}")
                st.markdown(f"**Debiteur:** {result.get('debiteur', 'N/A')}")

                if result.get("basis_classificatie"):
                    st.caption(f"Basis classificatie: {result['basis_classificatie']} (voor threshold)")

            with tab2:
                if result.get("verhaal"):
                    st.text_area(
                        "Werkbon Keten (zoals verzonden naar Claude)",
                        result["verhaal"],
                        height=400,
                        key=f"verhaal_{result.get('werkbon_key', i)}"
                    )
                else:
                    st.info("Geen werkbon keten beschikbaar")

    # Export
    st.divider()
    import pandas as pd

    df = pd.DataFrame([{
        "Werkbon": r.get("werkbon_code", ""),
        "Debiteur": r.get("debiteur", ""),
        "Klant": r.get("klant", ""),
        "Classificatie": r.get("classificatie", ""),
        "Basis": r.get("basis_classificatie", ""),
        "Confidence": f"{r.get('confidence', 0):.0%}",
        "Kosten": f"€{r.get('totaal_kosten', 0):,.2f}",
        "Toelichting": r.get("toelichting", ""),
        "Contract Referentie": r.get("contract_referentie", "")
    } for r in results])

    st.download_button(
        "📥 Download resultaten (CSV)",
        df.to_csv(index=False),
        "classificatie_resultaten.csv",
        "text/csv",
        use_container_width=True
    )

    # New classification button
    st.divider()
    col_new, col_clear = st.columns(2)
    with col_new:
        if st.button("🔄 Opnieuw classificeren", use_container_width=True):
            st.session_state.classificatie_resultaten = []
            st.rerun()
    with col_clear:
        if st.button("🗑️ Selectie wissen", use_container_width=True):
            st.session_state.werkbonnen_for_beoordeling = []
            st.session_state.classificatie_resultaten = []
            st.switch_page("pages/1_Werkbon_Selectie.py")
