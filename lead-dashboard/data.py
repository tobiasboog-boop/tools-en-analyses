"""
Data Fetching & Scoring
=======================
Alle data-ophaal functies (EmailOctopus, Pipedrive, Website, Power BI)
en scoring/health berekeningen.
"""
import streamlit as st
import pandas as pd
import requests
import re
import os
import hashlib
from datetime import datetime, timedelta
from dotenv import load_dotenv

from config import FUNNEL_CONFIG, INTERNE_MEDEWERKERS

load_dotenv()

# --- Constants ---
PIPEDRIVE_BASE = "https://notifica.pipedrive.com/api/v1"
EMAILOCTOPUS_LIST_ID = "729f9b7e-12ec-11f1-acfe-6b0432c704d7"
EMAILOCTOPUS_BASE = "https://emailoctopus.com/api/1.6"
ML_EXPORT_DIR = os.path.join(os.path.dirname(__file__), "docs", "mailerlite_export")
ML_ACTIVITY_PATH = os.path.join(ML_EXPORT_DIR, "campaign_activity.csv")
ML_CAMPAIGNS_PATH = os.path.join(ML_EXPORT_DIR, "campaigns.csv")
ML_SUBSCRIBERS_PATH = os.path.join(ML_EXPORT_DIR, "subscribers.csv")
POWERBI_EXCEL_DEFAULT = os.path.join(
    os.path.expanduser("~"), "Downloads",
    "Power BI activity Report views (5).xlsx"
)
POWERBI_CACHE_PATH = os.path.join(os.path.dirname(__file__), "data", "powerbi_cache.xlsx")


def get_secret(key, default=""):
    """Haal secret op: eerst st.secrets, dan os.environ, dan .env."""
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError, AttributeError):
        return os.getenv(key, default)


# ============================================================
#  FUNNEL PHASE
# ============================================================

def get_current_funnel_phase():
    """Bereken huidige weekfase en pijler op basis van cyclus startdatum."""
    start = datetime.strptime(FUNNEL_CONFIG["cyclus_startdatum"], "%Y-%m-%d")
    today = datetime.now()
    days_since = (today - start).days

    weekfasen = FUNNEL_CONFIG["weekfasen"]

    if days_since < 0:
        return {
            "pijler": FUNNEL_CONFIG["pijlers"][FUNNEL_CONFIG["huidige_pijler"]],
            "week_nr": 0,
            "weekfase": "Voorbereiding",
            "weekfase_beschrijving": "Cyclus is nog niet gestart.",
            "dag_in_week": 0,
            "maand_nr": 0,
        }

    maand_nr = days_since // 28
    dag_in_maand = days_since % 28
    week_nr = (dag_in_maand // 7) + 1  # 1-4
    dag_in_week = (dag_in_maand % 7) + 1  # 1-7

    pijler_idx = (FUNNEL_CONFIG["huidige_pijler"] + maand_nr) % len(FUNNEL_CONFIG["pijlers"])
    pijler = FUNNEL_CONFIG["pijlers"][pijler_idx]

    fase = weekfasen.get(min(week_nr, 4), weekfasen[1])

    return {
        "pijler": pijler,
        "week_nr": min(week_nr, 4),
        "weekfase": fase["naam"],
        "weekfase_beschrijving": fase["beschrijving"],
        "dag_in_week": dag_in_week,
        "maand_nr": maand_nr + 1,
    }


# ============================================================
#  CALL LIST
# ============================================================

def get_weekly_call_list(leads_df, health_df, week_nr):
    """Filter bellijst op basis van weekfase. Returns max 10-15 contacten."""
    if leads_df.empty:
        return pd.DataFrame()

    if week_nr == 1:
        return pd.DataFrame()

    elif week_nr == 2:
        warm = leads_df[
            (leads_df["Web Score"] >= 6) | (leads_df["Open Score"] >= 9)
        ].copy()
        return warm.head(10)

    elif week_nr == 3:
        webinar_proxy = leads_df[
            (leads_df["Clicks"] >= 2) | (leads_df["Totaal"] >= 15)
        ].copy()
        return webinar_proxy.head(15)

    elif week_nr == 4:
        multi_signal = leads_df[
            (leads_df["Web Score"] >= 4) &
            (leads_df["Open Score"] >= 3) &
            (leads_df["Totaal"] >= 12)
        ].copy()
        return multi_signal.head(10)

    return pd.DataFrame()


# ============================================================
#  DATA FETCHING
# ============================================================

@st.cache_data(ttl=3600)
def load_historical_engagement():
    """Laad historische opens/clicks per subscriber uit MailerLite export."""
    if not os.path.exists(ML_ACTIVITY_PATH):
        return {}
    try:
        df = pd.read_csv(ML_ACTIVITY_PATH)
        agg = df.groupby("subscriber_email").agg(
            opens=("opens_count", "sum"),
            clicks=("clicks_count", "sum"),
        ).to_dict("index")
        return {k.lower().strip(): v for k, v in agg.items()}
    except Exception:
        return {}


@st.cache_data(ttl=600)
def fetch_emailoctopus_campaign_activity():
    """
    Haal per-subscriber opens/clicks op uit EmailOctopus campagnes.
    Blends met historische MailerLite data.
    Returns dict: {email_lower: {opens, clicks}}
    """
    api_key = get_secret("EMAILOCTOPUS_API_KEY")
    hist = load_historical_engagement()
    combined = dict(hist)  # start met ML historisch

    if not api_key:
        return combined

    try:
        # Haal lijst van verzonden campagnes op
        r = requests.get(
            f"{EMAILOCTOPUS_BASE}/campaigns",
            params={"api_key": api_key, "limit": 100},
            timeout=20,
        )
        if r.status_code != 200:
            return combined
        campaigns = [c for c in r.json().get("data", []) if c.get("status") == "sent"]
        if not campaigns:
            return combined

        # Per campagne: haal opened + clicked subscribers op
        for campaign in campaigns:
            cid = campaign.get("id")
            for report_type in ["opened", "clicked"]:
                page = 1
                while True:
                    rr = requests.get(
                        f"{EMAILOCTOPUS_BASE}/campaigns/{cid}/reports/{report_type}",
                        params={"api_key": api_key, "limit": 100, "page": page},
                        timeout=15,
                    )
                    if rr.status_code != 200:
                        break
                    batch = rr.json().get("data", [])
                    if not batch:
                        break
                    for contact in batch:
                        email = (contact.get("email_address") or "").lower().strip()
                        if not email:
                            continue
                        if email not in combined:
                            combined[email] = {"opens": 0, "clicks": 0}
                        if report_type == "opened":
                            combined[email]["opens"] = combined[email].get("opens", 0) + 1
                        else:
                            combined[email]["clicks"] = combined[email].get("clicks", 0) + 1
                    if not rr.json().get("paging", {}).get("next"):
                        break
                    page += 1
    except Exception:
        pass

    return combined


# Stage-prioriteit voor sortering
_DEAL_STAGE_BONUS = {
    "Offerte verstuurd": 20,
    "Offerte aanmaken": 12,
    "Intern akkoord scope & offerte": 12,
    "Offerte": 12,
    "Vervolg contact na 1e afspraak": 8,
    "Programma van Eisen (scoping)": 8,
    "Interesse getoond": 5,
    "Contact gehad": 3,
    "Tijdelijk on Hold": 0,
}


@st.cache_data(ttl=600)
def fetch_pipedrive_deals():
    """
    Haal open deals op uit Pipedrive.
    Returns dict: {email_lower: {deal_fase, deal_waarde, deal_bonus, deal_titel}}
    """
    token = get_secret("PIPEDRIVE_API_TOKEN")
    if not token:
        return {}

    # Stages ophalen
    try:
        r = requests.get(f"{PIPEDRIVE_BASE}/stages", params={"api_token": token}, timeout=15)
        stages = {s["id"]: s["name"] for s in (r.json().get("data") or [])}
    except Exception:
        stages = {}

    deals = {}
    start = 0
    while True:
        try:
            r = requests.get(
                f"{PIPEDRIVE_BASE}/deals",
                params={"api_token": token, "limit": 500, "start": start, "status": "open"},
                timeout=30,
            )
            if r.status_code != 200:
                break
            data = r.json()
            batch = data.get("data") or []
            if not batch:
                break

            for deal in batch:
                person = deal.get("person_id") or {}
                emails = person.get("email") or []
                email = ""
                for e in emails:
                    val = (e.get("value") or "").lower().strip()
                    if val and (e.get("primary") or not email):
                        email = val
                if not email:
                    continue

                stage_id = deal.get("stage_id")
                stage_name = stages.get(stage_id, "Onbekend")
                bonus = _DEAL_STAGE_BONUS.get(stage_name, 3)
                value = deal.get("value") or 0

                if email not in deals or bonus > deals[email]["deal_bonus"]:
                    deals[email] = {
                        "deal_fase": stage_name,
                        "deal_waarde": value,
                        "deal_bonus": bonus,
                        "deal_titel": deal.get("title", ""),
                        "org_name": deal.get("org_name", ""),
                        "deal_id": deal.get("id"),
                        "stage_id": stage_id,
                    }

            pag = data.get("additional_data", {}).get("pagination", {})
            if not pag.get("more_items_in_collection"):
                break
            start = pag.get("next_start", start + 500)
        except Exception:
            break

    return deals


@st.cache_data(ttl=600)
def fetch_emailoctopus_subscribers():
    """Haal subscribers op uit EmailOctopus + historische engagement. Returns (df, status)."""
    api_key = get_secret("EMAILOCTOPUS_API_KEY")
    if not api_key:
        return pd.DataFrame(), "no_token"

    hist = load_historical_engagement()
    all_subs = []
    page = 1

    while True:
        try:
            r = requests.get(
                f"{EMAILOCTOPUS_BASE}/lists/{EMAILOCTOPUS_LIST_ID}/contacts",
                params={"api_key": api_key, "limit": 100, "page": page},
                timeout=30,
            )
            if r.status_code in (403, 429, 503):
                return pd.DataFrame(), "error"
            if r.status_code != 200:
                return pd.DataFrame(), "error"
            data = r.json()
            batch = data.get("data", [])
            if not batch:
                break
            all_subs.extend(batch)
            if not data.get("paging", {}).get("next"):
                break
            page += 1
        except Exception:
            return pd.DataFrame(), "error"

    if not all_subs:
        return pd.DataFrame(), "empty"

    records = []
    for sub in all_subs:
        fields = sub.get("fields", {})
        if not isinstance(fields, dict):
            fields = {}
        first = (fields.get("FirstName") or "").strip()
        last = (fields.get("LastName") or "").strip()
        name = f"{first} {last}".strip()
        email = (sub.get("email_address") or "").lower().strip()

        engagement = hist.get(email, {})
        records.append({
            "email": email,
            "name": name,
            "company": (fields.get("COMPANY") or "").strip(),
            "opened": int(engagement.get("opens", 0)),
            "clicked": int(engagement.get("clicks", 0)),
        })
    return pd.DataFrame(records), "ok"


@st.cache_data(ttl=600)
def fetch_pipedrive_persons():
    """Haal alle personen op uit Pipedrive."""
    token = get_secret("PIPEDRIVE_API_TOKEN")
    if not token:
        return pd.DataFrame()

    all_persons = []
    start = 0

    while True:
        try:
            r = requests.get(
                f"{PIPEDRIVE_BASE}/persons",
                params={"api_token": token, "limit": 500, "start": start},
                timeout=30,
            )
            if r.status_code != 200:
                break
            data = r.json()
            persons = data.get("data") or []
            if not persons:
                break
            all_persons.extend(persons)
            pag = data.get("additional_data", {}).get("pagination", {})
            if not pag.get("more_items_in_collection"):
                break
            start = pag.get("next_start", start + 500)
        except Exception:
            break

    if not all_persons:
        return pd.DataFrame()

    records = []
    for p in all_persons:
        emails = p.get("email", [])
        email = emails[0].get("value", "") if emails else ""
        phones = p.get("phone", [])
        phone = phones[0].get("value", "") if phones else ""
        records.append({
            "person_id": p.get("id"),
            "pipedrive_name": (p.get("name") or "").strip(),
            "pipedrive_email": email.lower().strip(),
            "pipedrive_org": (p.get("org_name") or "").strip(),
            "pipedrive_phone": phone,
            "pipedrive_last_activity": p.get("last_activity_date", ""),
        })
    return pd.DataFrame(records)


@st.cache_data(ttl=3600)
def fetch_pipedrive_stages():
    """Haal alle pipeline stages op als {stage_id: stage_name} dict."""
    token = get_secret("PIPEDRIVE_API_TOKEN")
    if not token:
        return {}
    try:
        r = requests.get(f"{PIPEDRIVE_BASE}/stages", params={"api_token": token}, timeout=15)
        return {s["id"]: s["name"] for s in (r.json().get("data") or [])}
    except Exception:
        return {}


def save_pipedrive_note(person_id: int, deal_id, content: str) -> bool:
    """Sla belnotitie op als note in Pipedrive (op persoon en optioneel deal)."""
    token = get_secret("PIPEDRIVE_API_TOKEN")
    if not token or not content.strip():
        return False
    payload = {
        "content": content,
        "person_id": person_id,
        "pinned_to_person_flag": 1,
    }
    if deal_id:
        payload["deal_id"] = int(deal_id)
        payload["pinned_to_deal_flag"] = 1
    try:
        r = requests.post(
            f"{PIPEDRIVE_BASE}/notes",
            params={"api_token": token},
            json=payload,
            timeout=15,
        )
        return r.status_code == 201
    except Exception:
        return False


def update_pipedrive_deal_stage(deal_id: int, stage_id: int) -> bool:
    """Werk deal stage bij in Pipedrive."""
    token = get_secret("PIPEDRIVE_API_TOKEN")
    if not token:
        return False
    try:
        r = requests.put(
            f"{PIPEDRIVE_BASE}/deals/{deal_id}",
            params={"api_token": token},
            json={"stage_id": stage_id},
            timeout=15,
        )
        return r.status_code == 200
    except Exception:
        return False


# ============================================================
#  PIPEDRIVE NOTES
# ============================================================

@st.cache_data(ttl=600)
def fetch_pipedrive_person_notes(person_id: int):
    """Haal meest recente notities op voor een Pipedrive persoon (max 5)."""
    token = get_secret("PIPEDRIVE_API_TOKEN")
    if not token or not person_id:
        return []
    try:
        r = requests.get(
            f"{PIPEDRIVE_BASE}/notes",
            params={"api_token": token, "person_id": int(person_id), "limit": 5,
                    "sort": "add_time DESC"},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("data") or []
    except Exception:
        pass
    return []


# ============================================================
#  MICROSOFT GRAPH — MAIL CONTACT HISTORY (UITGESTELD - MFA)
# ============================================================

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _get_graph_token():
    """Haal OAuth2 access token op voor Microsoft Graph via ROPC (username + password)."""
    tenant_id = get_secret("MAIL_TENANT_ID")
    client_id = get_secret("MAIL_CLIENT_ID")
    username = get_secret("MAIL_USERNAME")
    password = get_secret("MAIL_PASSWORD")
    if not all([tenant_id, client_id, username, password]):
        return None
    try:
        r = requests.post(
            f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
            data={
                "grant_type": "password",
                "client_id": client_id,
                "username": username,
                "password": password,
                "scope": "https://graph.microsoft.com/Mail.Read offline_access",
            },
            timeout=15,
        )
        return r.json().get("access_token") if r.status_code == 200 else None
    except Exception:
        return None


def _classify_reply(snippet: str) -> str:
    """Klassificeer een e-mailreactie via Claude Haiku."""
    api_key = get_secret("ANTHROPIC_API_KEY")
    if not api_key or not snippet.strip():
        return "Neutraal"
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=20,
            messages=[{
                "role": "user",
                "content": (
                    "Klassificeer deze e-mailreactie in één woord. Kies exact één van: "
                    "Geïnteresseerd, Niet-geïnteresseerd, Follow-up, Neutraal.\n\n"
                    f"Reactie: {snippet[:400]}"
                ),
            }],
        )
        label = msg.content[0].text.strip()
        for opt in ["Geïnteresseerd", "Niet-geïnteresseerd", "Follow-up", "Neutraal"]:
            if opt.lower() in label.lower():
                return opt
        return "Neutraal"
    except Exception:
        return "Neutraal"


@st.cache_data(ttl=1800)
def fetch_mail_contact_history(mailbox="tobias@notifica.nl", days=180):
    """
    Haal contact history op via Microsoft Graph API.
    Returns {email_lower: {last_contact, last_reply, reply_snippet, ai_class}}

    Vereist: Mail.Read Application permission op de Azure AD app + admin consent.
    """
    token = _get_graph_token()
    if not token:
        return {}

    headers = {"Authorization": f"Bearer {token}"}
    cutoff = (datetime.now() - pd.Timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")

    # --- Stap 1: Verzonden mails → sent_map {recipient_email: sent_date} ---
    sent_map = {}
    url = (
        f"{GRAPH_BASE}/users/{mailbox}/mailFolders/SentItems/messages"
        f"?$select=toRecipients,sentDateTime"
        f"&$filter=sentDateTime ge {cutoff}"
        f"&$top=250&$orderby=sentDateTime desc"
    )
    while url:
        try:
            r = requests.get(url, headers=headers, timeout=20)
            if r.status_code != 200:
                break
            data = r.json()
            for msg in data.get("value", []):
                sent_dt = msg.get("sentDateTime", "")[:10]
                for recipient in msg.get("toRecipients", []):
                    addr = (recipient.get("emailAddress", {}).get("address") or "").lower().strip()
                    if addr and addr not in sent_map:
                        sent_map[addr] = sent_dt
            url = data.get("@odata.nextLink")
        except Exception:
            break

    # --- Stap 2: Ontvangen mails → reply_map {sender_email: {date, snippet}} ---
    reply_map = {}
    url = (
        f"{GRAPH_BASE}/users/{mailbox}/messages"
        f"?$select=from,receivedDateTime,bodyPreview"
        f"&$filter=receivedDateTime ge {cutoff} and isDraft eq false"
        f"&$top=250&$orderby=receivedDateTime desc"
    )
    while url:
        try:
            r = requests.get(url, headers=headers, timeout=20)
            if r.status_code != 200:
                break
            data = r.json()
            for msg in data.get("value", []):
                addr = (
                    msg.get("from", {}).get("emailAddress", {}).get("address") or ""
                ).lower().strip()
                if not addr or addr == mailbox.lower():
                    continue
                recv_dt = msg.get("receivedDateTime", "")[:10]
                snippet = (msg.get("bodyPreview") or "").strip()
                if addr not in reply_map:
                    reply_map[addr] = {"date": recv_dt, "snippet": snippet}
            url = data.get("@odata.nextLink")
        except Exception:
            break

    # --- Stap 3: AI-classificatie voor replies ---
    history = {}
    all_emails = set(sent_map) | set(reply_map)
    for email in all_emails:
        entry = {}
        if email in sent_map:
            entry["last_contact"] = sent_map[email]
        if email in reply_map:
            entry["last_reply"] = reply_map[email]["date"]
            entry["reply_snippet"] = reply_map[email]["snippet"]
            entry["ai_class"] = _classify_reply(reply_map[email]["snippet"])
        if entry:
            history[email] = entry

    return history


def generate_nid(email):
    """Genereer een nid (8-char hash) van een emailadres. Zelfde logica als in tracking snippet."""
    return hashlib.sha256(email.lower().strip().encode()).hexdigest()[:12]


@st.cache_data(ttl=300)
def fetch_visitor_data_from_api(days=30):
    """Haal bezoekdata op via Cloudflare Workers API."""
    api_key = get_secret("VISITOR_ADMIN_KEY")
    if not api_key:
        return None, None, None
    try:
        r = requests.get(
            "https://notifica.nl/api/visitor-data",
            params={"key": api_key, "days": days, "format": "json"},
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("success"):
                identified = data.get("identified_visitors", [])
                id_df = pd.DataFrame(identified) if identified else pd.DataFrame()
                return pd.DataFrame(data["visitors"]), data.get("summary", {}), id_df
        return None, None, None
    except Exception:
        return None, None, None


def load_web_visitors():
    """Laad web visitors: API of CSV fallback. Returns (mapping, source, summary, df, identified_df)."""
    df, summary, id_df = fetch_visitor_data_from_api()
    if df is not None and not df.empty:
        mapping = {}
        for _, row in df.iterrows():
            key = str(row["company_name"]).strip().lower()
            score = int(row.get("website_visits_score", 0))
            if key not in mapping or score > mapping[key]:
                mapping[key] = score
        return mapping, "api", summary, df, id_df if id_df is not None else pd.DataFrame()

    try:
        csv_df = pd.read_csv(
            os.path.join(os.path.dirname(__file__), "web_visitors_mapping.csv")
        )
        mapping = {}
        for _, row in csv_df.iterrows():
            key = str(row["company_name"]).strip().lower()
            score = int(row["website_visits_score"])
            if key not in mapping or score > mapping[key]:
                mapping[key] = score
        return mapping, "csv", None, csv_df, pd.DataFrame()
    except Exception:
        return {}, "none", None, pd.DataFrame(), pd.DataFrame()


_NL_MAANDEN = {
    1: "januari", 2: "februari", 3: "maart", 4: "april",
    5: "mei", 6: "juni", 7: "juli", 8: "augustus",
    9: "september", 10: "oktober", 11: "november", 12: "december",
}


@st.cache_data(ttl=3600)
def fetch_powerbi_sql_data():
    """Haal Power BI report views op via Azure SQL (bisqq/notificaRAAS/Notifica.[Power BI activities]).
    Vereist: ODBC Driver 17 for SQL Server + service principal met db_datareader op notificaRAAS.
    Returns (DataFrame, status)."""
    import struct
    try:
        import pyodbc
    except ImportError:
        return None, "no_pyodbc"

    tenant_id = get_secret("POWERBI_TENANT_ID")
    client_id = get_secret("POWERBI_CLIENT_ID")
    client_secret = get_secret("POWERBI_CLIENT_SECRET")

    if not all([tenant_id, client_id, client_secret]):
        return None, "no_credentials"

    # Azure AD token voor Azure SQL (andere scope dan Power BI API)
    try:
        r = requests.post(
            f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "https://database.windows.net/.default",
            },
            timeout=15,
        )
        if r.status_code != 200:
            return None, "auth_failed"
        token = r.json()["access_token"]
    except Exception:
        return None, "auth_error"

    token_bytes = token.encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)

    conn_str = (
        "Driver={ODBC Driver 17 for SQL Server};"
        "Server=bisqq.database.windows.net;"
        "Database=notificaRAAS;"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=15;"
    )

    try:
        conn = pyodbc.connect(conn_str, attrs_before={1256: token_struct})
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                a.[Workspace name]    AS org_name,
                a.[Report name]       AS report_name,
                a.[Name]              AS user_name,
                COUNT(*)              AS views,
                YEAR(a.[Activity Datum])   AS jaar,
                MONTH(a.[Activity Datum])  AS maand_nr
            FROM Notifica.[Power BI activities] a
            WHERE a.[Activity Datum] >= CAST(DATEADD(month, -3, GETDATE()) AS date)
            GROUP BY a.[Workspace name], a.[Report name], a.[Name],
                     YEAR(a.[Activity Datum]), MONTH(a.[Activity Datum])
        """)
        rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        return None, f"sql_error: {str(e)[:120]}"

    if not rows:
        return None, "no_data"

    result = pd.DataFrame(
        rows,
        columns=["Pipedrive organisatie", "Report name", "Name",
                 "Aantal activity reportviews", "Jaar", "_maand_nr"],
    )
    result["Maand"] = result["_maand_nr"].map(_NL_MAANDEN)
    result = result.drop(columns=["_maand_nr"])
    return result, "ok"


def save_powerbi_cache(file_bytes: bytes) -> bool:
    """Sla geüpload Power BI Excel op als lokale cache. Returns True bij succes."""
    try:
        os.makedirs(os.path.dirname(POWERBI_CACHE_PATH), exist_ok=True)
        with open(POWERBI_CACHE_PATH, "wb") as f:
            f.write(file_bytes)
        return True
    except Exception:
        return False


def load_powerbi_data():
    """Laad Power BI data: Azure SQL → lokale cache → Downloads Excel.
    Returns (DataFrame, source_label, sql_status)."""
    sql_df, sql_status = fetch_powerbi_sql_data()
    if sql_df is not None and not sql_df.empty:
        return sql_df, "sql", sql_status

    if os.path.exists(POWERBI_CACHE_PATH):
        try:
            return pd.read_excel(POWERBI_CACHE_PATH), "cache", sql_status
        except Exception:
            pass

    if os.path.exists(POWERBI_EXCEL_DEFAULT):
        try:
            return pd.read_excel(POWERBI_EXCEL_DEFAULT), "excel", sql_status
        except Exception:
            pass

    return None, "none", sql_status


def validate_powerbi_data(pbi_df, excel_path=POWERBI_EXCEL_DEFAULT):
    """Vergelijk Power BI API data met Excel export."""
    if pbi_df is None or pbi_df.empty:
        return None
    if not os.path.exists(excel_path):
        return None
    try:
        excel_df = pd.read_excel(excel_path)
    except Exception:
        return None

    sql_orgs = set(pbi_df["Pipedrive organisatie"].dropna().unique())
    excel_orgs = set(excel_df["Pipedrive organisatie"].dropna().unique())

    sql_views = pbi_df.groupby("Pipedrive organisatie")["Aantal activity reportviews"].sum()
    excel_views = excel_df.groupby("Pipedrive organisatie")["Aantal activity reportviews"].sum()

    shared_orgs = sql_orgs & excel_orgs
    only_sql = sql_orgs - excel_orgs
    only_excel = excel_orgs - sql_orgs

    comparison = []
    for org in sorted(shared_orgs):
        sql_v = int(sql_views.get(org, 0))
        excel_v = int(excel_views.get(org, 0))
        diff = sql_v - excel_v
        diff_pct = (diff / excel_v * 100) if excel_v > 0 else 0
        comparison.append({
            "Organisatie": org,
            "Views (SQL)": sql_v,
            "Views (Excel)": excel_v,
            "Verschil": diff,
            "Verschil %": round(diff_pct, 1),
        })

    return {
        "sql_total_rows": len(pbi_df),
        "excel_total_rows": len(excel_df),
        "sql_total_views": int(pbi_df["Aantal activity reportviews"].sum()),
        "excel_total_views": int(excel_df["Aantal activity reportviews"].sum()),
        "sql_orgs": len(sql_orgs),
        "excel_orgs": len(excel_orgs),
        "shared_orgs": len(shared_orgs),
        "only_sql": sorted(only_sql),
        "only_excel": sorted(only_excel),
        "comparison": pd.DataFrame(comparison).sort_values("Verschil %", ascending=False, key=abs) if comparison else pd.DataFrame(),
    }


# ============================================================
#  SCORING
# ============================================================

def fuzzy_match_company(name, mapping_keys):
    """Match bedrijfsnaam tegen web visitors mapping."""
    if not name:
        return None, 0
    name_lower = name.strip().lower()

    if name_lower in mapping_keys:
        return name_lower, mapping_keys[name_lower]

    for key, score in mapping_keys.items():
        if len(key) >= 4 and (key in name_lower or name_lower in key):
            return key, score

    stop_words = {"bv", "b.v.", "nv", "n.v.", "holding", "groep", "group",
                  "nederland", "netherlands", "international", "the", "de",
                  "het", "van", "en"}
    name_words = {w for w in name_lower.split() if len(w) >= 3} - stop_words

    best_match, best_score, best_overlap = None, 0, 0
    for key, score in mapping_keys.items():
        key_words = {w for w in key.split() if len(w) >= 3} - stop_words
        overlap = name_words & key_words
        if len(overlap) >= 1 and len(overlap) > best_overlap:
            best_overlap = len(overlap)
            best_match = key
            best_score = score

    return (best_match, best_score) if best_match else (None, 0)


def calculate_engagement_score(opened, clicked):
    """Email engagement score. Returns (open_score, click_score)."""
    thresholds_open = [(20, 15), (10, 12), (5, 9), (3, 6), (1, 3)]
    thresholds_click = [(10, 15), (5, 12), (3, 9), (2, 6), (1, 3)]

    open_score = next((s for t, s in thresholds_open if opened >= t), 0)
    click_score = next((s for t, s in thresholds_click if clicked >= t), 0)
    return open_score, click_score


def classify_lead(total_score):
    if total_score >= 18:
        return "HOT"
    elif total_score >= 9:
        return "Warm"
    else:
        return "Cold"


def _nid_score(visits: int) -> int:
    """Score op basis van geïdentificeerde website-bezoeken (NID)."""
    if visits >= 4:
        return 10
    elif visits >= 2:
        return 6
    elif visits >= 1:
        return 3
    return 0


def _lf_score(company: str, lf_companies: dict) -> int:
    """Score op basis van Leadfeeder bedrijfsmatch."""
    if not company or not lf_companies:
        return 0
    _, score = fuzzy_match_company(company, lf_companies)
    return 5 if score else 0


def build_leads_df(ml_df, pd_df, web_mapping,
                   deals_dict=None, identified_df=None, lf_df=None):
    """
    Bouw unified lead tabel van alle bronnen.
    Signalen: e-mail opens/clicks + NID websitebezoek + Leadfeeder bedrijfsmatch + deal fase.
    """
    # Bouw NID-visit lookup: {nid: visit_count}
    nid_visits = {}
    if identified_df is not None and not identified_df.empty and "nid" in identified_df.columns:
        visit_col = "visits" if "visits" in identified_df.columns else "count"
        if visit_col in identified_df.columns:
            nid_visits = identified_df.set_index("nid")[visit_col].to_dict()
        else:
            nid_visits = {row["nid"]: 1 for _, row in identified_df.iterrows()}

    # Bouw Leadfeeder bedrijfsnamen lookup: {company_lower: 1}
    lf_companies = {}
    if lf_df is not None and not lf_df.empty and "Bedrijf" in lf_df.columns:
        for name in lf_df["Bedrijf"].dropna():
            lf_companies[str(name).lower().strip()] = 1

    deals = deals_dict or {}
    leads = []

    def _build_lead(email, name, company, phone, opened, clicked, pipedrive_match,
                    person_id=None):
        open_score, click_score = calculate_engagement_score(opened, clicked)

        # NID websitebezoek
        nid = generate_nid(email)
        visits = nid_visits.get(nid, 0)
        nid_web_score = _nid_score(visits)

        # Leadfeeder bedrijfsmatch
        lf_match = _lf_score(company, lf_companies) > 0
        lf_web_score = 5 if lf_match else 0

        # Pipedrive deal
        deal = deals.get(email, {})
        deal_fase = deal.get("deal_fase", "")
        deal_waarde = deal.get("deal_waarde", 0)
        deal_bonus = deal.get("deal_bonus", 0)
        deal_id = deal.get("deal_id")
        deal_stage_id = deal.get("stage_id")
        # Bedrijfsnaam uit deal als er geen andere is
        if not company and deal.get("org_name"):
            company = deal["org_name"]

        total = open_score + click_score + nid_web_score + lf_web_score + deal_bonus

        return {
            "Naam": name,
            "Email": email,
            "Bedrijf": company,
            "Telefoon": phone,
            "Opens": opened,
            "Clicks": clicked,
            "Open Score": open_score,
            "Click Score": click_score,
            "NID Bezoeken": visits,
            "NID Score": nid_web_score,
            "LF Bezocht": lf_match,
            "LF Score": lf_web_score,
            "Deal Fase": deal_fase,
            "Deal Waarde": deal_waarde,
            "Deal Bonus": deal_bonus,
            "Totaal": total,
            "Segment": classify_lead(total),
            "In Pipedrive": pipedrive_match,
            "Pipedrive ID": person_id,
            "Deal ID": deal_id,
            "Deal Stage ID": deal_stage_id,
        }

    if not ml_df.empty:
        for _, sub in ml_df.iterrows():
            email = sub["email"].lower().strip()
            pipedrive_org = ""
            pipedrive_match = False
            pipedrive_phone = ""
            person_id = None
            if not pd_df.empty:
                match = pd_df[pd_df["pipedrive_email"] == email]
                if not match.empty:
                    pipedrive_org = match.iloc[0]["pipedrive_org"]
                    pipedrive_phone = match.iloc[0]["pipedrive_phone"]
                    pipedrive_match = True
                    person_id = match.iloc[0].get("person_id")
            company = pipedrive_org or sub.get("company", "") or ""
            leads.append(_build_lead(
                email, sub["name"], company, pipedrive_phone,
                sub["opened"], sub["clicked"], pipedrive_match,
                person_id=person_id,
            ))

    elif not pd_df.empty:
        for _, p in pd_df.iterrows():
            if not p["pipedrive_email"]:
                continue
            leads.append(_build_lead(
                p["pipedrive_email"], p["pipedrive_name"],
                p["pipedrive_org"], p["pipedrive_phone"],
                0, 0, True,
                person_id=p.get("person_id"),
            ))

    if not leads:
        return pd.DataFrame()

    df = pd.DataFrame(leads)
    # Deals altijd bovenaan, daarna op totaal score
    df["_deal_prio"] = df["Deal Bonus"].apply(lambda x: 1 if x > 0 else 0)
    df = df.sort_values(["_deal_prio", "Totaal"], ascending=False).drop(columns=["_deal_prio"])
    return df.reset_index(drop=True)


# ============================================================
#  CUSTOMER HEALTH
# ============================================================

def calculate_customer_health(pbi_df):
    """Bereken customer health scores uit Power BI data."""
    if pbi_df is None or pbi_df.empty:
        return pd.DataFrame()

    mask = ~pbi_df["Name"].str.lower().apply(
        lambda n: any(intern in str(n).lower() for intern in INTERNE_MEDEWERKERS)
    )
    df = pbi_df[mask].copy()
    df = df[df["Pipedrive organisatie"] != "Total"]

    maand_order = {
        "januari": 1, "februari": 2, "maart": 3, "april": 4,
        "mei": 5, "juni": 6, "juli": 7, "augustus": 8,
        "september": 9, "oktober": 10, "november": 11, "december": 12,
    }
    df["maand_nr"] = df["Maand"].str.lower().map(maand_order)
    df = df.dropna(subset=["Jaar", "maand_nr"])
    df["periode"] = df["Jaar"].astype(int) * 100 + df["maand_nr"].astype(int)

    periodes = sorted(df["periode"].dropna().unique())
    if len(periodes) >= 2:
        recent_period = periodes[-1]
        prev_period = periodes[-2]
    elif len(periodes) == 1:
        recent_period = periodes[0]
        prev_period = None
    else:
        return pd.DataFrame()

    customers = []
    for org_name, grp in df.groupby("Pipedrive organisatie"):
        total_views = int(grp["Aantal activity reportviews"].sum())
        users = grp["Name"].nunique()
        reports = grp["Report name"].nunique()

        recent = grp[grp["periode"] == recent_period]
        recent_views = int(recent["Aantal activity reportviews"].sum()) if not recent.empty else 0

        if prev_period is not None:
            prev = grp[grp["periode"] == prev_period]
            prev_views = int(prev["Aantal activity reportviews"].sum()) if not prev.empty else 0
        else:
            prev_views = 0

        if prev_views > 0:
            change_pct = ((recent_views - prev_views) / prev_views) * 100
        elif recent_views > 0:
            change_pct = 100.0
        else:
            change_pct = 0.0

        if change_pct > 10:
            trend = "Stijgend"
        elif change_pct < -25:
            trend = "Dalend"
        else:
            trend = "Stabiel"

        if recent_views == 0:
            status = "Rood"
        elif trend == "Dalend" or users <= 1:
            status = "Oranje"
        else:
            status = "Groen"

        klantnr_match = re.match(r"^(\d{4})", str(org_name))
        klantnummer = klantnr_match.group(1) if klantnr_match else ""
        klantnaam = re.sub(r"^\d{4}\s*-\s*", "", str(org_name)).strip()

        customers.append({
            "Klantnummer": klantnummer,
            "Klant": klantnaam,
            "Pipedrive organisatie": org_name,
            "Views (totaal)": total_views,
            "Views (recent)": recent_views,
            "Views (vorig)": prev_views,
            "Gebruikers": users,
            "Rapporten": reports,
            "Trend": trend,
            "Trend %": round(change_pct, 1),
            "Status": status,
        })

    health_df = pd.DataFrame(customers)
    status_order = {"Rood": 0, "Oranje": 1, "Groen": 2}
    health_df["_sort"] = health_df["Status"].map(status_order)
    health_df = health_df.sort_values(["_sort", "Views (recent)"], ascending=[True, True])
    health_df = health_df.drop(columns=["_sort"]).reset_index(drop=True)

    return health_df


def get_customer_contacts(health_df, pd_df):
    """Koppel klant health data aan Pipedrive contactpersonen."""
    if health_df.empty or pd_df.empty:
        return health_df

    contacts = []
    for _, row in health_df.iterrows():
        klant = row["Klant"]
        matches = pd_df[pd_df["pipedrive_org"].str.contains(klant, case=False, na=False)]
        if not matches.empty:
            with_phone = matches[matches["pipedrive_phone"] != ""]
            if not with_phone.empty:
                contact = with_phone.iloc[0]
            else:
                contact = matches.iloc[0]
            contacts.append({
                "Contact": contact["pipedrive_name"],
                "Contact Email": contact["pipedrive_email"],
                "Contact Telefoon": contact["pipedrive_phone"],
            })
        else:
            contacts.append({
                "Contact": "",
                "Contact Email": "",
                "Contact Telefoon": "",
            })

    contact_df = pd.DataFrame(contacts)
    return pd.concat([health_df.reset_index(drop=True), contact_df], axis=1)


# ============================================================
#  CAMPAIGN & VISITOR ANALYSE DATA
# ============================================================

@st.cache_data(ttl=3600)
def load_campaign_data():
    """Laad campagne-overzicht uit MailerLite export."""
    if not os.path.exists(ML_CAMPAIGNS_PATH):
        return pd.DataFrame()
    try:
        df = pd.read_csv(ML_CAMPAIGNS_PATH)
        df = df[df["status"] == "sent"].copy()
        df["sent_at"] = pd.to_datetime(df["sent_at"], errors="coerce")
        df = df.sort_values("sent_at", ascending=False)

        cols = {
            "name": "Campagne",
            "subject": "Onderwerp",
            "sent_at": "Verzonden",
            "emails_sent": "Verstuurd",
            "opens_count": "Opens",
            "unique_opens_count": "Unieke Opens",
            "opens_rate": "Open Rate",
            "clicks_count": "Clicks",
            "unique_clicks_count": "Unieke Clicks",
            "clicks_rate": "Click Rate",
            "hard_bounces_count": "Hard Bounces",
            "soft_bounces_count": "Soft Bounces",
            "unsubscribes_count": "Uitschrijvingen",
            "id": "campaign_id",
        }
        available = {k: v for k, v in cols.items() if k in df.columns}
        result = df[list(available.keys())].rename(columns=available)

        # Rates als percentage
        for rate_col in ["Open Rate", "Click Rate"]:
            if rate_col in result.columns:
                result[rate_col] = (result[rate_col] * 100).round(1).astype(str) + "%"

        return result
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def load_campaign_activity():
    """Laad per-subscriber campagne activiteit, verrijkt met bedrijfsnaam."""
    if not os.path.exists(ML_ACTIVITY_PATH):
        return pd.DataFrame()
    try:
        act_df = pd.read_csv(ML_ACTIVITY_PATH)

        # Verrijk met bedrijfsnaam uit subscribers.csv
        if os.path.exists(ML_SUBSCRIBERS_PATH):
            subs = pd.read_csv(ML_SUBSCRIBERS_PATH, usecols=["email", "field_company", "field_name", "field_last_name"])
            subs["email"] = subs["email"].str.lower().str.strip()
            subs["Naam"] = (subs["field_name"].fillna("") + " " + subs["field_last_name"].fillna("")).str.strip()
            subs = subs.rename(columns={"field_company": "Bedrijf"})
            act_df["subscriber_email"] = act_df["subscriber_email"].str.lower().str.strip()
            act_df = act_df.merge(
                subs[["email", "Bedrijf", "Naam"]],
                left_on="subscriber_email", right_on="email", how="left",
            )

        act_df = act_df.rename(columns={
            "subscriber_email": "Email",
            "campaign_name": "Campagne",
            "opens_count": "Opens",
            "clicks_count": "Clicks",
            "campaign_id": "campaign_id",
        })
        return act_df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def fetch_leadfeeder_leads(days=14):
    """
    Haal recente bedrijfsbezoeken op via Leadfeeder (Dealfront) API.
    Geeft DataFrame terug met: Bedrijf, Industrie, Stad, Bezoeken, Laatste Bezoek,
    Kwaliteit, Bron, Pagina's (bezocht).
    """
    token = get_secret("LEADFEEDER_API_TOKEN")
    account_id = get_secret("LEADFEEDER_ACCOUNT_ID")
    if not token or not account_id:
        return pd.DataFrame()

    headers = {"Authorization": f"Token token={token}"}
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    leads = []
    page_size = 100
    page_cursor = None

    try:
        while True:
            params = {
                "start_date": start_date,
                "end_date": end_date,
                "per_page": page_size,
            }
            if page_cursor:
                params["page[cursor]"] = page_cursor

            r = requests.get(
                f"https://api.leadfeeder.com/accounts/{account_id}/leads",
                headers=headers,
                params=params,
                timeout=20,
            )
            if r.status_code != 200:
                break

            data = r.json()
            batch = data.get("data", [])
            included = data.get("included", [])

            # Bouw location lookup
            location_map = {}
            for inc in included:
                if inc.get("type") == "locations":
                    loc_id = inc.get("id")
                    attrs = inc.get("attributes", {})
                    location_map[loc_id] = f"{attrs.get('city', '')} {attrs.get('country_code', '')}".strip()

            for lead in batch:
                attrs = lead.get("attributes", {})
                rels = lead.get("relationships", {})

                # Locatie
                loc_data = rels.get("locations", {}).get("data", [])
                city = ""
                if loc_data:
                    city = location_map.get(loc_data[0].get("id", ""), "")

                # Bepaal traffic source van eerste bezoek
                sources = attrs.get("sources", []) or []
                bron = sources[0] if sources else ""

                leads.append({
                    "Bedrijf": attrs.get("name", ""),
                    "Industrie": attrs.get("industry", "") or "",
                    "Stad": city,
                    "Bezoeken": attrs.get("visits_count", 0),
                    "Laatste Bezoek": attrs.get("last_visit_at", "")[:10] if attrs.get("last_visit_at") else "",
                    "Kwaliteit": attrs.get("quality", 0) or 0,
                    "Medewerkers": attrs.get("employee_count", "") or "",
                    "Bron": bron,
                    "Website": attrs.get("website", "") or "",
                })

            # Paginatie
            meta = data.get("meta", {})
            next_cursor = meta.get("next_cursor")
            if not next_cursor or not batch:
                break
            page_cursor = next_cursor

    except Exception:
        pass

    if not leads:
        return pd.DataFrame()

    df = pd.DataFrame(leads)
    df = df.sort_values(["Bezoeken", "Kwaliteit"], ascending=False).reset_index(drop=True)
    return df


@st.cache_data(ttl=3600)
def load_subscriber_data():
    """Laad subscriber details uit MailerLite export."""
    if not os.path.exists(ML_SUBSCRIBERS_PATH):
        return pd.DataFrame()
    try:
        df = pd.read_csv(ML_SUBSCRIBERS_PATH)
        df["email"] = df["email"].str.lower().str.strip()
        df["Naam"] = (df["field_name"].fillna("") + " " + df["field_last_name"].fillna("")).str.strip()
        df = df.rename(columns={
            "field_company": "Bedrijf",
            "status": "Status",
            "source": "Bron",
            "created_at": "Aangemeld",
        })
        return df
    except Exception:
        return pd.DataFrame()
