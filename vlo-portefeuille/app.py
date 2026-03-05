import streamlit as st
from config import APP_TITLE, APP_ICON, APP_LAYOUT

st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout=APP_LAYOUT)

# Compact styling for tables and inputs
st.markdown("""
<style>
    /* Smaller font in data editor and dataframes */
    .stDataFrame, [data-testid="stDataEditor"] {
        font-size: 0.82rem;
    }
    /* Force narrow columns in data editor */
    [data-testid="stDataEditor"] [data-testid="column-header"],
    [data-testid="stDataEditor"] .dvn-scroller {
        font-size: 0.82rem;
    }
    [data-testid="stDataEditor"] input,
    [data-testid="stDataEditor"] select {
        font-size: 0.82rem !important;
    }
    /* Compact metric cards */
    [data-testid="stMetricValue"] {
        font-size: 1.4rem;
    }
    /* Compact number/text inputs */
    .stNumberInput, .stTextInput, .stSelectbox, .stDateInput {
        font-size: 0.9rem;
    }
    /* Tighter sidebar */
    div[data-testid="stSidebarContent"] {
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

pg = st.navigation([
    st.Page("pages/1_Omzetverdeling.py", title="Omzetverdeling", default=True),
    st.Page("pages/2_Overzicht.py", title="Overzicht"),
    st.Page("pages/3_Project_Detail.py", title="Project Detail"),
])
pg.run()
