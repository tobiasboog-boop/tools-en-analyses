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
    """Bereken engagement score (0-30 punten)."""
    score = 0

    # Open rate scoring (0-15 punten)
    open_rate = subscriber.get('open_rate', 0)
    if open_rate >= 80:
        score += 15
    elif open_rate >= 60:
        score += 12
    elif open_rate >= 40:
        score += 8
    elif open_rate >= 20:
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

def enrich_with_pipedrive(subscribers, pipedrive_persons):
    """Match MailerLite subscribers with Pipedrive persons and add phone numbers."""
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

    return subscribers

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

# Load subscribers
try:
    subscribers = get_subscribers(mailerlite_token)

    if not subscribers:
        st.warning("Geen subscribers gevonden!")
        st.stop()

    # Calculate engagement scores
    for sub in subscribers:
        sub['engagement_score'] = calculate_engagement_score(sub)

    # Enrich with Pipedrive data (if available)
    if pipedrive_enabled:
        try:
            pipedrive_persons = get_pipedrive_persons(pipedrive_token)
            subscribers = enrich_with_pipedrive(subscribers, pipedrive_persons)
            st.sidebar.success(f"✅ Pipedrive: {len(pipedrive_persons)} personen geladen")
        except Exception as e:
            st.sidebar.warning(f"⚠️ Pipedrive niet beschikbaar: {str(e)[:50]}")
            pipedrive_enabled = False
    else:
        st.sidebar.info("ℹ️ Pipedrive integratie uitgeschakeld")

    # Segment leads
    hot_leads = [s for s in subscribers if s['engagement_score'] >= 20]
    warm_leads = [s for s in subscribers if 10 <= s['engagement_score'] < 20]
    cold_leads = [s for s in subscribers if s['engagement_score'] < 10]

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
            st.info("💡 Deze leads hebben hoge engagement (80%+ open rate of 10+ clicks) • 📞 Telefoonnummers uit Pipedrive CRM")
        else:
            st.info("💡 Deze leads hebben hoge engagement (80%+ open rate of 10+ clicks)")

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
                'Open Rate': f"{s.get('open_rate', 0):.0f}%",
                'Clicks': s.get('clicked', 0)
            })
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
            warm_df = pd.DataFrame([{
                'Naam': s.get('name', 'Onbekend'),
                'Email': s.get('email', ''),
                'Score': s['engagement_score'],
                'Open Rate': f"{s.get('open_rate', 0):.0f}%",
                'Clicks': s.get('clicked', 0)
            } for s in warm_leads[:100]])

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

    # ==================== CAMPAIGN STATS ====================
    st.markdown("---")
    st.markdown("## 📊 Quick Stats")

    col1, col2, col3 = st.columns(3)

    with col1:
        avg_open = sum(s.get('open_rate', 0) for s in subscribers) / len(subscribers)
        st.metric("Gem. Open Rate", f"{avg_open:.1f}%")

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

        **1. HOT Leads (🔥 score ≥20)**
        - **Email deze mensen vandaag** (hoogste prioriteit!)
        - Zeer hoge engagement (80%+ open rate of 10+ clicks)
        - Download CSV en importeer in je email tool

        **2. Warm Leads (🟡 score 10-19)**
        - Goede engagement maar nog niet super actief
        - Stuur targeted follow-up emails
        - Ideaal voor persoonlijke benadering

        **3. Cold Leads (🧊 score <10)**
        - Lage engagement
        - Automatische nurture campagne via MailerLite
        - Geen directe sales actie nodig

        ### 📊 Scoring:
        - **Open Rate**: 0-15 punten (80%+ = 15 pts, 60-79% = 12 pts, etc.)
        - **Clicks**: 0-15 punten (10+ = 15 pts, 5-9 = 12 pts, etc.)
        - **Totaal**: 0-30 punten mogelijk

        ### 🔄 Data refresh:
        Dashboard gebruikt caching (1 uur). Wil je nieuwe data? Refresh de pagina!
        """)

except Exception as e:
    st.error(f"❌ Error bij laden van data: {e}")
    st.info("Check je API token en probeer opnieuw.")
