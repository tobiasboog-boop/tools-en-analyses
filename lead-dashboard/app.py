"""
Lead Dashboard - Notifica
Combineert MailerLite engagement, Pipedrive CRM en website bezoekdata
tot een unified lead scoring dashboard.
"""
import streamlit as st
import pandas as pd
import requests
from datetime import datetime

st.set_page_config(page_title="Lead Dashboard", page_icon="🎯", layout="wide")

# --- Authentication ---

def check_password():
    """Wachtwoordbeveiliging via session state."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.title("🔒 Lead Dashboard")
    password = st.text_input("Wachtwoord", type="password")
    if st.button("Inloggen"):
        if password == st.secrets.get("APP_PASSWORD", ""):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Onjuist wachtwoord")
    return False


if not check_password():
    st.stop()


# --- Data Fetching Functions ---

MAILERLITE_GROUP_ID = 177296943307818341


@st.cache_data(ttl=600)
def fetch_mailerlite_subscribers():
    """Haal alle subscribers op uit de hoofdgroep met engagement data."""
    token = st.secrets.get("MAILERLITE_API_TOKEN", "")
    if not token:
        return pd.DataFrame()

    headers = {"X-MailerLite-ApiKey": token}
    all_subscribers = []
    offset = 0
    limit = 100

    while True:
        try:
            response = requests.get(
                f"https://api.mailerlite.com/api/v2/groups/{MAILERLITE_GROUP_ID}/subscribers",
                headers=headers,
                params={"limit": limit, "offset": offset},
                timeout=30,
            )
            if response.status_code != 200:
                break
            batch = response.json()
            if not batch:
                break
            all_subscribers.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        except Exception:
            break

    if not all_subscribers:
        return pd.DataFrame()

    records = []
    for sub in all_subscribers:
        email = sub.get("email", "")
        name = sub.get("name", "") or ""
        last_name = sub.get("last_name", "") or ""
        full_name = f"{name} {last_name}".strip()
        company = ""

        # Zoek bedrijfsnaam in custom fields
        for field in sub.get("fields", []):
            if field.get("key") == "company":
                company = field.get("value", "") or ""
                break

        records.append({
            "email": email,
            "name": full_name,
            "company": company,
            "opened": int(sub.get("opened", 0) or 0),
            "clicked": int(sub.get("clicked", 0) or 0),
            "date_subscribe": sub.get("date_subscribe", ""),
            "type": sub.get("type", ""),
        })

    return pd.DataFrame(records)


@st.cache_data(ttl=600)
def fetch_pipedrive_persons():
    """Haal alle personen op uit Pipedrive met organisatie-info."""
    token = st.secrets.get("PIPEDRIVE_API_TOKEN", "")
    if not token:
        return pd.DataFrame()

    all_persons = []
    start = 0
    limit = 500

    while True:
        try:
            response = requests.get(
                "https://notifica.pipedrive.com/v1/persons",
                params={"api_token": token, "limit": limit, "start": start},
                timeout=30,
            )
            if response.status_code != 200:
                break
            data = response.json()
            persons = data.get("data") or []
            if not persons:
                break
            all_persons.extend(persons)
            pagination = data.get("additional_data", {}).get("pagination", {})
            if not pagination.get("more_items_in_collection"):
                break
            start = pagination.get("next_start", start + limit)
        except Exception:
            break

    if not all_persons:
        return pd.DataFrame()

    records = []
    for p in all_persons:
        org = p.get("org_name") or ""
        emails = p.get("email", [])
        email = emails[0].get("value", "") if emails else ""
        records.append({
            "pipedrive_name": (p.get("name") or "").strip(),
            "pipedrive_email": email.lower().strip(),
            "pipedrive_org": org.strip(),
            "pipedrive_last_activity": p.get("last_activity_date", ""),
        })

    return pd.DataFrame(records)


@st.cache_data(ttl=300)
def fetch_visitor_data_from_api(days=30):
    """Haal bezoekdata op via Cloudflare Workers API."""
    api_url = "https://notifica.nl/api/visitor-data"
    api_key = st.secrets.get("VISITOR_ADMIN_KEY", "")
    if not api_key:
        return None, None
    try:
        response = requests.get(
            api_url,
            params={"key": api_key, "days": days, "format": "json"},
            timeout=15,
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return pd.DataFrame(data["visitors"]), data.get("summary", {})
        return None, None
    except Exception:
        return None, None


def load_web_visitors():
    """Laad web visitors: eerst API, dan CSV fallback. Geeft mapping dict + bron."""
    # Probeer Cloudflare API
    df, summary = fetch_visitor_data_from_api()
    if df is not None and not df.empty:
        mapping = {}
        for _, row in df.iterrows():
            key = str(row["company_name"]).strip().lower()
            score = int(row.get("website_visits_score", 0))
            # Houd hoogste score per bedrijf (kan dubbel voorkomen)
            if key not in mapping or score > mapping[key]:
                mapping[key] = score
        return mapping, "api", summary, df

    # Fallback: CSV bestand
    try:
        csv_df = pd.read_csv("web_visitors_mapping.csv")
        mapping = {}
        for _, row in csv_df.iterrows():
            key = str(row["company_name"]).strip().lower()
            score = int(row["website_visits_score"])
            if key not in mapping or score > mapping[key]:
                mapping[key] = score
        return mapping, "csv", None, csv_df
    except Exception:
        return {}, "none", None, pd.DataFrame()


# --- Matching & Scoring ---

def fuzzy_match_company(name, mapping_keys):
    """Match bedrijfsnaam tegen web visitors mapping.
    Probeert: exact → contains → woord-match.
    Returns: (matched_key, score) of (None, 0).
    """
    if not name:
        return None, 0

    name_lower = name.strip().lower()

    # 1. Exact match
    if name_lower in mapping_keys:
        return name_lower, mapping_keys[name_lower]

    # 2. Bevat-match (Pipedrive naam bevat visitor naam of omgekeerd)
    for key, score in mapping_keys.items():
        if len(key) >= 4 and (key in name_lower or name_lower in key):
            return key, score

    # 3. Woord-overlap (minimaal 1 significant woord)
    stop_words = {"bv", "b.v.", "nv", "n.v.", "holding", "groep", "group",
                  "nederland", "netherlands", "international", "the", "de",
                  "het", "van", "en"}
    name_words = set(name_lower.split()) - stop_words
    # Verwijder te korte woorden
    name_words = {w for w in name_words if len(w) >= 3}

    best_match = None
    best_score = 0
    best_overlap = 0

    for key, score in mapping_keys.items():
        key_words = set(key.split()) - stop_words
        key_words = {w for w in key_words if len(w) >= 3}
        overlap = name_words & key_words
        if len(overlap) >= 1 and len(overlap) > best_overlap:
            best_overlap = len(overlap)
            best_match = key
            best_score = score

    if best_match:
        return best_match, best_score

    return None, 0


def calculate_engagement_score(opened, clicked):
    """Bereken engagement score op basis van opens en clicks.
    Opens: 0-15 punten, Clicks: 0-15 punten.
    """
    # Opens scoring (max 15)
    if opened >= 20:
        open_score = 15
    elif opened >= 10:
        open_score = 12
    elif opened >= 5:
        open_score = 9
    elif opened >= 3:
        open_score = 6
    elif opened >= 1:
        open_score = 3
    else:
        open_score = 0

    # Clicks scoring (max 15)
    if clicked >= 10:
        click_score = 15
    elif clicked >= 5:
        click_score = 12
    elif clicked >= 3:
        click_score = 9
    elif clicked >= 2:
        click_score = 6
    elif clicked >= 1:
        click_score = 3
    else:
        click_score = 0

    return open_score, click_score


def classify_lead(total_score):
    """Classificeer lead op basis van totaalscore."""
    if total_score >= 18:
        return "🔥 HOT"
    elif total_score >= 9:
        return "🟠 Warm"
    else:
        return "🔵 Cold"


# --- Main Dashboard ---

st.title("🎯 Lead Dashboard")
st.caption("Notifica - MailerLite × Pipedrive × Website Tracking")

# Data laden
with st.spinner("Data ophalen..."):
    ml_df = fetch_mailerlite_subscribers()
    pd_df = fetch_pipedrive_persons()
    web_mapping, web_source, web_summary, web_df = load_web_visitors()

# Status indicators
col1, col2, col3 = st.columns(3)
with col1:
    if not ml_df.empty:
        st.success(f"✅ MailerLite: {len(ml_df)} subscribers")
    else:
        st.warning("⚠️ MailerLite: geen data")
with col2:
    if not pd_df.empty:
        st.success(f"✅ Pipedrive: {len(pd_df)} personen")
    else:
        st.warning("⚠️ Pipedrive: geen data")
with col3:
    source_label = {"api": "Cloudflare API", "csv": "CSV fallback", "none": "geen data"}
    if web_mapping:
        st.success(f"✅ Web Visitors: {len(web_mapping)} bedrijven ({source_label[web_source]})")
    else:
        st.warning(f"⚠️ Web Visitors: {source_label[web_source]}")

st.divider()

# --- Build unified lead table ---

if ml_df.empty:
    st.error("Kan dashboard niet opbouwen zonder MailerLite data.")
    st.stop()

leads = []

for _, sub in ml_df.iterrows():
    email = sub["email"].lower().strip()
    name = sub["name"]
    company = sub["company"]
    opened = sub["opened"]
    clicked = sub["clicked"]

    # Engagement score
    open_score, click_score = calculate_engagement_score(opened, clicked)

    # Match met Pipedrive (op email)
    pipedrive_org = ""
    pipedrive_match = False
    if not pd_df.empty:
        match = pd_df[pd_df["pipedrive_email"] == email]
        if not match.empty:
            pipedrive_org = match.iloc[0]["pipedrive_org"]
            pipedrive_match = True

    # Bepaal bedrijfsnaam (Pipedrive > MailerLite company field)
    display_company = pipedrive_org or company or ""

    # Web visitors score via fuzzy match
    web_score = 0
    if web_mapping and display_company:
        _, web_score = fuzzy_match_company(display_company, web_mapping)

    # Totaal score
    total_score = open_score + click_score + web_score
    segment = classify_lead(total_score)

    leads.append({
        "Naam": name,
        "Email": email,
        "Bedrijf": display_company,
        "Opens": opened,
        "Clicks": clicked,
        "Open Score": open_score,
        "Click Score": click_score,
        "Web Score": web_score,
        "Totaal": total_score,
        "Segment": segment,
        "In Pipedrive": "✅" if pipedrive_match else "❌",
    })

leads_df = pd.DataFrame(leads)
leads_df = leads_df.sort_values("Totaal", ascending=False).reset_index(drop=True)

# --- Metrics ---

hot_count = len(leads_df[leads_df["Segment"] == "🔥 HOT"])
warm_count = len(leads_df[leads_df["Segment"] == "🟠 Warm"])
cold_count = len(leads_df[leads_df["Segment"] == "🔵 Cold"])
in_pipedrive = len(leads_df[leads_df["In Pipedrive"] == "✅"])

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Totaal Leads", len(leads_df))
m2.metric("🔥 HOT", hot_count)
m3.metric("🟠 Warm", warm_count)
m4.metric("🔵 Cold", cold_count)
m5.metric("In Pipedrive", f"{in_pipedrive}/{len(leads_df)}")

st.divider()

# --- Tabs ---

tab_all, tab_hot, tab_warm, tab_cold, tab_web = st.tabs(
    ["Alle Leads", "🔥 HOT Leads", "🟠 Warm Leads", "🔵 Cold Leads", "Website Bezoekers"]
)

# Display columns
display_cols = ["Naam", "Email", "Bedrijf", "Opens", "Clicks",
                "Open Score", "Click Score", "Web Score", "Totaal",
                "Segment", "In Pipedrive"]

with tab_all:
    st.subheader(f"Alle leads ({len(leads_df)})")

    # Filter
    filter_segment = st.multiselect(
        "Filter op segment", ["🔥 HOT", "🟠 Warm", "🔵 Cold"],
        default=["🔥 HOT", "🟠 Warm", "🔵 Cold"],
    )
    filtered = leads_df[leads_df["Segment"].isin(filter_segment)]

    search = st.text_input("Zoek op naam, email of bedrijf")
    if search:
        mask = (
            filtered["Naam"].str.contains(search, case=False, na=False) |
            filtered["Email"].str.contains(search, case=False, na=False) |
            filtered["Bedrijf"].str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]

    st.dataframe(
        filtered[display_cols],
        use_container_width=True,
        hide_index=True,
        height=500,
    )

with tab_hot:
    hot_df = leads_df[leads_df["Segment"] == "🔥 HOT"]
    st.subheader(f"🔥 HOT Leads ({len(hot_df)})")
    if hot_df.empty:
        st.info("Geen HOT leads gevonden.")
    else:
        st.caption("Score ≥ 18 — Hoge engagement + website activiteit")
        st.dataframe(hot_df[display_cols], use_container_width=True, hide_index=True)

with tab_warm:
    warm_df = leads_df[leads_df["Segment"] == "🟠 Warm"]
    st.subheader(f"🟠 Warm Leads ({len(warm_df)})")
    if warm_df.empty:
        st.info("Geen Warm leads gevonden.")
    else:
        st.caption("Score 9-17 — Matige engagement")
        st.dataframe(warm_df[display_cols], use_container_width=True, hide_index=True)

with tab_cold:
    cold_df = leads_df[leads_df["Segment"] == "🔵 Cold"]
    st.subheader(f"🔵 Cold Leads ({len(cold_df)})")
    if cold_df.empty:
        st.info("Geen Cold leads gevonden.")
    else:
        st.caption("Score < 9 — Lage engagement")
        st.dataframe(cold_df[display_cols], use_container_width=True, hide_index=True)

with tab_web:
    st.subheader("Website Bezoekers")

    if web_source == "api":
        st.success("Data via Cloudflare Workers API (live)")
        if web_summary:
            wc1, wc2, wc3 = st.columns(3)
            wc1.metric("🟢 Actief (recent)", web_summary.get("groen", 0))
            wc2.metric("🟠 Matig", web_summary.get("oranje", 0))
            wc3.metric("🔴 Inactief", web_summary.get("rood", 0))
    elif web_source == "csv":
        st.info("Data via CSV fallback (voeg VISITOR_ADMIN_KEY toe aan secrets voor live data)")
    else:
        st.warning("Geen web visitors data beschikbaar")

    if not web_df.empty:
        st.dataframe(
            web_df.sort_values(
                "website_visits_score" if "website_visits_score" in web_df.columns else web_df.columns[0],
                ascending=False,
            ),
            use_container_width=True,
            hide_index=True,
            height=400,
        )

# --- Scoring uitleg ---

with st.expander("📊 Scoring Uitleg"):
    st.markdown("""
**Lead Score: 0-40 punten** (Opens + Clicks + Website)

| Component | Max | Bereik |
|-----------|-----|--------|
| E-mail Opens | 15 | 0 opens=0, 1+=3, 3+=6, 5+=9, 10+=12, 20+=15 |
| E-mail Clicks | 15 | 0 clicks=0, 1+=3, 2+=6, 3+=9, 5+=12, 10+=15 |
| Website Bezoeken | 10 | 0-10 op basis van recente bezoekactiviteit |

**Segmentatie:**
- 🔥 **HOT** (≥18 punten): Hoge engagement, klaar voor opvolging
- 🟠 **Warm** (9-17 punten): Interesse, maar nog niet urgent
- 🔵 **Cold** (<9 punten): Lage engagement, nurturing nodig

**Databronnen:**
- **MailerLite**: E-mail opens en clicks per subscriber
- **Pipedrive**: Bedrijfskoppeling en CRM status
- **Website Tracking**: IP-naar-bedrijf herkenning via Cloudflare Workers + IPinfo.io
    """)

st.divider()
st.caption(f"Laatste update: {datetime.now().strftime('%d-%m-%Y %H:%M')} | Databronnen: MailerLite, Pipedrive, Cloudflare Workers")
