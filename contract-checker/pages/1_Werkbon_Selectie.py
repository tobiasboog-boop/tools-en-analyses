#!/usr/bin/env python3
"""Werkbon Selectie - Publieke versie

Selecteer werkbonnen uit de lokale Parquet dataset voor classificatie.
"""
import streamlit as st
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.auth import require_auth
from src.services.parquet_data_service import ParquetDataService, WerkbonVerhaalBuilder

st.set_page_config(page_title="Werkbon Selectie", layout="wide")

# Wachtwoord check
require_auth()

st.title("Werkbon Selectie")
st.caption("Selecteer werkbonnen uit de demo dataset (historische werkbonnen)")

# Initialize session state
if "werkbonnen_for_beoordeling" not in st.session_state:
    st.session_state.werkbonnen_for_beoordeling = []

# Load data service (cached)
@st.cache_resource
def get_data_service():
    return ParquetDataService(data_dir="data")

try:
    data_service = get_data_service()
except Exception as e:
    st.error(f"Kon data niet laden: {e}")
    st.stop()

# Sidebar filters
with st.sidebar:
    st.header("Filters")

    # Debiteur filter
    debiteuren = data_service.df_werkbonnen["debiteur"].dropna().unique()
    debiteur_codes = []
    for d in debiteuren:
        if " - " in str(d):
            code = str(d).split(" - ")[0].strip()
            if code not in debiteur_codes:
                debiteur_codes.append(code)

    selected_debiteuren = st.multiselect(
        "Debiteur(en)",
        options=sorted(debiteur_codes),
        default=debiteur_codes[:1] if debiteur_codes else []
    )

    st.divider()

    max_results = st.slider("Max resultaten", 10, 100, 50)

    st.divider()

    # Selection summary
    st.subheader("Geselecteerd")
    selected_count = len(st.session_state.werkbonnen_for_beoordeling)
    st.metric("Voor classificatie", selected_count)

    if selected_count > 0:
        if st.button("🗑️ Selectie wissen"):
            st.session_state.werkbonnen_for_beoordeling = []
            st.rerun()

        st.divider()

        if st.button("▶️ Naar Classificatie", type="primary"):
            st.switch_page("pages/2_Classificatie.py")

# Main content
if st.button("🔄 Werkbonnen laden", type="primary"):
    st.session_state.werkbonnen_list = data_service.get_hoofdwerkbon_list(
        debiteur_codes=selected_debiteuren if selected_debiteuren else None,
        limit=max_results
    )
    st.rerun()

# Show results
if "werkbonnen_list" in st.session_state and st.session_state.werkbonnen_list:
    werkbonnen = st.session_state.werkbonnen_list

    # Selection indicator
    selected_count = len(st.session_state.werkbonnen_for_beoordeling)
    if selected_count > 0:
        col_sel, col_btn = st.columns([3, 1])
        with col_sel:
            st.success(f"**{selected_count} werkbonnen geselecteerd** voor classificatie")
        with col_btn:
            if st.button("▶️ Naar Classificatie", type="primary", key="btn_top"):
                st.switch_page("pages/2_Classificatie.py")
        st.divider()

    st.caption(f"Gevonden: {len(werkbonnen)} hoofdwerkbonnen")

    # Select all / none
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("✅ Selecteer alle"):
            selected_keys = {w["hoofdwerkbon_key"] for w in st.session_state.werkbonnen_for_beoordeling}
            for wb in werkbonnen:
                if wb["hoofdwerkbon_key"] not in selected_keys:
                    st.session_state.werkbonnen_for_beoordeling.append(wb)
            st.rerun()
    with col2:
        if st.button("❌ Deselecteer alle"):
            st.session_state.werkbonnen_for_beoordeling = []
            st.rerun()

    # Werkbon list
    selected_keys = {w["hoofdwerkbon_key"] for w in st.session_state.werkbonnen_for_beoordeling}

    for i, wb in enumerate(werkbonnen):
        is_selected = wb["hoofdwerkbon_key"] in selected_keys

        # Compact label
        label = f"{wb['werkbon_code']} | {wb['aanmaakdatum']} | {wb['status']} | {wb['paragraaf_count']} par."

        col_check, col_expander = st.columns([0.3, 5])

        with col_check:
            checked = st.checkbox("", value=is_selected, key=f"chk_{i}", label_visibility="collapsed")
            if checked and not is_selected:
                st.session_state.werkbonnen_for_beoordeling.append(wb)
                st.rerun()
            elif not checked and is_selected:
                st.session_state.werkbonnen_for_beoordeling = [
                    w for w in st.session_state.werkbonnen_for_beoordeling
                    if w["hoofdwerkbon_key"] != wb["hoofdwerkbon_key"]
                ]
                st.rerun()

        with col_expander:
            with st.expander(label, expanded=False):
                # Load werkbon details on demand
                cache_key = f"keten_{wb['hoofdwerkbon_key']}"
                if cache_key in st.session_state:
                    keten = st.session_state[cache_key]
                    if keten:
                        builder = WerkbonVerhaalBuilder()
                        st.markdown(builder.build_verhaal(keten))

                        # Kosten overzicht
                        cat_totalen = {"Arbeid": 0, "Materiaal": 0, "Overig": 0, "Materieel": 0}
                        for wbon in keten.werkbonnen:
                            for p in wbon.paragrafen:
                                for k in p.kosten:
                                    cat = k.categorie.strip() if k.categorie else "Overig"
                                    if cat in cat_totalen:
                                        cat_totalen[cat] += k.kostprijs
                                    else:
                                        cat_totalen["Overig"] += k.kostprijs

                        st.markdown("**Kosten overzicht:**")
                        for cat in ["Arbeid", "Materiaal", "Overig", "Materieel"]:
                            st.markdown(f"- {cat}: €{cat_totalen[cat]:,.2f}")
                        st.metric("Totaal", f"€{sum(cat_totalen.values()):,.2f}")
                else:
                    if st.button("📄 Laad details", key=f"load_{wb['hoofdwerkbon_key']}"):
                        keten = data_service.get_werkbon_keten(
                            wb["hoofdwerkbon_key"],
                            include_kosten_details=True,
                            include_oplossingen=True,
                            include_opvolgingen=True
                        )
                        st.session_state[cache_key] = keten
                        st.rerun()

elif "werkbonnen_list" in st.session_state:
    st.info("Geen werkbonnen gevonden voor deze filters.")
else:
    st.info("Klik op **Werkbonnen laden** om te beginnen.")
