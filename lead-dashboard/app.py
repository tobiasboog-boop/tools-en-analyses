"""Lead Dashboard - Volledige versie met lead scoring"""
import streamlit as st
import pandas as pd
import requests
from datetime import datetime

st.set_page_config(
    page_title="🎯 Lead Action Dashboard",
    page_icon="🎯",
    layout="wide"
)

# ==================== CONFIG ====================

MAIN_GROUP_ID = 177296943307818341  # MailerLite actieve inschrijvingen
PIPEDRIVE_DOMAIN = "notifica"

# ==================== MAILERLITE API ====================

@st.cache_data(ttl=3600)  # Cache voor 1 uur
def get_subscribers(token):
    """Haal alle subscribers op met paginering."""
    all_subscribers = []
    offset = 0
    headers = {'X-MailerLite-ApiKey': token}

    with st.spinner("📊 Laden van subscriber data..."):
        while True:
            url = f"https://api.mailerlite.com/api/v2/groups/{MAIN_GROUP_ID}/subscribers"
            params = {'limit': 1000, 'offset': offset}

            try:
                response = requests.get(url, headers=headers, params=params, timeout=30)
                response.raise_for_status()
                batch = response.json()

                if not batch:
                    break

                all_subscribers.extend(batch)

                if len(batch) < 1000:
                    break

                offset += 1000

                if len(all_subscribers) >= 2000:  # Max 2000 voor snelheid
                    break

            except Exception as e:
                st.error(f"API Error: {e}")
                break

    return all_subscribers

def calculate_engagement_score(subscriber):
    """Bereken engagement score (0-40 punten)."""
    score = 0

    # Open count scoring (0-15 punten)
    # Gebaseerd op aantal keer dat emails zijn geopend
    opened = subscriber.get('opened', 0)
    if opened >= 10:
        score += 15
    elif opened >= 5:
        score += 12
    elif opened >= 3:
        score += 8
    elif opened >= 1:
        score += 4

    # Click scoring (0-15 punten)
    clicked = subscriber.get('clicked', 0)
    if clicked >= 10:
        score += 15
    elif clicked >= 5:
        score += 12
    elif clicked >= 3:
        score += 8
    elif clicked >= 1:
        score += 4

    # Website visits scoring (0-10 punten) - uit Pipedrive Web Visitors
    visits = subscriber.get('website_visits', 0)
    if visits >= 10:
        score += 10
    elif visits >= 5:
        score += 8
    elif visits >= 3:
        score += 6
    elif visits >= 1:
        score += 3

    return score

# ==================== PIPEDRIVE API ====================

@st.cache_data(ttl=3600)  # Cache voor 1 uur
def get_pipedrive_persons(token):
    """Haal alle Pipedrive persons op."""
    all_persons = []
    start = 0
    limit = 500

    with st.spinner("📞 Laden van Pipedrive CRM data..."):
        while True:
            url = f"https://{PIPEDRIVE_DOMAIN}.pipedrive.com/v1/persons"
            params = {
                'api_token': token,
                'start': start,
                'limit': limit
            }

            try:
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                if not data.get('data'):
                    break

                all_persons.extend(data['data'])

                # Check if there are more pages
                more_items = data.get('additional_data', {}).get('pagination', {}).get('more_items_in_collection', False)
                if not more_items:
                    break

                start += limit

                # Safety limit
                if len(all_persons) >= 2000:
                    break

            except Exception as e:
                st.warning(f"Pipedrive API warning: {e}")
                break

    return all_persons

# NOTE: Pipedrive Web Visitors heeft geen publieke API
# We gebruiken GA4 User-ID tracking als alternatief (zie get_ga4_user_engagement)

def extract_email(email_data):
    """Extract primary email from Pipedrive email array."""
    if not email_data:
        return None
    if isinstance(email_data, list) and len(email_data) > 0:
        # Find primary email or take first
        for item in email_data:
            if item.get('primary'):
                return item.get('value', '').lower()
        return email_data[0].get('value', '').lower()
    return None

def extract_phone(phone_data):
    """Extract primary phone from Pipedrive phone array."""
    if not phone_data:
        return None
    if isinstance(phone_data, list) and len(phone_data) > 0:
        # Find primary phone or take first
        for item in phone_data:
            if item.get('primary'):
                return item.get('value')
        return phone_data[0].get('value')
    return None

def enrich_with_pipedrive(subscribers, pipedrive_persons, ga4_user_data=None):
    """Match MailerLite subscribers with Pipedrive persons and add phone numbers + GA4 website visits."""
    # Create email lookup dict
    pipedrive_by_email = {}
    for person in pipedrive_persons:
        email = extract_email(person.get('email'))
        if email:
            pipedrive_by_email[email] = {
                'phone': extract_phone(person.get('phone')),
                'name': person.get('name'),
                'org_name': person.get('org_name')
            }

    # Enrich subscribers
    for sub in subscribers:
        email = sub.get('email', '').lower()
        if email in pipedrive_by_email:
            pd_data = pipedrive_by_email[email]
            sub['phone'] = pd_data['phone']
            sub['pipedrive_name'] = pd_data['name']
            sub['company'] = pd_data['org_name']
        else:
            sub['phone'] = None
            sub['pipedrive_name'] = None
            sub['company'] = None

        # Match website visits from GA4 User-ID tracking (by email)
        if ga4_user_data and email in ga4_user_data:
            sub['website_visits'] = ga4_user_data[email]['visits']
        else:
            sub['website_visits'] = 0

    return subscribers

# ==================== GA4 API ====================

def get_ga4_user_engagement(property_id, credentials_json):
    """Get website engagement per user (via User-ID = email).

    NOTE: User-ID dimension werkt pas nadat:
    1. Custom dimension is aangemaakt in GA4 UI (Admin -> Custom Definitions)
    2. Er genoeg data is verzameld (minimaal 24-48 uur)

    Voor nu returnen we lege dict - User-ID tracking volgt later.
    """
    # TODO: User-ID tracking vereist custom dimension setup in GA4
    # Temporarily disabled until property has data and custom dimension is configured
    return {}

    # Original code commented out - werkt niet zonder custom dimension
    # try:
    #     import json
    #     from google.analytics.data_v1beta import BetaAnalyticsDataClient
    #     from google.analytics.data_v1beta.types import RunReportRequest, Dimension, Metric, DateRange
    #     from google.oauth2 import service_account
    #
    #     credentials_info = json.loads(credentials_json)
    #     credentials = service_account.Credentials.from_service_account_info(
    #         credentials_info,
    #         scopes=['https://www.googleapis.com/auth/analytics.readonly']
    #     )
    #
    #     client = BetaAnalyticsDataClient(credentials=credentials)
    #
    #     # NOTE: userId is not a valid dimension in GA4 Data API
    #     # We need to create a custom dimension for user_id first
    #     request = RunReportRequest(
    #         property=f"properties/{property_id}",
    #         dimensions=[Dimension(name="customUser:user_id")],  # Requires custom dimension
    #         metrics=[
    #             Metric(name="sessions"),
    #             Metric(name="screenPageViews"),
    #             Metric(name="engagementRate")
    #         ],
    #         date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
    #     )
    #
    #     response = client.run_report(request)
    #
    #     user_data = {}
    #     for row in response.rows:
    #         user_id = row.dimension_values[0].value
    #         if user_id and user_id != '(not set)' and '@' in user_id:
    #             email = user_id.lower()
    #             user_data[email] = {
    #                 'visits': int(row.metric_values[0].value),
    #                 'page_views': int(row.metric_values[1].value),
    #                 'engagement_rate': float(row.metric_values[2].value)
    #             }
    #
    #     return user_data
    #
    # except Exception as e:
    #     st.sidebar.info(f"ℹ️ GA4 User-ID: {str(e)[:60]}")
    #     return {}

def get_ga4_high_intent_visitors(property_id, credentials_json):
    """Get visitors who viewed high-intent pages (pricing, contact, demo)."""
    try:
        import json
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import RunReportRequest, Dimension, Metric, DateRange
        from google.oauth2 import service_account

        # Parse credentials
        credentials_info = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(
            credentials_info,
            scopes=['https://www.googleapis.com/auth/analytics.readonly']
        )

        client = BetaAnalyticsDataClient(credentials=credentials)

        # High-intent pages
        high_intent_patterns = ['/tarieven', '/prijs', '/demo', '/contact', '/afspraak', '/bel-me']

        request = RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[
                Dimension(name="pagePath"),
                Dimension(name="city")
            ],
            metrics=[
                Metric(name="screenPageViews"),
                Metric(name="activeUsers")
            ],
            date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
        )

        response = client.run_report(request)

        # Filter for high-intent pages
        high_intent_data = []
        for row in response.rows:
            page_path = row.dimension_values[0].value
            if any(pattern in page_path.lower() for pattern in high_intent_patterns):
                high_intent_data.append({
                    'page': page_path,
                    'city': row.dimension_values[1].value,
                    'views': int(row.metric_values[0].value),
                    'users': int(row.metric_values[1].value)
                })

        return high_intent_data

    except Exception as e:
        st.sidebar.warning(f"GA4 error: {str(e)[:100]}")
        return []

# ==================== MAIN APP ====================

st.title("🎯 Lead Action Dashboard")
st.caption("Wie moet je vandaag emailen?")

# Get API tokens
try:
    mailerlite_token = st.secrets["MAILERLITE_API_TOKEN"]
except (KeyError, FileNotFoundError):
    st.error("❌ MAILERLITE_API_TOKEN niet gevonden in secrets!")
    st.stop()

# Pipedrive is optional
pipedrive_token = st.secrets.get("PIPEDRIVE_API_TOKEN")
pipedrive_enabled = bool(pipedrive_token)

# GA4 is optional
ga4_property_id = st.secrets.get("GA4_PROPERTY_ID")
ga4_credentials = st.secrets.get("GA4_SERVICE_ACCOUNT_JSON")
ga4_enabled = bool(ga4_property_id and ga4_credentials)

# Load subscribers
try:
    subscribers = get_subscribers(mailerlite_token)

    if not subscribers:
        st.warning("Geen subscribers gevonden!")
        st.stop()

    # Calculate engagement scores
    for sub in subscribers:
        sub['engagement_score'] = calculate_engagement_score(sub)

    # Get GA4 User-ID engagement data (if available)
    ga4_user_data = {}
    if ga4_enabled:
        try:
            ga4_user_data = get_ga4_user_engagement(ga4_property_id, ga4_credentials)
            if ga4_user_data:
                st.sidebar.success(f"✅ GA4 User-ID: {len(ga4_user_data)} matched subscribers")
        except Exception as e:
            st.sidebar.info("ℹ️ GA4 User-ID: Nog geen data (property is nieuw)")

    # Enrich with Pipedrive data (if available)
    if pipedrive_enabled:
        try:
            pipedrive_persons = get_pipedrive_persons(pipedrive_token)
            subscribers = enrich_with_pipedrive(subscribers, pipedrive_persons, ga4_user_data)

            # Count website visitors (from GA4)
            total_visits = sum(s.get('website_visits', 0) for s in subscribers)
            with_visits = len([s for s in subscribers if s.get('website_visits', 0) > 0])

            st.sidebar.success(f"✅ Pipedrive CRM: {len(pipedrive_persons)} personen")
            if with_visits > 0:
                st.sidebar.info(f"🌐 {with_visits} leads met website bezoeken ({total_visits} sessions)")
        except Exception as e:
            st.sidebar.warning(f"⚠️ Pipedrive niet beschikbaar: {str(e)[:50]}")
            pipedrive_enabled = False
    else:
        # Still enrich with GA4 data even if Pipedrive is disabled
        if ga4_user_data:
            for sub in subscribers:
                email = sub.get('email', '').lower()
                if email in ga4_user_data:
                    sub['website_visits'] = ga4_user_data[email]['visits']
                else:
                    sub['website_visits'] = 0
        st.sidebar.info("ℹ️ Pipedrive integratie uitgeschakeld")

    # Load GA4 data (if available)
    ga4_data = []
    if ga4_enabled:
        try:
            with st.spinner("🌐 Laden van GA4 website data..."):
                ga4_data = get_ga4_high_intent_visitors(ga4_property_id, ga4_credentials)
            if ga4_data:
                total_views = sum(d['views'] for d in ga4_data)
                st.sidebar.success(f"✅ GA4: {total_views} high-intent page views")
            else:
                st.sidebar.info("ℹ️ GA4: Geen high-intent data (nog)")
        except Exception as e:
            st.sidebar.warning(f"⚠️ GA4 niet beschikbaar: {str(e)[:50]}")
            ga4_enabled = False
    else:
        st.sidebar.info("ℹ️ GA4 integratie uitgeschakeld")

    # Segment leads (nieuwe thresholds voor 0-40 score range)
    hot_leads = [s for s in subscribers if s['engagement_score'] >= 25]
    warm_leads = [s for s in subscribers if 12 <= s['engagement_score'] < 25]
    cold_leads = [s for s in subscribers if s['engagement_score'] < 12]

    # ==================== METRICS ====================
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("🔥 HOT - Direct emailen!", len(hot_leads))

    with col2:
        st.metric("🟡 Warm - Follow-up", len(warm_leads))

    with col3:
        st.metric("🧊 Cold - Nurture", len(cold_leads))

    with col4:
        st.metric("📊 Totaal Leads", len(subscribers))

    st.markdown("---")

    # ==================== HOT LEADS ====================
    if hot_leads:
        st.markdown("## 🔥 HOT LEADS - Email of bel deze mensen vandaag!")
        if pipedrive_enabled:
            st.info("💡 Deze leads hebben hoge engagement (score ≥25: opens + clicks + website sessions via GA4 User-ID) • 📞 Telefoonnummers uit Pipedrive CRM")
        else:
            st.info("💡 Deze leads hebben hoge engagement (score ≥25 punten: opens + clicks + website sessions)")

        # Build dataframe with conditional columns
        hot_data = []
        for i, s in enumerate(hot_leads[:50]):
            row = {
                '#': i+1,
                'Naam': s.get('name', 'Onbekend'),
                'Email': s.get('email', ''),
            }
            if pipedrive_enabled:
                row['Telefoon'] = s.get('phone', '-')
                row['Bedrijf'] = s.get('company', '-')
            row.update({
                'Score': s['engagement_score'],
                'Opens': s.get('opened', 0),
                'Clicks': s.get('clicked', 0)
            })
            if pipedrive_enabled:
                row['Website'] = s.get('website_visits', 0)
            hot_data.append(row)

        hot_df = pd.DataFrame(hot_data)

        st.dataframe(
            hot_df,
            use_container_width=True,
            height=400,
            hide_index=True
        )

        # Download button
        csv = hot_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Download HOT leads CSV",
            csv,
            "hot_leads.csv",
            "text/csv",
            key='hot-csv'
        )
    else:
        st.info("Geen HOT leads op dit moment.")

    st.markdown("---")

    # ==================== WARM LEADS ====================
    with st.expander(f"🟡 WARM LEADS ({len(warm_leads)}) - Klik om te openen"):
        st.caption("Goede engagement maar nog niet super actief - ideaal voor targeted follow-up")

        if warm_leads:
            warm_data = []
            for s in warm_leads[:100]:
                row = {
                    'Naam': s.get('name', 'Onbekend'),
                    'Email': s.get('email', ''),
                    'Score': s['engagement_score'],
                    'Opens': s.get('opened', 0),
                    'Clicks': s.get('clicked', 0)
                }
                if pipedrive_enabled:
                    row['Website'] = s.get('website_visits', 0)
                warm_data.append(row)

            warm_df = pd.DataFrame(warm_data)

            st.dataframe(warm_df, use_container_width=True, hide_index=True)

            # Download
            csv = warm_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download WARM leads CSV",
                csv,
                "warm_leads.csv",
                "text/csv",
                key='warm-csv'
            )

    # ==================== COLD LEADS ====================
    with st.expander(f"🧊 COLD LEADS ({len(cold_leads)}) - Klik om te openen"):
        st.caption("Lage engagement - blijf nurture via automatische campagnes")
        st.metric("Totaal in nurture flow", len(cold_leads))

    # ==================== GA4 WEBSITE ENGAGEMENT ====================
    if ga4_enabled and ga4_data:
        st.markdown("---")
        st.markdown("## 🌐 Website Engagement (GA4)")
        st.caption("High-intent pagina's: tarieven, prijzen, demo, contact, afspraak")

        col1, col2, col3 = st.columns(3)

        with col1:
            total_views = sum(d['views'] for d in ga4_data)
            st.metric("High-Intent Views", f"{total_views:,}", "Laatste 30 dagen")

        with col2:
            total_users = sum(d['users'] for d in ga4_data)
            st.metric("Unieke Bezoekers", f"{total_users:,}")

        with col3:
            top_page = max(ga4_data, key=lambda x: x['views'])['page'] if ga4_data else '-'
            st.metric("Top Pagina", top_page[:30])

        # Show top pages
        if len(ga4_data) > 0:
            ga4_df = pd.DataFrame([{
                'Pagina': d['page'][:50],
                'Views': d['views'],
                'Bezoekers': d['users'],
                'Stad': d['city']
            } for d in sorted(ga4_data, key=lambda x: x['views'], reverse=True)[:10]])

            st.dataframe(ga4_df, use_container_width=True, hide_index=True)

        st.info("💡 **User-ID tracking actief** - over 2-3 weken kunnen we leads koppelen aan website gedrag!")

    # ==================== CAMPAIGN STATS ====================
    st.markdown("---")
    st.markdown("## 📊 Quick Stats")

    col1, col2, col3 = st.columns(3)

    with col1:
        avg_opens = sum(s.get('opened', 0) for s in subscribers) / len(subscribers)
        st.metric("Gem. Opens per Lead", f"{avg_opens:.1f}")

    with col2:
        total_opens = sum(s.get('opened', 0) for s in subscribers)
        st.metric("Totaal Opens", f"{total_opens:,}")

    with col3:
        total_clicks = sum(s.get('clicked', 0) for s in subscribers)
        st.metric("Totaal Clicks", f"{total_clicks:,}")

    # ==================== FOOTER ====================
    st.markdown("---")
    st.caption(f"📅 Laatste update: {datetime.now().strftime('%Y-%m-%d %H:%M')} • Auto-refresh: elk uur (cache)")
    st.caption("💡 **Tip**: Refresh de pagina voor nieuwe data")

    # Instructions
    with st.expander("ℹ️ Hoe gebruik je dit dashboard?"):
        st.markdown("""
        ### 🎯 Actieplan:

        **1. HOT Leads (🔥 score ≥25)**
        - **Email deze mensen vandaag** (hoogste prioriteit!)
        - Zeer hoge engagement: veel opens/clicks + website bezoeken
        - Download CSV en importeer in je email tool

        **2. Warm Leads (🟡 score 12-24)**
        - Goede engagement maar nog niet super actief
        - Stuur targeted follow-up emails
        - Ideaal voor persoonlijke benadering

        **3. Cold Leads (🧊 score <12)**
        - Lage engagement
        - Automatische nurture campagne via MailerLite
        - Geen directe sales actie nodig

        ### 📊 Scoring:
        - **Opens**: 0-15 punten (10+ = 15 pts, 5-9 = 12 pts, 3-4 = 8 pts, 1-2 = 4 pts)
        - **Clicks**: 0-15 punten (10+ = 15 pts, 5-9 = 12 pts, 3-4 = 8 pts, 1-2 = 4 pts)
        - **Website sessions**: 0-10 punten (10+ = 10 pts, 5-9 = 8 pts, 3-4 = 6 pts, 1-2 = 3 pts)
        - **Totaal**: 0-40 punten mogelijk

        ### 🌐 Website tracking:
        - Via GA4 User-ID tracking (email wordt gekoppeld bij form submit)
        - Telt alleen mee als de lead hun email heeft gedeeld op de website
        - Pas volledig actief over 2-3 weken (nieuwe GA4 property opgebouwd)

        ### 🔄 Data refresh:
        Dashboard gebruikt caching (1 uur). Wil je nieuwe data? Refresh de pagina!
        """)

except Exception as e:
    st.error(f"❌ Error bij laden van data: {e}")
    st.info("Check je API token en probeer opnieuw.")
