"""Actiegericht Lead Scoring Dashboard - Wie bellen/mailen vandaag?"""
import streamlit as st
import pandas as pd
from mailerlite_api_v2 import MailerLiteAPI
from datetime import datetime

# Try to import GA4 (optional)
try:
    from ga4_data_api import GA4DataAPI
    GA4_AVAILABLE = True
except Exception:
    GA4_AVAILABLE = False

# Page config
st.set_page_config(
    page_title="🎯 Lead Action Dashboard",
    page_icon="🎯",
    layout="wide"
)

# Custom CSS voor action buttons en styling
st.markdown("""
<style>
    .action-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        margin: 10px 0;
    }
    .hot-lead {
        background: #fee;
        border-left: 4px solid #e53e3e;
        padding: 15px;
        margin: 10px 0;
        border-radius: 5px;
    }
    .warm-lead {
        background: #fef5e7;
        border-left: 4px solid #f39c12;
        padding: 15px;
        margin: 10px 0;
        border-radius: 5px;
    }
    .contact-info {
        font-family: monospace;
        background: #f7f7f7;
        padding: 5px 10px;
        border-radius: 3px;
        display: inline-block;
        margin: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.title("🎯 Lead Action Dashboard")
st.markdown("### Wie moet je vandaag bellen of mailen?")
st.markdown("---")

# Initialize MailerLite API
@st.cache_resource
def init_mailerlite():
    return MailerLiteAPI()

ml = init_mailerlite()

# Load data
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_mailerlite_data():
    """Load MailerLite subscribers and engagement."""
    subscribers = ml.get_all_subscribers(limit=2000)

    # Calculate engagement score for each
    for sub in subscribers:
        email = sub['email']
        engagement = ml.get_engagement_score(email, subscriber_data=sub)
        sub['engagement_score'] = engagement['engagement_score']
        sub['open_rate'] = (sub.get('opened', 0) / sub.get('sent', 1) * 100) if sub.get('sent', 0) > 0 else 0
        sub['click_rate'] = (sub.get('clicked', 0) / sub.get('sent', 1) * 100) if sub.get('sent', 0) > 0 else 0

    # Sort by engagement
    subscribers.sort(key=lambda x: x['engagement_score'], reverse=True)

    return subscribers

with st.spinner("📊 Laden van MailerLite data..."):
    subscribers = load_mailerlite_data()

# Segment subscribers
hot_leads = [s for s in subscribers if s['engagement_score'] >= 20]  # Very engaged
warm_leads = [s for s in subscribers if 10 <= s['engagement_score'] < 20]  # Moderately engaged
cold_leads = [s for s in subscribers if s['engagement_score'] < 10]  # Low engagement

# Funnel overview
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "🔥 HOT - Direct emailen!",
        len(hot_leads),
        f"{len(hot_leads)/len(subscribers)*100:.1f}% van totaal"
    )

with col2:
    st.metric(
        "🟡 Warm - Email follow-up",
        len(warm_leads),
        f"{len(warm_leads)/len(subscribers)*100:.1f}% van totaal"
    )

with col3:
    st.metric(
        "🧊 Cold - Nurture campagne",
        len(cold_leads),
        f"{len(cold_leads)/len(subscribers)*100:.1f}% van totaal"
    )

st.markdown("---")

# ACTION SECTION 1: HOT LEADS - DIRECT CONTACT
st.markdown("## 🔥 HOT LEADS - Direct contact!")
st.markdown("Deze mensen openen ALLE emails en klikken actief door. **Email ze vandaag!**")
st.info("📞 **Telefoonnummers beschikbaar morgen** (via Pipedrive CRM data na quota reset om 01:00)")

if hot_leads:
    # Create compact dataframe
    hot_df = pd.DataFrame([{
        '#': i+1,
        'Naam': sub.get('name', 'Onbekend'),
        'Email': sub.get('email'),
        'Bedrijf': sub.get('fields', [{}])[0].get('value', 'Onbekend') if sub.get('fields') else 'Onbekend',
        'Score': sub['engagement_score'],
        'Opens': sub.get('opened', 0),
        'Clicks': sub.get('clicked', 0),
        'Open %': f"{sub['open_rate']:.0f}%",
    } for i, sub in enumerate(hot_leads[:20])])

    # Style dataframe
    def highlight_hot(row):
        return ['background-color: #fee2e2']*len(row)

    styled_df = hot_df.style.apply(highlight_hot, axis=1)

    # Display compact table
    st.dataframe(styled_df, use_container_width=True, height=400)

    # Action buttons
    col1, col2 = st.columns(2)
    with col1:
        csv = hot_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            "📥 Download Hot Leads (CSV)",
            csv,
            f"hot_leads_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv",
            use_container_width=True
        )
    with col2:
        st.metric("🔥 Direct emailen", len(hot_df), "Zeer betrokken")
else:
    st.info("Geen hot leads gevonden. Check je MailerLite data.")

st.markdown("---")

# ACTION SECTION 2: WARM LEADS - EMAIL FOLLOW-UP
st.markdown("## 📧 Warm Leads - Email Follow-up")
st.markdown("Deze mensen tonen interesse maar zijn niet super actief. **Stuur targeted email.**")

if warm_leads:
    warm_df = pd.DataFrame([{
        'Naam': sub.get('name', 'Onbekend'),
        'Email': sub.get('email'),
        'Score': sub['engagement_score'],
        'Opens': sub.get('opened', 0),
        'Open %': f"{sub['open_rate']:.0f}%",
    } for sub in warm_leads[:10]])

    for i, lead in enumerate(warm_df.to_dict('records')):
        st.markdown(f"""
        <div class="warm-lead">
            <strong>#{i+1} {lead['Naam']}</strong> •
            {lead['Email']} •
            Score: {lead['Score']}/30 •
            {lead['Opens']} opens ({lead['Open %']})
        </div>
        """, unsafe_allow_html=True)

    # Download button
    csv = warm_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        "📥 Download Warm Leads (CSV)",
        csv,
        f"warm_leads_{datetime.now().strftime('%Y%m%d')}.csv",
        "text/csv"
    )
else:
    st.info("Geen warm leads gevonden.")

st.markdown("---")

# CAMPAIGN PERFORMANCE
st.markdown("## 📊 Campaign Performance")

try:
    campaigns = ml.get_campaigns()
    sent_campaigns = [c for c in campaigns if c.get('status') == 'sent']

    if sent_campaigns:
        campaign_df = pd.DataFrame([{
            'Campaign': c.get('name', 'Unnamed')[:50],
            'Open Rate': f"{c.get('opened', {}).get('rate', 0)*100:.1f}%",
            'Click Rate': f"{c.get('clicked', {}).get('rate', 0)*100:.1f}%",
            'Opens': c.get('opened', {}).get('count', 0),
            'Clicks': c.get('clicked', {}).get('count', 0),
        } for c in sent_campaigns[:5]])

        st.dataframe(campaign_df, use_container_width=True)
except Exception as e:
    st.warning(f"Kan campaign data niet laden: {e}")

st.markdown("---")

# GA4 WEBSITE ENGAGEMENT
if GA4_AVAILABLE:
    st.markdown("## 🌐 Website Engagement (GA4)")

    try:
        @st.cache_resource
        def init_ga4():
            return GA4DataAPI()

        ga4 = init_ga4()

        @st.cache_data(ttl=3600)
        def load_ga4_high_intent():
            """Load high-intent page views from GA4."""
            return ga4.get_high_intent_pages(days=30)

        with st.spinner("📊 Laden van GA4 website data..."):
            high_intent_pages = load_ga4_high_intent()

        if high_intent_pages:
            # Summary metrics
            col1, col2, col3 = st.columns(3)

            with col1:
                total_views = sum(p['page_views'] for p in high_intent_pages)
                st.metric("High-Intent Page Views", f"{total_views:,}", "Laatste 30 dagen")

            with col2:
                pricing_views = sum(p['page_views'] for p in high_intent_pages if p['intent_type'] == 'pricing')
                st.metric("Pricing/Tarief Views", f"{pricing_views:,}")

            with col3:
                contact_views = sum(p['page_views'] for p in high_intent_pages if p['intent_type'] == 'contact')
                st.metric("Contact Views", f"{contact_views:,}")

            # Top pages
            st.markdown("**Top High-Intent Pages:**")
            ga4_df = pd.DataFrame([{
                'Pagina': p['page_path'][:60],
                'Type': p['intent_type'].title(),
                'Views': p['page_views'],
                'Unieke Bezoekers': p['active_users']
            } for p in high_intent_pages[:10]])

            st.dataframe(ga4_df, use_container_width=True, height=300)

            st.info("💡 **Tip**: User-ID tracking is actief - over 2-3 weken kunnen we leads koppelen aan website gedrag!")
        else:
            st.info("📊 GA4 data verzamelen... User-ID tracking is actief op notifica.nl. Data verschijnt over 2-3 weken.")

    except Exception as e:
        st.warning(f"GA4 data niet beschikbaar: {str(e)[:100]}")
        st.info("ℹ️ GA4 tracking wordt binnenkort toegevoegd aan het dashboard.")
else:
    st.info("🌐 **Website Engagement**: GA4 integratie komt binnenkort!")

st.markdown("---")

# FUNNEL STATISTICS
st.markdown("## 📈 Funnel Statistieken")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Totaal Subscribers", f"{len(subscribers):,}")

with col2:
    avg_open = sum(s['open_rate'] for s in subscribers) / len(subscribers) if subscribers else 0
    st.metric("Gem. Open Rate", f"{avg_open:.1f}%")

with col3:
    total_opens = sum(s.get('opened', 0) for s in subscribers)
    st.metric("Totaal Opens", f"{total_opens:,}")

with col4:
    total_clicks = sum(s.get('clicked', 0) for s in subscribers)
    st.metric("Totaal Clicks", f"{total_clicks:,}")

# Footer
st.markdown("---")
st.caption(f"📅 Laatste update: {datetime.now().strftime('%Y-%m-%d %H:%M')} • Data bron: MailerLite API")
st.caption("💡 **Tip**: Refresh de pagina voor nieuwe data • **Morgen**: Pipedrive CRM data wordt toegevoegd")

# Instructions
with st.expander("ℹ️ Hoe gebruik je dit dashboard?"):
    st.markdown("""
    ### 🎯 Actieplan:

    **1. HOT Leads (🔥)**
    - **Email deze mensen vandaag** (hoogste prioriteit!)
    - Ze openen alles en klikken actief door
    - Directe sales opportunity
    - 📞 **Tel. nummers beschikbaar morgen** (via Pipedrive)

    **2. Warm Leads (🟡)**
    - Stuur targeted email follow-up
    - Gebruik interesse uit clicks voor personalisatie
    - Plan eventueel call-back (na Pipedrive integratie)

    **3. Cold Leads (🧊)**
    - Nurture campagne (automatisch via MailerLite)
    - Content marketing
    - Geen directe sales actie nodig

    ### 📊 Data bronnen:
    - **Nu**: MailerLite API (email engagement)
    - **Morgen 01:00**: + Pipedrive API (CRM activiteit + telefoonnummers!)
    - **Over 2-3 weken**: + GA4 (website gedrag)
    """)
