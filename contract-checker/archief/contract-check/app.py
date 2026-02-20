#!/usr/bin/env python3
"""
WVC Contract Checker - Main Application Entry Point

Run with: streamlit run app.py
"""
import streamlit as st

st.set_page_config(
    page_title="Notifica Contract Check",
    page_icon="assets/notifica-logo.png",
    layout="wide"
)

# Define all pages
home_page = st.Page("Home.py", title="Home", default=True)

# CONFIGURATIE
# De drie lagen voor LLM classificatie:
# 1. Classificatie Opdracht - de taak voor de LLM
# 2. Bedrijfscontext - hoe werkt de klant (LLM-ready)
# 3. Contracten - contract teksten (LLM-ready)
# Plus: werkbon selectie, beoordeling, resultaten
opdracht_page = st.Page("pages/00_Classificatie_Opdracht.py", title="Classificatie Opdracht")
bedrijfscontext_page = st.Page("pages/01_Bedrijfscontext.py", title="Bedrijfscontext")
contracten_page = st.Page("pages/1_Contract_Register.py", title="Contracten")
selectie_page = st.Page("pages/2_Werkbon_Selectie.py", title="Werkbon Selectie")
beoordeling_page = st.Page("pages/3_Beoordeling.py", title="Beoordeling")
results_page = st.Page("pages/4_Results.py", title="Resultaten")
help_page = st.Page("pages/09_Help.py", title="Help")

# CLASSIFICEREN
# Dagelijks werk voor backoffice: snel werkbonnen classificeren.
quick_class_page = st.Page("pages/20_Quick_Classificatie.py", title="Start")
resultaten_page = st.Page("pages/21_Mijn_Resultaten.py", title="Mijn Resultaten")

# Navigation structure
pg = st.navigation({
    "": [home_page],
    "Configuratie": [
        opdracht_page,
        bedrijfscontext_page,
        contracten_page,
        selectie_page,
        beoordeling_page,
        results_page,
        help_page
    ],
    "Classificeren": [
        quick_class_page,
        resultaten_page
    ]
})

# Run selected page
pg.run()
