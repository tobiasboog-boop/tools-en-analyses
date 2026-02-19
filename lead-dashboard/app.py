"""Lead Dashboard - Clean setup"""
import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Lead Dashboard", page_icon="🎯")

st.title("🎯 Lead Dashboard")

# Test API
try:
    token = st.secrets["MAILERLITE_API_TOKEN"]
    st.success("✅ API Token gevonden!")
    
    # Simple API test
    headers = {'X-MailerLite-ApiKey': token}
    response = requests.get(
        "https://api.mailerlite.com/api/v2/groups",
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        groups = response.json()
        st.success(f"✅ API werkt! {len(groups)} groepen gevonden")
        
        # Show groups
        if groups:
            df = pd.DataFrame([{
                'ID': g['id'],
                'Naam': g['name'],
                'Subscribers': g['total']
            } for g in groups])
            st.dataframe(df)
    else:
        st.error(f"API Error: {response.status_code}")
        
except KeyError:
    st.error("❌ MAILERLITE_API_TOKEN niet gevonden")
except Exception as e:
    st.error(f"Error: {e}")

st.caption("Simpele test versie")
