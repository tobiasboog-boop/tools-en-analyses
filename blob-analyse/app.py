"""
BLOB Analyse — SLA Tracker
============================
Klant: 1229 (Zenith Security) — VASTGEZET, NIET WIJZIGBAAR
Doel:  SLA monitoring werkbonnen — responstijden, herstel, classificatie.

SECURITY:
    - App is locked op klant 1229 (Zenith Security)
    - Geen klant-switcher: Zenith moet zelf in de tool kunnen zonder andere klantdata
    - Data API dwingt permissies af via app_permissions (server-side)
    - Directe DB connecties zijn NIET toegestaan (geeft toegang tot alle DWH's)

Verbinding: Notifica Data API (SDK) — ENIGE toegestane verbindingsmethode
Starten:    pip install -r requirements.txt && streamlit run app.py
"""

import sys
import os
import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta
from pathlib import Path

# Load .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # dotenv optioneel

# SDK importeren (relatief pad in development)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '_sdk'))

from notifica_sdk import NotificaClient, NotificaError

# === Page config ===
st.set_page_config(
    page_title="SLA Tracker — Zenith Security",
    page_icon="📊",
    layout="wide",
)

# === Constanten ===
# SECURITY: Hardcoded klant — GEEN klant-switcher. Zenith (eindgebruiker)
# mag alleen eigen data zien. Data API dwingt dit ook server-side af.
KLANTNUMMER = 1229


# =============================================================================
# AUTHENTICATIE
# =============================================================================

def check_password():
    """Wachtwoord check bij opstarten."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("SLA Tracker — Zenith Security")
        st.caption("SLA monitoring en rapportage")

        with st.form("login_form"):
            password_input = st.text_input("Wachtwoord", type="password")
            submit = st.form_submit_button("Inloggen")

            if submit:
                app_password = os.getenv("APP_PASSWORD", "")
                # Try secrets.toml (Streamlit Cloud), fallback to .env
                try:
                    if hasattr(st, 'secrets') and "APP_PASSWORD" in st.secrets:
                        app_password = st.secrets["APP_PASSWORD"]
                except Exception:
                    pass  # Secrets.toml niet gevonden, gebruik .env
                if not app_password:
                    st.error("Geen APP_PASSWORD geconfigureerd.")
                elif password_input == app_password:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Incorrect wachtwoord")

        st.stop()


check_password()


# =============================================================================
# CLASSIFICATIE TABELLEN (gebaseerd op contractuele SLA-afspraken)
# =============================================================================

# Prioriteit mapping: tekst → nummer
PRIORITEIT_MAP = {
    "Urgent": 1,
    "Medium": 2,
    "Low": 3,
    "Geen SLA": 4,
    "Geen contract": 5,
}

# KPI Response targets (uren) per locatiesoort × prioriteit
# "nbd" = next business day, "be" = best effort, getal = uren
KPI_RESPONSE = {
    "Warehouse": {1: 4, 2: 12, 3: "nbd", 4: "be", 5: "be"},
    "Store":     {1: 12, 2: "nbd", 3: "nbd", 4: "be", 5: "be"},
    "Depot":     {1: 12, 2: "nbd", 3: "nbd", 4: "be", 5: "be"},
    "Fietshub":  {1: 24, 2: "nbd", 3: "nbd", 4: "be", 5: "be"},
    "Office":    {1: 12, 2: "nbd", 3: "nbd", 4: "be", 5: "be"},
}

# KPI Restore targets (uren) per locatiesoort × prioriteit
KPI_RESTORE = {
    "Warehouse": {1: 12, 2: "nbd", 3: "be", 4: "be", 5: "be"},
    "Store":     {1: 24, 2: "nbd", 3: "nbd", 4: "be", 5: "be"},
    "Depot":     {1: 24, 2: "nbd", 3: "nbd", 4: "be", 5: "be"},
    "Fietshub":  {1: "be", 2: "be", 3: "be", 4: "be", 5: "be"},
    "Office":    {1: 24, 2: 24, 3: "nbd", 4: "be", 5: "be"},
}

LOCATIE_SOORTEN = ["Store", "Warehouse", "Depot", "Fietshub", "Office"]
INSTALLATIE_SOORTEN = ["Camera", "Inbraak", "Toegang", "Intercom", "Overig"]


# =============================================================================
# DATA OPHALEN — Alleen via Notifica Data API (SDK)
# SECURITY: Geen directe DB connecties! Die geven toegang tot alle DWH's.
# De Data API dwingt klant-permissies af via app_permissions.
# =============================================================================

@st.cache_resource
def get_client():
    """NotificaClient initialiseren (cached)."""
    try:
        return NotificaClient()
    except NotificaError as e:
        st.error(f"Kan niet verbinden met Data API: {e}")
        st.info("Controleer .env: NOTIFICA_API_URL en NOTIFICA_APP_KEY")
        st.stop()


@st.cache_data(ttl=600)
def load_werkbonnen():
    """Werkbonnen ophalen via Data API. Inclusief AfspraakDatum voor oplossingstijd."""
    client = get_client()
    try:
        df = client.query(KLANTNUMMER, """
            SELECT
                wb."WerkbonDocumentKey",
                wb."Werkbon",
                wb."MeldDatum",
                wb."MeldTijd",
                wb."Klant",
                wb."Debiteur",
                wb."Prioriteit",
                wb."Prioriteit kenmerk",
                wb."Onderaannemer",
                wb."Betreft onderaannemer",
                wb."Meldpersoon",
                wb."Status",
                wb."Documentstatus",
                wb."Opleverdatum",
                wb."AfspraakDatum",
                wb."AfspraakTijd",
                wb."Monteur",
                wb."Type",
                wb."Soort",
                wb."Referentie",
                wb."ParentWerkbonDocumentKey",
                wb."Hoofdwerkbon"
            FROM werkbonnen."Werkbonnen" wb
            ORDER BY wb."MeldDatum" DESC
        """)
        return df
    except NotificaError as e:
        st.error(f"Fout bij ophalen werkbonnen: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=600)
def load_paragrafen(werkbon_keys):
    """Werkbonparagrafen ophalen — voor installatie soort en storing."""
    client = get_client()
    if not werkbon_keys:
        return pd.DataFrame()

    keys_str = ",".join(str(k) for k in werkbon_keys)
    try:
        return client.query(KLANTNUMMER, f"""
            SELECT
                wbp."WerkbonDocumentKey",
                wbp."Werkbonparagraaf",
                wbp."Storing",
                wbp."Oorzaak",
                wbp."Type" as "ParagraafType",
                wbp."Uitvoeringstatus",
                wbp."TijdstipUitgevoerd",
                wbp."InstallatieKey",
                wbp."ObjectKey"
            FROM werkbonnen."Werkbonparagrafen" wbp
            WHERE wbp."WerkbonDocumentKey" IN ({keys_str})
        """)
    except NotificaError as e:
        st.warning(f"Paragrafen ophalen mislukt: {e}")
        return pd.DataFrame()


# =============================================================================
# BLOBVELDEN — Schema discovery + laden via Data API
# Koppeling: Werkbon → Mobiele uitvoersessie → CLOB tabel (maatwerk schema)
# =============================================================================

@st.cache_data(ttl=3600)
def discover_clob_columns():
    """
    Ontdek kolomnamen van CLOB tabellen via Data API (LIMIT 1 query).
    Gecached voor 1 uur — schemanamen veranderen niet frequent.
    Returns: dict met per type: table, columns, id_col, text_col
    """
    client = get_client()
    result = {}
    tables = {
        "monteur_notities": "stg_at_mwbsess_clobs",
        "storing_meldingen": "stg_at_uitvbest_clobs",
        "werk_context": "stg_at_werk_clobs",
        "document_clobs": "stg_at_document_clobs",
    }
    for label, table in tables.items():
        try:
            sample = client.query(KLANTNUMMER, f'SELECT * FROM maatwerk.{table} LIMIT 1')
            if not sample.empty:
                cols = list(sample.columns)
                # BLOB tabellen gebruiken gc_id als key kolom
                id_col = 'gc_id' if 'gc_id' in cols else cols[0]
                text_col = next(
                    (c for c in cols
                     if any(p in c.lower() for p in ['tekst', 'text', 'clob', 'notitie', 'inhoud'])),
                    None
                )
                result[label] = {
                    "table": table,
                    "columns": cols,
                    "id_col": id_col,
                    "text_col": text_col,
                }
        except NotificaError:
            continue
    return result


@st.cache_data(ttl=600)
def load_sessie_koppeling(werkbon_keys):
    """Sessie-koppeling: werkbon (DocumentKey) → MobieleuitvoersessieRegelKey."""
    client = get_client()
    if not werkbon_keys:
        return pd.DataFrame()
    keys_str = ",".join(str(k) for k in werkbon_keys)
    try:
        return client.query(KLANTNUMMER, f"""
            SELECT s."MobieleuitvoersessieRegelKey", s."DocumentKey"
            FROM werkbonnen."Mobiele uitvoersessies" s
            WHERE s."DocumentKey" IN ({keys_str})
        """)
    except NotificaError as e:
        st.warning(f"Sessie-koppeling ophalen mislukt: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=600)
def _load_clob_table(_table_name, _id_col, _text_col, keys_str):
    """Interne helper: laad CLOB data uit één tabel."""
    client = get_client()
    try:
        # BLOB tabellen zijn lowercase, gc_id is lowercase
        return client.query(KLANTNUMMER, f"""
            SELECT {_id_col}, {_text_col}
            FROM maatwerk.{_table_name}
            WHERE {_id_col} IN ({keys_str})
        """)
    except NotificaError:
        return pd.DataFrame()


def load_all_blobvelden(werkbon_keys):
    """
    Laad alle blobvelden gekoppeld aan werkbonnen.
    Flow: werkbon_keys → sessie-koppeling → CLOB tabellen → merge per werkbon.
    Returns: dict met per type een DataFrame [WerkbonDocumentKey, <type>_tekst]
    """
    if not werkbon_keys:
        return {}

    schemas = discover_clob_columns()
    if not schemas:
        return {}

    sessies = load_sessie_koppeling(werkbon_keys)
    if sessies.empty:
        return {}

    sessie_keys = sessies["MobieleuitvoersessieRegelKey"].dropna().unique().tolist()
    if not sessie_keys:
        return {}

    sessie_to_werkbon = dict(zip(
        sessies["MobieleuitvoersessieRegelKey"],
        sessies["DocumentKey"]
    ))
    keys_str = ",".join(str(k) for k in sessie_keys)

    result = {}
    for label, info in schemas.items():
        text_col = info.get("text_col")
        if not text_col:
            continue

        clob_df = _load_clob_table(info["table"], info["id_col"], text_col, keys_str)
        if clob_df.empty:
            continue

        clob_df = clob_df.rename(columns={
            info["id_col"]: "sessie_key",
            text_col: "tekst",
        })
        clob_df["WerkbonDocumentKey"] = clob_df["sessie_key"].map(sessie_to_werkbon)
        clob_df = clob_df.dropna(subset=["WerkbonDocumentKey"])
        if clob_df.empty:
            continue

        # Groepeer per werkbon (meerdere sessies per werkbon mogelijk)
        grouped = (
            clob_df.groupby("WerkbonDocumentKey")["tekst"]
            .apply(lambda x: "\n---\n".join(str(v) for v in x.dropna() if str(v).strip()))
            .reset_index()
        )
        grouped.columns = ["WerkbonDocumentKey", f"{label}_tekst"]
        result[label] = grouped

    return result


# =============================================================================
# DATA VERWERKING
# =============================================================================

def parse_werkbon_code(werkbon_str):
    """Extract werkbon code uit 'WB260714 - Titel' format."""
    if pd.isna(werkbon_str):
        return ""
    parts = str(werkbon_str).split(" - ", 1)
    return parts[0].strip()


def parse_werkbon_titel(werkbon_str):
    """Extract titel uit 'WB260714 - Titel' format."""
    if pd.isna(werkbon_str):
        return ""
    parts = str(werkbon_str).split(" - ", 1)
    return parts[1].strip() if len(parts) > 1 else parts[0].strip()


def parse_klant_naam(klant_str):
    """Extract klantnaam uit '6897 - Naam Winkel Locatie' format."""
    if pd.isna(klant_str):
        return ""
    parts = str(klant_str).split(" - ", 1)
    return parts[1].strip() if len(parts) > 1 else parts[0].strip()


def detect_locatie_soort(klant_naam):
    """Detecteer locatiesoort op basis van klantnaam."""
    naam = str(klant_naam).lower()
    if "warehouse" in naam or "magazijn" in naam:
        return "Warehouse"
    elif "winkel" in naam or "store" in naam:
        return "Store"
    elif "depot" in naam:
        return "Depot"
    elif "fietshub" in naam or "fiets" in naam:
        return "Fietshub"
    elif "office" in naam or "kantoor" in naam or "hoofdkantoor" in naam:
        return "Office"
    return ""


def parse_prioriteit_tekst(prio_str):
    """
    Vertaal DWH prioriteit kenmerk naar SLA prioriteit.
    Gebaseerd op Syntess prioriteit codes:
      4UUR, 5UUR, 12UUR → Urgent
      24UUR, 24 uur      → Medium
      48 uur, 72UUR, Dag → Low
      ZSM                → Urgent (default, vaak aangepast na overleg CB)
      Geen prio          → Geen SLA
      Notitie, Remote, Wachtop, Derden, Draaiboek → handmatig
    """
    if pd.isna(prio_str):
        return ""
    prio = str(prio_str).strip().lower()
    # VOLGORDE IS BELANGRIJK: langere patronen eerst (24uur bevat 4uur als substring)
    # Low
    if "72uur" in prio or "72 uur" in prio:
        return "Low"
    if "48uur" in prio or "48 uur" in prio:
        return "Low"
    if prio == "dag":
        return "Low"
    # Medium
    if "24uur" in prio or "24 uur" in prio:
        return "Medium"
    # Urgent: korte responstijden (ná 24/48/72 check!)
    if "12uur" in prio or "12 uur" in prio:
        return "Urgent"
    if "5uur" in prio or "5 uur" in prio:
        return "Urgent"
    if "4uur" in prio or "4 uur" in prio:
        return "Urgent"
    if "dezelfde dag" in prio:
        return "Urgent"
    if "spoed" in prio:
        return "Urgent"
    # ZSM: default Urgent, maar kan na overleg CB anders zijn
    if "zsm" in prio or "z.s.m" in prio:
        return "Urgent"
    # Geen SLA
    if "geen prio" in prio:
        return "Geen SLA"
    if "derden" in prio or "extern" in prio:
        return "Geen contract"
    # Handmatige classificatie nodig
    if any(t in prio for t in ["notitie", "remote", "wachtop", "draaiboek"]):
        return ""
    return ""


def detect_installatie_soort(paragraaf_tekst, storing_tekst=""):
    """
    Detecteer installatie soort uit werkbonparagraaf en storing omschrijving.
    Zoekt naar keywords in de tekst.
    """
    tekst = f"{paragraaf_tekst or ''} {storing_tekst or ''}".lower()
    if "camera" in tekst or "cctv" in tekst or "video" in tekst:
        return "Camera"
    if "inbraak" in tekst or "alarm" in tekst or "spc" in tekst:
        return "Inbraak"
    if "toegang" in tekst or "interlock" in tekst or "deur" in tekst:
        return "Toegang"
    if "intercom" in tekst:
        return "Intercom"
    return "Overig"


def parse_datetime(date_val, time_val):
    """Combineer datum + tijd kolommen tot datetime."""
    if pd.isna(date_val):
        return pd.NaT

    try:
        dt = pd.to_datetime(date_val)
    except (ValueError, TypeError):
        return pd.NaT

    if pd.notna(time_val):
        try:
            t = pd.to_datetime(time_val)
            dt = dt.replace(hour=t.hour, minute=t.minute, second=t.second)
        except (ValueError, TypeError, AttributeError):
            pass

    return dt


def bereken_uren(start, eind):
    """Bereken aantal uren tussen twee datetimes, afgerond naar boven."""
    if pd.isna(start) or pd.isna(eind):
        return None
    diff = eind - start
    total_minutes = diff.total_seconds() / 60
    if total_minutes < 0:
        return None
    return int(np.ceil(total_minutes / 60))


def check_sla(kpi_waarde, werkelijke_uren, aanmaak_dt, reactie_dt):
    """
    Check of SLA is behaald.

    Returns: "Behaald", "Niet behaald", "Nvt", of ""
    """
    if kpi_waarde == "be":
        return "Behaald"

    if kpi_waarde == "nbd":
        # Next business day: behaald als reactie op dezelfde dag of volgende werkdag
        if pd.isna(aanmaak_dt) or pd.isna(reactie_dt):
            return ""
        aanmaak_date = aanmaak_dt.date() if hasattr(aanmaak_dt, 'date') else aanmaak_dt
        reactie_date = reactie_dt.date() if hasattr(reactie_dt, 'date') else reactie_dt

        # Bereken next business day
        nbd = aanmaak_date + timedelta(days=1)
        while nbd.weekday() >= 5:  # Skip weekend
            nbd += timedelta(days=1)

        if reactie_date <= nbd:
            return "Behaald"
        return "Niet behaald"

    if isinstance(kpi_waarde, (int, float)):
        if werkelijke_uren is None:
            return ""
        if werkelijke_uren <= kpi_waarde:
            return "Behaald"
        return "Niet behaald"

    return ""


def verwerk_werkbonnen(df, paragrafen_df=None):
    """Verwerk ruwe werkbonnen naar SLA tracker format."""
    if df.empty:
        return pd.DataFrame()

    result = pd.DataFrame()

    # Basisvelden uit DWH
    result["werkbon_nummer"] = df["Werkbon"].apply(parse_werkbon_code)
    result["titel"] = df["Werkbon"].apply(parse_werkbon_titel)
    result["locatie_naam"] = df["Klant"].apply(parse_klant_naam)
    result["datum_aanmaak"] = pd.to_datetime(df["MeldDatum"], errors="coerce")
    result["tijd_aanmaak"] = df.get("MeldTijd", pd.Series(dtype="object"))
    result["aanmaak_dt"] = df.apply(
        lambda r: parse_datetime(r.get("MeldDatum"), r.get("MeldTijd")), axis=1
    )

    # Locatiesoort detectie
    result["locatie_soort"] = result["locatie_naam"].apply(detect_locatie_soort)

    # Prioriteit
    prio_kenmerk = df.get("Prioriteit kenmerk", df.get("Prioriteit", pd.Series(dtype="object")))
    result["prio_sla_tekst"] = prio_kenmerk.apply(parse_prioriteit_tekst)
    result["prio_nummer"] = result["prio_sla_tekst"].map(PRIORITEIT_MAP)

    # Onderaannemer
    result["onderaannemer_ja_nee"] = df.get("Betreft onderaannemer", pd.Series(dtype="object")).apply(
        lambda x: str(x).strip() if pd.notna(x) else ""
    )
    result["onderaannemer_naam"] = df.get("Onderaannemer", pd.Series(dtype="object")).apply(parse_klant_naam)

    # Contact / meldpersoon
    result["contact"] = df.get("Meldpersoon", pd.Series(dtype="object"))

    # Status
    result["status"] = df.get("Status", pd.Series(dtype="object")).apply(
        lambda x: str(x).strip() if pd.notna(x) else ""
    )
    result["documentstatus"] = df.get("Documentstatus", pd.Series(dtype="object"))
    result["geannuleerd"] = df.get("Documentstatus", pd.Series(dtype="object")).apply(
        lambda x: "Ja" if pd.notna(x) and "Vervallen" in str(x) else "Nee"
    )

    # Datum oplossing: AfspraakDatum is betrouwbaarder dan Opleverdatum (vaak NULL)
    afspraak = pd.to_datetime(df.get("AfspraakDatum"), errors="coerce")
    oplever = pd.to_datetime(df.get("Opleverdatum"), errors="coerce")
    result["datum_oplossing"] = afspraak.fillna(oplever)

    # Tijd oplossing: AfspraakTijd
    result["tijd_oplossing"] = df.get("AfspraakTijd", pd.Series(dtype="object"))

    # Monteur
    result["monteur"] = df.get("Monteur", pd.Series(dtype="object"))

    # Debiteur (opdrachtgever)
    result["debiteur_naam"] = df.get("Debiteur", pd.Series(dtype="object")).apply(parse_klant_naam)

    # Gerelateerde werkbon
    result["gerelateerde_werkbon"] = df.get("Hoofdwerkbon", pd.Series(dtype="object")).apply(parse_werkbon_code)

    # Referentie
    result["referentie"] = df.get("Referentie", pd.Series(dtype="object"))

    # DWH key voor koppelingen
    result["werkbon_key"] = df["WerkbonDocumentKey"]

    # === Velden uit paragrafen ===
    result["installatie_soort"] = ""
    result["storing_paragraaf"] = ""
    if paragrafen_df is not None and not paragrafen_df.empty:
        # Eerste paragraaf per werkbon (meest relevant)
        para_first = paragrafen_df.drop_duplicates(subset="WerkbonDocumentKey", keep="first")
        para_map = para_first.set_index("WerkbonDocumentKey")

        # Installatie soort detecteren uit paragraaf tekst
        for idx, row_data in result.iterrows():
            wb_key = row_data["werkbon_key"]
            if wb_key in para_map.index:
                para = para_map.loc[wb_key]
                paragraaf_txt = para.get("Werkbonparagraaf", "")
                storing_txt = para.get("Storing", "")
                result.at[idx, "installatie_soort"] = detect_installatie_soort(paragraaf_txt, storing_txt)
                if pd.notna(storing_txt) and str(storing_txt).strip():
                    result.at[idx, "storing_paragraaf"] = str(storing_txt).strip()

    # === Handmatige velden (leeg — worden gevuld door blobveld verrijking) ===
    result["reactie_datum"] = pd.NaT
    result["reactie_tijd"] = ""
    result["prio_na_overleg"] = ""
    result["storing_omschrijving"] = ""
    result["toelichting"] = ""
    result["toelichting_niet_behaald"] = ""
    result["ouderdom_systeem"] = ""  # Zou uit Object.Plaatsingsdatum moeten komen via join

    # === Berekende velden ===
    result["maand"] = result["datum_aanmaak"].dt.month
    result["dag_binnenkomst"] = result["datum_aanmaak"].dt.day_name()

    return result


def bereken_sla_kolommen(df):
    """Bereken SLA kolommen op basis van ingevulde tijden."""
    if df.empty:
        return df

    df = df.copy()

    # Reactie datetime samenstellen
    df["reactie_dt"] = pd.to_datetime(df["reactie_datum"], errors="coerce")

    # Oplossing datetime
    df["oplossing_dt"] = pd.to_datetime(df["datum_oplossing"], errors="coerce")

    # Responstijd (uren)
    df["responstijd_uren"] = df.apply(
        lambda r: bereken_uren(r["aanmaak_dt"], r["reactie_dt"]), axis=1
    )

    # Herstelttijd (uren)
    df["hersteltijd_uren"] = df.apply(
        lambda r: bereken_uren(r["aanmaak_dt"], r["oplossing_dt"]), axis=1
    )

    # KPI targets opzoeken
    df["kpi_response"] = df.apply(
        lambda r: KPI_RESPONSE.get(r["locatie_soort"], {}).get(r["prio_nummer"], "")
        if pd.notna(r["prio_nummer"]) else "", axis=1
    )
    df["kpi_restore"] = df.apply(
        lambda r: KPI_RESTORE.get(r["locatie_soort"], {}).get(r["prio_nummer"], "")
        if pd.notna(r["prio_nummer"]) else "", axis=1
    )

    # SLA check
    df["sla_response"] = df.apply(
        lambda r: check_sla(r["kpi_response"], r["responstijd_uren"],
                            r["aanmaak_dt"], r["reactie_dt"]), axis=1
    )
    df["sla_restore"] = df.apply(
        lambda r: "Nvt" if r["geannuleerd"] == "Ja"
        else check_sla(r["kpi_restore"], r["hersteltijd_uren"],
                       r["aanmaak_dt"], r["oplossing_dt"]), axis=1
    )

    # Timedelta velden (HH:MM:SS formaat)
    def format_timedelta(td):
        """Format timedelta naar HH:MM:SS"""
        if pd.isna(td):
            return ""
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    df["reactietijd"] = (df["reactie_dt"] - df["aanmaak_dt"]).apply(format_timedelta)
    df["response_tijd"] = (df["oplossing_dt"] - df["aanmaak_dt"]).apply(format_timedelta)

    # Responsetijd range categorisering
    def categorize_response_time(uren):
        if pd.isna(uren):
            return ""
        if uren <= 4:
            return "0-4u"
        elif uren <= 12:
            return "4-12u"
        elif uren <= 24:
            return "12-24u"
        else:
            return ">24u"

    df["responsetijd_range"] = df["responstijd_uren"].apply(categorize_response_time)

    return df


# =============================================================================
# BLOBVELD TEKST EXTRACTIE & VERRIJKING
# =============================================================================

def extract_eerste_reactie(tekst):
    """
    Extract eerste reactie uit storingsmelding CLOB tekst.
    Zoekt naar pattern: "Naam DD-MM-YYYY HH:MM:" (typisch Syntess format).
    Voorbeeld: "Twan Lakerveld 15-03-2021 10:47:"
    Returns: (contactpersoon, datum_str, tijd_str) of (None, None, None)
    """
    if not tekst or pd.isna(tekst):
        return None, None, None
    tekst = str(tekst)
    pattern = r'([A-Z][a-z\u00e1\u00e9\u00ed\u00f3\u00fa]+(?:\s+[A-Za-z\u00e1\u00e9\u00ed\u00f3\u00fa]+)*?)\s+(\d{2}-\d{2}-\d{4})\s+(\d{2}:\d{2}):'
    matches = re.findall(pattern, tekst)
    if matches:
        naam, datum, tijd = matches[0]
        return naam.strip(), datum, tijd
    return None, None, None


def extract_storing_omschrijving(tekst):
    """
    Extract storing omschrijving uit CLOB tekst.
    Zoekt na labels als "Beschrijving Melding" of "STORING".
    """
    if not tekst or pd.isna(tekst):
        return ""
    tekst = str(tekst)
    # Na "Beschrijving Melding"
    match = re.search(r'Beschrijving Melding\s*[-:]\s*(.+?)(?:\n{2,}|$)', tekst, re.DOTALL)
    if match:
        return match.group(1).strip()[:500]
    # Na "STORING" label
    match = re.search(r'STORING\s*\n(.+?)(?:\n{2,}|$)', tekst, re.DOTALL)
    if match:
        return match.group(1).strip()[:500]
    # Fallback: strip RTF artifacts
    clean = re.sub(r'\\[a-z]+[\d]*\s?|[{}]', '', tekst)
    clean = re.sub(r'Arial;Symbol;\s*', '', clean)
    clean = clean.strip()
    return clean[:200] if clean else ""


def _strip_rtf(tekst):
    """Strip RTF artifacts uit CLOB tekst."""
    if not tekst or pd.isna(tekst):
        return ""
    t = str(tekst)
    t = re.sub(r'\\[a-z]+[\d]*\s?|[{}]', '', t)
    t = re.sub(r'Arial;Symbol;\s*', '', t)
    t = t.strip()
    return t[:300] if t else ""


def verrijk_met_blobvelden(df, blobvelden_dict):
    """
    Verrijk werkbonnen DataFrame met blobveld data.
    Vult 'handmatige velden' aan met data uit CLOB tabellen:
    - reactie_datum/tijd uit storing_meldingen (AT_UITVBEST)
    - storing_omschrijving uit storing_meldingen
    - toelichting uit monteur_notities (AT_MWBSESS) of werk_context (AT_WERK)
    """
    if not blobvelden_dict or df.empty:
        return df

    df = df.copy()

    # --- Storing meldingen → reactie datum/tijd, storing omschrijving ---
    if "storing_meldingen" in blobvelden_dict:
        storing = blobvelden_dict["storing_meldingen"]
        merged = df[["werkbon_key"]].merge(
            storing, left_on="werkbon_key", right_on="WerkbonDocumentKey", how="left"
        )
        tekst_col = "storing_meldingen_tekst"
        if tekst_col in merged.columns:
            extracted = merged[tekst_col].apply(extract_eerste_reactie)
            reactie_datum_str = extracted.apply(lambda x: x[1] if x else None)
            reactie_tijd_str = extracted.apply(lambda x: x[2] if x else None)

            mask_leeg = df["reactie_datum"].isna()
            df.loc[mask_leeg, "reactie_datum"] = pd.to_datetime(
                reactie_datum_str[mask_leeg], format="%d-%m-%Y", errors="coerce"
            )
            df.loc[mask_leeg, "reactie_tijd"] = reactie_tijd_str[mask_leeg]

            mask_storing = df["storing_omschrijving"] == ""
            df.loc[mask_storing, "storing_omschrijving"] = (
                merged.loc[mask_storing, tekst_col].apply(extract_storing_omschrijving)
            )

    # --- Monteur notities → toelichting ---
    if "monteur_notities" in blobvelden_dict:
        notities = blobvelden_dict["monteur_notities"]
        merged = df[["werkbon_key"]].merge(
            notities, left_on="werkbon_key", right_on="WerkbonDocumentKey", how="left"
        )
        tekst_col = "monteur_notities_tekst"
        if tekst_col in merged.columns:
            mask_leeg = df["toelichting"] == ""
            df.loc[mask_leeg, "toelichting"] = merged.loc[mask_leeg, tekst_col].apply(_strip_rtf)

    # --- Storing paragraaf als fallback voor storing_omschrijving ---
    if "storing_paragraaf" in df.columns:
        mask_leeg = df["storing_omschrijving"] == ""
        mask_para = df["storing_paragraaf"].fillna("").str.strip() != ""
        df.loc[mask_leeg & mask_para, "storing_omschrijving"] = df.loc[mask_leeg & mask_para, "storing_paragraaf"]

    # --- Werk context → toelichting fallback ---
    if "werk_context" in blobvelden_dict:
        context = blobvelden_dict["werk_context"]
        merged = df[["werkbon_key"]].merge(
            context, left_on="werkbon_key", right_on="WerkbonDocumentKey", how="left"
        )
        tekst_col = "werk_context_tekst"
        if tekst_col in merged.columns:
            mask_leeg = df["toelichting"] == ""
            df.loc[mask_leeg, "toelichting"] = merged.loc[mask_leeg, tekst_col].apply(_strip_rtf)

    return df


# =============================================================================
# STREAMLIT UI
# =============================================================================

# Data laden via Data API
with st.spinner("Werkbonnen laden via Data API..."):
    raw_df = load_werkbonnen()

if raw_df.empty:
    st.warning("Geen werkbonnen gevonden.")
    st.info("Controleer de Data API verbinding (.env: NOTIFICA_API_URL en NOTIFICA_APP_KEY)")
    st.stop()

data_source = "Data API"

# Paragrafen laden (voor installatie soort, storing)
werkbon_keys = raw_df["WerkbonDocumentKey"].dropna().unique().tolist()
paragrafen_df = load_paragrafen(werkbon_keys)

# Blobvelden laden via sessie-koppeling
with st.spinner("Blobvelden laden..."):
    blobvelden_dict = load_all_blobvelden(werkbon_keys)

# Verwerken en verrijken met paragrafen + blobvelden
df = verwerk_werkbonnen(raw_df, paragrafen_df)
df = verrijk_met_blobvelden(df, blobvelden_dict)
df = bereken_sla_kolommen(df)

# === SIDEBAR ===
with st.sidebar:
    st.header("Filters")

    # Opdrachtgever (debiteur)
    def parse_debiteur_naam(deb):
        if pd.isna(deb):
            return ""
        parts = str(deb).split(" - ", 1)
        return parts[1].strip() if len(parts) > 1 else parts[0].strip()

    alle_debiteuren = sorted(
        df["debiteur_naam"].dropna().unique().tolist()
    ) if "debiteur_naam" in df.columns else []
    sel_opdrachtgever = st.selectbox(
        "Opdrachtgever",
        options=["Alle"] + alle_debiteuren,
        index=0  # Standaard: toon alle opdrachtgevers
    )

    # Periode
    min_date = df["datum_aanmaak"].min()
    max_date = df["datum_aanmaak"].max()
    if pd.notna(min_date) and pd.notna(max_date):
        date_range = st.date_input(
            "Periode",
            value=(max_date - timedelta(days=90), max_date),
            min_value=min_date,
            max_value=max_date,
        )
    else:
        date_range = None

    # Locatiesoort
    locatie_opties = ["Alle"] + sorted(df["locatie_soort"].dropna().unique().tolist())
    sel_locatie = st.selectbox("Locatiesoort", locatie_opties)

    # Prioriteit
    prio_opties = ["Alle"] + sorted(df["prio_sla_tekst"].dropna().unique().tolist())
    sel_prio = st.selectbox("Prioriteit", prio_opties)

    # Status
    status_opties = ["Alle"] + sorted(df["status"].dropna().unique().tolist())
    sel_status = st.selectbox("Status", status_opties)

    # SLA filter
    sla_opties = ["Alle", "Behaald", "Niet behaald", "Nog onbekend"]
    sel_sla = st.selectbox("SLA Response", sla_opties)

    st.divider()
    st.caption(f"Data bron: {data_source}")
    if blobvelden_dict:
        blob_labels = ", ".join(blobvelden_dict.keys())
        st.caption(f"Blobvelden: {blob_labels}")
    else:
        st.caption("Blobvelden: niet beschikbaar")
    if st.button("Ververs data"):
        st.cache_data.clear()
        st.rerun()

# === HEADER ===
opdrachtgever_label = sel_opdrachtgever if sel_opdrachtgever != "Alle" else "Alle opdrachtgevers"
st.title(f"SLA Tracker — {opdrachtgever_label}")
st.caption(f"Zenith Security (1229) | Bron: {data_source} | {len(df)} werkbonnen")
st.divider()

# === FILTERS TOEPASSEN ===
filtered = df.copy()

if sel_opdrachtgever != "Alle":
    filtered = filtered[filtered["debiteur_naam"] == sel_opdrachtgever]

if date_range and len(date_range) == 2:
    start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
    filtered = filtered[
        (filtered["datum_aanmaak"] >= start) & (filtered["datum_aanmaak"] <= end + timedelta(days=1))
    ]

if sel_locatie != "Alle":
    filtered = filtered[filtered["locatie_soort"] == sel_locatie]
if sel_prio != "Alle":
    filtered = filtered[filtered["prio_sla_tekst"] == sel_prio]
if sel_status != "Alle":
    filtered = filtered[filtered["status"] == sel_status]
if sel_sla == "Behaald":
    filtered = filtered[filtered["sla_response"] == "Behaald"]
elif sel_sla == "Niet behaald":
    filtered = filtered[filtered["sla_response"] == "Niet behaald"]
elif sel_sla == "Nog onbekend":
    filtered = filtered[filtered["sla_response"] == ""]

# === KPI METRICS ===
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("Werkbonnen", len(filtered))
with col2:
    behaald_resp = len(filtered[filtered["sla_response"] == "Behaald"])
    totaal_resp = len(filtered[filtered["sla_response"].isin(["Behaald", "Niet behaald"])])
    pct = f"{(behaald_resp / totaal_resp * 100):.0f}%" if totaal_resp > 0 else "—"
    st.metric("SLA Response", pct)
with col3:
    behaald_rest = len(filtered[filtered["sla_restore"] == "Behaald"])
    totaal_rest = len(filtered[filtered["sla_restore"].isin(["Behaald", "Niet behaald"])])
    pct_rest = f"{(behaald_rest / totaal_rest * 100):.0f}%" if totaal_rest > 0 else "—"
    st.metric("SLA Restore", pct_rest)
with col4:
    niet_behaald = len(filtered[filtered["sla_response"] == "Niet behaald"])
    st.metric("Niet behaald", niet_behaald)
with col5:
    open_wb = len(filtered[filtered["status"].str.contains("Aanmaak|Ingepland", case=False, na=False)])
    st.metric("Open", open_wb)

st.divider()

# === TABS ===
tab_overzicht, tab_detail, tab_classificatie, tab_export = st.tabs(
    ["Overzicht", "Detail", "Classificatie", "Export"]
)

# --- TAB 1: OVERZICHT ---
with tab_overzicht:
    # Tabel met kernkolommen
    display_cols = {
        "werkbon_nummer": "Werkbon",
        "datum_aanmaak": "Datum",
        "locatie_naam": "Locatie",
        "locatie_soort": "Type locatie",
        "prio_sla_tekst": "Prioriteit",
        "onderaannemer_ja_nee": "OA",
        "status": "Status",
        "responstijd_uren": "Response (u)",
        "hersteltijd_uren": "Herstel (u)",
        "kpi_response": "KPI resp.",
        "kpi_restore": "KPI herst.",
        "sla_response": "SLA resp.",
        "sla_restore": "SLA herst.",
    }

    display_df = filtered[list(display_cols.keys())].rename(columns=display_cols)

    # Format datum
    if "Datum" in display_df.columns:
        display_df["Datum"] = pd.to_datetime(display_df["Datum"]).dt.strftime("%d-%m-%Y")

    # Kleuren voor SLA kolommen
    def color_sla(val):
        if val == "Behaald":
            return "background-color: #DCFCE7; color: #059669"
        elif val == "Niet behaald":
            return "background-color: #FEE2E2; color: #DC2626"
        elif val == "Nvt":
            return "background-color: #F3F4F6; color: #6B7280"
        return ""

    styled = display_df.style.map(color_sla, subset=["SLA resp.", "SLA herst."])

    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        height=500,
    )

    # SLA verdeling per locatiesoort
    st.subheader("SLA per locatiesoort")
    if not filtered.empty:
        sla_per_locatie = filtered.groupby("locatie_soort").agg(
            totaal=("werkbon_nummer", "count"),
            behaald_resp=("sla_response", lambda x: (x == "Behaald").sum()),
            niet_behaald_resp=("sla_response", lambda x: (x == "Niet behaald").sum()),
        ).reset_index()
        sla_per_locatie.columns = ["Locatiesoort", "Totaal", "Behaald", "Niet behaald"]
        sla_per_locatie["Score"] = (
            sla_per_locatie["Behaald"] /
            (sla_per_locatie["Behaald"] + sla_per_locatie["Niet behaald"]).replace(0, np.nan) * 100
        ).round(0).fillna(0).astype(int).astype(str) + "%"

        st.dataframe(sla_per_locatie, use_container_width=True, hide_index=True)


# --- TAB 2: DETAIL ---
with tab_detail:
    st.subheader("Werkbon detail")

    if not filtered.empty:
        werkbon_opties = filtered["werkbon_nummer"].tolist()
        sel_werkbon = st.selectbox("Selecteer werkbon", werkbon_opties)

        if sel_werkbon:
            row = filtered[filtered["werkbon_nummer"] == sel_werkbon].iloc[0]

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Basisgegevens**")
                st.write(f"**Werkbon:** {row['werkbon_nummer']}")
                st.write(f"**Titel:** {row['titel']}")
                st.write(f"**Locatie:** {row['locatie_naam']}")
                st.write(f"**Locatiesoort:** {row['locatie_soort'] or '—'}")
                st.write(f"**Datum aanmaak:** {row['datum_aanmaak']}")
                st.write(f"**Prioriteit:** {row['prio_sla_tekst'] or '—'}")
                st.write(f"**Status:** {row['status']}")

            with col2:
                st.markdown("**SLA informatie**")
                st.write(f"**Onderaannemer:** {row['onderaannemer_ja_nee']} — {row['onderaannemer_naam']}")
                st.write(f"**Contact:** {row['contact'] or '—'}")
                st.write(f"**Monteur:** {row['monteur'] or '—'}")
                st.write(f"**Geannuleerd:** {row['geannuleerd']}")
                st.write(f"**Responstijd:** {row['responstijd_uren'] or '—'} uur")
                st.write(f"**Hersteltijd:** {row['hersteltijd_uren'] or '—'} uur")
                st.write(f"**KPI Response:** {row['kpi_response']}")
                st.write(f"**KPI Restore:** {row['kpi_restore']}")

            col3, col4 = st.columns(2)
            with col3:
                sla_resp = row["sla_response"]
                color = "#059669" if sla_resp == "Behaald" else "#DC2626" if sla_resp == "Niet behaald" else "#6B7280"
                st.markdown(f"**SLA Response:** <span style='color:{color};font-weight:bold'>{sla_resp or '—'}</span>",
                            unsafe_allow_html=True)
            with col4:
                sla_rest = row["sla_restore"]
                color = "#059669" if sla_rest == "Behaald" else "#DC2626" if sla_rest == "Niet behaald" else "#6B7280"
                st.markdown(f"**SLA Restore:** <span style='color:{color};font-weight:bold'>{sla_rest or '—'}</span>",
                            unsafe_allow_html=True)

            # Gerelateerde werkbon
            if row.get("gerelateerde_werkbon"):
                st.write(f"**Gerelateerde werkbon:** {row['gerelateerde_werkbon']}")

            # Blobveld data (uit CLOB tabellen)
            st.divider()
            st.markdown("**Blobveld data**")
            col5, col6 = st.columns(2)
            with col5:
                storing = row.get("storing_omschrijving", "")
                st.write(f"**Storing omschrijving:** {storing or '—'}")
                toel = row.get("toelichting", "")
                st.write(f"**Toelichting:** {toel or '—'}")
            with col6:
                r_datum = row.get("reactie_datum")
                r_tijd = row.get("reactie_tijd", "")
                datum_str = pd.Timestamp(r_datum).strftime("%d-%m-%Y") if pd.notna(r_datum) else "—"
                st.write(f"**Reactie datum:** {datum_str}")
                st.write(f"**Reactie tijd:** {r_tijd or '—'}")
    else:
        st.info("Geen werkbonnen in huidige selectie.")


# --- TAB 3: CLASSIFICATIE ---
with tab_classificatie:
    st.subheader("SLA Classificatie Tabellen")

    st.markdown("**KPI Response targets** (uren)")
    resp_data = []
    for loc in LOCATIE_SOORTEN:
        row = {"Locatiesoort": loc}
        for prio_naam, prio_num in PRIORITEIT_MAP.items():
            val = KPI_RESPONSE.get(loc, {}).get(prio_num, "—")
            row[prio_naam] = val
        resp_data.append(row)
    st.dataframe(pd.DataFrame(resp_data), use_container_width=True, hide_index=True)

    st.markdown("**KPI Restore targets** (uren)")
    rest_data = []
    for loc in LOCATIE_SOORTEN:
        row = {"Locatiesoort": loc}
        for prio_naam, prio_num in PRIORITEIT_MAP.items():
            val = KPI_RESTORE.get(loc, {}).get(prio_num, "—")
            row[prio_naam] = val
        rest_data.append(row)
    st.dataframe(pd.DataFrame(rest_data), use_container_width=True, hide_index=True)

    st.markdown("""
    **Legenda:**
    - Getal = maximaal aantal uren
    - **nbd** = next business day (volgende werkdag)
    - **be** = best effort (geen harde SLA)
    """)


# --- TAB 4: EXPORT ---
with tab_export:
    st.subheader("Export")

    # Volledige dataset voor export (37 kolommen, 1-op-1 met Excel)
    export_cols = {
        "werkbon_nummer": "Werkbon nummer",
        "gerelateerde_werkbon": "Gerelateerde werkbon",
        "datum_aanmaak": "Datum aanmaak",
        "tijd_aanmaak": "Tijd aanmaak",
        "locatie_naam": "Locatie naam",
        "titel": "Titel",
        "storing_omschrijving": "Storing omschrijving",
        "locatie_soort": "Locatie soort",
        "installatie_soort": "Installatie soort",
        "onderaannemer_ja_nee": "Onderaannemer",
        "onderaannemer_naam": "Welke onderaannemer? (indien bekend)",
        "prio_sla_tekst": "Prio volgens SLA",
        "reactie_datum": "Reactie datum",
        "reactie_tijd": "Reactie tijd",
        "contact": "Contact CB",
        "prio_na_overleg": "Prio na overleg CB",
        "datum_oplossing": "Datum oplossing",
        "tijd_oplossing": "Tijd oplossing",
        "geannuleerd": "Geannuleerd?",
        "toelichting": "Toelichting",
        "ouderdom_systeem": "Ouderdom systeem",
        "maand": "Maand",
        "aanmaak_dt": "aanmaak d+t",
        "reactie_dt": "reactie d+t",
        "oplossing_dt": "response d+t",
        "reactietijd": "reactietijd",
        "response_tijd": "response tijd",
        "prio_nummer": "Prio",
        "responstijd_uren": "reasponsetijd uren",
        "hersteltijd_uren": "restoretijd uren",
        "kpi_response": "KPI response",
        "kpi_restore": "KPI restore",
        "sla_response": "SLA response",
        "sla_restore": "SLA restore",
        "responsetijd_range": "responsetijd range",
        "dag_binnenkomst": "Dag binnenkomst",
        "toelichting_niet_behaald": "Toelichting bij Niet Behaald",
    }

    export_df = filtered[list(export_cols.keys())].rename(columns=export_cols)

    # CSV
    csv_data = export_df.to_csv(index=False, sep=";")
    st.download_button(
        label="Download CSV",
        data=csv_data,
        file_name=f"sla_tracker_coolblue_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )

    # Excel
    from io import BytesIO
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="SLA Tracker")
    st.download_button(
        label="Download Excel",
        data=buffer.getvalue(),
        file_name=f"sla_tracker_coolblue_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.caption(f"{len(export_df)} rijen | Gefilterde selectie")


# === FOOTER ===
st.divider()
st.caption("SLA Tracker v1.0 | Zenith Security (1229) | Notifica B.V.")
