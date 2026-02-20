#!/usr/bin/env python3
"""Step 2: Werkbon Selectie - Selecteer werkbonnen voor beoordeling.

Twee modi:
- VALIDATIE: Historische werkbonnen (facturatie bekend) voor hit rate meting
- CLASSIFICATIE: Openstaande werkbonnen voor dagelijkse beoordeling
"""
import json
from datetime import date, timedelta
from typing import List, Dict, Any

import pandas as pd
import streamlit as st
from sqlalchemy import text

from src.models.database import SessionLocal
from src.services.werkbon_keten_service import (
    WerkbonKetenService,
    WerkbonVerhaalBuilder
)
from src.services.contract_loader import ContractLoader
from src.config import config


# Configure page to use full width
st.set_page_config(layout="wide")

st.title("Werkbon Selectie")

# De 3 debiteuren uit contract_relatie
DEBITEUREN = {
    "007453": "Stichting Bazalt Wonen",
    "177460": "Stichting Thuisvester (Oosterhout)",
    "005102": "Trivire",
}

# Paragraaf types (selecteerbaar in UI)
PARAGRAAF_TYPES = {
    "Storing": "Storing",
    "Onderhoud en Storing": "Onderhoud en Storing",
    "Onderhoud": "Onderhoud",
    "Onbekend (regie/project)": "Onbekend (regie/project)",
}
DEFAULT_PARAGRAAF_TYPES = ["Storing", "Onderhoud en Storing"]

# Session state initialization
if "werkbonnen_for_beoordeling" not in st.session_state:
    st.session_state.werkbonnen_for_beoordeling = []
if "selectie_modus" not in st.session_state:
    st.session_state.selectie_modus = "validatie"
if "hide_beoordeeld" not in st.session_state:
    st.session_state.hide_beoordeeld = True  # Default: verberg al beoordeelde


def get_beoordeelde_werkbonnen() -> set:
    """Haal set van hoofdwerkbon_keys op die al beoordeeld zijn."""
    db = SessionLocal()
    try:
        query = text(f"""
            SELECT DISTINCT hoofdwerkbon_key
            FROM {config.DB_SCHEMA}.classifications
            WHERE hoofdwerkbon_key IS NOT NULL
        """)
        result = db.execute(query)
        return {row[0] for row in result}
    except Exception as e:
        st.warning(f"Kon beoordeelde werkbonnen niet laden: {e}")
        return set()
    finally:
        db.close()


def get_werkbonnen_actie_details(hoofdwerkbon_keys: List[int]) -> Dict[int, Dict[str, bool]]:
    """Bepaal per hoofdwerkbon welke openstaande acties er zijn.

    Checkt op:
    1. Toekomstige planregels (planning."Geplande en contracturen medewerkers")
    2. Vervolgbonnen die niet uitgevoerd zijn (Status = Aanmaak of In uitvoering)
    3. Openstaande pakbonnen (Pakbon Status = Openstaand)

    Returns:
        Dict van hoofdwerkbon_key -> {"planning": bool, "vervolgbon": bool, "pakbon": bool}
    """
    if not hoofdwerkbon_keys:
        return {}

    db = SessionLocal()
    result_dict = {key: {"planning": False, "vervolgbon": False, "pakbon": False} for key in hoofdwerkbon_keys}

    try:
        # Maak placeholders voor IN clause
        placeholders = ", ".join([f":key_{i}" for i in range(len(hoofdwerkbon_keys))])
        params = {f"key_{i}": key for i, key in enumerate(hoofdwerkbon_keys)}

        # 1. Check toekomstige planregels
        query_planning = text(f"""
            SELECT DISTINCT w."HoofdwerkbonDocumentKey"
            FROM werkbonnen."Werkbonnen" w
            INNER JOIN werkbonnen."Werkbonparagrafen" wp
                ON w."WerkbonDocumentKey" = wp."WerkbonDocumentKey"
            INNER JOIN planning."Geplande en contracturen medewerkers" p
                ON wp."WerkbonparagraafKey" = p."WerkbonParagraafKey"
            WHERE w."HoofdwerkbonDocumentKey" IN ({placeholders})
            AND p."Datum" > CURRENT_DATE
        """)
        for row in db.execute(query_planning, params):
            if row[0] in result_dict:
                result_dict[row[0]]["planning"] = True

        # 2. Check vervolgbonnen niet uitgevoerd
        query_vervolg = text(f"""
            SELECT DISTINCT w."HoofdwerkbonDocumentKey"
            FROM werkbonnen."Werkbonnen" w
            WHERE w."HoofdwerkbonDocumentKey" IN ({placeholders})
            AND w."HoofdwerkbonDocumentKey" != w."WerkbonDocumentKey"
            AND TRIM(w."Status") IN ('Aanmaak', 'In uitvoering')
        """)
        for row in db.execute(query_vervolg, params):
            if row[0] in result_dict:
                result_dict[row[0]]["vervolgbon"] = True

        # 3. Check openstaande pakbonnen
        query_kosten = text(f"""
            SELECT DISTINCT w."HoofdwerkbonDocumentKey"
            FROM werkbonnen."Werkbonnen" w
            INNER JOIN werkbonnen."Werkbonparagrafen" wp
                ON w."WerkbonDocumentKey" = wp."WerkbonDocumentKey"
            INNER JOIN financieel."Kosten" k
                ON wp."WerkbonparagraafKey" = k."WerkbonparagraafKey"
            WHERE w."HoofdwerkbonDocumentKey" IN ({placeholders})
            AND TRIM(k."Pakbon Status") = 'Openstaand'
        """)
        for row in db.execute(query_kosten, params):
            if row[0] in result_dict:
                result_dict[row[0]]["pakbon"] = True

    except Exception as e:
        st.warning(f"Kon actie-open check niet uitvoeren: {e}")
    finally:
        db.close()

    return result_dict


def load_werkbonnen(
    debiteur_codes: List[str],
    start_date: date,
    end_date: date,
    limit: int,
    modus: str = "validatie",
    admin_fases: List[str] = None,
    paragraaf_types: List[str] = None
) -> List[Dict[str, Any]]:
    """Load werkbonnen for one or more debiteuren.

    Args:
        debiteur_codes: Lijst van debiteur codes om te filteren
        modus: "validatie" (Historisch) or "classificatie" (Openstaand)
        admin_fases: Lijst van administratieve fases om te filteren (leeg = alle)
        paragraaf_types: Lijst van paragraaf types om te filteren (leeg = alle)
    """
    if not debiteur_codes:
        return []
    if not paragraaf_types:
        return []

    db = SessionLocal()

    # Build filter based on modus
    if modus == "validatie":
        # Historisch - voor hit rate meting
        status_filter = "AND TRIM(w.\"Documentstatus\") = 'Historisch'"
    else:
        # Openstaand - voor classificatie
        status_filter = "AND TRIM(w.\"Documentstatus\") = 'Openstaand'"

    # Build debiteur filter (multi-select support)
    debiteur_placeholders = " OR ".join([f"w.\"Debiteur\" LIKE :deb_{i}" for i in range(len(debiteur_codes))])
    debiteur_filter = f"({debiteur_placeholders})"

    # Build paragraaf type filter
    type_placeholders = ", ".join([f":type_{i}" for i in range(len(paragraaf_types))])
    type_filter = f"TRIM(wp.\"Type\") IN ({type_placeholders})"

    # Build admin fase filter (support multiple selections)
    if admin_fases and len(admin_fases) > 0:
        # Build placeholders for IN clause
        placeholders = ", ".join([f":admin_fase_{i}" for i in range(len(admin_fases))])
        admin_fase_filter = f"AND TRIM(w.\"Administratieve fase\") IN ({placeholders})"
    else:
        admin_fase_filter = ""

    # Query werkbonnen die paragrafen hebben van geselecteerde types
    query = text(f"""
        SELECT
            w."HoofdwerkbonDocumentKey" as hoofdwerkbon_key,
            w."WerkbonDocumentKey" as werkbon_document_key,
            w."Werkbon" as werkbon,
            SPLIT_PART(w."Werkbon", ' - ', 1) as werkbon_code,
            d."Aanmaakdatum"::date as aanmaakdatum,
            w."Status" as status,
            w."Documentstatus" as documentstatus,
            TRIM(w."Administratieve fase") as admin_fase,
            w."Klant" as klant,
            w."Debiteur" as debiteur,
            COUNT(DISTINCT wp."WerkbonparagraafKey") as paragraaf_count
        FROM werkbonnen."Werkbonnen" w
        INNER JOIN werkbonnen."Werkbonparagrafen" wp
            ON w."WerkbonDocumentKey" = wp."WerkbonDocumentKey"
        INNER JOIN stam."Documenten" d
            ON d."DocumentKey" = w."WerkbonDocumentKey"
        WHERE {debiteur_filter}
          AND w."HoofdwerkbonDocumentKey" = w."WerkbonDocumentKey"
          AND d."Aanmaakdatum"::date >= :start_date
          AND d."Aanmaakdatum"::date <= :end_date
          AND {type_filter}
          AND TRIM(w."Status") = 'Uitgevoerd'
          {status_filter}
          {admin_fase_filter}
        GROUP BY w."HoofdwerkbonDocumentKey", w."WerkbonDocumentKey", w."Werkbon", d."Aanmaakdatum"::date,
                 w."Status", w."Documentstatus", w."Administratieve fase", w."Klant", w."Debiteur"
        ORDER BY aanmaakdatum DESC
        LIMIT :limit
    """)

    params = {
        "start_date": start_date,
        "end_date": end_date,
        "limit": limit,
    }
    # Add debiteur parameters
    for i, code in enumerate(debiteur_codes):
        params[f"deb_{i}"] = f"{code} - %"
    # Add paragraaf type parameters
    for i, ptype in enumerate(paragraaf_types):
        params[f"type_{i}"] = ptype
    # Add admin fase parameters for IN clause
    if admin_fases and len(admin_fases) > 0:
        for i, fase in enumerate(admin_fases):
            params[f"admin_fase_{i}"] = fase

    result = db.execute(query, params)

    werkbonnen = []
    for row in result:
        werkbonnen.append({
            "hoofdwerkbon_key": int(row[0]) if row[0] is not None else None,
            "werkbon_document_key": int(row[1]) if row[1] is not None else None,
            "werkbon": row[2],
            "werkbon_code": row[3],
            "aanmaakdatum": row[4],
            "status": row[5].strip() if row[5] else "",
            "documentstatus": row[6].strip() if row[6] else "",
            "admin_fase": row[7] if row[7] else "",
            "klant": row[8],
            "debiteur": row[9],
            "paragraaf_count": row[10],
        })

    db.close()
    return werkbonnen


# Sidebar
with st.sidebar:
    st.header("Modus")

    # Modus selectie - validatie eerst (voor testen), dan classificatie (productie)
    modus = st.radio(
        "Selecteer modus",
        options=["validatie", "classificatie"],
        format_func=lambda x: "🔬 Validatie" if x == "validatie" else "📋 Classificatie",
        index=0 if st.session_state.selectie_modus == "validatie" else 1,
    )
    st.session_state.selectie_modus = modus

    st.divider()
    st.header("Filters voor Selectie")

    # Debiteur selectie (multi-select)
    debiteur_options = {f"{code} - {name}": code for code, name in DEBITEUREN.items()}
    selected_debiteur_labels = st.multiselect(
        "Debiteur(en)",
        options=list(debiteur_options.keys()),
        default=[list(debiteur_options.keys())[0]]  # Eerste als default
    )
    selected_debiteuren = [debiteur_options[label] for label in selected_debiteur_labels]

    st.divider()

    # Periode filters
    st.subheader("Periode")
    st.caption("Filter op **aanmaakdatum** van de werkbon")

    period_options = {
        "Laatste 3 dagen": 3,
        "Laatste week": 7,
        "Laatste 2 weken": 14,
        "Laatste maand": 30,
        "Laatste 3 maanden": 90,
        "Custom": -1,
    }

    selected_period = st.selectbox(
        "Snelkeuze",
        options=list(period_options.keys()),
        index=2  # Default: laatste 2 weken
    )

    today = date.today()
    if selected_period == "Custom":
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Van", value=today - timedelta(days=30))
        with col2:
            end_date = st.date_input("Tot", value=today)
    else:
        days = period_options[selected_period]
        start_date = today - timedelta(days=days)
        end_date = today

    st.caption(f"📅 Aanmaakdatum: {start_date} t/m {end_date}")

    st.divider()

    # Paragraaf type filter
    st.subheader("Paragraaf type")
    selected_paragraaf_types = st.multiselect(
        "Type(s)",
        options=list(PARAGRAAF_TYPES.keys()),
        default=DEFAULT_PARAGRAAF_TYPES,
        help="Filter op type werkbonparagraaf"
    )

    st.divider()

    # Administratieve fase filter
    st.subheader("Administratieve fase")
    admin_fase_options = [
        "001 - .",
        "002 - Gecontroleerd door callcenter-medewerker",
        "003 - Klaar voor gereedmelden",
        "004 - Klaar voor gereedmelden P6",
        "005 - Klaar voor gemelden Trivire",
        "006 - Klaar voor gereedmelden Rhiant",
        "007 - Contract meesturen",
        "008 - Gereed materiaal garantie",
        "01 - initieel",
        "02 - Geen opdracht",
        "03 - Opdr. verstrekt inleners/ZZP (arbeid)",
        "04 - Inkoopfactuur ontvangen ZZP/Inlener",
    ]
    selected_admin_fases = st.multiselect(
        "Filter op fase(s)",
        options=admin_fase_options,
        default=[],
        help="Selecteer één of meer fases (leeg = alle fases)"
    )

    st.divider()

    # Actie open filters (3 aparte checkboxes)
    st.subheader("Verberg met actie open")
    st.caption("Verberg werkbonnen met openstaande acties")
    filter_planning = st.checkbox(
        "Toekomstige planning",
        value=False,
        help="Verberg werkbonnen met planregels in de toekomst"
    )
    filter_vervolgbon = st.checkbox(
        "Open vervolgbonnen",
        value=False,
        help="Verberg werkbonnen met vervolgbonnen in status Aanmaak of In uitvoering"
    )
    filter_pakbon = st.checkbox(
        "Openstaande pakbonnen",
        value=False,
        help="Verberg werkbonnen met Pakbon Status = Openstaand"
    )

    st.divider()

    # Filter voor al beoordeelde werkbonnen
    hide_beoordeeld = st.checkbox(
        "Verberg al beoordeeld",
        value=st.session_state.hide_beoordeeld,
        help="Verberg werkbonnen die al een classificatie hebben"
    )
    st.session_state.hide_beoordeeld = hide_beoordeeld

    st.divider()

    # Maximum aantal
    max_results = st.slider("Max resultaten", min_value=5, max_value=100, value=20)

    st.divider()

    # Geselecteerde werkbonnen voor beoordeling
    st.subheader("Geselecteerd")
    selected_count = len(st.session_state.werkbonnen_for_beoordeling)
    st.metric("Voor beoordeling", selected_count)

    if selected_count > 0:
        if st.button("🗑️ Wissen", key="clear_selection"):
            st.session_state.werkbonnen_for_beoordeling = []
            st.rerun()

        st.divider()
        if st.button("▶️ Naar Beoordeling", type="primary"):
            st.switch_page("pages/3_Beoordeling.py")


# Main content - selectie-indicator bovenin
selected_count = len(st.session_state.werkbonnen_for_beoordeling)
if selected_count > 0:
    col_sel, col_btn, col_clear = st.columns([2, 1, 1])
    with col_sel:
        st.success(f"**{selected_count} werkbonnen geselecteerd** voor beoordeling")
    with col_btn:
        if st.button("▶️ Naar Beoordeling", type="primary", use_container_width=True):
            st.switch_page("pages/3_Beoordeling.py")
    with col_clear:
        if st.button("🗑️ Wissen", key="clear_top", use_container_width=True):
            st.session_state.werkbonnen_for_beoordeling = []
            st.rerun()
    st.divider()

# Modus indicator met uitleg
if modus == "validatie":
    st.info("""🔬 **Validatie** — Uitgevoerd + Historisch

De AI classificeert werkbonnen **zonder** facturatiegegevens te zien (geen spieken).
Na de classificatie halen we de facturatiestatus uit de database om de voorspelling te controleren.
Zo meten we de **hit rate**: hoe vaak klopt de AI-classificatie met de werkelijke facturatie?""")
else:
    st.warning("""📋 **Classificatie** — Uitgevoerd + Openstaand

De AI classificeert werkbonnen die nog op beoordeling wachten.
Facturatiestatus is nog niet bekend, dus er is geen achteraf-controle mogelijk.""")

# Load button
col_load, col_info = st.columns([1, 3])
with col_load:
    if st.button("🔄 Werkbonnen laden", type="primary"):
        if not selected_debiteuren:
            st.warning("Selecteer minimaal één debiteur.")
        elif not selected_paragraaf_types:
            st.warning("Selecteer minimaal één paragraaf type.")
        else:
            st.session_state.werkbonnen_list = load_werkbonnen(
                selected_debiteuren, start_date, end_date, max_results, modus,
                selected_admin_fases, selected_paragraaf_types
            )
            st.session_state.werkbonnen_max_results = max_results  # Voor limiet-waarschuwing
            st.session_state.werkbonnen_for_beoordeling = []  # Reset selectie bij nieuwe load
            st.rerun()

# Show werkbonnen list
if "werkbonnen_list" in st.session_state and st.session_state.werkbonnen_list:
    werkbonnen_raw = st.session_state.werkbonnen_list

    # Haal beoordeelde werkbonnen op
    beoordeelde_keys = get_beoordeelde_werkbonnen()

    # Haal actie-details op voor alle werkbonnen (voor filtering én weergave)
    alle_keys = [wb["hoofdwerkbon_key"] for wb in werkbonnen_raw]
    actie_details = get_werkbonnen_actie_details(alle_keys)

    # Filter werkbonnen
    werkbonnen = werkbonnen_raw
    filter_stats = []

    # Filter op beoordeeld
    if st.session_state.hide_beoordeeld:
        before_count = len(werkbonnen)
        werkbonnen = [wb for wb in werkbonnen if wb["hoofdwerkbon_key"] not in beoordeelde_keys]
        filtered_count = before_count - len(werkbonnen)
        if filtered_count > 0:
            filter_stats.append(f"{filtered_count} beoordeeld")

    # Filter op toekomstige planning
    if filter_planning:
        before_count = len(werkbonnen)
        werkbonnen = [wb for wb in werkbonnen if not actie_details.get(wb["hoofdwerkbon_key"], {}).get("planning", False)]
        filtered_count = before_count - len(werkbonnen)
        if filtered_count > 0:
            filter_stats.append(f"{filtered_count} planning")

    # Filter op open vervolgbonnen
    if filter_vervolgbon:
        before_count = len(werkbonnen)
        werkbonnen = [wb for wb in werkbonnen if not actie_details.get(wb["hoofdwerkbon_key"], {}).get("vervolgbon", False)]
        filtered_count = before_count - len(werkbonnen)
        if filtered_count > 0:
            filter_stats.append(f"{filtered_count} vervolgbon")

    # Filter op openstaande pakbonnen
    if filter_pakbon:
        before_count = len(werkbonnen)
        werkbonnen = [wb for wb in werkbonnen if not actie_details.get(wb["hoofdwerkbon_key"], {}).get("pakbon", False)]
        filtered_count = before_count - len(werkbonnen)
        if filtered_count > 0:
            filter_stats.append(f"{filtered_count} pakbon")

    # Toon statistieken
    if filter_stats:
        st.caption(f"{len(werkbonnen)} werkbonnen | verborgen: {', '.join(filter_stats)}")
    else:
        # Toon resultaat info met limiet-waarschuwing indien van toepassing
        beoordeeld_in_list = sum(1 for wb in werkbonnen if wb["hoofdwerkbon_key"] in beoordeelde_keys)
        loaded_max = st.session_state.get("werkbonnen_max_results", 20)
        limiet_bereikt = len(werkbonnen_raw) >= loaded_max

        info_parts = [f"{len(werkbonnen)} werkbonnen"]
        if beoordeeld_in_list > 0:
            info_parts.append(f"{beoordeeld_in_list} al beoordeeld (✓)")
        st.caption(" | ".join(info_parts))

        if limiet_bereikt:
            st.warning(f"⚠️ Maximum van {loaded_max} resultaten bereikt. Pas filters aan of verhoog de limiet.")

    # Maak set van geselecteerde keys voor snelle O(1) lookup
    selected_keys = {w["hoofdwerkbon_key"] for w in st.session_state.werkbonnen_for_beoordeling}

    # Select all / none buttons
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("✅ Selecteer alle"):
            # Voeg alle werkbonnen toe die nog niet geselecteerd zijn
            for wb in werkbonnen:
                if wb["hoofdwerkbon_key"] not in selected_keys:
                    st.session_state.werkbonnen_for_beoordeling.append(wb)
            st.rerun()
    with col2:
        if st.button("❌ Deselecteer alle"):
            st.session_state.werkbonnen_for_beoordeling = []
            st.rerun()

    # Contract loader en cache voor efficiency
    contract_loader = ContractLoader()
    contract_cache = {}  # debiteur_code -> contract_filename

    # Legenda
    with st.expander("Legenda", expanded=False):
        st.markdown("""
        - 📁 Historisch | 📂 Openstaand
        - ✓ Al beoordeeld
        - ⏳ Openstaande acties: Planning, Vervolgbon, Pakbon
        """)

    # Compacte werkbonlijst - één regel per werkbon met checkbox en expander
    for i, wb in enumerate(werkbonnen):
        is_selected = wb["hoofdwerkbon_key"] in selected_keys
        is_beoordeeld = wb["hoofdwerkbon_key"] in beoordeelde_keys

        # Haal actie details op voor deze werkbon
        wb_acties = actie_details.get(wb["hoofdwerkbon_key"], {})
        actie_labels = []
        if wb_acties.get("planning"):
            actie_labels.append("Planning")
        if wb_acties.get("vervolgbon"):
            actie_labels.append("Vervolgbon")
        if wb_acties.get("pakbon"):
            actie_labels.append("Pakbon")

        # Zoek contract voor deze werkbon
        debiteur = wb.get("debiteur", "")
        debiteur_code = None
        contract_badge = ""

        if debiteur and " - " in debiteur:
            parts = debiteur.split(" - ")
            if parts and parts[0].strip().isdigit():
                debiteur_code = parts[0].strip()

        if debiteur_code:
            if debiteur_code not in contract_cache:
                contract = contract_loader.get_contract_for_debiteur(debiteur_code)
                contract_cache[debiteur_code] = contract["filename"] if contract else None

            contract_filename = contract_cache[debiteur_code]
            if contract_filename:
                # Verkort contract naam voor compacte weergave
                contract_short = contract_filename.replace(".txt", "").replace(".docx", "")[:15]
                contract_badge = f" | 📄 {contract_short}"
            else:
                contract_badge = " | ❌ Geen contract"

        # Compacte info string
        doc_icon = "📁" if wb['documentstatus'] == 'Historisch' else "📂"
        beoordeeld_icon = " ✓" if is_beoordeeld else ""
        actie_open_icon = f" ⏳ {', '.join(actie_labels)}" if actie_labels else ""
        label = f"{wb['werkbon_code']} | {wb['aanmaakdatum']} | {doc_icon} | {wb['paragraaf_count']} par.{contract_badge}{beoordeeld_icon}{actie_open_icon}"

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
                # Lazy loading: alleen laden wanneer gebruiker erom vraagt
                cache_key = f"keten_{wb['hoofdwerkbon_key']}"
                if cache_key in st.session_state:
                    # Toon gecachte data
                    keten = st.session_state[cache_key]
                    if keten:
                        builder = WerkbonVerhaalBuilder()
                        st.markdown(builder.build_verhaal(keten))

                        # Bereken kosten per categorie
                        cat_totalen = {"Arbeid": 0, "Materiaal": 0, "Overig": 0, "Materieel": 0}
                        for wbon in keten.werkbonnen:
                            for p in wbon.paragrafen:
                                for k in p.kosten:
                                    cat = k.categorie.strip() if k.categorie else "Overig"
                                    if cat in cat_totalen:
                                        cat_totalen[cat] += k.kostprijs
                                    else:
                                        cat_totalen["Overig"] += k.kostprijs

                        # Toon uitsplitsing: altijd alle 4 categorieën + Totaal
                        st.markdown("**Kosten overzicht:**")
                        for cat in ["Arbeid", "Materiaal", "Overig", "Materieel"]:
                            st.markdown(f"- {cat}: €{cat_totalen[cat]:,.2f}")
                        totaal = sum(cat_totalen.values())
                        st.metric("Totaal", f"€{totaal:,.2f}")
                else:
                    # Toon laad-knop
                    if st.button("📄 Laad details", key=f"load_{wb['hoofdwerkbon_key']}"):
                        try:
                            service = WerkbonKetenService()
                            keten = service.get_werkbon_keten(
                                wb["hoofdwerkbon_key"],
                                include_kosten_details=True
                            )
                            service.close()
                            st.session_state[cache_key] = keten
                            st.rerun()
                        except Exception as e:
                            st.error(f"Fout: {e}")

elif "werkbonnen_list" in st.session_state:
    st.info("Geen werkbonnen gevonden voor deze filters.")
else:
    st.info("Klik op **Werkbonnen laden** om te beginnen.")


