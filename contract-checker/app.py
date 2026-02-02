#!/usr/bin/env python3
"""
Contract Checker - DEMO VERSIE
Publieke versie met Parquet data (geen database connectie).
Conform DWH versie qua layout en functionaliteit.
"""
import json
import streamlit as st
from pathlib import Path
from datetime import date, timedelta
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.auth import require_auth, get_secret
from src.services.parquet_data_service import ParquetDataService, WerkbonVerhaalBuilder

# Fixed batch size (like DWH version)
BATCH_SIZE = 10


# === CONTRACT LOADING ===
@st.cache_resource
def load_contracts():
    """Load all contracts from contracts folder."""
    contracts_dir = Path(__file__).parent / "contracts"
    contracts = {}

    # Load metadata
    meta_path = contracts_dir / "contracts_metadata.json"
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        for c in meta.get("contracts", []):
            contract_file = contracts_dir / c["filename"]
            if contract_file.exists():
                content = contract_file.read_text(encoding="utf-8")
                contracts[c["id"]] = {
                    "id": c["id"],
                    "filename": c["filename"],
                    "content": content,
                    "clients": c.get("clients", [])
                }

    return contracts


def get_contract_for_debiteur(debiteur_code: str, contracts: dict):
    """Get contract for a specific debiteur."""
    # Extract code from "005102 - Trivire" format
    code = debiteur_code.split(" - ")[0].strip() if " - " in debiteur_code else debiteur_code

    for contract in contracts.values():
        if code in contract.get("clients", []):
            return contract
    return None


# === USAGE TRACKING ===
USAGE_FILE = Path(__file__).parent / "data" / "usage_count.json"


def get_usage_count() -> int:
    """Get total number of classifications."""
    try:
        if USAGE_FILE.exists():
            with open(USAGE_FILE, "r") as f:
                data = json.load(f)
                return data.get("classification_count", 0)
    except Exception:
        pass
    return 0


def increment_usage(count: int = 1):
    """Increment the classification counter."""
    try:
        current = get_usage_count()
        with open(USAGE_FILE, "w") as f:
            json.dump({"classification_count": current + count}, f)
    except Exception:
        pass


# === PAGE CONFIG ===
st.set_page_config(
    page_title="Contract Checker - DEMO",
    page_icon="🧪",
    layout="wide"
)

# === LOGO ===
def get_logo_path():
    """Get logo path for embedding."""
    logo_path = Path(__file__).parent / "assets" / "notifica-logo-kleur.svg"
    if logo_path.exists():
        return str(logo_path)
    return None

# === PASSWORD PROTECTION ===
require_auth()

# === DEMO DISCLAIMER ===
st.markdown("""
<div style="background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%); padding: 15px 20px; border-radius: 8px; border-left: 4px solid #3b82f6; margin-bottom: 20px;">
    <strong style="color: #1e40af;">📊 DEMO VERSIE - Historische Data</strong>
    <p style="color: #1e3a8a; margin: 8px 0 0 0; font-size: 0.9rem;">
        Deze tool werkt met een historische dataset voor demonstratie- en validatiedoeleinden.
        Aan de resultaten kunnen geen rechten worden ontleend. Handmatige controle blijft vereist.
    </p>
</div>
""", unsafe_allow_html=True)

# === LOAD DATA SERVICE ===
@st.cache_resource
def get_data_service():
    data_dir = Path(__file__).parent / "data"
    return ParquetDataService(data_dir=str(data_dir))

try:
    data_service = get_data_service()
except Exception as e:
    st.error(f"Kon data niet laden: {e}")
    st.stop()

# Load contracts
contracts = load_contracts()
if not contracts:
    st.error("Geen contracten gevonden in contracts/ folder")
    st.stop()

# Check for API key (from secrets or env)
api_key = get_secret("ANTHROPIC_API_KEY", "")

# Session state initialization
if "werkbonnen_batch" not in st.session_state:
    st.session_state.werkbonnen_batch = None
if "classificatie_resultaten" not in st.session_state:
    st.session_state.classificatie_resultaten = []

# === SIDEBAR ===
with st.sidebar:
    # Logo bovenaan sidebar (zoals DWH versie)
    logo_path = get_logo_path()
    if logo_path:
        st.image(logo_path, width=140)

    st.header("Status")

    # API key check and input
    if api_key:
        st.success("✅ Claude API")
        st.caption("Model: claude-3-haiku-20240307")
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
    st.caption(f"Batch grootte: {BATCH_SIZE} (vast)")

    st.divider()
    st.markdown("[📖 Handleiding](https://notifica.nl/tools/contract-checker)")

    # Usage counter (like DWH "Pilot Gebruik")
    st.divider()
    st.header("Demo Gebruik")
    st.metric("Geclassificeerd", f"{get_usage_count()} werkbonnen")

# === MAIN CONTENT ===

st.title("🧪 Contract Checker - DEMO")
st.caption("Werkbonnen classificeren met AI")
st.markdown("[📖 Handleiding & uitleg](https://notifica.nl/tools/contract-checker)")

# Check API
if not api_key:
    st.warning("⚠️ Voer een Anthropic API key in via de sidebar om te classificeren.")
    st.stop()


# === FILTERS ===
st.header("Filters")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Datumbereik")

    # Get date range from data
    df_wb = data_service.df_werkbonnen
    if "melddatum" in df_wb.columns:
        df_wb["melddatum"] = df_wb["melddatum"].astype(str)
        dates = df_wb["melddatum"].dropna()
        dates = dates[dates.str.match(r'^\d{4}-\d{2}-\d{2}')]
        if len(dates) > 0:
            min_date = dates.min()[:10]
            max_date = dates.max()[:10]
        else:
            min_date = "2024-01-01"
            max_date = "2024-12-31"
    else:
        min_date = "2024-01-01"
        max_date = "2024-12-31"

    try:
        default_end = date.fromisoformat(max_date)
        default_start = default_end - timedelta(days=30)
        min_date_obj = date.fromisoformat(min_date)
        if default_start < min_date_obj:
            default_start = min_date_obj
    except:
        default_end = date.today()
        default_start = default_end - timedelta(days=30)

    date_range = st.date_input(
        "Selecteer periode",
        value=(default_start, default_end),
        key="date_filter"
    )

    if len(date_range) == 2:
        filter_start, filter_end = date_range
    else:
        filter_start, filter_end = default_start, default_end

with col2:
    st.subheader("Debiteur")

    # Get unique debiteuren
    debiteuren = df_wb["debiteur"].dropna().unique()
    debiteur_options = sorted([str(d) for d in debiteuren])

    selected_debiteuren = st.multiselect(
        "Filter op debiteur (leeg = alle)",
        options=debiteur_options,
        key="debiteur_filter"
    )


# Count werkbonnen with filters
def count_werkbonnen(start_date, end_date, debiteur_filter):
    """Count werkbonnen matching filters."""
    df = data_service.df_werkbonnen.copy()

    # Filter op hoofdwerkbonnen
    df = df[df["werkbon_key"] == df["hoofdwerkbon_key"]]

    # Date filter
    if "melddatum" in df.columns:
        df["melddatum_str"] = df["melddatum"].astype(str)
        mask = (df["melddatum_str"] >= str(start_date)) & (df["melddatum_str"] <= str(end_date))
        df = df[mask]

    # Debiteur filter
    if debiteur_filter:
        df = df[df["debiteur"].isin(debiteur_filter)]

    return len(df)


total = count_werkbonnen(filter_start, filter_end, selected_debiteuren if selected_debiteuren else None)
st.metric("Te classificeren werkbonnen", total)

if total == 0:
    st.info("Geen werkbonnen gevonden met de huidige filters. Pas de filters aan.")
    st.stop()

st.divider()


# === CONTRACT INFO ===
# Show which contracts are available
contract_options = {c["id"]: c["filename"] for c in contracts.values()}
st.info(f"📋 Beschikbare contracten: {', '.join(contract_options.values())}")

st.divider()


# === LOAD BATCH ===
st.header(f"Volgende {BATCH_SIZE} werkbonnen")

if st.button("🔄 Laad werkbonnen", type="secondary"):
    st.session_state.werkbonnen_batch = None
    st.session_state.classificatie_resultaten = []
    st.rerun()

# Load batch
if st.session_state.werkbonnen_batch is None:
    with st.spinner("Werkbonnen laden..."):
        # Get filtered werkbonnen
        werkbonnen_list = data_service.get_hoofdwerkbon_list(
            debiteur_codes=[d.split(" - ")[0].strip() for d in selected_debiteuren] if selected_debiteuren else None,
            limit=BATCH_SIZE * 5  # Load more to filter by date
        )

        # Filter by date
        filtered = []
        for wb in werkbonnen_list:
            wb_date = wb.get("aanmaakdatum", "")
            if wb_date:
                try:
                    wb_date_obj = date.fromisoformat(str(wb_date)[:10])
                    if filter_start <= wb_date_obj <= filter_end:
                        filtered.append(wb)
                        if len(filtered) >= BATCH_SIZE:
                            break
                except:
                    pass

        st.session_state.werkbonnen_batch = filtered[:BATCH_SIZE]

werkbonnen = st.session_state.werkbonnen_batch

if not werkbonnen:
    st.info("Geen werkbonnen gevonden met de huidige filters")
    st.stop()

st.success(f"{len(werkbonnen)} werkbonnen geladen")

# Preview
with st.expander(f"Bekijk {len(werkbonnen)} werkbonnen", expanded=True):
    for i, wb in enumerate(werkbonnen):
        st.markdown(f"""
        **{i+1}. {wb.get('debiteur', 'Onbekend')[:40]}**
        - Werkbon: {wb.get('werkbon_code', 'N/A')} | Datum: {wb.get('aanmaakdatum', 'N/A')}
        - Paragrafen: {wb.get('paragraaf_count', 0)}
        """)

st.divider()


# === CLASSIFICATION FUNCTION ===
def classify_werkbon(werkbon_key: int, contract_text: str, api_key: str, threshold_ja: float, threshold_nee: float) -> dict:
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
            model="claude-3-haiku-20240307",
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
if st.button("🚀 Classificeer batch", type="primary", use_container_width=True):
    results = []
    progress = st.progress(0)
    status = st.empty()

    for i, wb in enumerate(werkbonnen):
        debiteur = wb.get("debiteur", "")
        status.text(f"Classificeren {i+1}/{len(werkbonnen)}: {debiteur[:30]}...")

        # Get contract for this werkbon's debiteur
        contract = get_contract_for_debiteur(debiteur, contracts)

        if not contract:
            # No contract found for this debiteur
            results.append({
                "werkbon_key": wb["hoofdwerkbon_key"],
                "werkbon_code": wb.get("werkbon_code", ""),
                "debiteur": debiteur,
                "datum": wb.get("aanmaakdatum", ""),
                "classificatie": "TWIJFEL",
                "basis_classificatie": "GEEN_CONTRACT",
                "confidence": 0.0,
                "toelichting": f"Geen contract gevonden voor debiteur {debiteur}",
                "contract_referentie": "",
                "contract_filename": None
            })
            progress.progress((i + 1) / len(werkbonnen))
            continue

        result = classify_werkbon(
            wb["hoofdwerkbon_key"],
            contract["content"],
            api_key,
            threshold_ja,
            threshold_nee
        )

        # Add werkbon info to result
        result["werkbon_code"] = wb.get("werkbon_code", "")
        result["debiteur"] = debiteur
        result["datum"] = wb.get("aanmaakdatum", "")
        result["contract_filename"] = contract["filename"]
        results.append(result)

        progress.progress((i + 1) / len(werkbonnen))

    status.empty()
    progress.empty()

    st.session_state.classificatie_resultaten = results
    st.session_state.werkbonnen_batch = None  # Clear for next batch

    # Increment usage counter
    increment_usage(len(results))

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

    col1, col2, col3 = st.columns(3)

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
            <strong>{icon} {result.get('debiteur', '')[:40]}</strong>
            <span style="margin-left: 1rem; padding: 0.2rem 0.5rem; background: white; border-radius: 0.25rem;">
                {classificatie}
            </span>
            <span style="margin-left: 0.5rem; color: #666; font-size: 0.9rem;">
                ({confidence:.0%}){kosten_info}{keten_info}
            </span>
        </div>
        """, unsafe_allow_html=True)

        with st.expander(f"Details - {result.get('debiteur', 'Werkbon')[:30]}"):
            tab1, tab2 = st.tabs(["📋 Classificatie", "📄 Volledige Werkbon Keten"])

            with tab1:
                st.markdown(f"**Toelichting:** {result.get('toelichting', 'N/A')}")
                st.markdown(f"**Contract:** {result.get('contract_filename', 'N/A')}")
                st.markdown(f"**Contract referentie:** {result.get('contract_referentie', 'N/A')}")
                st.markdown(f"**Werkbon:** {result.get('werkbon_code', 'N/A')}")
                st.markdown(f"**Datum:** {result.get('datum', 'N/A')}")

                if result.get("basis_classificatie"):
                    st.caption(f"Basis classificatie: {result['basis_classificatie']} (voor threshold)")

            with tab2:
                if result.get("verhaal"):
                    st.text_area(
                        "Werkbon Keten (zoals verzonden naar Claude)",
                        result["verhaal"],
                        height=400,
                        key=f"verhaal_{result.get('werkbon_key', id(result))}"
                    )
                else:
                    st.info("Geen werkbon keten beschikbaar")

    # Export
    st.divider()
    import pandas as pd

    df = pd.DataFrame([{
        "Werkbon": r.get("werkbon_code", ""),
        "Debiteur": r.get("debiteur", ""),
        "Datum": r.get("datum", ""),
        "Contract": r.get("contract_filename", ""),
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

    # Next batch button
    st.divider()
    if st.button("➡️ Volgende batch", type="primary", use_container_width=True):
        st.session_state.classificatie_resultaten = []
        st.session_state.werkbonnen_batch = None
        st.rerun()
