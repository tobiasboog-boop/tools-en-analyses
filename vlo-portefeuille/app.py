import streamlit as st
from config import APP_TITLE, APP_ICON, APP_LAYOUT

st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout=APP_LAYOUT)

pg = st.navigation([
    st.Page("pages/1_Omzetverdeling.py", title="Omzetverdeling", default=True),
    st.Page("pages/2_Overzicht.py", title="Overzicht"),
    st.Page("pages/3_Project_Detail.py", title="Project Detail"),
])
pg.run()
