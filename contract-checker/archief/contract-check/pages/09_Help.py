#!/usr/bin/env python3
"""Help page - Documentation and support."""
import streamlit as st



# Configure page to use full width
st.set_page_config(layout="wide")

st.title("Help & Documentatie")

tab1, tab2, tab3, tab4 = st.tabs(["Overzicht", "Workflow", "Setup", "Troubleshooting"])

with tab1:
    st.header("WVC Contract Checker")

    st.markdown("""
    **AI-gedreven classificatie van werkbonnen voor contract analyse.**

    Dit systeem helpt WVC om automatisch te bepalen of werkbonkosten binnen of buiten een servicecontract vallen.
    Claude AI analyseert elke werkbon tegen het juiste contract en geeft een classificatie.

    ### Classificatie Logica

    Elke werkbon wordt geclassificeerd als:

    | Classificatie | Betekenis | Score |
    |---------------|-----------|-------|
    | **JA** | Volledig binnen contract | ≥ 0.85 |
    | **NEE** | Buiten contract (factureren) | ≥ 0.85 |
    | **ONZEKER** | Handmatige review nodig | < 0.85 |

    ### Twee Modi

    **Classificatie Modus**
    - Voor openstaande werkbonnen (Uitgevoerd + Openstaand)
    - De AI bepaalt of kosten binnen/buiten contract vallen
    - Gebruikt voor dagelijkse operationele beslissingen

    **Validatie Modus**
    - Voor historische werkbonnen (Uitgevoerd + Historisch)
    - Vergelijkt AI classificatie met werkelijke facturatie
    - Meet **hit rate**: hoe vaak klopt de AI?
    - Gebruikt voor kwaliteitsmeting en verbetering

    ### De Drie Lagen voor Classificatie

    De prompt naar Claude AI bestaat uit drie lagen:

    | Laag | Bron | Beschrijving |
    |------|------|--------------|
    | **1. Opdracht + Bedrijfscontext** | Classificatie Opdracht + Bedrijfscontext pagina's | System prompt: wat moet de AI doen? Hoe werkt WVC? |
    | **2. Contract** | Contract Register | User message: het relevante contract (LLM-ready) |
    | **3. Werkbon** | Automatisch uit SQL | User message: het werkbon verhaal met alle details |

    De classificatie werkt als volgt:

    1. **Classificatie opdracht**: Definieert de taak voor de AI (ingesteld via Classificatie Opdracht pagina)
    2. **Bedrijfscontext**: Hoe WVC werkt met contracten, werkbonnen, Syntess (ingesteld via Bedrijfscontext pagina)
    3. **Debiteur-specifiek contract**: Voor elke werkbon wordt de `debiteur_code` gebruikt om het
       juiste contract te vinden via de `contract_relatie` tabel
    4. **Werkbon verhaal**: Alle details van de werkbon inclusief kosten, paragrafen, opvolgingen
       worden gecombineerd tot een compleet verhaal
    5. **AI analyse**: Claude ontvangt opdracht + context als system prompt, en contract + werkbon als user message

    ⚠️ **Dit is GEEN machine learning** - Er wordt geen model getraind op historische data.
    Claude leest simpelweg het contract en de werkbon, en maakt een beoordeling op basis van
    de contractvoorwaarden en WVC werkwijze.
    """)

    st.divider()

    st.header("Success Metrics")

    col1, col2, col3 = st.columns(3)
    col1.metric("False Negative Rate", "< 5%", help="Gemiste facturatie")
    col2.metric("False Positive Rate", "< 3%", help="Onjuiste contract coverage")
    col3.metric("ONZEKER percentage", "15-25%", help="Handmatige review nodig")

with tab2:
    st.header("Workflow: De 6 Stappen")

    st.markdown("""
    Het systeem bestaat uit 6 hoofdstappen die je in volgorde doorloopt:
    """)

    st.subheader("🏠 Home")
    st.markdown("""
    - **Workflow uitleg**: Visuele uitleg van alle stappen
    - **Data Analyse**: Inzicht in werkbonnen in Syntess (status, leeftijd, veldgebruik)
    - **Quick navigation**: Directe links naar alle pagina's
    """)

    st.divider()

    st.subheader("1. Classificatie Opdracht")
    st.markdown("""
    **Definieer de taak die aan de AI wordt gesteld.**

    Hier stel je in:
    - De opdracht: wat moet de AI beoordelen?
    - Het output formaat: hoe moet de AI antwoorden?

    Dit vormt samen met de bedrijfscontext de system prompt voor Claude.
    """)

    st.divider()

    st.subheader("2. Bedrijfscontext")
    st.markdown("""
    **Configureer de algemene werkwijze van WVC.**

    Hier stel je in hoe WVC werkt met:
    - Algemene werkwijze (verplicht)
    - Syntess configuratie (optioneel)
    - Werkbon verwerking (optioneel)
    - Contract interpretatie (optioneel)

    Deze context wordt bij elke classificatie meegestuurd naar de AI zodat beslissingen
    genomen worden binnen de juiste WVC procedures.

    Tip: Beschrijf hier ook hoe WVC omgaat met uitzonderingen, speciaal gevallen,
    en interpretatie van contractartikelen.
    """)

    st.divider()

    st.subheader("3. Contract Register")
    st.markdown("""
    **Beheer contracten en koppel ze aan debiteuren.**

    - Upload Excel met contracten uit OneDrive/SharePoint
    - Systeem verrijkt contracten automatisch (LLM-ready versie)
    - Koppel contracten aan debiteuren via het register
    - Eén contract kan aan meerdere debiteuren gekoppeld zijn

    **Belangrijk**: De `contract_relatie` tabel bepaalt welk contract bij welke werkbon hoort.
    Per werkbon wordt de debiteur code gebruikt om het juiste contract op te zoeken.
    """)

    st.divider()

    st.subheader("4. Werkbon Selectie")
    st.markdown("""
    **Selecteer werkbonnen uit Syntess datawarehouse.**

    **Filters:**
    - Debiteur: Selecteer specifieke debiteur
    - Datumbereik: Filter op periode
    - Max resultaten: Beperk aantal werkbonnen

    **Twee modi:**
    - **Classificatie**: Openstaande werkbonnen (Uitgevoerd + Openstaand)
    - **Validatie**: Historische werkbonnen (Uitgevoerd + Historisch)

    **Per werkbon zie je:**
    - 📄 Contract badge: Welk contract gekoppeld is
    - ❌ Geen contract: Als er geen contract gevonden is
    - ✓ Al beoordeeld: Als werkbon al eerder geclassificeerd is

    💡 **Tip**: Filter op "Verberg al beoordeelde" om alleen nieuwe werkbonnen te zien.
    """)

    st.divider()

    st.subheader("5. Beoordeling")
    st.markdown("""
    **Classificeer werkbonnen met AI.**

    **Preview werkbonnen en contracten:**
    - Zie per debiteur groep welk contract gebruikt wordt
    - Controleer of de juiste contracten gekoppeld zijn
    - Zie hoeveel werkbonnen per debiteur

    **Start Beoordeling:**
    - AI haalt automatisch het juiste contract op per werkbon
    - WVC werkwijze wordt meegestuurd als context
    - Werkbon verhaal wordt gebouwd uit alle details
    - Claude analyseert en geeft classificatie: JA/NEE/ONZEKER

    **Opties:**
    - Resultaten opslaan in database (aangeraden)
    - Verhaal tonen per werkbon (voor debugging)

    Bij validatie modus wordt ook de werkelijke facturatie getoond na classificatie.
    """)

    st.divider()

    st.subheader("6. Resultaten")
    st.markdown("""
    **Bekijk en analyseer classificatie resultaten.**

    **4 tabs:**

    1. **Overzicht**: Dashboard met KPI's
       - Totaal aantal classificaties
       - Verdeling JA/NEE/ONZEKER
       - Hit rate (alleen validatie modus)

    2. **Alle Resultaten**: Gedetailleerde tabel
       - Filters op classificatie, modus, datum
       - Sorteerbaar per kolom
       - Toon alle details per werkbon

    3. **Validatie**: Kwaliteitsmetrics (alleen validatie modus)
       - Hit rate berekening
       - False positives / negatives
       - Per classificatie breakdown
       - Classificaties die nog validatie nodig hebben

    4. **Export**: Download naar Excel
       - Selecteer periode
       - Download resultaten voor rapportage

    💡 **Tip**: Gebruik validatie modus regelmatig om AI performance te meten.
    """)

with tab3:
    st.header("Setup & Installatie")

    st.subheader("Prerequisites")
    st.markdown("""
    - Python 3.9+
    - Toegang tot WVC Postgres datawarehouse (Syntess data)
    - Anthropic API key
    - Contracten folder (OneDrive sync of lokaal)
    """)

    st.subheader("Installatie")
    st.code("""
# Clone repository
git clone <repo-url>
cd contract-check

# Create virtual environment
python -m venv .venv
.venv\\Scripts\\activate  # Windows
# of: source .venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials
    """, language="bash")

    st.subheader("Database Setup")
    st.markdown("""
    De app creëert automatisch de benodigde tabellen in het `contract_checker` schema.

    **Belangrijkste tabellen:**
    - `contracts`: Contractbestanden en content
    - `contract_relatie`: Koppeling contract <-> debiteur
    - `classifications`: AI classificatie resultaten
    - `client_config`: WVC werkwijze configuratie
    """)

    st.subheader("Configuration (.env)")
    st.code("""
# Database (WVC Datawarehouse)
DB_HOST=your-datawarehouse-host
DB_PORT=5432
DB_NAME=your-database-name
DB_USER=your-username
DB_PASSWORD=your-password
DB_SCHEMA=contract_checker

# Anthropic API
ANTHROPIC_API_KEY=sk-ant-...

# Contracts folder
CONTRACTS_FOLDER=C:/Users/YourName/OneDrive/Contracten

# Classification
CONFIDENCE_THRESHOLD=0.85
    """, language="ini")

    st.subheader("Running the App")
    st.code("""
# Start Streamlit
streamlit run Home.py

# The app will be available at http://localhost:8501
    """, language="bash")

    st.divider()

    st.subheader("Data Bronnen")
    st.markdown("""
    **Syntess Datawarehouse:**
    - `werkbonnen."Werkbonnen"`: Hoofdwerkbonnen en vervolgbonnen
    - `werkbonnen."Werkbonparagrafen"`: Paragrafen per werkbon
    - `werkbonnen."Werkbon kosten"`: Kostenregels
    - `werkbonnen."Werkbon opvolgingen"`: Opvolgingen
    - `werkbonnen."Werkbon oplossingen"`: Oplossingen
    - `stam."Documenten"`: Document metadata (aanmaakdatum)

    **Contract Checker Schema:**
    - `contract_checker.contracts`: Contracten
    - `contract_checker.contract_relatie`: Debiteur-contract mapping
    - `contract_checker.classifications`: Resultaten
    - `contract_checker.client_config`: WVC werkwijze
    """)

with tab4:
    st.header("Troubleshooting")

    st.subheader("Database Connection Errors")
    st.markdown("""
    **Error:** `connection failed: SSL error: certificate verify failed`

    **Oplossing:**
    - Controleer DB_HOST, DB_PORT, DB_NAME in .env
    - Controleer of de database bestaat
    - Test connectie met psql of DBeaver

    ---

    **Error:** `relation "contract_checker.contracts" does not exist`

    **Oplossing:**
    - De app zou tabellen automatisch moeten aanmaken
    - Check of je schrijfrechten hebt op het schema
    - Run `init_db()` handmatig indien nodig
    """)

    st.divider()

    st.subheader("Contract Loading Errors")
    st.markdown("""
    **Error:** `Geen contracten gevonden voor debiteur`

    **Oplossing:**
    - Ga naar **Contract Register** (Contracten pagina)
    - Controleer of er een relatie bestaat voor deze debiteur
    - Voeg een nieuwe relatie toe via het register

    ---

    **Error:** `Contract file not found`

    **Oplossing:**
    - Controleer CONTRACTS_FOLDER in .env
    - Controleer of de folder bestaat en toegankelijk is
    - Controleer of de bestandsnamen exact matchen (hoofdlettergevoelig)
    - OneDrive sync moet compleet zijn

    ---

    **Error:** `Unsupported file type`

    **Oplossing:**
    - Alleen .docx en .xlsx worden ondersteund
    - Converteer .doc naar .docx
    - PDF's worden niet ondersteund
    """)

    st.divider()

    st.subheader("Classification Errors")
    st.markdown("""
    **Error:** `API key missing`

    **Oplossing:**
    - Set ANTHROPIC_API_KEY in .env
    - Vraag een API key aan op https://console.anthropic.com
    - Herstart de app na .env aanpassing

    ---

    **Error:** `Rate limit exceeded`

    **Oplossing:**
    - Verlaag aantal werkbonnen (max resultaten filter)
    - Wacht even voor je verder gaat
    - Upgrade je Anthropic plan voor hogere limits

    ---

    **Probleem:** Classificatie is ONZEKER voor te veel werkbonnen

    **Oplossing:**
    - Verbeter de classificatie opdracht en bedrijfscontext in de Configuratie pagina's
    - Voeg specifieke interpretatie regels toe
    - Verrijk contract met duidelijkere artikelen
    - Check of het juiste contract gebruikt wordt (preview in Beoordeling)

    ---

    **Probleem:** Hit rate is te laag (validatie modus)

    **Oplossing:**
    - Analyseer false positives/negatives in Results tab
    - Verbeter WVC werkwijze met geleerde lessen
    - Check of contracten up-to-date zijn
    - Verlaag confidence threshold (risico: meer fouten)
    """)

    st.divider()

    st.subheader("Performance Tips")
    st.markdown("""
    **Database queries zijn traag:**
    - Werkbon queries zijn gecached (5 minuten)
    - Gebruik filters om aantal werkbonnen te beperken
    - Analyse tab op Home is gecached

    **Classificatie duurt lang:**
    - Elke werkbon = 1 API call naar Claude
    - 10 werkbonnen ≈ 30-60 seconden
    - Batch grote aantallen in kleinere sets
    - Gebruik "Verberg al beoordeelde" filter

    **Contracten laden traag:**
    - LLM-ready contracten worden gecached in database
    - Eerste keer inladen duurt langer (verrijking)
    - Daarna direct uit database
    """)

    st.divider()

    st.subheader("Contact & Support")
    st.markdown("""
    **Notifica**: Technische implementatie, data pipeline, AI integratie
    - mark@notifica.nl
    - dolf@notifica.nl

    **WVC**: Contracten, domeinkennis, validatie
    """)

    st.divider()

    st.subheader("Versie Info")
    st.markdown("""
    **App versie**: 2.0
    **AI model**: Claude Sonnet 4.5 (claude-sonnet-4-20250514)
    **Database schema**: contract_checker
    **Laatste update**: Januari 2026
    """)
