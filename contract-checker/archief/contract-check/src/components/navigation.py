"""
Custom Sidebar Navigation
Implements collapsible sections for better UX
"""
import streamlit as st


def render_navigation():
    """Render custom sidebar navigation with collapsible sections."""

    # Hide default Streamlit navigation
    st.markdown("""
    <style>
    [data-testid="stSidebarNav"] {display: none;}
    </style>
    """, unsafe_allow_html=True)

    # Custom navigation in sidebar
    with st.sidebar:
        st.title("Contract Check")
        st.divider()

        # Configuratie section (collapsible)
        with st.expander("Configuratie", expanded=False):
            st.page_link("pages/00_Classificatie_Opdracht.py", label="Classificatie Opdracht")
            st.page_link("pages/01_Bedrijfscontext.py", label="Bedrijfscontext")
            st.page_link("pages/1_Contract_Register.py", label="Contract Register")
            st.page_link("pages/2_Werkbon_Selectie.py", label="Werkbon Selectie")
            st.page_link("pages/3_Beoordeling.py", label="Beoordeling")
            st.page_link("pages/4_Results.py", label="Results")
            st.page_link("pages/09_Help.py", label="Help")

        st.divider()

        # Gebruiker section (collapsible)
        with st.expander("Gebruiker", expanded=False):
            st.page_link("pages/20_Quick_Classificatie.py", label="Quick Classificatie")
            st.page_link("pages/21_Mijn_Resultaten.py", label="Mijn Resultaten")
