#!/usr/bin/env python3
"""
Contract Checker V2 - VERBETERDE VERSIE
Focus op werkbon oplossingen voor betere classificatie.

Version: 2026-02-09-v2
VERBETERING: AI analyseert nu expliciet de werkbon oplossingen (vrije tekst van monteur)
voor nauwkeurigere classificaties.

Dit is een aparte versie voor A/B testing met de originele app.py.
"""
import json
import streamlit as st
from pathlib import Path
from datetime import date, timedelta
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.auth import require_auth, get_secret
from src.services.parquet_data_service import ParquetDataService, WerkbonVerhaalBuilder as OriginalVerhaalBuilder

# Fixed batch size (like DWH version)
BATCH_SIZE = 10


def load_individuele_contracten() -> set:
    """Laad lijst met individuele contracten uit bestand."""
    contracts_file = Path(__file__).parent / "data" / "individuele_contracten.txt"
    contracts = set()

    if contracts_file.exists():
        with open(contracts_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    contracts.add(line.lower())

    return contracts


def is_individueel_contract(paragraaf_naam: str, individuele_contracten: set) -> bool:
    """Check of een paragraaf naam matched met een individueel contract."""
    if not paragraaf_naam:
        return False

    paragraaf_lower = paragraaf_naam.lower()

    # Check voor partial match (elk individueel contract in de naam)
    for contract in individuele_contracten:
        if contract in paragraaf_lower:
            return True

    return False


# === VERBETERDE VERHAAL BUILDER ===
class VerbeterdeVerhaalBuilder(OriginalVerhaalBuilder):
    """Verbeterde builder die oplossingen prominenter toont."""

    def build_verhaal(self, keten, chronological: bool = True) -> str:
        """Build verhaal met oplossingen EERST (belangrijker dan kosten)."""
        lines = []

        # Header
        lines.append(f"# Werkbonketen voor {keten.relatie_naam}")
        lines.append(f"Relatiecode: {keten.relatie_code}")
        lines.append("")

        # Summary
        lines.append("## Samenvatting")
        lines.append(f"- Aantal werkbonnen in keten: {keten.aantal_werkbonnen}")
        lines.append(f"- Totaal aantal paragrafen: {keten.aantal_paragrafen}")
        lines.append(f"- Totale kosten: €{keten.totaal_kosten:,.2f}")
        lines.append("")

        # Sort werkbonnen by melddatum
        werkbonnen = sorted(
            keten.werkbonnen,
            key=lambda w: w.melddatum or "",
            reverse=chronological
        )

        # Each werkbon
        for i, wb in enumerate(werkbonnen, 1):
            if wb.is_hoofdwerkbon:
                lines.append(f"## Hoofdwerkbon: {wb.werkbon_nummer}")
            else:
                lines.append(f"## Vervolgbon (niveau {wb.niveau}): {wb.werkbon_nummer}")

            lines.append(f"- **Status: {wb.status}** | Documentstatus: {wb.documentstatus}")
            if wb.administratieve_fase:
                lines.append(f"- Administratieve fase: {wb.administratieve_fase}")

            lines.append(f"- Type: {wb.type}")
            if wb.melddatum:
                melding = wb.melddatum
                if wb.meldtijd:
                    melding += f" {wb.meldtijd}"
                lines.append(f"- Melding: {melding}")
            if wb.afspraakdatum:
                lines.append(f"- Afspraakdatum: {wb.afspraakdatum}")
            if wb.opleverdatum:
                lines.append(f"- Opleverdatum: {wb.opleverdatum}")

            if wb.monteur:
                lines.append(f"- Monteur: {wb.monteur}")
            lines.append(f"- Locatie: {wb.postcode} {wb.plaats}")

            # Paragrafen
            if wb.paragrafen:
                lines.append("### Werkbonparagrafen")
                for p in wb.paragrafen:
                    lines.append(f"\n**{p.naam}** ({p.type})")
                    lines.append(f"- Uitvoeringstatus: {p.uitvoeringstatus}")

                    if p.plandatum:
                        lines.append(f"- Plandatum: {p.plandatum}")
                    if p.uitgevoerd_op:
                        uitvoering = p.uitgevoerd_op
                        if p.tijdstip_uitgevoerd:
                            uitvoering += f" {p.tijdstip_uitgevoerd}"
                        lines.append(f"- Uitgevoerd: {uitvoering}")

                    if p.storing:
                        lines.append(f"- Storingscode: {p.storing}")
                    if p.oorzaak:
                        lines.append(f"- Oorzaakcode: {p.oorzaak}")

                    # ⭐ OPLOSSINGEN EERST - Dit is de belangrijkste info!
                    if p.oplossingen:
                        lines.append("")
                        lines.append("🔍 **WAT HEEFT DE MONTEUR GEDAAN? (Oplossingen):**")
                        oplossingen = sorted(
                            p.oplossingen,
                            key=lambda o: o.aanmaakdatum or "",
                            reverse=chronological
                        )
                        for opl in oplossingen:
                            datum = f"[{opl.aanmaakdatum}] " if opl.aanmaakdatum else ""
                            lines.append(f"- {datum}{opl.oplossing}")
                            if opl.oplossing_uitgebreid:
                                lines.append(f"  Toelichting: {opl.oplossing_uitgebreid}")

                    # Kostenregels daarna
                    if p.kosten:
                        lines.append("")
                        lines.append("**Kostenregels:**")
                        for k in p.kosten:
                            cat = k.categorie.upper() if k.categorie else "ONBEKEND"
                            lines.append(f"- [{cat}] {k.omschrijving}")
                            lines.append(f"  Aantal: {k.aantal} | Verrekenprijs: €{k.verrekenprijs:,.2f} | Kostprijs: €{k.kostprijs:,.2f}")
                            if k.taak:
                                lines.append(f"  Taak: {k.taak}")
                            if k.boekdatum:
                                lines.append(f"  Boekdatum: {k.boekdatum}")

                    # Opvolgingen
                    if p.opvolgingen:
                        lines.append("")
                        lines.append("**Opvolgingen:**")
                        opvolgingen = sorted(
                            p.opvolgingen,
                            key=lambda o: o.aanmaakdatum or "",
                            reverse=chronological
                        )
                        for opv in opvolgingen:
                            datum = f"[{opv.aanmaakdatum}] " if opv.aanmaakdatum else ""
                            status = f"({opv.status})" if opv.status else ""
                            lines.append(f"- {datum}**{opv.opvolgsoort}** {status}")
                            if opv.beschrijving:
                                lines.append(f"  > {opv.beschrijving}")

                lines.append("")

        return "\n".join(lines)


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


# === USAGE TRACKING (Parquet persistent storage) ===
import pandas as pd

def get_history_path():
    """Get path to classification history Parquet file."""
    return Path(__file__).parent / "data" / "classification_history_v2.parquet"


def get_processed_keys_path():
    """Get path to processed werkbon keys file."""
    return Path(__file__).parent / "data" / "processed_werkbon_keys_v2.parquet"


def get_usage_count() -> int:
    """Get total number of classifications from Parquet file."""
    history_path = get_history_path()
    if history_path.exists():
        try:
            df = pd.read_parquet(history_path)
            return len(df)
        except Exception:
            return 0
    return 0


def load_history() -> list:
    """Load classification history from Parquet file."""
    history_path = get_history_path()
    if history_path.exists():
        try:
            df = pd.read_parquet(history_path)
            return df.to_dict('records')
        except Exception:
            return []
    return []


def save_to_history(results: list):
    """Save classification results to Parquet file (persistent storage)."""
    from datetime import datetime

    history_path = get_history_path()

    # Load existing history
    existing_records = []
    if history_path.exists():
        try:
            df_existing = pd.read_parquet(history_path)
            existing_records = df_existing.to_dict('records')
        except Exception:
            pass

    # Add new records
    timestamp = datetime.now().isoformat()
    for r in results:
        history_entry = {
            "timestamp": timestamp,
            "werkbon_key": r.get("werkbon_key"),
            "werkbon_code": r.get("werkbon_code", ""),
            "debiteur": r.get("debiteur", ""),
            "datum": str(r.get("datum", "")),
            "contract_filename": r.get("contract_filename", ""),
            "classificatie": r.get("classificatie", ""),
            "basis_classificatie": r.get("basis_classificatie", ""),
            "confidence": r.get("confidence", 0) * 100,
            "toelichting": r.get("toelichting", ""),
            "contract_referentie": r.get("contract_referentie", ""),
            "totaal_kosten": r.get("totaal_kosten", 0),
        }
        existing_records.append(history_entry)

    # Save to Parquet
    df = pd.DataFrame(existing_records)
    history_path.parent.mkdir(exist_ok=True)
    df.to_parquet(history_path, index=False)


def load_processed_werkbon_keys() -> set:
    """Load set of already processed werkbon keys from Parquet."""
    keys_path = get_processed_keys_path()
    if keys_path.exists():
        try:
            df = pd.read_parquet(keys_path)
            return set(df["werkbon_key"].tolist())
        except Exception:
            return set()
    return set()


def save_processed_werkbon_keys(keys: set):
    """Save processed werkbon keys to Parquet file."""
    keys_path = get_processed_keys_path()
    df = pd.DataFrame({"werkbon_key": list(keys)})
    keys_path.parent.mkdir(exist_ok=True)
    df.to_parquet(keys_path, index=False)


def clear_all_history():
    """Clear all history and processed keys (for reset functionality)."""
    history_path = get_history_path()
    keys_path = get_processed_keys_path()
    if history_path.exists():
        history_path.unlink()
    if keys_path.exists():
        keys_path.unlink()


# === PAGE CONFIG ===
st.set_page_config(
    page_title="Contract Checker V2 - DEMO",
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

# === V2 INFO BANNER ===
st.markdown("""
<div style="background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%); padding: 15px 20px; border-radius: 8px; border-left: 4px solid #22c55e; margin-bottom: 20px;">
    <strong style="color: #15803d;">✨ VERSIE 2 - Verbeterde AI Analyse</strong>
    <p style="color: #166534; margin: 8px 0 0 0; font-size: 0.9rem;">
        Deze versie legt meer nadruk op de <strong>werkbon oplossingen</strong> (vrije tekst van de monteur).
        Test deze versie naast de originele om te zien welke nauwkeuriger classificeert.
    </p>
</div>
""", unsafe_allow_html=True)

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

# Check for API key
api_key = get_secret("ANTHROPIC_API_KEY", "")

# Session state initialization
if "werkbonnen_batch" not in st.session_state:
    st.session_state.werkbonnen_batch = None
if "classificatie_resultaten" not in st.session_state:
    st.session_state.classificatie_resultaten = []
if "processed_werkbon_keys" not in st.session_state:
    st.session_state.processed_werkbon_keys = load_processed_werkbon_keys()

# === SIDEBAR ===
with st.sidebar:
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

    # Usage counter
    st.divider()
    st.header("Demo Gebruik (V2)")
    st.metric("Geclassificeerd", f"{get_usage_count()} werkbonnen")
    st.caption("✅ Persistente opslag - blijft bewaard")

# === MAIN CONTENT ===

st.title("🧪 Contract Checker V2 - DEMO")
st.caption("Werkbonnen classificeren met AI | v2026-02-09-v2 (Verbeterd)")
st.markdown("[📖 Handleiding & uitleg](https://notifica.nl/tools/contract-checker)")

# === TABS ===
tab_classify, tab_history, tab_vergelijk = st.tabs(["🚀 Classificeren", "📜 Geschiedenis", "⚖️ V1 vs V2"])

# === COMPARISON TAB ===
with tab_vergelijk:
    st.header("Verschil tussen V1 en V2")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🔵 V1 - Origineel")
        st.markdown("""
        **Hoe werkt het:**
        - AI krijgt werkbongegevens in standaardvolgorde
        - Oplossingen staan onderaan het verhaal
        - Geen speciale nadruk op wat de monteur heeft gedaan

        **Prompt focus:**
        - Type werkzaamheden
        - Materialen en onderdelen
        - Arbeidsuren en kosten
        - Contractvoorwaarden
        """)

    with col2:
        st.subheader("🟢 V2 - Verbeterd")
        st.markdown("""
        **Hoe werkt het:**
        - AI krijgt oplossingen **EERST** te zien (prominenter)
        - Extra emoji marker: 🔍 "WAT HEEFT DE MONTEUR GEDAAN?"
        - Prompt instrueert AI expliciet om oplossingen te analyseren

        **Prompt focus:**
        - ⭐ **EERST: Werkbon oplossingen (vrije tekst monteur)**
        - Type werkzaamheden
        - Materialen en onderdelen
        - Arbeidsuren en kosten
        - Contractvoorwaarden
        """)

    st.divider()

    st.info("""
    **💡 Advies voor A/B testing:**

    1. Selecteer dezelfde periode en debiteur in beide versies
    2. Classificeer bijvoorbeeld 50 werkbonnen in V1 en 50 in V2
    3. Vergelijk de resultaten:
       - Hoeveel JA/NEE/TWIJFEL in beide versies?
       - Controleer handmatig een steekproef: welke is accurater?
       - Let vooral op werkbonnen waar de oplossing cruciaal is

    4. Export beide resultatensets naar CSV voor analyse
    """)

# === HISTORY TAB ===
with tab_history:
    st.header("Classificatie Geschiedenis (V2)")
    st.caption("✅ Persistent opgeslagen in Parquet - blijft bewaard na refresh.")

    history = load_history()

    if not history:
        st.info("Nog geen classificaties uitgevoerd. Start met classificeren in het andere tabblad.")
    else:
        df_hist = pd.DataFrame(history)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Totaal", len(df_hist))
        with col2:
            ja_count = len(df_hist[df_hist["classificatie"] == "JA"])
            st.metric("JA", ja_count)
        with col3:
            nee_count = len(df_hist[df_hist["classificatie"] == "NEE"])
            st.metric("NEE", nee_count)
        with col4:
            twijfel_count = len(df_hist[df_hist["classificatie"] == "TWIJFEL"])
            st.metric("TWIJFEL", twijfel_count)

        st.divider()

        # Filters
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filter_class = st.multiselect(
                "Filter op classificatie",
                options=["JA", "NEE", "TWIJFEL"],
                key="hist_filter_class_v2"
            )
        with col_f2:
            filter_deb = st.multiselect(
                "Filter op debiteur",
                options=sorted(df_hist["debiteur"].unique().tolist()),
                key="hist_filter_deb_v2"
            )

        # Apply filters
        df_display = df_hist.copy()
        if filter_class:
            df_display = df_display[df_display["classificatie"].isin(filter_class)]
        if filter_deb:
            df_display = df_display[df_display["debiteur"].isin(filter_deb)]

        # Display
        st.dataframe(
            df_display[[
                "timestamp", "werkbon_code", "debiteur", "datum",
                "classificatie", "confidence", "toelichting"
            ]].sort_values("timestamp", ascending=False),
            use_container_width=True,
            hide_index=True,
            column_config={
                "timestamp": st.column_config.DatetimeColumn("Tijdstip", format="DD-MM-YYYY HH:mm"),
                "werkbon_code": "Werkbon",
                "debiteur": "Debiteur",
                "datum": "Werkbon Datum",
                "classificatie": "Classificatie",
                "confidence": st.column_config.NumberColumn("Confidence", format="%.0f%%"),
                "toelichting": "Toelichting"
            }
        )

        st.divider()

        # Export
        st.download_button(
            "📥 Download volledige geschiedenis (CSV)",
            df_hist.to_csv(index=False),
            "classificatie_geschiedenis_v2.csv",
            "text/csv",
            use_container_width=True
        )

        # Clear history
        if st.button("🗑️ Wis volledige geschiedenis", type="secondary", key="clear_hist_v2"):
            clear_all_history()
            st.session_state.processed_werkbon_keys = set()
            st.success("Geschiedenis en verwerkte werkbonnen gewist!")
            st.rerun()

# === CLASSIFICATION TAB ===
with tab_classify:
    if not api_key:
        st.warning("⚠️ Voer een Anthropic API key in via de sidebar om te classificeren.")
        st.stop()

    # === FILTERS ===
    st.header("Filters")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Melddatum")

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
            key="date_filter_v2"
        )

        if len(date_range) == 2:
            filter_start, filter_end = date_range
        else:
            filter_start, filter_end = default_start, default_end

    with col2:
        st.subheader("Debiteur")

        debiteuren = df_wb["debiteur"].dropna().unique()
        debiteur_options = sorted([str(d) for d in debiteuren])

        selected_debiteuren = st.multiselect(
            "Filter op debiteur (leeg = alle)",
            options=debiteur_options,
            key="debiteur_filter_v2"
        )

    # === CONTRACT-TYPE FILTER (PHASE 2) ===
    st.divider()
    st.subheader("📋 Contract-type filter")

    contract_type_filter = st.radio(
        "Toon werkbonnen voor:",
        options=["Alle contracten", "Alleen individuele contracten", "Alleen collectieve contracten"],
        index=0,
        horizontal=True,
        help="Individuele contracten staan in 'Contractvoorwaarden diverse WBV.xlsx'. Rest is collectief.",
        key="contract_type_filter_v2"
    )

    # Load individuele contracten lijst
    individuele_contracten = load_individuele_contracten()

    if individuele_contracten:
        st.caption(f"ℹ️ {len(individuele_contracten)} individuele contracten geladen")
    else:
        st.warning("⚠️ Geen individuele contracten lijst gevonden. Alle werkbonnen worden als 'onbekend' behandeld.")

    # Count werkbonnen
    def count_werkbonnen(start_date, end_date, debiteur_filter, contract_filter):
        df = data_service.df_werkbonnen.copy()
        df = df[df["werkbon_key"] == df["hoofdwerkbon_key"]]

        if "melddatum" in df.columns:
            df["melddatum_str"] = df["melddatum"].astype(str)
            mask = (df["melddatum_str"] >= str(start_date)) & (df["melddatum_str"] <= str(end_date))
            df = df[mask]

        if debiteur_filter:
            df = df[df["debiteur"].isin(debiteur_filter)]

        # Contract-type filter
        if contract_filter != "Alle contracten":
            df_para = data_service.df_paragrafen.copy()
            df_para["is_individueel"] = df_para["naam"].apply(
                lambda x: is_individueel_contract(x, individuele_contracten)
            )
            werkbon_type = df_para.groupby("werkbon_key")["is_individueel"].max().to_dict()

            if contract_filter == "Alleen individuele contracten":
                df = df[df["werkbon_key"].apply(lambda x: werkbon_type.get(x, False) == True)]
            elif contract_filter == "Alleen collectieve contracten":
                df = df[df["werkbon_key"].apply(lambda x: werkbon_type.get(x, False) == False)]

        return len(df)

    total = count_werkbonnen(
        filter_start,
        filter_end,
        selected_debiteuren if selected_debiteuren else None,
        contract_type_filter
    )
    st.metric("Te classificeren werkbonnen", total)

    if total == 0:
        st.info("Geen werkbonnen gevonden met de huidige filters. Pas de filters aan.")
        st.stop()

    st.divider()

    # Contract info
    contract_options = {c["id"]: c["filename"] for c in contracts.values()}
    st.info(f"📋 Beschikbare contracten: {', '.join(contract_options.values())}")

    st.divider()

    # === LOAD BATCH ===
    st.header(f"Volgende {BATCH_SIZE} werkbonnen")

    # Check filter changes
    current_filters = {
        "start": str(filter_start),
        "end": str(filter_end),
        "debiteuren": tuple(sorted(selected_debiteuren)) if selected_debiteuren else (),
        "contract_type": contract_type_filter
    }
    if "last_filters" not in st.session_state:
        st.session_state.last_filters = None

    if st.session_state.last_filters != current_filters:
        st.session_state.werkbonnen_batch = None
        st.session_state.classificatie_resultaten = []
        st.session_state.processed_werkbon_keys = set()
        st.session_state.last_filters = current_filters

    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("🔄 Laad nieuwe batch", type="secondary", use_container_width=True, key="load_batch_v2"):
            if st.session_state.werkbonnen_batch:
                for wb in st.session_state.werkbonnen_batch:
                    if wb.get("hoofdwerkbon_key"):
                        st.session_state.processed_werkbon_keys.add(wb["hoofdwerkbon_key"])
                save_processed_werkbon_keys(st.session_state.processed_werkbon_keys)
            st.session_state.werkbonnen_batch = None
            st.session_state.classificatie_resultaten = []
            st.rerun()
    with col_btn2:
        if st.button("🗑️ Reset verwerkte bonnen", type="secondary", use_container_width=True, key="reset_v2"):
            st.session_state.processed_werkbon_keys = set()
            save_processed_werkbon_keys(set())
            st.session_state.werkbonnen_batch = None
            st.session_state.classificatie_resultaten = []
            st.success("Verwerkte werkbonnen gereset!")
            st.rerun()

    if st.session_state.processed_werkbon_keys:
        st.caption(f"📊 {len(st.session_state.processed_werkbon_keys)} werkbonnen al verwerkt (worden overgeslagen)")

    # Load batch
    if st.session_state.werkbonnen_batch is None:
        with st.spinner("Werkbonnen laden..."):
            debiteur_codes = [d.split(" - ")[0].strip() for d in selected_debiteuren] if selected_debiteuren else None

            df = data_service.df_werkbonnen.copy()
            df = df[df["werkbon_key"] == df["hoofdwerkbon_key"]]
            df["melddatum_str"] = df["melddatum"].fillna("").astype(str).str[:10]
            df = df[(df["melddatum_str"] >= str(filter_start)) & (df["melddatum_str"] <= str(filter_end))]

            if debiteur_codes:
                mask = df["debiteur"].apply(lambda x: any(code in str(x) for code in debiteur_codes))
                df = df[mask]

            # Contract-type filter (individueel/collectief)
            if contract_type_filter != "Alle contracten":
                # Join met werkbonparagrafen om contract type te bepalen
                df_para = data_service.df_paragrafen.copy()

                # Bepaal voor elke paragraaf of het individueel of collectief is
                df_para["is_individueel"] = df_para["naam"].apply(
                    lambda x: is_individueel_contract(x, individuele_contracten)
                )

                # Groepeer per werkbon: als minimaal 1 paragraaf individueel is, is werkbon individueel
                werkbon_type = df_para.groupby("werkbon_key")["is_individueel"].max().to_dict()

                # Filter werkbonnen
                if contract_type_filter == "Alleen individuele contracten":
                    df = df[df["werkbon_key"].apply(lambda x: werkbon_type.get(x, False) == True)]
                    st.caption(f"📋 Filter actief: Alleen individuele contracten")
                elif contract_type_filter == "Alleen collectieve contracten":
                    df = df[df["werkbon_key"].apply(lambda x: werkbon_type.get(x, False) == False)]
                    st.caption(f"📋 Filter actief: Alleen collectieve contracten")

            if st.session_state.processed_werkbon_keys:
                df = df[~df["werkbon_key"].isin(st.session_state.processed_werkbon_keys)]

            df = df.sort_values("melddatum", ascending=False).head(BATCH_SIZE)

            werkbonnen_list = []
            for _, row in df.iterrows():
                werkbon_code = str(row["werkbon"]).split(" - ")[0] if row["werkbon"] else ""
                werkbonnen_list.append({
                    "hoofdwerkbon_key": int(row["werkbon_key"]),
                    "werkbon_code": werkbon_code,
                    "debiteur": row["debiteur"],
                    "melddatum": str(row["melddatum"])[:10] if row["melddatum"] else "",
                    "aanmaakdatum": str(row.get("aanmaakdatum", ""))[:10] if row.get("aanmaakdatum") else "",
                })

            st.session_state.werkbonnen_batch = werkbonnen_list

    werkbonnen = st.session_state.werkbonnen_batch

    if not werkbonnen:
        if st.session_state.processed_werkbon_keys:
            st.info(f"Alle {len(st.session_state.processed_werkbon_keys)} werkbonnen zijn al verwerkt. Klik op 'Reset verwerkte bonnen' om opnieuw te beginnen.")
        else:
            st.info("Geen werkbonnen gevonden met de huidige filters")
        st.stop()

    st.success(f"{len(werkbonnen)} werkbonnen geladen")

    # Preview
    with st.expander(f"Bekijk {len(werkbonnen)} werkbonnen", expanded=True):
        for i, wb in enumerate(werkbonnen):
            st.markdown(f"""
            **{i+1}. {wb.get('debiteur', 'Onbekend')[:40]}**
            - Werkbon: {wb.get('werkbon_code', 'N/A')} | Melddatum: {wb.get('melddatum', 'N/A')}
            """)

    st.divider()

    # === CLASSIFY BUTTON ===
    if st.button("🚀 Classificeer batch (V2)", type="primary", use_container_width=True):
        import anthropic

        def classify_werkbon(werkbon_key: int, contract_text: str, threshold_ja: float, threshold_nee: float) -> dict:
            """Classify using IMPROVED V2 prompt."""
            keten = data_service.get_werkbon_keten(
                werkbon_key,
                include_kosten_details=True,
                include_oplossingen=True,
                include_opvolgingen=True
            )

            if not keten:
                return {"error": "Werkbon niet gevonden", "werkbon_key": werkbon_key}

            # Gebruik verbeterde builder
            builder = VerbeterdeVerhaalBuilder()
            verhaal = builder.build_verhaal(keten)

            # ⭐ VERBETERDE SYSTEM PROMPT V3 - Aangescherpt op basis van WVC feedback ronde 2
            system_prompt = """Je bent een expert in het analyseren van servicecontracten voor verwarmingssystemen.

Je taak is om te bepalen of een werkbon binnen of buiten een servicecontract valt.

⭐ BELANGRIJKSTE ANALYSE PUNT: Lees EERST de "WAT HEEFT DE MONTEUR GEDAAN? (Oplossingen)" sectie.
Dit is een vrij tekstveld waar de monteur beschrijft wat er aan de hand was en wat hij heeft gedaan.
Deze informatie is CRUCIAAL en weegt ZWAARDER dan de automatische kostenregels.

🔍 KRITISCHE REGELS (op volgorde van prioriteit):

📌 REGEL 1 - ALTIJD BINNEN CONTRACT (JA):
- **Radiatorkranen** → ALTIJD JA, ook als ze > 2 meter van de ketel zitten!
- **Installatie vullen en ontluchten** → ALTIJD JA (bijvullen, ontluchten, installatie gevuld)
- **Ketelonderdelen**: Ventilator, gasklep, expansievat, warmtewisselaar, ontstekingselektrode,
  pakking, printplaat, sensor, drukmeter, ontluchter, pomp van de ketel, waterdrukschakelaar
- **"Ketel lek"**, "onderdeel in/aan de ketel", "lekkage aan ketel"

📌 REGEL 2 - ALTIJD BUITEN CONTRACT (NEE):
- **Tapwaterboiler** → ALTIJD NEE (regie, ook als het in de paragraaf staat)
- **Vloerverwarming** → ALTIJD NEE (buiten contract)
- **Lekkage leiding BUITEN ketelkast** → NEE (keuken, badkamer, woonkamer, etc.)
- **Oorzaak: probleem derden / electricien** → NEE (factureren aan derden)
- **Verstopping** → NEE (buiten contract)
- **Radiatoren** (niet radiatorkranen!) op afstand → NEE
- **Leidingen** op afstand (> 2m van ketel) → NEE

📌 REGEL 3 - ONDERSCHEID KETELKAST VS BUITEN:
**"BINNEN DE MANTEL" (< 2 meter van cv-ketel):**
- Onderdelen die DEEL UITMAKEN VAN DE CV-KETEL ZELF → JA
- "Lekkage ONDER de ketel" = buiten de ketelkast → NEE
- Lekkage leiding in keuken/badkamer/woonkamer → NEE (ook als ketel daar staat)

📌 REGEL 4 - VEELVOORKOMENDE GEVALLEN:
1. **Storing + ketelonderdeel vervangen** → JA
2. **Storing + radiator/leiding op afstand** → NEE
3. **Radiatorkraan/knop defect** → JA (ongeacht locatie!)
4. **Installatie gevuld en ontlucht** → JA (ongeacht locatie!)
5. **Tapwaterboiler storing** → NEE (altijd regie)
6. **Vloerverwarming storing** → NEE (buiten contract)
7. **Probleem derden / electricien** → NEE (factureren)
8. **Niet thuis geweest** → JA met lage confidence (werk niet uitgevoerd maar geen regie)

Analyseer vervolgens:
- Type werkzaamheden (onderhoud, reparatie, storing, modificatie)
- Locatie: binnen ketelkast vs buiten ketel
- Gebruikte materialen en onderdelen
- Arbeidsuren en kostenposten
- Oorzaak: wie/wat veroorzaakt het probleem
- Storingscodes en oorzaken

Geef je antwoord ALLEEN in het volgende JSON formaat:
{
    "classificatie": "JA" of "NEE",
    "confidence": 0.0-1.0,
    "contract_referentie": "Verwijzing naar relevant contract artikel",
    "toelichting": "Korte uitleg: vermeld EXPLICIET wat de monteur deed en welke regel van toepassing is"
}

Classificatie:
- JA: Werkzaamheden vallen volledig binnen het contract (niet factureren aan klant)
- NEE: Werkzaamheden vallen buiten het contract (wel factureren aan klant)

confidence: Je zekerheid over de classificatie (0.0 = zeer onzeker, 1.0 = zeer zeker)

BELANGRIJK:
- Geef ALTIJD een classificatie (JA of NEE), ook als je onzeker bent
- Bij twijfel over locatie → kijk naar wat de monteur schrijft in oplossingen
- Ketelonderdelen zijn BINNEN contract, ook als ze "duur" zijn
- RADIATORKRANEN zijn ALTIJD binnen contract (ook op afstand > 2m)
- TAPWATERBOILER is ALTIJD regie (NEE)
- INSTALLATIE VULLEN/ONTLUCHTEN is ALTIJD binnen contract (JA)"""

            contract_truncated = contract_text[:15000] if len(contract_text) > 15000 else contract_text

            user_message = f"""### CONTRACT ###
{contract_truncated}

### WERKBON VERHAAL ###
{verhaal}

Classificeer deze werkbon. Let VOORAL op de "WAT HEEFT DE MONTEUR GEDAAN?" sectie.
Geef je antwoord in JSON formaat."""

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

                # Parse JSON
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

        results = []
        progress = st.progress(0)
        status = st.empty()

        for i, wb in enumerate(werkbonnen):
            debiteur = wb.get("debiteur", "")
            status.text(f"Classificeren {i+1}/{len(werkbonnen)}: {debiteur[:30]}...")

            contract = get_contract_for_debiteur(debiteur, contracts)

            if not contract:
                results.append({
                    "werkbon_key": wb["hoofdwerkbon_key"],
                    "werkbon_code": wb.get("werkbon_code", ""),
                    "debiteur": debiteur,
                    "datum": wb.get("melddatum", ""),
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
                threshold_ja,
                threshold_nee
            )

            result["werkbon_code"] = wb.get("werkbon_code", "")
            result["debiteur"] = debiteur
            result["datum"] = wb.get("aanmaakdatum", "")
            result["contract_filename"] = contract["filename"]
            results.append(result)

            progress.progress((i + 1) / len(werkbonnen))

        status.empty()
        progress.empty()

        st.session_state.classificatie_resultaten = results
        st.session_state.werkbonnen_batch = None

        # Mark as processed
        for r in results:
            if r.get("werkbon_key"):
                st.session_state.processed_werkbon_keys.add(r["werkbon_key"])

        save_processed_werkbon_keys(st.session_state.processed_werkbon_keys)
        save_to_history(results)

        st.session_state.just_classified = len(results)
        st.rerun()

    # === RESULTS ===
    if st.session_state.classificatie_resultaten:
        results = st.session_state.classificatie_resultaten

        if "just_classified" in st.session_state and st.session_state.just_classified:
            st.success(f"✅ {st.session_state.just_classified} werkbonnen geclassificeerd met V2!")
            st.session_state.just_classified = None

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

            st.markdown(f"""
            <div style="padding: 1rem; background: {color}; border-radius: 0.5rem; border-left: 4px solid {border}; margin-bottom: 0.5rem;">
                <strong>{icon} {result.get('debiteur', '')[:40]}</strong>
                <span style="margin-left: 1rem; padding: 0.2rem 0.5rem; background: white; border-radius: 0.25rem;">
                    {classificatie}
                </span>
                <span style="margin-left: 0.5rem; color: #666; font-size: 0.9rem;">
                    ({confidence:.0%}){kosten_info}
                </span>
            </div>
            """, unsafe_allow_html=True)

            with st.expander(f"Details - {result.get('debiteur', 'Werkbon')[:30]}"):
                detail_tab1, detail_tab2 = st.tabs(["📋 Classificatie", "📄 Werkbon Verhaal (V2)"])

                with detail_tab1:
                    st.markdown(f"**Toelichting:** {result.get('toelichting', 'N/A')}")
                    st.markdown(f"**Contract:** {result.get('contract_filename', 'N/A')}")
                    st.markdown(f"**Contract referentie:** {result.get('contract_referentie', 'N/A')}")
                    st.markdown(f"**Werkbon:** {result.get('werkbon_code', 'N/A')}")
                    st.markdown(f"**Datum:** {result.get('datum', 'N/A')}")

                with detail_tab2:
                    if result.get("verhaal"):
                        st.text_area(
                            "Werkbon Verhaal (V2 - met oplossingen prominent)",
                            result["verhaal"],
                            height=400,
                            key=f"verhaal_v2_{result.get('werkbon_key', id(result))}"
                        )

        # Export
        st.divider()

        df = pd.DataFrame([{
            "Werkbon": r.get("werkbon_code", ""),
            "Debiteur": r.get("debiteur", ""),
            "Datum": r.get("datum", ""),
            "Contract": r.get("contract_filename", ""),
            "Classificatie": r.get("classificatie", ""),
            "Confidence": f"{r.get('confidence', 0):.0%}",
            "Kosten": f"€{r.get('totaal_kosten', 0):,.2f}",
            "Toelichting": r.get("toelichting", ""),
        } for r in results])

        st.download_button(
            "📥 Download resultaten V2 (CSV)",
            df.to_csv(index=False),
            "classificatie_resultaten_v2.csv",
            "text/csv",
            use_container_width=True
        )

        # Next batch
        st.divider()
        if st.button("➡️ Volgende batch", type="primary", use_container_width=True, key="next_v2"):
            st.session_state.classificatie_resultaten = []
            st.session_state.werkbonnen_batch = None
            st.rerun()
