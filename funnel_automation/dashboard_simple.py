"""Lead Scoring Dashboard - Simpel & Snel (alles in 1 bestand)"""
import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from typing import Dict, List, Optional

# ==================== MAILERLITE API ====================

class MailerLiteAPI:
    """MailerLite API client - inline versie."""

    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://api.mailerlite.com/api/v2"
        self.headers = {
            'X-MailerLite-ApiKey': self.api_token,
            'Content-Type': 'application/json'
        }
        self.main_group_id = 177296943307818341

    def get_subscribers(self, limit: int = 2000) -> List[Dict]:
        """Haal alle subscribers op."""
        all_subscribers = []
        offset = 0

        while True:
            url = f"{self.base_url}/groups/{self.main_group_id}/subscribers"
            params = {'limit': 1000, 'offset': offset}

            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
                response.raise_for_status()
                batch = response.json()

                if not batch:
                    break

                all_subscribers.extend(batch)

                if len(batch) < 1000:
                    break

                offset += 1000

                if len(all_subscribers) >= limit:
                    break

            except Exception as e:
                st.error(f"API Error: {e}")
                break

        return all_subscribers

    def calculate_engagement_score(self, subscriber: Dict) -> int:
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

# ==================== STREAMLIT APP ====================

st.set_page_config(
    page_title="🎯 Lead Dashboard",
    page_icon="🎯",
    layout="wide"
)

st.title("🎯 Lead Action Dashboard")
st.caption("Wie moet je vandaag emailen?")

# Load API token from secrets
try:
    api_token = st.secrets["MAILERLITE_API_TOKEN"]
except (KeyError, FileNotFoundError):
    st.error("❌ MAILERLITE_API_TOKEN niet gevonden in secrets!")
    st.info("Voeg je API token toe in Streamlit Cloud Settings → Secrets")
    st.stop()

# Initialize API
@st.cache_resource
def init_api():
    return MailerLiteAPI(api_token)

ml = init_api()

# Load data
@st.cache_data(ttl=3600)
def load_data():
    with st.spinner("📊 Laden van subscriber data..."):
        subscribers = ml.get_subscribers(limit=2000)

        # Calculate engagement scores
        for sub in subscribers:
            sub['engagement_score'] = ml.calculate_engagement_score(sub)

        return subscribers

try:
    subscribers = load_data()

    if not subscribers:
        st.warning("Geen subscribers gevonden!")
        st.stop()

    # Segment leads
    hot_leads = [s for s in subscribers if s['engagement_score'] >= 20]
    warm_leads = [s for s in subscribers if 10 <= s['engagement_score'] < 20]
    cold_leads = [s for s in subscribers if s['engagement_score'] < 10]

    # Summary metrics
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

    # HOT LEADS
    if hot_leads:
        st.markdown("## 🔥 HOT LEADS - Email deze mensen vandaag!")

        hot_df = pd.DataFrame([{
            '#': i+1,
            'Naam': s.get('name', 'Onbekend'),
            'Email': s.get('email', ''),
            'Score': s['engagement_score'],
            'Open Rate': f"{s.get('open_rate', 0):.0f}%",
            'Clicks': s.get('clicked', 0)
        } for i, s in enumerate(hot_leads[:20])])

        st.dataframe(hot_df, use_container_width=True, height=400)

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

    # WARM LEADS
    with st.expander(f"🟡 WARM LEADS ({len(warm_leads)}) - Klik om te openen"):
        if warm_leads:
            warm_df = pd.DataFrame([{
                'Naam': s.get('name', 'Onbekend'),
                'Email': s.get('email', ''),
                'Score': s['engagement_score'],
                'Open Rate': f"{s.get('open_rate', 0):.0f}%"
            } for s in warm_leads[:50]])

            st.dataframe(warm_df, use_container_width=True)

    # COLD LEADS
    with st.expander(f"🧊 COLD LEADS ({len(cold_leads)}) - Klik om te openen"):
        st.caption(f"Totaal: {len(cold_leads)} leads in nurture flow")

    # Footer
    st.markdown("---")
    st.caption(f"📅 Laatste update: {datetime.now().strftime('%Y-%m-%d %H:%M')} • Auto-refresh: elk uur")

except Exception as e:
    st.error(f"❌ Error: {e}")
    st.info("Check je API token en probeer opnieuw.")
