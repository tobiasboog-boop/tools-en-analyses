"""
Zenith Werkbon Rapportage
==========================
Complete versie met alle 37 kolommen en Excel export

Laatste update: 2026-02-19
"""
import streamlit as st
import pandas as pd
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import re
from io import BytesIO
import numpy as np

# Load environment
try:
    from dotenv import load_dotenv
    env_path = Path('.env')
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# SDK import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '_sdk'))
from notifica_sdk import NotificaClient

# Page config
st.set_page_config(
    page_title="Zenith Werkbon Rapportage",
    page_icon="📊",
    layout="wide"
)

KLANTNUMMER = 1229

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def strip_rtf(text):
    """Strip RTF formatting from BLOB text"""
    if not text or not isinstance(text, str):
        return ''
    # Remove RTF control words
    text = re.sub(r'\\[a-z]+[0-9]*\s?', ' ', text)
    text = re.sub(r'[{}]', '', text)
    text = re.sub(r'\\par', '\n', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def map_priority(prio_raw):
    """Map DWH priority to Excel format"""
    if pd.isna(prio_raw):
        return 'Medium'
    prio_str = str(prio_raw).upper()
    if '12UUR' in prio_str or '4UUR' in prio_str:
        return 'Urgent'
    elif 'LOW' in prio_str or 'NBD' in prio_str:
        return 'Low'
    else:
        return 'Medium'

def map_installatie_soort(inst_raw):
    """Map DWH installation type to Excel format"""
    if pd.isna(inst_raw):
        return ''
    if inst_raw == 'Camerasysteem':
        return 'Camera'
    elif inst_raw == 'Inbraaksysteem':
        return 'Inbraak'
    else:
        return inst_raw

def guess_location_type(location_name):
    """Heuristic to guess location type based on name"""
    if pd.isna(location_name):
        return ''
    name_lower = str(location_name).lower()
    if 'winkel' in name_lower or 'store' in name_lower:
        return 'Store'
    elif 'dc' in name_lower or 'distributie' in name_lower:
        return 'Warehouse'
    elif 'kantoor' in name_lower or 'office' in name_lower:
        return 'Office'
    else:
        return ''

def extract_storing_omschrijving(notitie_text):
    """Extract storing description from BLOB notitie (first sentence)"""
    if not notitie_text:
        return ''
    # Strip RTF first
    clean = strip_rtf(notitie_text)
    # Take first line or text before ':'
    if ':' in clean:
        return clean.split(':')[0].strip()
    else:
        # Take first 100 chars
        return clean[:100].strip()

def calculate_kpi_hours(prio):
    """Get KPI hours for priority"""
    if prio == 'Urgent':
        return {'response': 12, 'restore': 24}
    elif prio == 'Medium':
        return {'response': 24, 'restore': 48}
    elif prio == 'Low':
        return {'response': 48, 'restore': 72}
    else:
        return {'response': 24, 'restore': 48}

def categorize_response_time(hours):
    """Categorize response time into ranges"""
    if pd.isna(hours):
        return ''
    if hours <= 4:
        return '0-4u'
    elif hours <= 8:
        return '4-8u'
    elif hours <= 12:
        return '8-12u'
    elif hours <= 24:
        return '12-24u'
    else:
        return '>24u'

# ============================================================================
# STREAMLIT APP
# ============================================================================

st.title("📊 Zenith Werkbon Rapportage - Complete Export")
st.markdown("**Status:** Alle 37 kolommen - Data ophalen en exporteren naar Excel met kleurcodering")

# Filters
with st.sidebar:
    st.header("Filters")
    default_start = datetime.now() - timedelta(days=30)
    default_end = datetime.now()
    start_date = st.date_input("Van", default_start)
    end_date = st.date_input("Tot", default_end)

    # Haal klantlijst op voor filter (lightweight query)
    if st.button("🔄 Ververs klantlijst", help="Haal beschikbare klanten op voor deze periode"):
        with st.spinner("Klanten ophalen..."):
            try:
                client = NotificaClient()
                klanten_query = client.query(KLANTNUMMER, f'''
                    SELECT DISTINCT wb."Klant"
                    FROM werkbonnen."Werkbonnen" wb
                    WHERE wb."MeldDatum" >= '{start_date}'
                      AND wb."MeldDatum" <= '{end_date}'
                      AND wb."Klant" IS NOT NULL
                    ORDER BY wb."Klant"
                ''')
                st.session_state.klanten_lijst = klanten_query['Klant'].tolist()
                st.success(f"✓ {len(st.session_state.klanten_lijst)} klanten gevonden")
            except Exception as e:
                st.error(f"Fout bij ophalen klanten: {e}")

    # Toon klantfilter als lijst beschikbaar is
    klant_filter = None
    if 'klanten_lijst' in st.session_state and st.session_state.klanten_lijst:
        klant_filter = st.multiselect(
            "Filter op klant",
            options=st.session_state.klanten_lijst,
            default=st.session_state.get('selected_klanten', []),
            help="Type om te zoeken (bijv. 'coolblue' toont alle Coolblue locaties)"
        )
        if klant_filter:
            st.session_state.selected_klanten = klant_filter
    else:
        st.info("💡 Klik 'Ververs klantlijst' om te filteren op klant")

    st.markdown("---")
    st.markdown("**Kleurcodering in Excel:**")
    st.markdown("🔴 Rood = Niet in database (handmatig invullen)")
    st.markdown("🟡 Geel = Automatisch afgeleid (controleren)")

# Main button
if st.button("📥 Data Ophalen & Exporteren", type="primary"):
    client = NotificaClient()

    with st.spinner("Data ophalen uit DWH..."):

        # ====================================================================
        # STAP 1: BASIS WERKBONNEN OPHALEN
        # ====================================================================
        st.info("Stap 1/6: Basis werkbonnen ophalen...")

        werkbonnen_basis = client.query(KLANTNUMMER, f'''
            SELECT
                wb."WerkbonDocumentKey",
                wb."Werkbon",
                wb."Klant",
                wb."MeldDatum",
                wb."MeldTijd",
                wb."Prioriteit",
                wb."Betreft onderaannemer",
                wb."Onderaannemer",
                wb."ParentWerkbonDocumentKey",
                wb."Status",
                ssm."Werkboncode",
                ssm."Werkbon titel"
            FROM werkbonnen."Werkbonnen" wb
            JOIN notifica."SSM Werkbonnen" ssm
              ON wb."WerkbonDocumentKey" = ssm."WerkbonDocumentKey"
            WHERE wb."MeldDatum" >= '{start_date}'
              AND wb."MeldDatum" <= '{end_date}'
            ORDER BY wb."MeldDatum" DESC
        ''')

        if werkbonnen_basis.empty:
            st.warning("Geen werkbonnen gevonden in deze periode.")
            st.stop()

        st.success(f"✓ {len(werkbonnen_basis)} werkbonnen gevonden")

        # Sla unieke klanten op voor filter
        unique_klanten = sorted(werkbonnen_basis['Klant'].dropna().unique().tolist())
        st.session_state.klanten_lijst = unique_klanten

        # Pas klantfilter toe indien ingesteld
        if klant_filter:
            werkbonnen_basis = werkbonnen_basis[werkbonnen_basis['Klant'].isin(klant_filter)]
            st.info(f"📌 Gefilterd op {len(klant_filter)} klant(en) - {len(werkbonnen_basis)} werkbonnen")

        if werkbonnen_basis.empty:
            st.warning("Geen werkbonnen gevonden na filtering.")
            st.stop()

        # ====================================================================
        # STAP 2: PARAGRAFEN & INSTALLATIES
        # ====================================================================
        st.info("Stap 2/6: Paragrafen en installaties ophalen...")

        wb_keys = werkbonnen_basis['WerkbonDocumentKey'].tolist()
        wb_keys_str = ','.join(str(k) for k in wb_keys)

        paragrafen = client.query(KLANTNUMMER, f'''
            SELECT
                para."WerkbonDocumentKey",
                para."Uitgevoerd op" AS datum_oplossing,
                para."TijdstipUitgevoerd" AS tijd_oplossing,
                para."InstallatieKey",
                inst."Installatiesoort"
            FROM werkbonnen."Werkbonparagrafen" para
            LEFT JOIN notifica."SSM Installaties" inst
              ON para."InstallatieKey" = inst."InstallatieKey"
            WHERE para."WerkbonDocumentKey" IN ({wb_keys_str})
        ''')

        st.success(f"✓ {len(paragrafen)} paragrafen gevonden")

        # ====================================================================
        # STAP 3: REACTIE TIJDEN (LOGBOEK)
        # ====================================================================
        st.info("Stap 3/6: Reactie tijden ophalen...")

        logboek = client.query(KLANTNUMMER, f'''
            SELECT
                log."WerkbonDocumentKey",
                MIN(log."Datum en tijd") AS reactie_datetime
            FROM notifica."SSM Logboek werkbonfases" log
            WHERE log."WerkbonDocumentKey" IN ({wb_keys_str})
              AND log."Waarde" LIKE '%In uitvoering%'
            GROUP BY log."WerkbonDocumentKey"
        ''')

        st.success(f"✓ {len(logboek)} reactie tijden gevonden")

        # ====================================================================
        # STAP 4: BLOB NOTITIES
        # ====================================================================
        st.info("Stap 4/6: BLOB monteur notities ophalen...")

        # Eerst sessies ophalen
        sessies = client.query(KLANTNUMMER, f'''
            SELECT
                s."DocumentKey" AS "WerkbonDocumentKey",
                s."MobieleuitvoersessieRegelKey"
            FROM werkbonnen."Mobiele uitvoersessies" s
            WHERE s."DocumentKey" IN ({wb_keys_str})
        ''')

        blob_notities = pd.DataFrame()
        if not sessies.empty:
            sessie_keys = sessies['MobieleuitvoersessieRegelKey'].tolist()
            sessie_keys_str = ','.join(str(k) for k in sessie_keys)

            blob_raw = client.query(KLANTNUMMER, f'''
                SELECT
                    m.gc_id AS "MobieleuitvoersessieRegelKey",
                    m.notitie
                FROM maatwerk.stg_at_mwbsess_clobs m
                WHERE m.gc_id IN ({sessie_keys_str})
                  AND m.notitie IS NOT NULL
            ''')

            # Merge met sessies om WerkbonDocumentKey te krijgen
            if not blob_raw.empty:
                blob_notities = sessies.merge(
                    blob_raw,
                    on='MobieleuitvoersessieRegelKey',
                    how='inner'
                )

        st.success(f"✓ {len(blob_notities)} BLOB notities gevonden")

        # ====================================================================
        # STAP 5: DATA COMBINEREN
        # ====================================================================
        st.info("Stap 5/6: Data samenvoegen en transformeren...")

        # Merge alles
        df = werkbonnen_basis.copy()
        df = df.merge(paragrafen, on='WerkbonDocumentKey', how='left')
        df = df.merge(logboek, on='WerkbonDocumentKey', how='left')
        df = df.merge(
            blob_notities[['WerkbonDocumentKey', 'notitie']].drop_duplicates(subset=['WerkbonDocumentKey']),
            on='WerkbonDocumentKey',
            how='left'
        )

        # ====================================================================
        # STAP 6: KOLOMMEN TRANSFORMEREN (1-21)
        # ====================================================================

        result_df = pd.DataFrame()

        # 1. Werkbon nummer
        result_df['Werkbon nummer'] = df['Werkboncode']

        # 2. Gerelateerde werkbon
        result_df['Gerelateerde werkbon'] = df['ParentWerkbonDocumentKey']

        # 3. Datum aanmaak
        result_df['Datum aanmaak'] = pd.to_datetime(df['MeldDatum'])

        # 4. Tijd aanmaak - GEBRUIK LOGBOEK REACTIE TIJD!
        # (Uit mapping: eerste logboek entry is eigenlijk tijd aanmaak)
        # Voor nu gebruiken we MeldTijd, maar dit zou eigenlijk eerste logboek entry moeten zijn
        result_df['Tijd aanmaak'] = df['MeldTijd']

        # 5. Locatie naam - extract na ' - '
        result_df['Locatie naam'] = df['Klant'].apply(
            lambda x: x.split(' - ', 1)[1].strip() if pd.notna(x) and ' - ' in x else x
        )

        # 6. Titel
        result_df['Titel'] = df['Werkbon titel']

        # 7. Storing omschrijving - eerste zin uit BLOB notitie
        result_df['Storing omschrijving'] = df['notitie'].apply(extract_storing_omschrijving)

        # 8. Locatie soort - NIET IN DATABASE (heuristic)
        result_df['Locatie soort'] = result_df['Locatie naam'].apply(guess_location_type)

        # 9. Installatie soort - mapping
        result_df['Installatie soort'] = df['Installatiesoort'].apply(map_installatie_soort)

        # 10. Onderaannemer
        result_df['Onderaannemer'] = df['Betreft onderaannemer']

        # 11. Welke onderaannemer? - filter Zenith
        result_df['Welke onderaannemer? (indien bekend)'] = df['Onderaannemer'].apply(
            lambda x: '' if pd.isna(x) or '000000 - Zenith' in str(x) else x
        )

        # 12. Prio volgens SLA - mapping
        result_df['Prio volgens SLA'] = df['Prioriteit'].apply(map_priority)

        # 13-14. Reactie datum & tijd - split logboek datetime
        result_df['Reactie datum'] = pd.to_datetime(df['reactie_datetime']).dt.date
        result_df['Reactie tijd'] = pd.to_datetime(df['reactie_datetime']).dt.time

        # 15. Contact CB - NIET IN DATABASE
        result_df['Contact CB'] = ''

        # 16. Prio na overleg CB - assumptie: zelfde
        result_df['Prio na overleg CB'] = result_df['Prio volgens SLA']

        # 17-18. Datum & tijd oplossing
        result_df['Datum oplossing'] = pd.to_datetime(df['datum_oplossing'])
        result_df['Tijd oplossing'] = df['tijd_oplossing']

        # 19. Geannuleerd?
        result_df['Geannuleerd?'] = df['Status'].apply(
            lambda x: 'Ja' if pd.notna(x) and 'Geannuleerd' in str(x) else 'Nee'
        )

        # 20. Toelichting - volledige BLOB notitie (RTF stripped)
        result_df['Toelichting'] = df['notitie'].apply(strip_rtf)

        # 21. Ouderdom systeem - VAAK LEEG
        result_df['Ouderdom systeem'] = ''

        # ====================================================================
        # BEREKENDE VELDEN (22-37)
        # ====================================================================

        # 22. Maand
        result_df['Maand'] = result_df['Datum aanmaak'].dt.month

        # 23. aanmaak d+t - combineer datum + tijd
        result_df['aanmaak d+t'] = pd.to_datetime(
            result_df['Datum aanmaak'].astype(str) + ' ' + result_df['Tijd aanmaak'].astype(str),
            errors='coerce'
        )

        # 24. reactie d+t - combineer reactie datum + tijd
        result_df['reactie d+t'] = pd.to_datetime(
            result_df['Reactie datum'].astype(str) + ' ' + result_df['Reactie tijd'].astype(str),
            errors='coerce'
        )

        # 25. response d+t - combineer oplossing datum + tijd
        result_df['response d+t'] = pd.to_datetime(
            result_df['Datum oplossing'].astype(str) + ' ' + result_df['Tijd oplossing'].astype(str),
            errors='coerce'
        )

        # 26. reactietijd - verschil tussen reactie en aanmaak
        result_df['reactietijd'] = result_df['reactie d+t'] - result_df['aanmaak d+t']

        # 27. response tijd - verschil tussen oplossing en aanmaak
        result_df['response tijd'] = result_df['response d+t'] - result_df['aanmaak d+t']

        # 28. Prio - mapping naar nummer
        prio_map = {'Urgent': 1, 'Medium': 2, 'Low': 3}
        result_df['Prio'] = result_df['Prio volgens SLA'].map(prio_map)

        # 29. reasponsetijd uren - ceiling van reactietijd in uren
        result_df['reasponsetijd uren'] = result_df['reactietijd'].apply(
            lambda x: np.ceil(x.total_seconds() / 3600) if pd.notna(x) else None
        )

        # 30. restoretijd uren - ceiling van response tijd in uren
        result_df['restoretijd uren'] = result_df['response tijd'].apply(
            lambda x: np.ceil(x.total_seconds() / 3600) if pd.notna(x) else None
        )

        # 31-32. KPI response & restore - lookup op basis van prio
        result_df['KPI response'] = result_df['Prio volgens SLA'].apply(
            lambda x: calculate_kpi_hours(x)['response']
        )
        result_df['KPI restore'] = result_df['Prio volgens SLA'].apply(
            lambda x: calculate_kpi_hours(x)['restore']
        )

        # 33-34. SLA response & restore - behaald/niet behaald
        result_df['SLA response'] = result_df.apply(
            lambda row: 'Behaald' if pd.notna(row['reasponsetijd uren']) and row['reasponsetijd uren'] <= row['KPI response'] else 'Niet Behaald',
            axis=1
        )
        result_df['SLA restore'] = result_df.apply(
            lambda row: 'Behaald' if pd.notna(row['restoretijd uren']) and row['restoretijd uren'] <= row['KPI restore'] else 'Niet Behaald',
            axis=1
        )

        # 35. responsetijd range - categorisering
        result_df['responsetijd range'] = result_df['reasponsetijd uren'].apply(categorize_response_time)

        # 36. Dag binnenkomst - weekday (1=Monday, 7=Sunday)
        result_df['Dag binnenkomst'] = result_df['Datum aanmaak'].dt.dayofweek + 1

        # 37. Toelichting bij Niet Behaald - leeg voor nu
        result_df['Toelichting bij Niet Behaald'] = ''

        st.success(f"✓ Data getransformeerd - {len(result_df)} werkbonnen klaar")

        # ====================================================================
        # EXCEL EXPORT MET KLEURCODERING
        # ====================================================================
        st.info("Excel bestand maken met kleurcodering...")

        output = BytesIO()

        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            result_df.to_excel(writer, sheet_name='Werkbonnen', index=False)

            workbook = writer.book
            worksheet = writer.sheets['Werkbonnen']

            # Formaten
            red_format = workbook.add_format({'bg_color': '#FEE2E2'})  # Rood - niet in database
            yellow_format = workbook.add_format({'bg_color': '#FEF3C7'})  # Geel - automatisch afgeleid

            # Kolom indexen (0-based)
            col_locatie_soort = 7  # Kolom H - Locatie soort
            col_contact_cb = 14  # Kolom O - Contact CB
            col_ouderdom = 20  # Kolom U - Ouderdom systeem

            # Kleurcodering toepassen
            for row_num in range(1, len(result_df) + 1):
                # Rood - niet in database
                worksheet.write(row_num, col_contact_cb, result_df.iloc[row_num - 1]['Contact CB'], red_format)
                worksheet.write(row_num, col_ouderdom, result_df.iloc[row_num - 1]['Ouderdom systeem'], red_format)

                # Geel - automatisch afgeleid (heuristic)
                loc_soort = result_df.iloc[row_num - 1]['Locatie soort']
                if loc_soort:  # Alleen als er een waarde is ingevuld
                    worksheet.write(row_num, col_locatie_soort, loc_soort, yellow_format)

            # Instructies sheet
            instructies = pd.DataFrame({
                'Kolom': [
                    'Contact CB',
                    'Locatie soort',
                    'Ouderdom systeem'
                ],
                'Status': [
                    'ROOD - Niet in database',
                    'GEEL - Automatisch afgeleid',
                    'ROOD - Niet in database'
                ],
                'Actie': [
                    'Handmatig invullen (bijv. Carlo, Emma)',
                    'Controleren en aanpassen indien nodig',
                    'Handmatig invullen indien bekend'
                ]
            })
            instructies.to_excel(writer, sheet_name='Instructies', index=False)

        output.seek(0)

        # ====================================================================
        # PREVIEW & DOWNLOAD
        # ====================================================================

        st.success("✅ Export klaar!")

        # Preview eerste 10 rijen
        st.subheader("Preview (eerste 10 werkbonnen)")
        st.dataframe(result_df.head(10))

        # Stats
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Totaal werkbonnen", len(result_df))
        with col2:
            sla_response_ok = (result_df['SLA response'] == 'Behaald').sum()
            st.metric("SLA response behaald", f"{sla_response_ok}/{len(result_df)}")
        with col3:
            sla_restore_ok = (result_df['SLA restore'] == 'Behaald').sum()
            st.metric("SLA restore behaald", f"{sla_restore_ok}/{len(result_df)}")
        with col4:
            geannuleerd = (result_df['Geannuleerd?'] == 'Ja').sum()
            st.metric("Geannuleerd", geannuleerd)

        # Download button
        filename = f"zenith_werkbonnen_{start_date}_{end_date}.xlsx"
        st.download_button(
            label="📥 Download Excel",
            data=output,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.info("💡 **Let op:** Rode cellen moeten handmatig worden ingevuld. Gele cellen zijn automatisch afgeleid en kunnen worden gecontroleerd.")
