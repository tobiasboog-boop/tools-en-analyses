"""
Blob Analyse - Zenith Security
Streamlit App voor AI-analyse van werkbon blobvelden

4 Business Case Tabs:
1. Meerwerk Scanner - Detecteer gemiste facturatie
2. Contract Checker - Classificeer contract vs. meerwerk
3. Terugkeer Analyse - Vind terugkerende storingen
4. Rapportage - Maandoverzichten voor rapportages

Documentatie Tab:
5. Data Model - Uitleg over koppelingen tussen blobvelden en werkbonnen
"""

import streamlit as st
import json
import re
import pandas as pd
from pathlib import Path
from collections import defaultdict

# Page config
st.set_page_config(
    page_title="Blob Analyse - Zenith Security",
    page_icon="🔍",
    layout="wide"
)


@st.cache_data
def load_blob_data():
    """Laad de blobvelden sample data."""
    data_path = Path(__file__).parent / "data" / "sample_data.json"
    if not data_path.exists():
        return None
    with open(data_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@st.cache_data
def load_werkbonnen_data():
    """Laad de werkbonnen data uit DWH extract."""
    data_path = Path(__file__).parent / "data" / "werkbonnen_zenith.json"
    if not data_path.exists():
        return None
    with open(data_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# =============================================================================
# USE CASE 1: MEERWERK SCANNER
# =============================================================================

MEERWERK_PATTERNS = {
    "vervangen": {
        "patterns": [r"vervangen", r"vervanging", r"nieuwe?\s+\w+\s+geplaatst"],
        "indicatie": "Component vervanging",
        "gem_waarde": 150
    },
    "accu": {
        "patterns": [r"accu\s*(vervangen|gewisseld|nieuw)", r"batterij\s*(vervangen|nieuw)"],
        "indicatie": "Accu vervanging",
        "gem_waarde": 85
    },
    "pir": {
        "patterns": [r"pir\s*(vervangen|defect|nieuw)", r"detector\s*(vervangen|nieuw)"],
        "indicatie": "PIR/Detector vervanging",
        "gem_waarde": 120
    },
    "camera": {
        "patterns": [r"camera\s*(vervangen|nieuw|geplaatst)", r"recorder\s*(vervangen|nieuw)"],
        "indicatie": "Camera/Recorder vervanging",
        "gem_waarde": 350
    },
    "slot": {
        "patterns": [r"slot\s*(vervangen|nieuw)", r"sleutel\s*(bijgemaakt|nieuw|gemaakt)"],
        "indicatie": "Slot/Sleutel werk",
        "gem_waarde": 75
    },
    "sirene": {
        "patterns": [r"sirene\s*(vervangen|defect|nieuw)"],
        "indicatie": "Sirene vervanging",
        "gem_waarde": 95
    },
    "kabel": {
        "patterns": [r"kabel\s*(getrokken|nieuw|vervangen)", r"bekabeling\s*(nieuw|aangepast)"],
        "indicatie": "Bekabeling werk",
        "gem_waarde": 200
    },
    "software": {
        "patterns": [r"software\s*(update|upgrade)", r"firmware\s*(update|upgrade)"],
        "indicatie": "Software/Firmware update",
        "gem_waarde": 50
    },
    "extra_werk": {
        "patterns": [r"extra\s+\w+", r"bijkomend", r"aanvullend", r"tevens\s+\w+\s+(geplaatst|vervangen)"],
        "indicatie": "Extra werkzaamheden",
        "gem_waarde": 100
    }
}


def scan_for_meerwerk(tekst):
    """Scan een notitie op meerwerk indicatoren."""
    tekst_lower = tekst.lower()
    gevonden = []

    for categorie, config in MEERWERK_PATTERNS.items():
        for pattern in config["patterns"]:
            if re.search(pattern, tekst_lower):
                gevonden.append({
                    "categorie": categorie,
                    "indicatie": config["indicatie"],
                    "geschatte_waarde": config["gem_waarde"]
                })
                break  # Eén match per categorie is genoeg

    return gevonden


def clean_tekst(tekst):
    """Verwijder RTF rommel uit tekst."""
    # Verwijder "Arial;Symbol;" en varianten
    tekst = re.sub(r'^[A-Za-z;]+;\s*\n*', '', tekst)
    # Verwijder leading 'd' die vaak overblijft
    tekst = re.sub(r'^\s*d([A-Z])', r'\1', tekst)
    return tekst.strip()


def run_meerwerk_analyse(blob_data):
    """Voer meerwerk analyse uit op notities MET werkbon koppeling."""
    resultaten = []

    for notitie in blob_data.get("monteur_notities", []):
        # Skip notities zonder werkbon koppeling
        if not notitie.get("werkbon"):
            continue

        tekst = notitie.get("tekst", "")
        tekst_clean = clean_tekst(tekst)
        meerwerk = scan_for_meerwerk(tekst_clean)

        if meerwerk:
            totaal_waarde = sum(m["geschatte_waarde"] for m in meerwerk)
            resultaten.append({
                "id": notitie.get("id"),
                "tekst": tekst_clean[:300],
                "meerwerk_items": meerwerk,
                "aantal_items": len(meerwerk),
                "geschatte_waarde": totaal_waarde,
                "werkbon": notitie.get("werkbon"),
                "sessie_info": notitie.get("sessie_info")
            })

    return sorted(resultaten, key=lambda x: x["geschatte_waarde"], reverse=True)


# =============================================================================
# USE CASE 2: CONTRACT CHECKER
# =============================================================================

CONTRACT_KEYWORDS = [
    "onderhoud", "preventief", "controle", "inspectie", "jaarlijks",
    "periodiek", "checklist", "servicebeurt", "onderhoudsbeurt"
]

MEERWERK_KEYWORDS = [
    "vervangen", "defect", "kapot", "storing", "reparatie", "nieuw",
    "extra", "bijkomend", "uitbreiding", "aanpassing", "wijziging"
]


def classify_werk(tekst):
    """Classificeer werk als contract of meerwerk."""
    tekst_lower = tekst.lower()

    # Vind welke keywords matchen
    contract_matches = [kw for kw in CONTRACT_KEYWORDS if kw in tekst_lower]
    meerwerk_matches = [kw for kw in MEERWERK_KEYWORDS if kw in tekst_lower]

    contract_score = len(contract_matches)
    meerwerk_score = len(meerwerk_matches)

    # Bepaal classificatie
    if meerwerk_score > contract_score:
        classificatie = "MEERWERK"
        confidence = min(95, 50 + (meerwerk_score - contract_score) * 15)
    elif contract_score > meerwerk_score:
        classificatie = "CONTRACT"
        confidence = min(95, 50 + (contract_score - meerwerk_score) * 15)
    else:
        classificatie = "ONZEKER"
        confidence = 50

    return {
        "classificatie": classificatie,
        "confidence": confidence,
        "contract_indicators": contract_score,
        "meerwerk_indicators": meerwerk_score,
        "contract_matches": contract_matches,
        "meerwerk_matches": meerwerk_matches
    }


def run_contract_analyse(blob_data):
    """Voer contract classificatie uit op notities MET werkbon koppeling."""
    resultaten = {"CONTRACT": [], "MEERWERK": [], "ONZEKER": []}

    for notitie in blob_data.get("monteur_notities", []):
        # Skip notities zonder werkbon koppeling
        if not notitie.get("werkbon"):
            continue

        tekst = notitie.get("tekst", "")
        tekst_clean = clean_tekst(tekst)
        classificatie = classify_werk(tekst_clean)

        resultaten[classificatie["classificatie"]].append({
            "id": notitie.get("id"),
            "tekst": tekst_clean[:250],
            "classificatie": classificatie["classificatie"],
            "confidence": classificatie["confidence"],
            "contract_matches": classificatie["contract_matches"],
            "meerwerk_matches": classificatie["meerwerk_matches"],
            "werkbon": notitie.get("werkbon")
        })

    return resultaten


# =============================================================================
# USE CASE 3: TERUGKEER ANALYSE
# =============================================================================

STORING_PATTERNS = [
    r"storing", r"defect", r"kapot", r"niet werkend", r"geen signaal",
    r"probleem", r"fout", r"error", r"alarm", r"vals\s*alarm"
]


def extract_storingen(blob_data):
    """Extraheer storingen uit de data."""
    storingen = []

    # Analyseer storing_meldingen
    for melding in blob_data.get("storing_meldingen", []):
        tekst = melding.get("tekst", "").lower()

        # Tel storing indicatoren
        storing_score = sum(1 for p in STORING_PATTERNS if re.search(p, tekst))

        if storing_score > 0:
            storingen.append({
                "id": melding.get("id"),
                "tekst": melding.get("tekst", "")[:200],
                "type": "storing_melding",
                "score": storing_score
            })

    # Analyseer ook monteur notities
    for notitie in blob_data.get("monteur_notities", []):
        tekst = notitie.get("tekst", "").lower()
        storing_score = sum(1 for p in STORING_PATTERNS if re.search(p, tekst))

        if storing_score >= 2:  # Hogere drempel voor notities
            storingen.append({
                "id": notitie.get("id"),
                "tekst": notitie.get("tekst", "")[:200],
                "type": "monteur_notitie",
                "score": storing_score
            })

    return storingen


def analyse_terugkeer_patronen(blob_data, werkbonnen_data):
    """Analyseer terugkerende storingen en probleemlocaties."""
    # Verzamel alle storingen
    storingen = extract_storingen(blob_data)

    # Groepeer op keywords/type storing
    storing_types = defaultdict(int)
    for storing in storingen:
        tekst = storing["tekst"].lower()
        if "pir" in tekst or "detector" in tekst:
            storing_types["PIR/Detector problemen"] += 1
        elif "camera" in tekst or "recorder" in tekst:
            storing_types["Camera/Video problemen"] += 1
        elif "communicatie" in tekst or "signaal" in tekst:
            storing_types["Communicatie problemen"] += 1
        elif "accu" in tekst or "batterij" in tekst or "stroom" in tekst:
            storing_types["Voeding/Accu problemen"] += 1
        elif "slot" in tekst or "deur" in tekst:
            storing_types["Toegang/Slot problemen"] += 1
        else:
            storing_types["Overige storingen"] += 1

    return {
        "totaal_storingen": len(storingen),
        "storing_types": dict(storing_types),
        "details": sorted(storingen, key=lambda x: x["score"], reverse=True)[:50]
    }


# =============================================================================
# USE CASE 4: RAPPORTAGE
# =============================================================================

def get_rapportage_data(blob_data):
    """Verzamel data voor maandrapportage - alleen notities met werkbon koppeling."""
    rapport_items = []

    for notitie in blob_data.get("monteur_notities", []):
        # Alleen notities met werkbon koppeling
        if not notitie.get("werkbon"):
            continue

        werkbon = notitie.get("werkbon", {})
        tekst = clean_tekst(notitie.get("tekst", ""))

        # Extract datum voor maandgroepering
        melddatum = werkbon.get("melddatum", "")
        maand = melddatum[:7] if melddatum else "Onbekend"  # Format: "2024-01"

        rapport_items.append({
            "werkbon_code": werkbon.get("werkbon_code", ""),
            "klant": werkbon.get("klant", "Onbekend"),
            "monteur": werkbon.get("monteur", "Onbekend"),
            "datum": melddatum[:10] if melddatum else "",
            "maand": maand,
            "status": werkbon.get("status", "").strip(),
            "notitie": tekst,
            "blob_id": notitie.get("id", "")
        })

    return rapport_items


def groepeer_per_maand(rapport_items):
    """Groepeer rapport items per maand."""
    per_maand = defaultdict(list)
    for item in rapport_items:
        per_maand[item["maand"]].append(item)
    return dict(sorted(per_maand.items(), reverse=True))


def groepeer_per_klant(rapport_items):
    """Groepeer rapport items per klant."""
    per_klant = defaultdict(list)
    for item in rapport_items:
        per_klant[item["klant"]].append(item)
    return dict(sorted(per_klant.items()))


def groepeer_per_monteur(rapport_items):
    """Groepeer rapport items per monteur."""
    per_monteur = defaultdict(list)
    for item in rapport_items:
        per_monteur[item["monteur"]].append(item)
    return dict(sorted(per_monteur.items()))


# =============================================================================
# STREAMLIT APP
# =============================================================================

# Load data
blob_data = load_blob_data()
werkbonnen_data = load_werkbonnen_data()

# Header
st.title("🔍 Blob Analyse - Zenith Security")
st.markdown("**Business Case Analyse** van werkbon blobvelden")

st.divider()

# Sidebar
with st.sidebar:
    # Notifica logo
    logo_path = Path(__file__).parent / "assets" / "notifica_logo.jpg"
    if logo_path.exists():
        st.image(str(logo_path), width=120)
        st.divider()

    st.header("Over deze app")
    st.markdown("""
    Deze app analyseert ongestructureerde blobvelden
    uit Syntess werkbonnen voor Zenith Security.

    **4 Business Cases:**
    1. 💰 Meerwerk Scanner
    2. 📋 Contract Checker
    3. 🔄 Terugkeer Analyse
    4. 📊 Rapportage

    **Documentatie:**
    5. 🗂️ Data Model
    """)

    st.divider()
    st.markdown("**Klant:** Zenith Security (1229)")
    st.markdown("**Status:** Pilot / Prototype")

    if blob_data:
        st.divider()
        st.markdown("**Dataset:**")
        totals = blob_data.get("metadata", {}).get("totals", {})
        # Tel notities met werkbon koppeling
        notities_met_werkbon = sum(1 for n in blob_data.get("monteur_notities", []) if n.get("werkbon"))
        totaal_notities = totals.get('monteur_notities', 0)
        st.caption(f"Notities met werkbon: {notities_met_werkbon}/{totaal_notities}")
        st.caption(f"Storingen: {totals.get('storing_meldingen', 0)}")
        st.caption(f"Uren: {totals.get('uren_registraties', 0)}")

# Main tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "💰 Meerwerk Scanner",
    "📋 Contract Checker",
    "🔄 Terugkeer Analyse",
    "📊 Rapportage",
    "🗂️ Data Model"
])

# =============================================================================
# TAB 1: MEERWERK SCANNER
# =============================================================================
with tab1:
    st.header("Meerwerk Scanner")

    # Korte uitleg bovenaan
    st.markdown("""
    Scan monteurnotities op mogelijk **niet-gefactureerd meerwerk**.
    Woorden als "vervangen", "nieuw", "extra" worden automatisch gedetecteerd.
    """)

    with st.expander("Hoe werkt het?"):
        st.markdown("""
        **Detectie keywords:** vervangen, nieuw, accu, pir, camera, slot, kabel, extra

        | Categorie | Geschatte waarde |
        |-----------|------------------|
        | Component vervanging | ~150 EUR |
        | Accu/Batterij | ~85 EUR |
        | PIR/Detector | ~120 EUR |
        | Camera/Recorder | ~350 EUR |
        | Slot/Sleutel | ~75 EUR |
        | Bekabeling | ~200 EUR |
        """)

    st.divider()

    if blob_data:
        resultaten = run_meerwerk_analyse(blob_data)

        if resultaten:
            # === FILTERS ===
            st.subheader("Filters")
            filter_col1, filter_col2, filter_col3 = st.columns(3)

            # Verzamel alle unieke categorieën
            alle_categorieen = set()
            for r in resultaten:
                for m in r["meerwerk_items"]:
                    alle_categorieen.add(m["indicatie"])

            with filter_col1:
                geselecteerde_types = st.multiselect(
                    "Meerwerk type",
                    options=sorted(alle_categorieen),
                    default=[],
                    placeholder="Alle types"
                )

            with filter_col2:
                min_waarde = st.slider(
                    "Minimale waarde (EUR)",
                    min_value=0,
                    max_value=500,
                    value=0,
                    step=25
                )

            with filter_col3:
                zoek_tekst = st.text_input("Zoek in notitie", placeholder="bijv. 'camera'")

            # Pas filters toe
            gefilterd = resultaten
            if geselecteerde_types:
                gefilterd = [r for r in gefilterd if any(
                    m["indicatie"] in geselecteerde_types for m in r["meerwerk_items"]
                )]
            if min_waarde > 0:
                gefilterd = [r for r in gefilterd if r["geschatte_waarde"] >= min_waarde]
            if zoek_tekst:
                gefilterd = [r for r in gefilterd if zoek_tekst.lower() in r["tekst"].lower()]

            st.divider()

            # Samenvatting
            totaal_notities = sum(1 for n in blob_data.get('monteur_notities', []) if n.get("werkbon"))
            totaal_meerwerk = len(gefilterd)
            totaal_waarde = sum(r["geschatte_waarde"] for r in gefilterd)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Notities met werkbon", totaal_notities)
            with col2:
                st.metric("Meerwerk gevonden", f"{totaal_meerwerk} / {len(resultaten)}")
            with col3:
                st.metric("Geschatte waarde", f"{totaal_waarde} EUR")

            st.divider()

            # Toon resultaten als cards
            for i, result in enumerate(gefilterd[:10], 1):
                werkbon = result.get("werkbon", {})
                indicaties = [m["indicatie"] for m in result["meerwerk_items"]]

                # === WERKBON HEADER ===
                if werkbon:
                    werkbon_code = werkbon.get("werkbon_code", "Onbekend")
                    klant = werkbon.get("klant", "")
                    monteur = werkbon.get("monteur", "")
                    datum = werkbon.get("melddatum", "")[:10] if werkbon.get("melddatum") else ""
                    status = werkbon.get("status", "").strip()

                    st.markdown(f"### #{i} | {werkbon_code}")
                    st.caption(f"Klant: {klant} | Monteur: {monteur} | Datum: {datum} | Status: {status}")
                else:
                    st.markdown(f"### #{i} | Werkbon niet gekoppeld")
                    st.caption(f"Blobveld ID: {result.get('id', 'onbekend')}")

                # === TWEE KOLOMMEN: NOTITIE + ANALYSE ===
                col_left, col_right = st.columns([3, 2])

                with col_left:
                    st.markdown("**Monteur notitie:**")
                    # Toon notitie in een box
                    st.code(result["tekst"], language=None)

                with col_right:
                    st.markdown("**Gedetecteerd meerwerk:**")
                    for m in result["meerwerk_items"]:
                        st.write(f"- {m['indicatie']} (~{m['geschatte_waarde']} EUR)")

                    st.markdown(f"**Totaal:** ~{result['geschatte_waarde']} EUR")

                    # Actie vraag
                    st.warning("Actie: Controleer of dit gefactureerd is")

                st.divider()

            # Meer resultaten
            if len(gefilterd) > 10:
                with st.expander(f"Bekijk {len(gefilterd) - 10} overige resultaten"):
                    for i, result in enumerate(gefilterd[10:], 11):
                        werkbon = result.get("werkbon", {})
                        wb_code = werkbon.get("werkbon_code", f"ID: {result.get('id')}") if werkbon else f"ID: {result.get('id')}"
                        indicaties = ", ".join([m["indicatie"] for m in result["meerwerk_items"]])
                        st.write(f"**#{i}** | {wb_code[:40]}... | {indicaties}")

            if len(gefilterd) == 0 and len(resultaten) > 0:
                st.info(f"Geen resultaten met huidige filters. Totaal zonder filter: {len(resultaten)}")

        else:
            st.success("Geen potentieel meerwerk gevonden in de dataset")
    else:
        st.warning("Geen data geladen")

# =============================================================================
# TAB 2: CONTRACT CHECKER
# =============================================================================
with tab2:
    st.header("Contract Checker")

    st.warning("""
    **Status: In ontwikkeling**

    Deze functie wordt pas volledig operationeel wanneer contractgegevens beschikbaar zijn.
    """)

    st.markdown("""
    **Doel:** Werkbonnen automatisch beoordelen tegen contractuele afspraken.

    **Wat is nodig:**
    - Contractgegevens per klant (wat valt onder het servicecontract?)
    - Koppeling tussen klant en contracttype

    **Wanneer operationeel:**
    - Werkbonnen vergelijken met contractafspraken
    - Automatisch signaleren: "Dit valt buiten contract, factureer als meerwerk"
    - Voorkomen dat werk onterecht als contract wordt afgehandeld
    """)

# =============================================================================
# TAB 3: TERUGKEER ANALYSE
# =============================================================================
with tab3:
    st.header("Terugkeer Analyse")

    st.warning("""
    **Status: In ontwikkeling**

    Deze functie wordt krachtiger wanneer we meer historische data en locatiegegevens koppelen.
    """)

    st.markdown("""
    **Doel:** Herkennen van terugkerende storingen bij dezelfde klant of locatie.

    **Waarom is dit waardevol?**

    Door blobvelden te analyseren kunnen we patronen ontdekken die je in losse werkbonnen niet ziet:
    - Klant X heeft in 6 maanden 4x een PIR-storing gehad
    - Locatie Y heeft structurele communicatieproblemen
    - Component Z faalt vaker dan normaal bij bepaalde installaties

    **Wat levert dit op?**
    - Proactief preventief onderhoud aanbieden voordat klant belt
    - Structurele problemen aanpakken ipv steeds opnieuw repareren
    - Extra omzet uit preventieve contracten
    """)

    st.divider()

    st.subheader("Hoe werkt het?")

    st.markdown("""
    **Stap 1: Koppeling leggen**
    ```
    Blobveld (notitie) → Werkbon → Klant/Locatie
    ```
    Via de werkbon-koppeling weten we bij welke klant een storing hoort.

    **Stap 2: Patronen zoeken**
    - Groepeer storingen per klant
    - Tel frequentie per storingstype
    - Identificeer uitschieters (meer dan X storingen in Y maanden)

    **Stap 3: Actie ondernemen**
    - Klanten met terugkerende storingen benaderen
    - Preventief onderhoudscontract aanbieden
    - Root cause aanpakken
    """)

    st.divider()

    st.subheader("Wat is nodig?")

    st.markdown("""
    - **Meer historische data** - Huidige sample is beperkt (198 notities)
    - **Klant-identificatie** - Nu hebben we klantnaam, maar unieke klant-ID is beter
    - **Tijdsperiode** - Data over langere periode om trends te zien
    """)

    st.info("""
    **Voorbeeld van gewenste output:**

    | Klant | Storingen (6 mnd) | Type | Actie |
    |-------|-------------------|------|-------|
    | Lucardi 490 | 4x | PIR/Detector | Preventief contract aanbieden |
    | Zeeman 263 | 3x | Communicatie | Technische inspectie plannen |
    """)

# =============================================================================
# TAB 4: RAPPORTAGE
# =============================================================================
with tab4:
    st.header("Rapportage")

    st.markdown("""
    Genereer overzichten van werkbonnen met monteurnotities voor maandrapportages.
    Niet meer handmatig copy-pasten uit Syntess!
    """)

    st.divider()

    if blob_data:
        # Haal rapportage data op
        rapport_items = get_rapportage_data(blob_data)

        if rapport_items:
            # === FILTERS ===
            st.subheader("Filters")
            filter_col1, filter_col2, filter_col3 = st.columns(3)

            # Verzamel unieke waarden
            alle_maanden = sorted(set(item["maand"] for item in rapport_items if item["maand"] != "Onbekend"), reverse=True)
            alle_klanten = sorted(set(item["klant"] for item in rapport_items))
            alle_monteurs = sorted(set(item["monteur"] for item in rapport_items))

            with filter_col1:
                geselecteerde_maand = st.selectbox(
                    "Periode",
                    options=["Alle"] + alle_maanden,
                    index=0
                )

            with filter_col2:
                geselecteerde_klant = st.selectbox(
                    "Klant",
                    options=["Alle"] + alle_klanten,
                    index=0
                )

            with filter_col3:
                geselecteerde_monteur = st.selectbox(
                    "Monteur",
                    options=["Alle"] + alle_monteurs,
                    index=0
                )

            # Pas filters toe
            gefilterd = rapport_items
            if geselecteerde_maand != "Alle":
                gefilterd = [r for r in gefilterd if r["maand"] == geselecteerde_maand]
            if geselecteerde_klant != "Alle":
                gefilterd = [r for r in gefilterd if r["klant"] == geselecteerde_klant]
            if geselecteerde_monteur != "Alle":
                gefilterd = [r for r in gefilterd if r["monteur"] == geselecteerde_monteur]

            st.divider()

            # === SAMENVATTING ===
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Werkbonnen", len(gefilterd))
            with col2:
                st.metric("Unieke klanten", len(set(r["klant"] for r in gefilterd)))
            with col3:
                st.metric("Unieke monteurs", len(set(r["monteur"] for r in gefilterd)))

            st.divider()

            # === COMPACTE MATRIX WEERGAVE ===
            st.subheader("Overzicht")

            # Maak dataframe voor compacte weergave
            df_data = []
            for item in gefilterd:
                # Verkort notitie voor matrix weergave
                notitie_kort = item['notitie'][:80] + "..." if len(item['notitie']) > 80 else item['notitie']
                df_data.append({
                    "Werkbon": item['werkbon_code'],
                    "Klant": item['klant'][:25] + "..." if len(item['klant']) > 25 else item['klant'],
                    "Monteur": item['monteur'],
                    "Datum": item['datum'],
                    "Status": item['status'],
                    "Notitie": notitie_kort
                })

            df = pd.DataFrame(df_data)

            # Toon als interactieve tabel
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Werkbon": st.column_config.TextColumn("Werkbon", width="small"),
                    "Klant": st.column_config.TextColumn("Klant", width="medium"),
                    "Monteur": st.column_config.TextColumn("Monteur", width="small"),
                    "Datum": st.column_config.TextColumn("Datum", width="small"),
                    "Status": st.column_config.TextColumn("Status", width="small"),
                    "Notitie": st.column_config.TextColumn("Notitie", width="large"),
                }
            )

            # === DETAIL WEERGAVE ===
            st.divider()
            with st.expander("Volledige notities bekijken"):
                for item in gefilterd:
                    st.markdown(f"**{item['werkbon_code']}** | {item['klant']} | {item['monteur']} | {item['datum']}")
                    if item['notitie']:
                        st.text(item['notitie'][:500])
                    st.markdown("---")

            # === EXPORT SECTIE ===
            st.divider()
            st.subheader("Export")

            # CSV download
            csv = df.to_csv(index=False, sep=";")
            st.download_button(
                label="Download als CSV",
                data=csv,
                file_name=f"werkbonnen_rapport_{geselecteerde_maand if geselecteerde_maand != 'Alle' else 'alle'}.csv",
                mime="text/csv"
            )

        else:
            st.info("Geen werkbonnen met notities gevonden in de dataset.")
    else:
        st.warning("Geen data geladen")

# =============================================================================
# TAB 5: DATA MODEL
# =============================================================================
with tab5:
    st.header("🗂️ Data Model & Koppelingen")

    st.markdown("""
    Dit tabblad legt uit hoe de blobvelden uit Syntess gekoppeld worden aan werkbonnen in het DWH,
    en hoe deze data uiteindelijk in het semantisch model terecht komt.
    """)

    st.divider()

    # ===================
    # SECTIE 1: WAT ZIJN BLOBVELDEN?
    # ===================
    st.subheader("📦 Wat zijn Blobvelden?")

    st.markdown("""
    **Blobvelden** zijn ongestructureerde tekstvelden uit het Syntess ERP-systeem.
    Ze bevatten vrije tekst die monteurs invullen, zoals notities en werkbeschrijvingen.

    In Syntess worden deze opgeslagen als **binary large objects (blobs)** - vandaar de naam.
    Wij exporteren ze naar leesbare tekstbestanden voor analyse.
    """)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**RTF Blobvelden** (Rich Text Format)")
        st.code("""
Bron: AT_MWBSESS, AT_UITVBEST, AT_WERK
Format: .txt bestanden met RTF markup
Inhoud: Monteur notities, storingsmeldingen
        """, language="text")

    with col2:
        st.markdown("**XML Blobvelden** (Gestructureerd)")
        st.code("""
Bron: AT_MWBSESS
Format: .txt bestanden met XML data
Inhoud: Urenregistraties (INGELEVERDE_URENREGELS)
        """, language="text")

    st.divider()

    # ===================
    # SECTIE 2: DE BLOBVELD BRONNEN
    # ===================
    st.subheader("📁 Blobveld Bronnen")

    st.markdown("We gebruiken 4 types blobvelden uit 3 verschillende Syntess tabellen:")

    bronnen_data = [
        {"Tabel": "AT_MWBSESS", "Blobveld": "NOTITIE", "Inhoud": "Monteur notities over uitgevoerd werk", "Aantal": blob_data.get("metadata", {}).get("totals", {}).get("monteur_notities", 0) if blob_data else 0},
        {"Tabel": "AT_MWBSESS", "Blobveld": "INGELEVERDE_URENREGELS", "Inhoud": "XML met geregistreerde uren", "Aantal": blob_data.get("metadata", {}).get("totals", {}).get("uren_registraties", 0) if blob_data else 0},
        {"Tabel": "AT_UITVBEST", "Blobveld": "TEKST", "Inhoud": "Storingsmeldingen en werkbeschrijvingen", "Aantal": blob_data.get("metadata", {}).get("totals", {}).get("storing_meldingen", 0) if blob_data else 0},
        {"Tabel": "AT_WERK", "Blobveld": "GC_INFORMATIE", "Inhoud": "Case/werkbon context informatie", "Aantal": blob_data.get("metadata", {}).get("totals", {}).get("werk_context", 0) if blob_data else 0},
    ]

    # Toon als tabel
    st.table(bronnen_data)

    st.divider()

    # ===================
    # SECTIE 3: DE KOPPELING
    # ===================
    st.subheader("🔗 De Koppeling: Blobveld → Werkbon")

    st.markdown("""
    **Het probleem:** Blobvelden bevatten waardevolle tekst, maar hoe weten we bij welke werkbon ze horen?

    **De oplossing:** Via de DWH tabel `werkbonnen."Mobiele uitvoersessies"` kunnen we de koppeling maken.
    """)

    st.info("""
    **De koppelingsketen:**

    ```
    Blobveld bestand (bijv. "123456.NOTITIE.txt")
            ↓
    Blob ID = 123456 (= MobieleuitvoersessieRegelKey)
            ↓
    DWH tabel: werkbonnen."Mobiele uitvoersessies"
            ↓
    DocumentKey (= WerkbonDocumentKey)
            ↓
    DWH tabel: werkbonnen."Documenten"
            ↓
    Werkbon details (code, klant, monteur, status, etc.)
    ```
    """)

    # Visueel diagram
    st.markdown("### Visuele weergave")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.markdown("**📄 Blobveld**")
        st.code("123456.NOTITIE.txt")
        st.caption("Bestandsnaam")

    with col2:
        st.markdown("**→**")
        st.caption("Extract ID")

    with col3:
        st.markdown("**🔑 Sessie Tabel**")
        st.code("""MobieleuitvoersessieRegelKey
= 123456""")
        st.caption("DWH Lookup")

    with col4:
        st.markdown("**→**")
        st.caption("Join op DocumentKey")

    with col5:
        st.markdown("**📋 Werkbon**")
        st.code("""WB211396
Lucardi 490""")
        st.caption("Resultaat")

    st.divider()

    # ===================
    # SECTIE 4: DWH STRUCTUUR
    # ===================
    st.subheader("🗄️ DWH Database Structuur")

    st.markdown("""
    De Data Warehouse (DWH) bevat gestructureerde data uit Syntess, georganiseerd per klant.
    """)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Database connectie:**")
        st.code("""
Host: 10.3.152.9
Port: 5432
Database: 1229 (Zenith Security)
Schema: werkbonnen
        """, language="text")

    with col2:
        st.markdown("**Relevante tabellen:**")
        st.code("""
werkbonnen."Mobiele uitvoersessies"
werkbonnen."Documenten"
werkbonnen."Uren"
        """, language="text")

    st.divider()

    # ===================
    # SECTIE 5: SQL VOORBEELDEN
    # ===================
    st.subheader("💻 SQL Queries")

    with st.expander("Koppeling query: Blob ID → Werkbon"):
        st.code("""
-- Haal werkbon info op via blob ID (MobieleuitvoersessieRegelKey)
SELECT
    s."MobieleuitvoersessieRegelKey" AS blob_id,
    s."DocumentKey",
    d."Werkboncode" AS werkbon_code,
    d."Klantnaam" AS klant,
    d."Status",
    d."Melddatum"
FROM werkbonnen."Mobiele uitvoersessies" s
LEFT JOIN werkbonnen."Documenten" d
    ON s."DocumentKey" = d."DocumentKey"
WHERE s."MobieleuitvoersessieRegelKey" IN (123456, 123457, ...)
        """, language="sql")

    with st.expander("Alle sessies voor een werkbon"):
        st.code("""
-- Haal alle blobvelden op voor een specifieke werkbon
SELECT
    s."MobieleuitvoersessieRegelKey" AS blob_id,
    s."Medewerker",
    s."Datum",
    s."Status"
FROM werkbonnen."Mobiele uitvoersessies" s
WHERE s."DocumentKey" = 'WB211396'
        """, language="sql")

    st.divider()

    # ===================
    # SECTIE 6: SEMANTISCH MODEL
    # ===================
    st.subheader("🧠 Integratie in Semantisch Model")

    st.markdown("""
    De volgende stap is het beschikbaar maken van de blobvelden in het **semantisch model** in Power BI.
    """)

    st.success("""
    **Stap 1: Blobvelden toevoegen (direct te realiseren)**
    1. Nieuwe DWH tabel met blobveld teksten aanmaken
    2. Koppeling leggen naar werkbonnen via `DocumentKey`
    3. Tabel toevoegen aan het semantisch model
    4. Gebruikers kunnen notities direct in Power BI bekijken bij werkbonnen

    **Koppelveld:** `DocumentKey` (= WerkbonDocumentKey)
    """)

    st.info("""
    **Stap 2: AI-verrijking (toekomstige uitbreiding)**
    - Automatische meerwerk detectie
    - Classificatie van werkzaamheden
    - Terugkeer patronen herkenning
    """)

    st.markdown("""
    **Dataflow diagram:**
    ```
    Syntess Blobvelden → Python Extract → DWH Tabel → Semantisch Model → Power BI
                                              ↓
                               (Toekomst: AI verrijking)
    ```
    """)

    st.divider()

    # ===================
    # SECTIE 7: HUIDIGE DATASET STATS
    # ===================
    st.subheader("📊 Huidige Dataset Statistieken")

    if blob_data:
        metadata = blob_data.get("metadata", {})
        totals = metadata.get("totals", {})
        koppeling_stats = metadata.get("werkbon_koppeling", {})

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Totaal blob records", sum(totals.values()) if totals else 0)

        with col2:
            st.metric("Met sessie koppeling", koppeling_stats.get("totaal_sessies_gekoppeld", "N/A"))

        with col3:
            st.metric("Met werkbon details", koppeling_stats.get("totaal_werkbonnen", "N/A"))

        st.markdown("**Per blobveld type:**")
        for veld, aantal in totals.items():
            st.write(f"- {veld.replace('_', ' ').title()}: {aantal}")
    else:
        st.warning("Geen data geladen")

# Footer
st.divider()
st.caption("Blob Analyse v0.5 | Zenith Security Pilot | © Notifica B.V.")
