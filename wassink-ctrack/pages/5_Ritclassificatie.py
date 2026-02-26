import streamlit as st
import pandas as pd
import io
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.database import load_trips
from src.auth import check_password

st.set_page_config(page_title="Ritclassificatie", page_icon="📋", layout="wide")
if not check_password():
    st.stop()
st.title("Ritclassificatie (Woon-werk / Zakelijk)")
st.caption("Classificatie van ritten voor Belastingdienst: LB km (woon-werk) vs OB km (zakelijk)")

try:
    trips = load_trips()
except Exception as e:
    st.error(f"Data fout: {e}")
    st.stop()


# =====================================================================
# DATABRONNEN TOELICHTING
# =====================================================================

with st.expander("Databronnen & mogelijkheden", expanded=False):
    src_ctrack, src_syntess = st.columns(2)

    with src_ctrack:
        st.markdown("#### ✅ C-Track GPS (actief)")
        st.markdown("""
        **Beschikbare gegevens:**
        - Ritten met start/eindlocatie en -tijd
        - Kilometers per rit (GPS-gemeten)
        - Thuisadres herkenning (C-Track labels)
        - Vestiging- en projectlocaties
        - Bestuurder naam
        - Kenteken / voertuig

        **Huidige classificatie op basis van:**
        - Locatietype (Thuis / Vestiging / Project)
        - Tijdstip en weekdag
        - Ritpatronen per bestuurder
        """)

    with src_syntess:
        st.markdown("#### 🔗 Syntess DWH (na koppeling)")
        st.markdown("""
        **Extra gegevens na koppeling:**
        - **Personeelsnummer** *(vereist voor Belastingdienst)*
        - **Functie**: Projectmonteur vs Servicemonteur
        - **Afdeling** en kostenplaats
        - Datum in/uit dienst

        **Wat dit oplevert:**
        - Automatisch juiste controle-tijdvensters per functietype
        - Personeelsnummer op export (Belastingdienst-eis)
        - Geboekte reistijd vs GPS-reistijd vergelijking
        - Werkbon-verificatie: was monteur op locatie?
        """)


# =====================================================================
# CLASSIFICATIELOGICA
# =====================================================================

def locatie_type(locatie: str) -> str:
    """Bepaal het type locatie op basis van C-Track labels."""
    if pd.isna(locatie) or locatie.strip() == '':
        return 'Onbekend'
    loc = locatie.strip()
    if loc.startswith('Thuis') or loc.startswith("'Thuis"):
        return 'Thuis'
    if loc.startswith('Vestiging'):
        return 'Vestiging'
    if loc.startswith('Project'):
        return 'Project'
    if loc.startswith('Opdrachtgever'):
        return 'Opdrachtgever'
    return 'Overig'


def classificeer_rit(row: pd.Series) -> str:
    """
    Classificeer een rit als Woon-werk, Zakelijk, of Prive.

    Regels:
    1. Thuis <-> Vestiging/Project/Opdrachtgever = Woon-werk (LB)
    2. Tussen werklocaties = Zakelijk (OB)
    3. Werklocatie <-> Overig = Zakelijk (OB) - serviceadres zonder label
    4. Thuis -> Thuis = Prive
    5. Weekend zonder werklocatie = Prive
    6. Doordeweeks na 18:00 zonder werklocatie = Prive
    7. Overig <-> Overig doordeweeks 6:00-18:00 = Zakelijk (waarschijnlijk)
    8. Rest = Te beoordelen
    """
    start_type = row['start_type']
    eind_type = row['eind_type']
    uur = row['start'].hour
    weekdag = row['start'].dayofweek  # 0=ma, 6=zo

    werk_types = {'Vestiging', 'Project', 'Opdrachtgever'}

    # Thuis -> Thuis (parkeren, korte rit)
    if start_type == 'Thuis' and eind_type == 'Thuis':
        return 'Prive'

    # Thuis <-> werklocatie = woon-werk
    if start_type == 'Thuis' and eind_type in werk_types:
        return 'Woon-werk'
    if eind_type == 'Thuis' and start_type in werk_types:
        return 'Woon-werk'

    # Tussen werklocaties = zakelijk
    if start_type in werk_types and eind_type in werk_types:
        return 'Zakelijk'

    # Werklocatie <-> Overig = zakelijk (serviceadres zonder C-Track label)
    if start_type in werk_types and eind_type == 'Overig':
        return 'Zakelijk'
    if eind_type in werk_types and start_type == 'Overig':
        return 'Zakelijk'

    # Weekend ritten zonder werklocatie = prive
    if weekdag >= 5:
        if start_type not in werk_types and eind_type not in werk_types:
            return 'Prive'

    # Doordeweeks na 18:00 zonder werklocatie = prive
    if weekdag < 5 and uur >= 18:
        if start_type not in werk_types and eind_type not in werk_types:
            return 'Prive'

    # Overig <-> Overig doordeweeks tijdens werktijd = waarschijnlijk zakelijk
    # (servicemonteurs rijden van klant naar klant, adressen niet gelabeld in C-Track)
    if weekdag < 5 and 6 <= uur < 18:
        if start_type == 'Overig' and eind_type == 'Overig':
            return 'Zakelijk'

    # Thuis <-> Overig doordeweeks voor 18:00 = waarschijnlijk woon-werk
    # (bijv. naar klantadres dat niet gelabeld is)
    if weekdag < 5 and uur < 18:
        if start_type == 'Thuis' and eind_type == 'Overig':
            return 'Woon-werk'
        if eind_type == 'Thuis' and start_type == 'Overig':
            return 'Woon-werk'

    return 'Te beoordelen'


def bepaal_route_type(row: pd.Series) -> str:
    """Bepaal of rit rechtstreeks naar huis is, via vestiging, of overig."""
    start_type = row['start_type']
    eind_type = row['eind_type']

    if start_type == 'Thuis' and eind_type in ('Project', 'Opdrachtgever'):
        return 'Rechtstreeks'
    if eind_type == 'Thuis' and start_type in ('Project', 'Opdrachtgever'):
        return 'Rechtstreeks'
    if start_type == 'Thuis' and eind_type == 'Vestiging':
        return 'Via vestiging'
    if eind_type == 'Thuis' and start_type == 'Vestiging':
        return 'Via vestiging'
    if start_type == 'Vestiging' and eind_type in ('Project', 'Opdrachtgever'):
        return 'Zakelijk'
    if eind_type == 'Vestiging' and start_type in ('Project', 'Opdrachtgever'):
        return 'Zakelijk'
    return ''


# Classificatie toepassen
trips['start_type'] = trips['startlocation'].apply(locatie_type)
trips['eind_type'] = trips['endlocation'].apply(locatie_type)
trips['classificatie'] = trips.apply(classificeer_rit, axis=1)
trips['route_type'] = trips.apply(bepaal_route_type, axis=1)

# LB/OB km berekenen
trips['lb_km'] = trips.apply(
    lambda r: r['afstand_km'] if r['classificatie'] == 'Woon-werk' else 0, axis=1
)
trips['ob_km'] = trips.apply(
    lambda r: r['afstand_km'] if r['classificatie'] == 'Zakelijk' else 0, axis=1
)


# =====================================================================
# FILTERS
# =====================================================================

col1, col2, col3 = st.columns(3)
with col1:
    bestuurders = sorted(trips['bestuurder'].dropna().unique())
    sel_bestuurder = st.selectbox("Bestuurder", ["Alle"] + bestuurders)
with col2:
    datums = sorted(trips['datum'].unique())
    if len(datums) >= 2:
        date_range = st.date_input(
            "Periode",
            value=(datums[0], datums[-1]),
            min_value=datums[0],
            max_value=datums[-1],
        )
    else:
        date_range = (datums[0], datums[0])
with col3:
    classificaties = ['Alle', 'Woon-werk', 'Zakelijk', 'Prive', 'Te beoordelen']
    sel_class = st.selectbox("Classificatie", classificaties)

# Filter toepassen
data = trips.copy()
if sel_bestuurder != "Alle":
    data = data[data['bestuurder'] == sel_bestuurder]
if isinstance(date_range, tuple) and len(date_range) == 2:
    data = data[(data['datum'] >= date_range[0]) & (data['datum'] <= date_range[1])]
if sel_class != "Alle":
    data = data[data['classificatie'] == sel_class]


# =====================================================================
# KPI'S
# =====================================================================

st.markdown("---")
k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    st.metric("Totaal ritten", f"{len(data):,}")
with k2:
    st.metric("Totaal km", f"{data['afstand_km'].sum():,.0f}")
with k3:
    st.metric("LB km (woon-werk)", f"{data['lb_km'].sum():,.0f}")
with k4:
    st.metric("OB km (zakelijk)", f"{data['ob_km'].sum():,.0f}")
with k5:
    te_beoordelen = len(data[data['classificatie'] == 'Te beoordelen'])
    st.metric("Te beoordelen", f"{te_beoordelen}")


# =====================================================================
# CLASSIFICATIE VERDELING
# =====================================================================

st.markdown("---")
col_chart, col_table = st.columns([2, 1])

with col_chart:
    st.subheader("Verdeling classificaties")
    class_counts = trips.groupby('classificatie').agg(
        ritten=('afstand_km', 'count'),
        km=('afstand_km', 'sum')
    ).reset_index()
    class_counts['km'] = class_counts['km'].round(0)
    class_counts = class_counts.sort_values('ritten', ascending=False)

    st.bar_chart(
        class_counts.set_index('classificatie')['ritten'],
        horizontal=True,
    )

with col_table:
    st.subheader("Samenvatting")
    summary = class_counts.rename(columns={
        'classificatie': 'Type',
        'ritten': 'Ritten',
        'km': 'Kilometers',
    })
    st.dataframe(summary, use_container_width=True, hide_index=True)


# =====================================================================
# DAGOVERZICHT PER BESTUURDER
# =====================================================================

st.markdown("---")
st.subheader("Dagoverzicht per bestuurder")

if sel_bestuurder != "Alle":
    dag_data = data.sort_values('start')
    dag_overzicht = dag_data.groupby('datum').agg(
        ritten=('afstand_km', 'count'),
        totaal_km=('afstand_km', 'sum'),
        lb_km=('lb_km', 'sum'),
        ob_km=('ob_km', 'sum'),
        eerste_start=('start', 'first'),
        laatste_eind=('eind', 'last'),
        eerste_locatie=('startlocation', 'first'),
        laatste_locatie=('endlocation', 'last'),
    ).reset_index()

    dag_overzicht['totaal_km'] = dag_overzicht['totaal_km'].round(1)
    dag_overzicht['lb_km'] = dag_overzicht['lb_km'].round(1)
    dag_overzicht['ob_km'] = dag_overzicht['ob_km'].round(1)
    dag_overzicht['eerste_start'] = dag_overzicht['eerste_start'].dt.strftime('%H:%M')
    dag_overzicht['laatste_eind'] = dag_overzicht['laatste_eind'].dt.strftime('%H:%M')

    st.dataframe(
        dag_overzicht.rename(columns={
            'datum': 'Datum',
            'ritten': 'Ritten',
            'totaal_km': 'Totaal km',
            'lb_km': 'LB km',
            'ob_km': 'OB km',
            'eerste_start': 'Start',
            'laatste_eind': 'Eind',
            'eerste_locatie': 'Vertrek',
            'laatste_locatie': 'Aankomst',
        }),
        use_container_width=True,
        hide_index=True,
    )
else:
    per_best = data.groupby('bestuurder').agg(
        ritten=('afstand_km', 'count'),
        totaal_km=('afstand_km', 'sum'),
        lb_km=('lb_km', 'sum'),
        ob_km=('ob_km', 'sum'),
    ).reset_index()
    per_best['totaal_km'] = per_best['totaal_km'].round(0)
    per_best['lb_km'] = per_best['lb_km'].round(0)
    per_best['ob_km'] = per_best['ob_km'].round(0)
    per_best = per_best.sort_values('totaal_km', ascending=False)

    st.dataframe(
        per_best.rename(columns={
            'bestuurder': 'Bestuurder',
            'ritten': 'Ritten',
            'totaal_km': 'Totaal km',
            'lb_km': 'LB km',
            'ob_km': 'OB km',
        }),
        use_container_width=True,
        hide_index=True,
    )


# =====================================================================
# GEDETAILLEERDE RITTENTABEL
# =====================================================================

st.markdown("---")
st.subheader("Ritten detail")

# Databron indicator per kolom
st.markdown(
    '<p style="font-size: 0.85em; color: #888;">'
    '🟢 = C-Track (beschikbaar) &nbsp;&nbsp; '
    '🔵 = Syntess DWH (na koppeling)'
    '</p>',
    unsafe_allow_html=True,
)

detail = data[[
    'bestuurder', 'datum', 'start', 'eind',
    'startlocation', 'endlocation', 'afstand_km',
    'start_type', 'eind_type', 'classificatie', 'route_type',
    'lb_km', 'ob_km', 'kenteken',
]].copy()

detail['start_tijd'] = detail['start'].dt.strftime('%H:%M')
detail['eind_tijd'] = detail['eind'].dt.strftime('%H:%M')
detail['afstand_km'] = detail['afstand_km'].round(1)
detail['lb_km'] = detail['lb_km'].round(1)
detail['ob_km'] = detail['ob_km'].round(1)

# Verkort locatienamen voor weergave
detail['startpunt'] = detail['startlocation'].str.split(';').str[0]
detail['eindpunt'] = detail['endlocation'].str.split(';').str[0]

# Syntess placeholder kolommen
detail['personeelsnr'] = '-'
detail['functie'] = '-'

display_cols = {
    'personeelsnr': '🔵 Pers.nr',
    'bestuurder': '🟢 Bestuurder',
    'functie': '🔵 Functie',
    'datum': '🟢 Datum',
    'start_tijd': '🟢 Start',
    'eind_tijd': '🟢 Eind',
    'startpunt': '🟢 Startpunt',
    'eindpunt': '🟢 Eindpunt',
    'afstand_km': '🟢 Km',
    'classificatie': '🟢 Classificatie',
    'route_type': '🟢 Route',
    'lb_km': 'LB km',
    'ob_km': 'OB km',
}

st.dataframe(
    detail[list(display_cols.keys())].rename(columns=display_cols).sort_values(
        ['🟢 Datum', '🟢 Bestuurder', '🟢 Start']
    ),
    use_container_width=True,
    hide_index=True,
    height=500,
)


# =====================================================================
# SYNTESS MEERWAARDE PREVIEW
# =====================================================================

st.markdown("---")
st.subheader("Na Syntess DWH-koppeling")

st.markdown("""
Met de Syntess-koppeling worden de volgende verbeteringen mogelijk:
""")

mw1, mw2, mw3 = st.columns(3)

with mw1:
    st.markdown("##### Personeelsnummer")
    st.markdown("""
    **Bron:** `stam.Medewerkers`

    Koppeling van C-Track bestuurdersnaam
    aan Syntess medewerkercode. Vereist
    voor de Belastingdienst-export.
    """)

with mw2:
    st.markdown("##### Functie-classificatie")
    st.markdown("""
    **Bron:** `stam.Medewerkers`

    Automatisch onderscheid tussen
    **Projectmonteur** (7:00-15:45) en
    **Servicemonteur** (8:00-17:00).
    Juiste controle-tijdvensters per type.
    """)

with mw3:
    st.markdown("##### Reistijd-verificatie")
    st.markdown("""
    **Bron:** `stam.Werkbonnen` / `stam.Uren`

    Vergelijk geboekte reistijd met
    GPS-gemeten rijtijd. Signaleer
    afwijkingen automatisch.
    """)

# Voorbeeld tabel van wat het oplevert
st.markdown("**Voorbeeld: hoe de export eruitziet na koppeling**")
voorbeeld = pd.DataFrame({
    'Personeelsnr': ['W-1234', 'W-1234', 'W-5678', 'W-5678'],
    'Naam': ['Thomas Sievers', 'Thomas Sievers', 'Gerton Vlastuin', 'Gerton Vlastuin'],
    'Functie': ['Servicemonteur', 'Servicemonteur', 'Projectmonteur', 'Projectmonteur'],
    'Starttijd': ['07:48', '17:22', '06:45', '15:30'],
    'Startpunt': ['Thuis', 'Vestiging Winterswijk', 'Thuis', 'Project Elver'],
    'Eindpunt': ['Vestiging Winterswijk', 'Thuis', 'Project Elver', 'Thuis'],
    'Km': [46.1, 53.7, 12.3, 12.3],
    'Type': ['Woon-werk', 'Woon-werk', 'Woon-werk', 'Woon-werk'],
    'Controlevenster': ['7:30-8:30 ✓', '16:30-17:30 ✓', '5:45-7:30 ✓', '15:15-17:00 ✓'],
    'Geboekte reistijd': ['45 min', '50 min', '20 min', '20 min'],
    'GPS reistijd': ['45 min', '49 min', '18 min', '19 min'],
    'LB km': [46.1, 53.7, 12.3, 12.3],
    'OB km': [0, 0, 0, 0],
})

st.dataframe(voorbeeld, use_container_width=True, hide_index=True)

st.info(
    "De kolommen **Personeelsnr**, **Functie**, **Controlevenster**, "
    "**Geboekte reistijd** en **GPS reistijd** komen beschikbaar "
    "na koppeling met het Syntess Data Warehouse."
)


# =====================================================================
# EXCEL EXPORT (Anne's format)
# =====================================================================

st.markdown("---")
st.subheader("Excel export (Belastingdienst format)")

col_info, col_btn = st.columns([3, 1])
with col_info:
    st.markdown(
        "Export in het format van Anne Wassink. "
        "Kolom **Personeelsnummer** wordt gevuld na Syntess-koppeling."
    )

# Bouw export dataframe in Anne's kolomvolgorde
export = data[[
    'bestuurder', 'start', 'eind',
    'startlocation', 'endlocation', 'afstand_km',
    'classificatie', 'route_type', 'lb_km', 'ob_km',
]].copy()

export['personeelsnummer'] = ''  # Vullen na Syntess-koppeling
export['starttijd'] = export['start'].dt.strftime('%Y-%m-%d %H:%M')
export['eindtijd'] = export['eind'].dt.strftime('%Y-%m-%d %H:%M')
export['rechtstreeks_nr_huis'] = export['route_type'].apply(
    lambda x: 'Ja' if x == 'Rechtstreeks' else ''
)
export['via_vestiging'] = export['route_type'].apply(
    lambda x: 'Ja' if x == 'Via vestiging' else ''
)
export['tussenstop_prive'] = export['classificatie'].apply(
    lambda x: 'Ja' if x == 'Prive' else ''
)

# Kolomvolgorde Anne's format
excel_df = export[[
    'personeelsnummer',
    'bestuurder',
    'starttijd',
    'eindtijd',
    'startlocation',
    'endlocation',
    'afstand_km',
    'rechtstreeks_nr_huis',
    'via_vestiging',
    'tussenstop_prive',
    'lb_km',
    'ob_km',
]].copy()

excel_df.columns = [
    'Personeelsnummer',
    'Naam medewerker',
    'Starttijd',
    'Eindtijd',
    'Startpunt',
    'Eindpunt',
    'Aantal km',
    'Rechtstreeks nr huis',
    'Via vestiging',
    'Tussenstop overig (prive)',
    'LB KM',
    'OB km',
]

excel_df = excel_df.sort_values(['Naam medewerker', 'Starttijd'])

# Excel download
buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
    excel_df.to_excel(writer, sheet_name='Ritclassificatie', index=False)

    # Controle-sheet met regels
    controles = pd.DataFrame({
        'Controle': [
            'Prive ritten na werktijd',
            'Projectmonteurs',
            'Servicemonteurs',
        ],
        'Omschrijving': [
            'Van huis, naar adres, terug naar huis na 18 uur doordeweeks en volledige weekenddagen',
            'Werktijd 7:00-15:45. Controle ritten tussen 5:45-7:30 en 15:15-17:00',
            'Werktijd 8:00-17:00. Controle ritten tussen 7:30-8:30 en 16:30-17:30',
        ],
        'Databron': [
            'C-Track GPS (beschikbaar)',
            'C-Track GPS + Syntess functie (na koppeling)',
            'C-Track GPS + Syntess functie (na koppeling)',
        ],
    })
    controles.to_excel(writer, sheet_name='Controles', index=False)

    # Databronnen sheet
    bronnen = pd.DataFrame({
        'Kolom': [
            'Personeelsnummer', 'Naam medewerker', 'Starttijd', 'Eindtijd',
            'Startpunt', 'Eindpunt', 'Aantal km',
            'Rechtstreeks nr huis', 'Via vestiging', 'Tussenstop overig (prive)',
            'LB KM', 'OB km',
        ],
        'Databron': [
            'Syntess DWH (stam.Medewerkers)', 'C-Track GPS', 'C-Track GPS', 'C-Track GPS',
            'C-Track GPS', 'C-Track GPS', 'C-Track GPS',
            'C-Track GPS (classificatie)', 'C-Track GPS (classificatie)', 'C-Track GPS (classificatie)',
            'Berekend (C-Track + classificatie)', 'Berekend (C-Track + classificatie)',
        ],
        'Status': [
            'Na Syntess-koppeling', 'Beschikbaar', 'Beschikbaar', 'Beschikbaar',
            'Beschikbaar', 'Beschikbaar', 'Beschikbaar',
            'Beschikbaar', 'Beschikbaar', 'Beschikbaar',
            'Beschikbaar', 'Beschikbaar',
        ],
    })
    bronnen.to_excel(writer, sheet_name='Databronnen', index=False)

buffer.seek(0)

st.download_button(
    label="Download Excel (Belastingdienst format)",
    data=buffer,
    file_name="ritclassificatie_wassink.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)

# Preview
with st.expander("Preview export (eerste 20 rijen)"):
    st.dataframe(excel_df.head(20), use_container_width=True, hide_index=True)
