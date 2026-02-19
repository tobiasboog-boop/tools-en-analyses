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


def load_collectieve_patronen() -> set:
    """Laad patronen die collectieve systemen identificeren."""
    patterns_file = Path(__file__).parent / "data" / "collectieve_patronen.txt"
    patterns = set()

    if patterns_file.exists():
        with open(patterns_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    patterns.add(line.lower())

    return patterns


def is_collectief_systeem(paragraaf_naam: str, collectieve_patronen: set) -> bool:
    """Check of een paragraaf naam een collectief systeem is (centraal ketelhuis, HVC, etc.)."""
    if not paragraaf_naam:
        return False

    paragraaf_lower = paragraaf_naam.lower()

    for patroon in collectieve_patronen:
        if patroon in paragraaf_lower:
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
                    if p.factureerwijze:
                        lines.append(f"- ⚠️ Factureerwijze: {p.factureerwijze}")
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
    page_title="Contract Checker V3 - DEMO",
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

# === V3 INFO BANNER ===
st.markdown("""
<div style="background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%); padding: 15px 20px; border-radius: 8px; border-left: 4px solid #22c55e; margin-bottom: 20px;">
    <strong style="color: #15803d;">✨ VERSIE 3 - 90% Nauwkeurigheid</strong>
    <p style="color: #166534; margin: 8px 0 0 0; font-size: 0.9rem;">
        Verbeterde classificatie met <strong>storingscode-differentiatie</strong> (006.1 vs 006.2),
        prioriteitsregels voor probleem-derden, en deterministische AI-analyse.
        Backtest: 35 van 39 bonnen correct geclassificeerd.
    </p>
</div>
""", unsafe_allow_html=True)

# === DEMO DISCLAIMER ===
st.markdown("""
<div style="background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%); padding: 15px 20px; border-radius: 8px; border-left: 4px solid #3b82f6; margin-bottom: 20px;">
    <strong style="color: #1e40af;">📊 DEMO - Historische Data</strong>
    <p style="color: #1e3a8a; margin: 8px 0 0 0; font-size: 0.9rem;">
        Deze tool werkt met een historische dataset van WVC-werkbonnen voor validatie.
        De AI classificeert op basis van storingscodes, contracttype en beschikbare werkbondata.
        Handmatige controle blijft vereist — aan de resultaten kunnen geen rechten worden ontleend.
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
    st.header("Demo Gebruik")
    st.metric("Geclassificeerd", f"{get_usage_count()} werkbonnen")
    st.caption("✅ Persistente opslag - blijft bewaard")

# === MAIN CONTENT ===

st.title("🧪 Contract Checker V3 - DEMO")
st.caption("Werkbonnen classificeren met AI | v2026-02-17-v6 (generiek, contracttekst-gestuurd)")
st.markdown("[📖 Handleiding & uitleg](https://notifica.nl/tools/contract-checker)")

# === TABS ===
tab_classify, tab_history = st.tabs(["🚀 Classificeren", "📜 Geschiedenis"])

# === HISTORY TAB ===
with tab_history:
    st.header("Classificatie Geschiedenis")
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
        options=["Alle contracten", "Alleen individuele installaties", "Alleen collectieve systemen"],
        index=0,
        horizontal=True,
        help="Individueel = eigen ketel/installatie. Collectief = centraal ketelhuis, HVC, stadsverwarming.",
        key="contract_type_filter_v2"
    )

    # Load collectieve patronen (blacklist approach)
    collectieve_patronen = load_collectieve_patronen()

    if collectieve_patronen:
        st.caption(f"ℹ️ Collectieve systemen herkend op: {', '.join(sorted(collectieve_patronen))}")
    else:
        st.warning("⚠️ Geen collectieve patronen gevonden in data/collectieve_patronen.txt")

    # Build werkbon → collectief/individueel mapping (eenmalig)
    def build_contract_type_mapping():
        df_para = data_service.df_paragrafen.copy()
        df_para["is_collectief"] = df_para["naam"].apply(
            lambda x: is_collectief_systeem(x, collectieve_patronen)
        )
        # Als minstens 1 paragraaf collectief is → werkbon is collectief
        return df_para.groupby("werkbon_key")["is_collectief"].max().to_dict()

    werkbon_collectief_map = build_contract_type_mapping()

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

        # Contract-type filter (blacklist: collectief herkennen, rest = individueel)
        if contract_filter != "Alle contracten":
            if contract_filter == "Alleen individuele installaties":
                df = df[df["werkbon_key"].apply(lambda x: not werkbon_collectief_map.get(x, False))]
            elif contract_filter == "Alleen collectieve systemen":
                df = df[df["werkbon_key"].apply(lambda x: werkbon_collectief_map.get(x, False))]

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

            # Contract-type filter (blacklist: collectief herkennen, rest = individueel)
            if contract_type_filter != "Alle contracten":
                if contract_type_filter == "Alleen individuele installaties":
                    df = df[df["werkbon_key"].apply(lambda x: not werkbon_collectief_map.get(x, False))]
                    st.caption("📋 Filter actief: Alleen individuele installaties (eigen ketel)")
                elif contract_type_filter == "Alleen collectieve systemen":
                    df = df[df["werkbon_key"].apply(lambda x: werkbon_collectief_map.get(x, False))]
                    st.caption("📋 Filter actief: Alleen collectieve systemen (centraal ketelhuis/HVC)")

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

            # ⭐ SYSTEM PROMPT V6 - Generiek (contracttekst-gestuurd)
            system_prompt = """Je bent een expert in het analyseren van servicecontracten voor verwarmingssystemen.

Je taak is om te bepalen of een werkbon binnen of buiten een servicecontract valt.
Het CONTRACT dat je meekrijgt bevat het BASISPRINCIPE en de BELANGRIJKE UITZONDERINGEN voor deze specifieke woningbouwvereniging. Lees dit EERST en volg de contractregels nauwkeurig.

⭐ BELANGRIJKSTE ANALYSE PUNT: Lees daarna de "WAT HEEFT DE MONTEUR GEDAAN? (Oplossingen)" sectie.
Dit is een vrij tekstveld waar de monteur beschrijft wat er aan de hand was en wat hij heeft gedaan.
Deze informatie is CRUCIAAL en weegt ZWAARDER dan storingscodes of kostenregels.

🔍 UNIVERSELE REGELS (gelden voor ALLE contracten, op volgorde van prioriteit):

📌 REGEL 0 - HOOGSTE PRIORITEIT (ALTIJD NEE, ongeacht andere regels):
- **Factureerwijze "Regie (alles factureren)"** → ALTIJD NEE. Als de paragraaf op Regie staat, is het antwoord altijd NEE.
- **Oorzaakcode 900 / "Probleem door derde"** → ALTIJD NEE (factureren aan derden)
  Dit geldt OOK als de storingscode iets anders suggereert (bijv. lekkage onder ketel + probleem derden = NEE)
- **Tapwaterboiler / geiser / moederhaard** → ALTIJD NEE (regie)
- **Vloerverwarming (verdelers, pompen, regelingen)** → ALTIJD NEE (buiten contract)
- **Verstopping** → ALTIJD NEE (buiten contract)

📌 REGEL 1 - OPLOSSING GAAT VOOR OP STORINGSCODE:
- Als de OPLOSSING van de monteur is "installatie gevuld en ontlucht" / "bijgevuld" / "ontlucht" → ALTIJD JA
  Dit geldt OOK als de storingscode iets anders suggereert (bijv. "GEEN CV en WW" + oplossing gevuld/ontlucht = JA)
- Als de OPLOSSING een ander verhaal vertelt dan de storingscode, volg dan de OPLOSSING

📌 REGEL 2 - KETELONDERDELEN = BINNEN DE MANTEL (ALTIJD JA):
De volgende onderdelen zitten fysiek IN de cv-ketel (binnen de mantel) en vallen ALTIJD binnen contract:
- Hydroblok, driewegklep, manometer, automatisch vulsysteem, vulset
- Expansievat, warmtewisselaar, branderunit, gasblok, ventilator
- Printplaat, ontstekingselektrode, ionisatie-electrode
- Pompje (cv-pomp in de ketel), overloopbeveiliging, veiligheidsklep
Als de werkbon (of een vervolgbon/meenemen-bon) deze onderdelen noemt → JA.

📌 REGEL 3 - CONTRACTTEKST IS LEIDEND:
Volg het CONTRACT voor contractspecifieke regels over:
- Welke onderdelen/locaties wel of niet gedekt zijn
- Of er een afstandsgrens geldt (bijv. "2 meter van de ketel")
- Hoe radiatoren, radiatorkranen, WTW-units, RGA/LTV behandeld worden
- Deze regels VERSCHILLEN per woningbouwvereniging — lees het contract!

📌 REGEL 4 - STORINGSCODES (universeel, Syntess-systeemcodes):
- **Storingscode 006.1 "Lekkage ONDER de ketel"** = lekkage dichtbij/onder de ketel (binnen de mantel)
- **Storingscode 006.2 "Lekkage aan de installatie"** = lekkage op AFSTAND van de ketel (buiten de mantel) → NEE
  LET OP: 006.1 ≠ 006.2! Dit is een CRUCIAAL onderscheid.
  006.2 betekent dat de lekkage NIET aan de ketel zelf zit maar aan de installatie op afstand → classificeer als NEE.

📌 REGEL 5 - BIJ TWIJFEL:
- **Radiatoren vervangen** → classificeer als NEE (medewerker kan dit beter beoordelen dan AI)
- **CV-leiding niet in het zicht (reparatie)** → classificeer als NEE (moeilijk te beoordelen door AI)
- **Niet thuis geweest** → JA met lage confidence (werk niet uitgevoerd maar geen regie)

Analyseer vervolgens:
- Type werkzaamheden (onderhoud, reparatie, storing, modificatie)
- Locatie: binnen ketelkast/mantel vs buiten ketel
- Gebruikte materialen en onderdelen
- Arbeidsuren en kostenposten
- Oorzaak: wie/wat veroorzaakt het probleem
- Storingscodes en oorzaken

Geef je antwoord ALLEEN in het volgende JSON formaat:
{
    "classificatie": "JA" of "NEE",
    "confidence": 0.0-1.0,
    "contract_referentie": "Verwijzing naar relevant contract artikel of -regel",
    "toelichting": "Korte uitleg: vermeld EXPLICIET wat de monteur deed en welke contractregel van toepassing is"
}

Classificatie:
- JA: Werkzaamheden vallen volledig binnen het contract (niet factureren aan klant)
- NEE: Werkzaamheden vallen buiten het contract (wel factureren aan klant)

confidence: Je zekerheid over de classificatie (0.0 = zeer onzeker, 1.0 = zeer zeker)

BELANGRIJK:
- Geef ALTIJD een classificatie (JA of NEE), ook als je onzeker bent
- Bij twijfel over locatie → kijk naar wat de monteur schrijft in oplossingen
- Ketelonderdelen (binnen de mantel) zijn BINNEN contract, ook als ze "duur" zijn
- OORZAAK "PROBLEEM DOOR DERDE" → ALTIJD NEE, ook bij lekkage onder ketel
- OPLOSSING "gevuld en ontlucht" → ALTIJD JA, ook als storingscode iets anders suggereert
- Volg het CONTRACT voor contractspecifieke regels over radiatorkranen, WTW-units, afstandsgrenzen etc."""

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
                    temperature=0,
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

                    # Clean control characters die JSON parsing breken
                    import re
                    text_clean = re.sub(r'[\x00-\x1f\x7f]', ' ', text.strip())

                    try:
                        result = json.loads(text_clean)
                    except json.JSONDecodeError:
                        # Fallback: probeer classificatie en confidence via regex te extraheren
                        class_match = re.search(r'"classificatie"\s*:\s*"(JA|NEE)"', text, re.IGNORECASE)
                        conf_match = re.search(r'"confidence"\s*:\s*([\d.]+)', text)
                        toel_match = re.search(r'"toelichting"\s*:\s*"([^"]*)"', text)
                        ref_match = re.search(r'"contract_referentie"\s*:\s*"([^"]*)"', text)

                        if class_match:
                            result = {
                                "classificatie": class_match.group(1).upper(),
                                "confidence": float(conf_match.group(1)) if conf_match else 0.8,
                                "toelichting": toel_match.group(1) if toel_match else "Geëxtraheerd via regex fallback",
                                "contract_referentie": ref_match.group(1) if ref_match else ""
                            }
                        else:
                            raise json.JSONDecodeError("Geen classificatie gevonden", text, 0)

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
