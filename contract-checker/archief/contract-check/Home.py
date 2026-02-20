#!/usr/bin/env python3
"""
Notifica Contract Check - Home
Welkom pagina met workflow uitleg en werkbon data analyse.
"""
import pandas as pd
import streamlit as st
from sqlalchemy import text

from src.models.database import SessionLocal

# Configure page to use full width
st.set_page_config(layout="wide", page_title="Contract Check")

st.title("Notifica Contract Check")
st.caption("AI-gedreven classificatie van werkbonnen voor contract analyse")

# Quick action for daily users
col_btn, col_space = st.columns([1, 3])
with col_btn:
    if st.button("▶ Start Classificatie", type="primary"):
        st.switch_page("pages/20_Quick_Classificatie.py")

st.divider()

# === WORKFLOW UITLEG ===
st.markdown("## Hoe werkt het systeem?")

st.markdown("""
Dit systeem helpt om automatisch te bepalen of werkbonkosten binnen of buiten een servicecontract vallen.
""")

# Workflow diagram met stappen
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("""
    <div style="padding: 1.5rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 0.5rem; color: white; height: 200px;">
        <div style="font-size: 2rem; margin-bottom: 0.5rem;">1</div>
        <div style="font-weight: bold; font-size: 1.1rem; margin-bottom: 0.5rem;">Classificatie Opdracht</div>
        <div style="font-size: 0.85rem; opacity: 0.9;">
            Definieer de taak: wat moet de AI beoordelen? Bedrijfscontext toevoegen.
        </div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div style="padding: 1.5rem; background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); border-radius: 0.5rem; color: white; height: 200px;">
        <div style="font-size: 2rem; margin-bottom: 0.5rem;">2</div>
        <div style="font-weight: bold; font-size: 1.1rem; margin-bottom: 0.5rem;">Contract Register</div>
        <div style="font-size: 0.85rem; opacity: 0.9;">
            Beheer contracten per debiteur. Contracten worden gekoppeld aan debiteuren via het register.
        </div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div style="padding: 1.5rem; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); border-radius: 0.5rem; color: white; height: 200px;">
        <div style="font-size: 2rem; margin-bottom: 0.5rem;">3</div>
        <div style="font-weight: bold; font-size: 1.1rem; margin-bottom: 0.5rem;">Werkbon Selectie</div>
        <div style="font-size: 0.85rem; opacity: 0.9;">
            Selecteer werkbonnen uit Syntess. Zie direct welk contract bij elke werkbon hoort.
        </div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown("""
    <div style="padding: 1.5rem; background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); border-radius: 0.5rem; color: white; height: 200px;">
        <div style="font-size: 2rem; margin-bottom: 0.5rem;">4</div>
        <div style="font-weight: bold; font-size: 1.1rem; margin-bottom: 0.5rem;">Beoordeling</div>
        <div style="font-size: 0.85rem; opacity: 0.9;">
            Claude AI classificeert elke werkbon: binnen contract (JA), buiten contract (NEE), of ONZEKER.
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("")

col5, col6 = st.columns([1, 1])

with col5:
    st.markdown("""
    <div style="padding: 1.5rem; background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); border-radius: 0.5rem; color: white; height: 200px;">
        <div style="font-size: 2rem; margin-bottom: 0.5rem;">5</div>
        <div style="font-weight: bold; font-size: 1.1rem; margin-bottom: 0.5rem;">Resultaten</div>
        <div style="font-size: 0.85rem; opacity: 0.9;">
            Bekijk classificatie resultaten, validatie metrics (hit rate), en exporteer naar Excel.
        </div>
    </div>
    """, unsafe_allow_html=True)

with col6:
    st.markdown("""
    <div style="padding: 1.5rem; background: linear-gradient(135deg, #30cfd0 0%, #330867 100%); border-radius: 0.5rem; color: white; height: 200px;">
        <div style="font-size: 2rem; margin-bottom: 0.5rem;">+</div>
        <div style="font-weight: bold; font-size: 1.1rem; margin-bottom: 0.5rem;">Data Analyse</div>
        <div style="font-size: 0.85rem; opacity: 0.9;">
            Analyseer werkbonnen in Syntess: veldgebruik, fases, leeftijd. Zie hieronder.
        </div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# Key features
st.markdown("### Belangrijkste kenmerken")

col_a, col_b, col_c = st.columns(3)

with col_a:
    st.markdown("""
    **Per debiteur contract matching**
    - Elk werkbon wordt automatisch gekoppeld aan het juiste contract via debiteur code
    - Geen handmatige selectie meer nodig
    """)

with col_b:
    st.markdown("""
    **Validatie mode**
    - Test AI performance op historische data
    - Meet hit rate: hoe vaak klopt de AI?
    - Vergelijk AI vs werkelijke facturatie
    """)

with col_c:
    st.markdown("""
    **Classificatie mode**
    - Dagelijkse beoordeling van openstaande werkbonnen
    - Directe feedback: JA/NEE/ONZEKER
    - Opslaan in database voor rapportage
    """)

st.divider()

# === PORTAAL KEUZE ===
st.markdown("## Welk portaal gebruik je?")

col_config, col_user = st.columns(2)

with col_config:
    st.markdown("""
    <div style="padding: 2rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 1rem; color: white; height: 340px;">
        <div style="font-weight: bold; font-size: 1.5rem; margin-bottom: 1rem;">CONFIGURATIE</div>
        <div style="font-size: 0.95rem; line-height: 1.6; margin-bottom: 1.5rem;">
            Configureren en testen:<br><br>
            • Classificatie opdracht instellen<br>
            • Bedrijfscontext beheren<br>
            • Contracten uploaden<br>
            • Validatie uitvoeren<br>
            • Resultaten exporteren
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_user:
    st.markdown("""
    <div style="padding: 2rem; background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); border-radius: 1rem; color: white; height: 340px;">
        <div style="font-weight: bold; font-size: 1.5rem; margin-bottom: 1rem;">CLASSIFICEREN</div>
        <div style="font-size: 0.95rem; line-height: 1.6; margin-bottom: 1.5rem;">
            Voor dagelijks werk door backoffice:<br><br>
            • Start classificatie (1 knop!)<br>
            • Bekijk recente resultaten<br>
            • Grote duidelijke overzichten<br>
            • Geen filters of settings<br>
            • Snel snel snel!
        </div>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# === DATA ANALYSE (INKLAPBAAR) ===
with st.expander("Werkbon Data Analyse (klik om te openen)", expanded=False):
    st.caption("Live inzicht in werkbonnen uit het Syntess datawarehouse")

    with st.expander("ℹ️ Over deze analyse"):
        st.markdown("""
        **Doel:** Inzicht krijgen in de werkbonnen die klaar zijn voor classificatie.

        We analyseren werkbonnen met status **Uitgevoerd + Openstaand**. Dit zijn bonnen waar:
        - Het werk is afgerond (Uitgevoerd)
        - De administratieve afhandeling nog moet gebeuren (Openstaand)

        **Hoofdwerkbon vs werkbon:** Een hoofdwerkbon kan vervolgbonnen hebben (bijv. voor extra werk of materiaal).
        Bij classificatie is de hoofdwerkbon leidend, maar alle informatie van vervolgbonnen wordt meegenomen
        (kosten, omschrijvingen, paragrafen, etc.).

        **Veldgebruik:** Laat zien welke velden WVC actief invult. Dit helpt bij het inschatten van datakwaliteit
        en welke informatie beschikbaar is voor classificatie.
        """)

    @st.cache_data(ttl=300)  # Cache 5 minuten
    def get_werkbon_analyse():
        """Haal werkbon analyse data op (gecached)."""
        db = SessionLocal()
    
        # 1. Status + Documentstatus overzicht (alle werkbonnen + hoofdwerkbonnen)
        query_status = text("""
            SELECT
                TRIM("Status") as status,
                TRIM("Documentstatus") as documentstatus,
                COUNT(*) as aantal_werkbonnen,
                SUM(CASE WHEN "HoofdwerkbonDocumentKey" = "WerkbonDocumentKey" THEN 1 ELSE 0 END) as aantal_hoofdwerkbonnen
            FROM werkbonnen."Werkbonnen"
            GROUP BY TRIM("Status"), TRIM("Documentstatus")
            ORDER BY
                CASE TRIM("Documentstatus")
                    WHEN 'Openstaand' THEN 1
                    WHEN 'Gereed' THEN 2
                    WHEN 'Historisch' THEN 3
                END,
                CASE TRIM("Status")
                    WHEN 'Aanmaak' THEN 1
                    WHEN 'In uitvoering' THEN 2
                    WHEN 'Uitgevoerd' THEN 3
                    WHEN 'Vervallen' THEN 4
                END
        """)
        result_status = db.execute(query_status)
        status_data = [{
            "Status": r[0],
            "Documentstatus": r[1],
            "Werkbonnen": r[2],
            "Hoofdwerkbonnen": r[3]
        } for r in result_status]
    
        # 2. Administratieve fase (alleen Uitgevoerd + Openstaand) met hoofdwerkbonnen
        query_fase = text("""
            SELECT
                COALESCE(TRIM("Administratieve fase"), '(leeg)') as admin_fase,
                COUNT(*) as werkbonnen,
                SUM(CASE WHEN "HoofdwerkbonDocumentKey" = "WerkbonDocumentKey" THEN 1 ELSE 0 END) as hoofdwerkbonnen
            FROM werkbonnen."Werkbonnen"
            WHERE TRIM("Status") = 'Uitgevoerd'
              AND TRIM("Documentstatus") = 'Openstaand'
            GROUP BY COALESCE(TRIM("Administratieve fase"), '(leeg)')
            ORDER BY werkbonnen DESC
        """)
        result_fase = db.execute(query_fase)
        fase_data = [{
            "Administratieve fase": r[0],
            "Werkbonnen": r[1],
            "Hoofdwerkbonnen": r[2]
        } for r in result_fase]
    
        # 3. Paragraaf type (alleen Uitgevoerd + Openstaand)
        query_type = text("""
            SELECT
                COALESCE(TRIM(p."Type"), '(leeg)') as paragraaf_type,
                COUNT(DISTINCT w."WerkbonDocumentKey") as werkbonnen,
                COUNT(*) as paragrafen
            FROM werkbonnen."Werkbonnen" w
            JOIN werkbonnen."Werkbonparagrafen" p ON p."WerkbonDocumentKey" = w."WerkbonDocumentKey"
            WHERE TRIM(w."Status") = 'Uitgevoerd'
              AND TRIM(w."Documentstatus") = 'Openstaand'
            GROUP BY COALESCE(TRIM(p."Type"), '(leeg)')
            ORDER BY werkbonnen DESC
        """)
        result_type = db.execute(query_type)
        type_data = [{"Paragraaf type": r[0], "Werkbonnen": r[1], "Paragrafen": r[2]} for r in result_type]
    
        # 4. Soort (Periodiek/Eenmalig) voor Uitgevoerd + Openstaand
        query_soort = text("""
            SELECT
                COALESCE(TRIM("Soort"), '(leeg)') as soort,
                COUNT(*) as aantal
            FROM werkbonnen."Werkbonnen"
            WHERE TRIM("Status") = 'Uitgevoerd'
              AND TRIM("Documentstatus") = 'Openstaand'
            GROUP BY COALESCE(TRIM("Soort"), '(leeg)')
            ORDER BY aantal DESC
        """)
        result_soort = db.execute(query_soort)
        soort_data = [{"Soort": r[0], "Aantal": r[1]} for r in result_soort]
    
        # 5. Leeftijd analyse (Uitgevoerd + Openstaand) - gebaseerd op Aanmaakdatum uit stam.Documenten
        query_leeftijd = text("""
            SELECT leeftijd, werkbonnen, hoofdwerkbonnen
            FROM (
                SELECT
                    CASE
                        WHEN d."Aanmaakdatum" >= CURRENT_DATE - INTERVAL '1 month' THEN '< 1 maand'
                        WHEN d."Aanmaakdatum" >= CURRENT_DATE - INTERVAL '3 months' THEN '1-3 maanden'
                        WHEN d."Aanmaakdatum" >= CURRENT_DATE - INTERVAL '6 months' THEN '3-6 maanden'
                        WHEN d."Aanmaakdatum" >= CURRENT_DATE - INTERVAL '12 months' THEN '6-12 maanden'
                        ELSE '> 12 maanden'
                    END as leeftijd,
                    CASE
                        WHEN d."Aanmaakdatum" >= CURRENT_DATE - INTERVAL '1 month' THEN 1
                        WHEN d."Aanmaakdatum" >= CURRENT_DATE - INTERVAL '3 months' THEN 2
                        WHEN d."Aanmaakdatum" >= CURRENT_DATE - INTERVAL '6 months' THEN 3
                        WHEN d."Aanmaakdatum" >= CURRENT_DATE - INTERVAL '12 months' THEN 4
                        ELSE 5
                    END as sort_order,
                    COUNT(*) as werkbonnen,
                    SUM(CASE WHEN w."HoofdwerkbonDocumentKey" = w."WerkbonDocumentKey" THEN 1 ELSE 0 END) as hoofdwerkbonnen
                FROM werkbonnen."Werkbonnen" w
                JOIN stam."Documenten" d ON d."DocumentKey" = w."WerkbonDocumentKey"
                WHERE TRIM(w."Status") = 'Uitgevoerd'
                  AND TRIM(w."Documentstatus") = 'Openstaand'
                GROUP BY 1, 2
            ) sub
            ORDER BY sort_order
        """)
        result_leeftijd = db.execute(query_leeftijd)
        leeftijd_data = [{
            "Leeftijd": r[0],
            "Werkbonnen": r[1],
            "Hoofdwerkbonnen": r[2]
        } for r in result_leeftijd]
    
        # 6. Veldgebruik analyse (alleen hoofdwerkbonnen Uitgevoerd + Openstaand)
        query_veldgebruik = text("""
            WITH hoofdwerkbonnen AS (
                SELECT w."WerkbonDocumentKey", w."Administratieve fase"
                FROM werkbonnen."Werkbonnen" w
                WHERE TRIM(w."Status") = 'Uitgevoerd'
                  AND TRIM(w."Documentstatus") = 'Openstaand'
                  AND w."HoofdwerkbonDocumentKey" = w."WerkbonDocumentKey"
            ),
            paragraaf_info AS (
                SELECT
                    p."WerkbonDocumentKey",
                    MAX(CASE WHEN TRIM(COALESCE(p."Storing", '')) != '' THEN 1 ELSE 0 END) as heeft_storingscode,
                    MAX(CASE WHEN TRIM(COALESCE(p."Oorzaak", '')) != '' THEN 1 ELSE 0 END) as heeft_oorzaakcode
                FROM werkbonnen."Werkbonparagrafen" p
                WHERE p."WerkbonDocumentKey" IN (SELECT "WerkbonDocumentKey" FROM hoofdwerkbonnen)
                GROUP BY p."WerkbonDocumentKey"
            ),
            oplossing_info AS (
                SELECT
                    p."WerkbonDocumentKey",
                    1 as heeft_oplossing
                FROM werkbonnen."Werkbonparagrafen" p
                JOIN werkbonnen."Werkbon oplossingen" o ON o."WerkbonparagaafKey" = p."WerkbonparagraafKey"
                WHERE p."WerkbonDocumentKey" IN (SELECT "WerkbonDocumentKey" FROM hoofdwerkbonnen)
                GROUP BY p."WerkbonDocumentKey"
            ),
            opvolging_info AS (
                SELECT
                    p."WerkbonDocumentKey",
                    1 as heeft_opvolging
                FROM werkbonnen."Werkbonparagrafen" p
                JOIN werkbonnen."Werkbon opvolgingen" op ON op."WerkbonparagraafKey" = p."WerkbonparagraafKey"
                WHERE p."WerkbonDocumentKey" IN (SELECT "WerkbonDocumentKey" FROM hoofdwerkbonnen)
                GROUP BY p."WerkbonDocumentKey"
            )
            SELECT
                (SELECT COUNT(*) FROM hoofdwerkbonnen) as totaal,
                (SELECT COUNT(*) FROM hoofdwerkbonnen WHERE TRIM(COALESCE("Administratieve fase", '')) != '') as met_admin_fase,
                COALESCE(SUM(pi.heeft_storingscode), 0) as met_storingscode,
                COALESCE(SUM(pi.heeft_oorzaakcode), 0) as met_oorzaakcode,
                (SELECT COUNT(*) FROM oplossing_info) as met_oplossing,
                (SELECT COUNT(*) FROM opvolging_info) as met_opvolging
            FROM hoofdwerkbonnen h
            LEFT JOIN paragraaf_info pi ON pi."WerkbonDocumentKey" = h."WerkbonDocumentKey"
        """)
        result_veldgebruik = db.execute(query_veldgebruik)
        row = result_veldgebruik.fetchone()
        veldgebruik_data = {
            "totaal": row[0] or 0,
            "admin_fase": row[1] or 0,
            "storingscode": row[2] or 0,
            "oorzaakcode": row[3] or 0,
            "oplossing": row[4] or 0,
            "opvolging": row[5] or 0,
        }
    
        # Detail queries voor alle velden (alleen als ze gebruikt worden)
    
        # Administratieve fase detail - inclusief mix analyse
        if veldgebruik_data["admin_fase"] > 0:
            query_fase_detail = text("""
                SELECT
                    COALESCE(TRIM("Administratieve fase"), '(leeg)') as fase,
                    COUNT(*) as hoofdwerkbonnen
                FROM werkbonnen."Werkbonnen"
                WHERE TRIM("Status") = 'Uitgevoerd'
                  AND TRIM("Documentstatus") = 'Openstaand'
                  AND "HoofdwerkbonDocumentKey" = "WerkbonDocumentKey"
                GROUP BY COALESCE(TRIM("Administratieve fase"), '(leeg)')
                ORDER BY hoofdwerkbonnen DESC
            """)
            result_fase = db.execute(query_fase_detail)
            veldgebruik_data["admin_fase_detail"] = [
                {"Administratieve fase": r[0], "Hoofdwerkbonnen": r[1]} for r in result_fase
            ]
    
            # Mix analyse
            query_fase_mix = text("""
                WITH trajecten AS (
                    SELECT
                        h."WerkbonDocumentKey" as hoofdwerkbon_key,
                        COUNT(DISTINCT TRIM(COALESCE(w."Administratieve fase", ''))) as distinct_fases,
                        COUNT(*) as werkbonnen_in_traject
                    FROM werkbonnen."Werkbonnen" h
                    JOIN werkbonnen."Werkbonnen" w ON w."HoofdwerkbonDocumentKey" = h."WerkbonDocumentKey"
                    WHERE TRIM(h."Status") = 'Uitgevoerd'
                      AND TRIM(h."Documentstatus") = 'Openstaand'
                      AND h."HoofdwerkbonDocumentKey" = h."WerkbonDocumentKey"
                    GROUP BY h."WerkbonDocumentKey"
                )
                SELECT
                    CASE
                        WHEN werkbonnen_in_traject = 1 THEN 'Alleen hoofdwerkbon'
                        WHEN distinct_fases = 1 THEN 'Uniform (hoofd + vervolg zelfde fase)'
                        ELSE 'Mix (verschillende fases)'
                    END as type,
                    COUNT(*) as hoofdwerkbonnen
                FROM trajecten
                GROUP BY 1
                ORDER BY hoofdwerkbonnen DESC
            """)
            result_mix = db.execute(query_fase_mix)
            veldgebruik_data["admin_fase_mix"] = [
                {"Type": r[0], "Hoofdwerkbonnen": r[1]} for r in result_mix
            ]
    
        # Storingscode detail (top 15)
        if veldgebruik_data["storingscode"] > 0:
            query_storing_detail = text("""
                SELECT
                    COALESCE(TRIM(p."Storing"), '(leeg)') as storingscode,
                    COUNT(DISTINCT p."WerkbonDocumentKey") as werkbonnen
                FROM werkbonnen."Werkbonparagrafen" p
                JOIN werkbonnen."Werkbonnen" w ON p."WerkbonDocumentKey" = w."WerkbonDocumentKey"
                WHERE TRIM(w."Status") = 'Uitgevoerd'
                  AND TRIM(w."Documentstatus") = 'Openstaand'
                  AND w."HoofdwerkbonDocumentKey" = w."WerkbonDocumentKey"
                  AND TRIM(COALESCE(p."Storing", '')) != ''
                GROUP BY COALESCE(TRIM(p."Storing"), '(leeg)')
                ORDER BY werkbonnen DESC
                LIMIT 15
            """)
            result_storing = db.execute(query_storing_detail)
            veldgebruik_data["storingscode_detail"] = [
                {"Storingscode": r[0], "Werkbonnen": r[1]} for r in result_storing
            ]
    
        # Oorzaakcode detail (top 15)
        if veldgebruik_data["oorzaakcode"] > 0:
            query_oorzaak_detail = text("""
                SELECT
                    COALESCE(TRIM(p."Oorzaak"), '(leeg)') as oorzaakcode,
                    COUNT(DISTINCT p."WerkbonDocumentKey") as werkbonnen
                FROM werkbonnen."Werkbonparagrafen" p
                JOIN werkbonnen."Werkbonnen" w ON p."WerkbonDocumentKey" = w."WerkbonDocumentKey"
                WHERE TRIM(w."Status") = 'Uitgevoerd'
                  AND TRIM(w."Documentstatus") = 'Openstaand'
                  AND w."HoofdwerkbonDocumentKey" = w."WerkbonDocumentKey"
                  AND TRIM(COALESCE(p."Oorzaak", '')) != ''
                GROUP BY COALESCE(TRIM(p."Oorzaak"), '(leeg)')
                ORDER BY werkbonnen DESC
                LIMIT 15
            """)
            result_oorzaak = db.execute(query_oorzaak_detail)
            veldgebruik_data["oorzaakcode_detail"] = [
                {"Oorzaakcode": r[0], "Werkbonnen": r[1]} for r in result_oorzaak
            ]
    
        # Oplossingen detail (top soorten)
        if veldgebruik_data["oplossing"] > 0:
            query_oplossing_detail = text("""
                SELECT
                    COALESCE(TRIM(o."Oplossing"), '(leeg)') as oplossing,
                    COUNT(DISTINCT w."WerkbonDocumentKey") as werkbonnen
                FROM werkbonnen."Werkbon oplossingen" o
                JOIN werkbonnen."Werkbonparagrafen" p ON o."WerkbonparagaafKey" = p."WerkbonparagraafKey"
                JOIN werkbonnen."Werkbonnen" w ON p."WerkbonDocumentKey" = w."WerkbonDocumentKey"
                WHERE TRIM(w."Status") = 'Uitgevoerd'
                  AND TRIM(w."Documentstatus") = 'Openstaand'
                  AND w."HoofdwerkbonDocumentKey" = w."WerkbonDocumentKey"
                GROUP BY COALESCE(TRIM(o."Oplossing"), '(leeg)')
                ORDER BY werkbonnen DESC
                LIMIT 15
            """)
            result_oplossing = db.execute(query_oplossing_detail)
            veldgebruik_data["oplossing_detail"] = [
                {"Oplossing": r[0], "Werkbonnen": r[1]} for r in result_oplossing
            ]
    
        # Opvolgingen detail (per status)
        if veldgebruik_data["opvolging"] > 0:
            query_opvolging_detail = text("""
                SELECT
                    COALESCE(TRIM(op."Status"), '(leeg)') as status,
                    COUNT(DISTINCT w."WerkbonDocumentKey") as werkbonnen,
                    COUNT(*) as opvolgingen
                FROM werkbonnen."Werkbon opvolgingen" op
                JOIN werkbonnen."Werkbonparagrafen" p ON op."WerkbonparagraafKey" = p."WerkbonparagraafKey"
                JOIN werkbonnen."Werkbonnen" w ON p."WerkbonDocumentKey" = w."WerkbonDocumentKey"
                WHERE TRIM(w."Status") = 'Uitgevoerd'
                  AND TRIM(w."Documentstatus") = 'Openstaand'
                  AND w."HoofdwerkbonDocumentKey" = w."WerkbonDocumentKey"
                GROUP BY COALESCE(TRIM(op."Status"), '(leeg)')
                ORDER BY werkbonnen DESC
            """)
            result_opvolging = db.execute(query_opvolging_detail)
            veldgebruik_data["opvolging_detail"] = [
                {"Status": r[0], "Werkbonnen": r[1], "Opvolgingen": r[2]} for r in result_opvolging
            ]
    
        db.close()
        return {
            "status": status_data,
            "fase": fase_data,
            "type": type_data,
            "soort": soort_data,
            "leeftijd": leeftijd_data,
            "veldgebruik": veldgebruik_data,
        }
    
    # Laad data
    if st.button("🔄 Analyse laden", key="load_analyse"):
        st.cache_data.clear()
    
    with st.spinner("Analyse laden..."):
        analyse = get_werkbon_analyse()
    
    # KPIs bovenaan
    df_status = pd.DataFrame(analyse["status"])
    
    # Bereken totalen
    uitgevoerd_openstaand = df_status[
        (df_status["Status"] == "Uitgevoerd") &
        (df_status["Documentstatus"] == "Openstaand")
    ]["Werkbonnen"].sum()
    
    uitgevoerd_historisch = df_status[
        (df_status["Status"] == "Uitgevoerd") &
        (df_status["Documentstatus"] == "Historisch")
    ]["Werkbonnen"].sum()
    
    totaal_openstaand = df_status[df_status["Documentstatus"] == "Openstaand"]["Werkbonnen"].sum()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📂 Te classificeren", f"{uitgevoerd_openstaand:,}",
                  help="Uitgevoerd + Openstaand")
    with col2:
        st.metric("📁 Historisch", f"{uitgevoerd_historisch:,}",
                  help="Uitgevoerd + Historisch (voor validatie)")
    with col3:
        st.metric("📋 Totaal openstaand", f"{totaal_openstaand:,}",
                  help="Alle werkbonnen met Documentstatus=Openstaand")
    with col4:
        st.metric("📊 Totaal", f"{df_status['Werkbonnen'].sum():,}")
    
    st.divider()
    
    # === OVERZICHT: Status + Documentstatus ===
    st.markdown("#### Overzicht: Alle werkbonnen")
    
    # Legenda met kleuren
    st.markdown("""
    <div style="display: flex; gap: 1rem; margin-bottom: 0.5rem; font-size: 0.85rem;">
        <span style="background: #dcfce7; padding: 2px 8px; border-radius: 4px;">🟢 Classificatie (Uitgevoerd+Openstaand)</span>
        <span style="background: #dbeafe; padding: 2px 8px; border-radius: 4px;">🔵 Validatie / Training data (Uitgevoerd+Historisch)</span>
    </div>
    """, unsafe_allow_html=True)
    
    # Voeg totaalrij en percentage toe
    df_status_display = pd.DataFrame(analyse["status"])
    df_status_display["% Hoofd"] = (
        df_status_display["Hoofdwerkbonnen"] / df_status_display["Werkbonnen"] * 100
    ).round(1).astype(str) + "%"
    # Totaalrij
    totaal_werkbonnen = df_status_display["Werkbonnen"].sum()
    totaal_hoofdwerkbonnen = df_status_display["Hoofdwerkbonnen"].sum()
    totaal_pct = round(totaal_hoofdwerkbonnen / totaal_werkbonnen * 100, 1) if totaal_werkbonnen > 0 else 0
    totaal_row = pd.DataFrame([{
        "Status": "TOTAAL",
        "Documentstatus": "",
        "Werkbonnen": totaal_werkbonnen,
        "Hoofdwerkbonnen": totaal_hoofdwerkbonnen,
        "% Hoofd": f"{totaal_pct}%"
    }])
    df_status_with_total = pd.concat([df_status_display, totaal_row], ignore_index=True)
    
    # Kleur functie voor rijen
    def highlight_rows(row):
        if row["Status"] == "Uitgevoerd" and row["Documentstatus"] == "Openstaand":
            return ["background-color: #dcfce7"] * len(row)  # Groen - classificatie
        elif row["Status"] == "Uitgevoerd" and row["Documentstatus"] == "Historisch":
            return ["background-color: #dbeafe"] * len(row)  # Blauw - validatie
        elif row["Status"] == "TOTAAL":
            return ["background-color: #f3f4f6; font-weight: bold"] * len(row)  # Grijs - totaal
        return [""] * len(row)
    
    styled_df = df_status_with_total.style.apply(highlight_rows, axis=1)
    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True
    )
    
    # === TRIAGE: Wat doen we met Uitgevoerd + Openstaand? ===
    st.divider()
    st.markdown("### 🟢 Uitgevoerd + Openstaand: Wat nu?")
    
    st.markdown("""
    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin: 1rem 0;">
        <div style="padding: 1rem; background: #f0fdf4; border-left: 4px solid #22c55e; border-radius: 0 0.5rem 0.5rem 0;">
            <div style="font-weight: bold; color: #166534; margin-bottom: 0.5rem;">✅ Klaar voor facturatie</div>
            <div style="font-size: 0.85rem; color: #374151;">
                Werkzaamheden afgerond, kosten definitief.<br>
                <em>→ Classificeren: binnen/buiten contract</em>
            </div>
        </div>
        <div style="padding: 1rem; background: #fefce8; border-left: 4px solid #eab308; border-radius: 0 0.5rem 0.5rem 0;">
            <div style="font-weight: bold; color: #854d0e; margin-bottom: 0.5rem;">⏳ Nog actie nodig</div>
            <div style="font-size: 0.85rem; color: #374151;">
                Bestelling staat nog open, of werk ingepland<br>
                (vervolgwerkbon, planregels in toekomst).<br>
                <em>→ Wachten tot acties afgerond</em>
            </div>
        </div>
        <div style="padding: 1rem; background: #fef2f2; border-left: 4px solid #ef4444; border-radius: 0 0.5rem 0.5rem 0;">
            <div style="font-weight: bold; color: #991b1b; margin-bottom: 0.5rem;">❓ Onduidelijk</div>
            <div style="font-size: 0.85rem; color: #374151;">
                Status onbekend, lange doorlooptijd.<br>
                <em>→ Beoordelen: wat moet ermee gebeuren?</em>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.caption("De onderstaande analyses helpen bij het identificeren van werkbonnen per categorie.")
    
    # === DETAIL: Uitgevoerd + Openstaand ===
    st.divider()
    st.markdown("#### Detail: Doorsnedes")
    st.caption(f"Inzicht in de {uitgevoerd_openstaand:,} werkbonnen (inclusief vervolgbonnen). Hoofdwerkbonnen worden apart getoond waar relevant.")
    
    # Eerste rij: Administratieve fase + Leeftijd
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Administratieve fase")
        st.caption("Waar staat de bon in het administratieve proces?")
        df_fase = pd.DataFrame(analyse["fase"])
        if not df_fase.empty:
            df_fase["% Hoofd"] = (
                df_fase["Hoofdwerkbonnen"] / df_fase["Werkbonnen"] * 100
            ).round(1).astype(str) + "%"
            totaal_wb = df_fase["Werkbonnen"].sum()
            totaal_hoofd = df_fase["Hoofdwerkbonnen"].sum()
            totaal_pct = round(totaal_hoofd / totaal_wb * 100, 1) if totaal_wb > 0 else 0
            totaal_fase = pd.DataFrame([{
                "Administratieve fase": "TOTAAL",
                "Werkbonnen": totaal_wb,
                "Hoofdwerkbonnen": totaal_hoofd,
                "% Hoofd": f"{totaal_pct}%"
            }])
            df_fase_with_total = pd.concat([df_fase, totaal_fase], ignore_index=True)
            st.dataframe(df_fase_with_total, use_container_width=True, hide_index=True)
        else:
            st.info("Geen data")
    
    with col2:
        st.markdown("#### Leeftijd (sinds aanmaak)")
        st.caption("Hoe lang staat de bon al open?")
        df_leeftijd = pd.DataFrame(analyse["leeftijd"])
        if not df_leeftijd.empty:
            # Grafiek met kleurverloop (groen = jong, rood = oud)
            import plotly.express as px
            df_chart = df_leeftijd.copy()
            colors = ["#22c55e", "#84cc16", "#eab308", "#f97316", "#ef4444"]
            fig = px.bar(
                df_chart,
                x="Leeftijd",
                y="Werkbonnen",
                color="Leeftijd",
                color_discrete_sequence=colors[:len(df_chart)],
            )
            fig.update_layout(
                showlegend=False,
                margin=dict(l=0, r=0, t=10, b=0),
                height=250,
                xaxis_title="",
                yaxis_title="",
            )
            st.plotly_chart(fig, use_container_width=True)
    
            # Tabel met totaal
            df_leeftijd["% Hoofd"] = (
                df_leeftijd["Hoofdwerkbonnen"] / df_leeftijd["Werkbonnen"] * 100
            ).round(1).astype(str) + "%"
            totaal_wb = df_leeftijd["Werkbonnen"].sum()
            totaal_hoofd = df_leeftijd["Hoofdwerkbonnen"].sum()
            totaal_pct = round(totaal_hoofd / totaal_wb * 100, 1) if totaal_wb > 0 else 0
            totaal_leeftijd = pd.DataFrame([{
                "Leeftijd": "TOTAAL",
                "Werkbonnen": totaal_wb,
                "Hoofdwerkbonnen": totaal_hoofd,
                "% Hoofd": f"{totaal_pct}%"
            }])
            df_leeftijd_with_total = pd.concat([df_leeftijd, totaal_leeftijd], ignore_index=True)
            with st.expander("📊 Tabel"):
                st.dataframe(df_leeftijd_with_total, use_container_width=True, hide_index=True)
        else:
            st.info("Geen data")
    
    # Tweede rij: Paragraaf type + Soort
    col3, col4 = st.columns(2)
    
    with col3:
        st.markdown("#### Paragraaf type")
        st.caption("Storing, Onderhoud, Onderhoud+Storing, etc.")
        df_type = pd.DataFrame(analyse["type"])
        if not df_type.empty:
            df_type["Par/WB"] = (
                df_type["Paragrafen"] / df_type["Werkbonnen"]
            ).round(2)
            totaal_wb = df_type["Werkbonnen"].sum()
            totaal_par = df_type["Paragrafen"].sum()
            totaal_ratio = round(totaal_par / totaal_wb, 2) if totaal_wb > 0 else 0
            totaal_type = pd.DataFrame([{
                "Paragraaf type": "TOTAAL",
                "Werkbonnen": totaal_wb,
                "Paragrafen": totaal_par,
                "Par/WB": totaal_ratio
            }])
            df_type_with_total = pd.concat([df_type, totaal_type], ignore_index=True)
            st.dataframe(df_type_with_total, use_container_width=True, hide_index=True)
        else:
            st.info("Geen data")
    
    with col4:
        st.markdown("#### Soort")
        st.caption("Periodiek vs Eenmalig")
        df_soort = pd.DataFrame(analyse["soort"])
        if not df_soort.empty:
            totaal_soort = pd.DataFrame([{
                "Soort": "TOTAAL",
                "Aantal": df_soort["Aantal"].sum()
            }])
            df_soort_with_total = pd.concat([df_soort, totaal_soort], ignore_index=True)
            st.dataframe(df_soort_with_total, use_container_width=True, hide_index=True)
        else:
            st.info("Geen data")
    
    # === VELDGEBRUIK: Datakwaliteit indicatoren ===
    st.divider()
    st.markdown("#### Veldgebruik (datakwaliteit)")
    st.caption("Per hoofdwerkbon: welke velden zijn ingevuld?")
    
    veldgebruik = analyse["veldgebruik"]
    totaal = veldgebruik["totaal"]
    
    if totaal > 0:
        # Bereken percentages
        def pct(val):
            return round(val / totaal * 100, 1) if totaal > 0 else 0
    
        # Overzichtstabel
        veldgebruik_rows = [
            {"Veld": "Administratieve fase", "Hoofdwerkbonnen": veldgebruik["admin_fase"], "Percentage": f"{pct(veldgebruik['admin_fase'])}%"},
            {"Veld": "Storingscode", "Hoofdwerkbonnen": veldgebruik["storingscode"], "Percentage": f"{pct(veldgebruik['storingscode'])}%"},
            {"Veld": "Oorzaakcode", "Hoofdwerkbonnen": veldgebruik["oorzaakcode"], "Percentage": f"{pct(veldgebruik['oorzaakcode'])}%"},
            {"Veld": "Oplossingen", "Hoofdwerkbonnen": veldgebruik["oplossing"], "Percentage": f"{pct(veldgebruik['oplossing'])}%"},
            {"Veld": "Opvolgingen", "Hoofdwerkbonnen": veldgebruik["opvolging"], "Percentage": f"{pct(veldgebruik['opvolging'])}%"},
        ]
        df_veldgebruik = pd.DataFrame(veldgebruik_rows)
        st.dataframe(df_veldgebruik, use_container_width=True, hide_index=True)
        st.caption(f"Totaal: {totaal:,} hoofdwerkbonnen met status Uitgevoerd + Openstaand")
    
        # Detail expanders
        st.markdown("##### Details per veld")
    
        # Administratieve fase
        if veldgebruik["admin_fase"] > 0:
            with st.expander(f"📋 Administratieve fase ({veldgebruik['admin_fase']:,} hoofdwerkbonnen)"):
                # Mix analyse met uitleg
                df_mix = pd.DataFrame(veldgebruik.get("admin_fase_mix", []))
                if not df_mix.empty:
                    st.markdown("**Mix analyse**: Is de fase uniform binnen hoofd + vervolgbonnen?")
                    st.dataframe(df_mix, use_container_width=True, hide_index=True)
                    st.divider()
    
                # Detail per fase
                df_fase = pd.DataFrame(veldgebruik.get("admin_fase_detail", []))
                if not df_fase.empty:
                    st.markdown("**Per fase** (alleen de hoofdwerkbon)")
                    st.dataframe(df_fase, use_container_width=True, hide_index=True)
    
        # Storingscode
        if veldgebruik["storingscode"] > 0:
            with st.expander(f"🔧 Storingscode ({veldgebruik['storingscode']:,} hoofdwerkbonnen)"):
                df_storing = pd.DataFrame(veldgebruik.get("storingscode_detail", []))
                if not df_storing.empty:
                    st.caption("Top 15 storingscodes")
                    st.dataframe(df_storing, use_container_width=True, hide_index=True)
    
        # Oorzaakcode
        if veldgebruik["oorzaakcode"] > 0:
            with st.expander(f"🎯 Oorzaakcode ({veldgebruik['oorzaakcode']:,} hoofdwerkbonnen)"):
                df_oorzaak = pd.DataFrame(veldgebruik.get("oorzaakcode_detail", []))
                if not df_oorzaak.empty:
                    st.caption("Top 15 oorzaakcodes")
                    st.dataframe(df_oorzaak, use_container_width=True, hide_index=True)
    
        # Oplossingen
        if veldgebruik["oplossing"] > 0:
            with st.expander(f"💡 Oplossingen ({veldgebruik['oplossing']:,} hoofdwerkbonnen)"):
                df_oplossing = pd.DataFrame(veldgebruik.get("oplossing_detail", []))
                if not df_oplossing.empty:
                    st.caption("Top 15 oplossingen")
                    st.dataframe(df_oplossing, use_container_width=True, hide_index=True)
    
        # Opvolgingen
        if veldgebruik["opvolging"] > 0:
            with st.expander(f"📌 Opvolgingen ({veldgebruik['opvolging']:,} hoofdwerkbonnen)"):
                df_opvolging = pd.DataFrame(veldgebruik.get("opvolging_detail", []))
                if not df_opvolging.empty:
                    st.caption("Opvolgingen per status")
                    st.dataframe(df_opvolging, use_container_width=True, hide_index=True)
    else:
        st.info("Geen data")
    
    st.divider()
