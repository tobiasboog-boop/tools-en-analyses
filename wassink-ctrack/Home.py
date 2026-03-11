import streamlit as st
import sys, os

sys.path.insert(0, os.path.dirname(__file__))
from src.database import check_connections
from src.auth import check_password
from src.sidebar import show_logo

st.set_page_config(
    page_title="Wassink Ritclassificatie",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

if not check_password():
    st.stop()

show_logo()

st.title("Wassink Ritclassificatie")
st.caption("Belastingdienst — LB km (prive) vs OB km (woon-werk)")

# --- Connection status ---
st.subheader("Koppelingen")
conn_status = check_connections()
cols = st.columns(2)
for i, (naam, label) in enumerate([('ctrack', 'C-Track DWH'), ('syntess', 'Syntess DWH')]):
    s = conn_status[naam]
    icon = "🟢" if s['ok'] else "🔴"
    with cols[i]:
        st.markdown(f"{icon} **{label}** — {s['bron']}")
        if s['detail']:
            st.caption(s['detail'])

st.markdown("---")
st.markdown("Ga naar **Ritclassificatie** in het menu links.")
