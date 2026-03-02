import streamlit as st
import pandas as pd
import io
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.database import load_trips
from src.auth import check_password
from src.sidebar import show_logo

st.set_page_config(page_title="Ritclassificatie", page_icon="📋", layout="wide")
if not check_password():
    st.stop()
show_logo()
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

with st.expander("Hoe worden ritten geclassificeerd? (LB/OB regelgeving)", expanded=False):
    st.markdown("""
    De classificatie bepaalt per rit of kilometers meetellen als **LB km** (Loonbelasting, woon-werk)
    of **OB km** (Omzetbelasting, zakelijk). Dit gebeurt automatisch op basis van C-Track locatielabels
    en tijdstip/weekdag.
    """)

    regels = pd.DataFrame({
        'Regel': [
            '1. Thuis collega',
            '2. Eigen Thuis → eigen Thuis',
            '3. Eigen Thuis ↔ Vestiging/Project',
            '4. Tussen werklocaties',
            '5. Werklocatie ↔ Overig adres',
            '6. Weekend (geen werklocatie)',
            '7. Doordeweeks na 18:00',
            '8. Overig ↔ Overig (werkdag 6-18u)',
            '9. Eigen Thuis ↔ Overig (werkdag)',
            '10. Rest',
        ],
        'Conditie': [
            'Start of eind bij Thuis van ANDERE bestuurder',
            'Start en eind bij eigen Thuis (parkeren/korte rit)',
            'Eigen Thuis naar vestiging, project of opdrachtgever (en vice versa)',
            'Vestiging ↔ Project ↔ Opdrachtgever',
            'Vestiging/Project naar ongelabeld adres (of omgekeerd)',
            'Za/zo zonder werklocatie in start/eind',
            'Ma-vr na 18:00 zonder werklocatie',
            'Twee ongelabelde adressen, doordeweeks 6:00-18:00',
            'Eigen Thuis naar ongelabeld adres, doordeweeks voor 18:00',
            'Geen van bovenstaande regels van toepassing',
        ],
        'Classificatie': [
            'Zakelijk (OB) — collega ophalen/afzetten',
            'Prive',
            'Woon-werk (LB)',
            'Zakelijk (OB)',
            'Zakelijk (OB)',
            'Prive',
            'Prive',
            'Zakelijk (OB) — waarschijnlijk klantbezoek',
            'Woon-werk (LB) — waarschijnlijk naar klant',
            'Te beoordelen (handmatig)',
        ],
    })
    st.dataframe(regels, use_container_width=True, hide_index=True)

    st.markdown("""
    **Belangrijk:** De herkenning van "eigen Thuis" vs "Thuis collega" werkt op basis van naammatching.
    C-Track labelt thuisadressen als *"Thuis {naam}"*. Als de naam overeenkomt met de bestuurder → eigen woon-werk.
    Als het een andere naam is → zakelijk (collega ophalen/afzetten).

    **Voorbeeld:** Thomas Sievers rijdt naar *"Thuis Sven S."* → Sven ≠ Thomas → **Zakelijk** (collega ophalen).
    Thomas Sievers rijdt naar *"Thuis Thomas Sievers"* → Thomas = Thomas → **Woon-werk**.
    """)

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
        - Bestuurder naam + eigen Thuis vs Thuis collega
        - Kenteken / voertuig

        **Huidige classificatie op basis van:**
        - Locatietype (eigen Thuis / Thuis collega / Vestiging / Project)
        - Tijdstip en weekdag
        - Ritpatronen per bestuurder

        **Personeelsnummer:** Wassink plant een leeg C-Track veld
        te gebruiken voor personeelsnummer. Dit maakt directe
        koppeling met Syntess SSM mogelijk.
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

def locatie_type(locatie: str, bestuurder: str = '') -> str:
    """Bepaal het type locatie op basis van C-Track labels.

    Onderscheidt eigen Thuis vs Thuis collega (ophalen/afzetten).
    """
    if pd.isna(locatie) or locatie.strip() == '':
        return 'Onbekend'
    loc = locatie.strip().lstrip("'")
    if loc.startswith('Thuis'):
        thuis_naam = loc.split(';')[0].replace('Thuis ', '', 1).strip()
        if bestuurder and thuis_naam:
            driver_parts = bestuurder.lower().split()
            thuis_parts = thuis_naam.lower().split()
            if any(p in thuis_parts for p in driver_parts if len(p) > 1):
                return 'Thuis'
            return 'Thuis collega'
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
    1. Eigen Thuis <-> Vestiging/Project/Opdrachtgever = Woon-werk (LB)
    2. Thuis collega = Zakelijk (ophalen/afzetten collega)
    3. Tussen werklocaties = Zakelijk (OB)
    4. Werklocatie <-> Overig = Zakelijk (OB) - serviceadres zonder label
    5. Eigen Thuis -> eigen Thuis = Prive (parkeren/korte rit)
    6. Weekend zonder werklocatie = Prive
    7. Doordeweeks na 18:00 zonder werklocatie = Prive
    8. Overig <-> Overig doordeweeks 6:00-18:00 = Zakelijk (waarschijnlijk)
    9. Eigen Thuis <-> Overig doordeweeks voor 18:00 = Woon-werk
    10. Rest = Te beoordelen
    """
    start_type = row['start_type']
    eind_type = row['eind_type']
    uur = row['start'].hour
    weekdag = row['start'].dayofweek  # 0=ma, 6=zo

    werk_types = {'Vestiging', 'Project', 'Opdrachtgever'}

    # Thuis collega = altijd zakelijk (ophalen/afzetten collega)
    if start_type == 'Thuis collega' or eind_type == 'Thuis collega':
        return 'Zakelijk'

    # Eigen Thuis -> eigen Thuis (parkeren, korte rit)
    if start_type == 'Thuis' and eind_type == 'Thuis':
        return 'Prive'

    # Eigen Thuis <-> werklocatie = woon-werk
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

    # Eigen Thuis <-> Overig doordeweeks voor 18:00 = waarschijnlijk woon-werk
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

    # Thuis collega = altijd zakelijk (ophalen/afzetten)
    if start_type == 'Thuis collega' or eind_type == 'Thuis collega':
        return 'Collega ophalen'

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


# Classificatie toepassen (met bestuurder voor Thuis eigen vs collega)
trips['start_type'] = trips.apply(
    lambda r: locatie_type(r['startlocation'], r['bestuurder']), axis=1
)
trips['eind_type'] = trips.apply(
    lambda r: locatie_type(r['endlocation'], r['bestuurder']), axis=1
)
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
    # Gebruik ALLE ritten van deze bestuurder (ongeacht classificatie-filter)
    # zodat de route-keten altijd compleet zichtbaar is
    alle_ritten_bestuurder = trips[trips['bestuurder'] == sel_bestuurder].copy()
    if isinstance(date_range, tuple) and len(date_range) == 2:
        alle_ritten_bestuurder = alle_ritten_bestuurder[
            (alle_ritten_bestuurder['datum'] >= date_range[0]) &
            (alle_ritten_bestuurder['datum'] <= date_range[1])
        ]

    dag_data = alle_ritten_bestuurder.sort_values('start')
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

    # Toon complete rittenreeks per dag (alle ritten, ook buiten filter)
    with st.expander("Volledige rittenreeks (route-continuiteit)", expanded=False):
        if sel_class != "Alle":
            st.caption(
                f"Alle ritten worden getoond voor route-continuiteit. "
                f"Ritten buiten filter '{sel_class}' zijn grijs gemarkeerd."
            )
        for datum, dag_trips in dag_data.groupby('datum'):
            dag_sorted = dag_trips.sort_values('start')
            st.markdown(f"**{datum}** ({len(dag_sorted)} ritten)")
            rows = []
            for _, r in dag_sorted.iterrows():
                sp = str(r['startlocation']).split(';')[0].strip()
                ep = str(r['endlocation']).split(';')[0].strip()
                in_filter = sel_class == "Alle" or r['classificatie'] == sel_class
                prefix = "" if in_filter else "~~"
                suffix = "" if in_filter else "~~"
                rows.append({
                    'Tijd': f"{r['start'].strftime('%H:%M')}-{r['eind'].strftime('%H:%M')}",
                    'Startpunt': sp,
                    'Eindpunt': ep,
                    'Km': round(r['afstand_km'], 1),
                    'Type': r['classificatie'],
                    'Route': r['route_type'],
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
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
# DWH KOPPELING: WAT WORDT ER MOGELIJK?
# =====================================================================

st.markdown("---")
st.subheader("Na DWH-koppeling: Syntess SSM + C-Track")

st.markdown(
    "Het Syntess SSM datamodel bevat standaard tabellen voor medewerker- en "
    "ritregistratie. Door deze te koppelen aan de C-Track GPS-data "
    "ontstaat een **sluitende verantwoording** richting de Belastingdienst."
)

# SSM Views tabel
with st.expander("Syntess SSM views beschikbaar voor koppeling", expanded=True):
    ssm_views = pd.DataFrame({
        'SSM View': [
            'SSM Bedrijfsmedewerkers',
            'SSM Werkbonparagraaf kosten en geboekte uren',
            'SSM Medewerker mobiliteit',
            'Mobiele uitvoersessies',
            'Tijdregistraties mobiele uitvoersessies',
        ],
        'Schema': [
            'notifica', 'notifica', 'notifica',
            'werkbonnen', 'werkbonnen',
        ],
        'Relevante velden': [
            'Medewerker Code, Volledige naam, Functie, '
            'Datum in dienst, Afdeling, Type medewerker',
            'Arbeid begintijd, Arbeid eindtijd, Uitvoeringsdatum, '
            'MedewerkerKey, WerkbonDocumentKey',
            'Afstand (woon-werk km), Weekdagnummer, Vervoermiddel, '
            'Brandstoftype, Reistype, Begin-/Einddatum',
            'Reistijd, Werktijd, Datum, Tijdstip, Meegereden (J/N), '
            'DocumentKey (werkbon), MedewerkerKey',
            'Status (Begin/Vertrek/Pauze/Gereed), Datum/tijd, '
            'MobieleuitvoersessieRegelKey',
        ],
        'Status': [
            'Bevestigd',
            'Bevestigd',
            'Valideren bij klant (consultancy)',
            'Valideren bij klant (consultancy)',
            'Valideren bij klant (consultancy)',
        ],
        'Vergelijking met C-Track': [
            'Koppel bestuurdersnaam aan personeelsnummer + functie '
            '(Projectmonteur vs Servicemonteur)',
            'Vergelijk werkbon arbeidstijden met GPS-aanwezigheid '
            'op projectlocatie',
            'Vergelijk opgegeven woon-werk km met GPS-gemeten afstand '
            'per medewerker per weekdag',
            'Vergelijk geboekte reistijd per werkbon met GPS-rijtijd '
            'op dezelfde dag',
            'Vergelijk exacte vertrek-/aankomsttijden uit app met '
            'GPS start-/eindtijd per rit',
        ],
    })
    st.dataframe(ssm_views, use_container_width=True, hide_index=True)
    st.caption(
        "SSM Geboekte uren is niet opgenomen (te breed, bevat ook indirecte uren). "
        "SSM Werkbonparagraaf bevat de relevante arbeidstijden per werkbon."
    )

# Drie pijlers meerwaarde
mw1, mw2, mw3 = st.columns(3)

with mw1:
    st.markdown("##### 1. Belastingdienst-export")
    st.markdown("""
    **SSM View:** `SSM Bedrijfsmedewerkers` ✅

    - **Medewerker Code** op elke rit
    - **Functie** bepaalt controlevenster
    - Projectmonteur: 7:00-15:45
    - Servicemonteur: 8:00-17:00

    *Vereist voor aangifte.*
    """)

with mw2:
    st.markdown("##### 2. Werkbon vs GPS")
    st.markdown("""
    **SSM View:** `SSM Werkbonparagraaf` ✅

    - **Arbeid begintijd/eindtijd** per werkbon
    - Vergelijk met GPS aankomst/vertrek
    - Was monteur daadwerkelijk op locatie?

    *De kern: werkbon reistijd vs GPS.*
    """)

with mw3:
    st.markdown("##### 3. Woon-werk verificatie")
    st.markdown("""
    **SSM View:** `SSM Medewerker mobiliteit` ⚠️

    - **Afstand**: opgegeven woon-werk km
    - Per **Weekdagnummer** (ma-vr)
    - Vergelijk met C-Track GPS km

    *⚠️ View moet bij klant gevalideerd
    worden (consultancy).*
    """)

# Concrete voorbeelden
st.markdown("---")
st.markdown("**Voorbeeld 1: Woon-werk km - Syntess opgave vs C-Track GPS**")
st.caption("SSM Medewerker mobiliteit.Afstand vs C-Track GPS afstand_km")
vb_ww = pd.DataFrame({
    'Pers.nr': ['W-1234', 'W-1234', 'W-5678', 'W-5678'],
    'Medewerker': ['Thomas Sievers', 'Thomas Sievers', 'Gerton Vlastuin', 'Gerton Vlastuin'],
    'Functie': ['Servicemonteur', 'Servicemonteur', 'Projectmonteur', 'Projectmonteur'],
    'Syntess woon-werk km': ['46 km (ma-vr)', '46 km (ma-vr)', '12 km (ma-vr)', '12 km (ma-vr)'],
    'C-Track GPS km': ['46.1 km', '53.7 km', '12.3 km', '12.3 km'],
    'Route': ['Thuis > Vestiging', 'Vestiging > Thuis', 'Thuis > Project', 'Project > Thuis'],
    'Afwijking': ['+ 0.1 km', '+ 7.7 km (!)', '+ 0.3 km', '+ 0.3 km'],
})
st.dataframe(vb_ww, use_container_width=True, hide_index=True)

st.markdown("**Voorbeeld 2: Werkbon reistijd vs GPS rijtijd**")
st.caption("SSM Werkbonparagraaf.Arbeid begintijd/eindtijd vs C-Track GPS drivingtime")
vb_rt = pd.DataFrame({
    'Pers.nr': ['W-1234', 'W-1234', 'W-5678'],
    'Medewerker': ['Thomas Sievers', 'Thomas Sievers', 'Gerton Vlastuin'],
    'Datum': ['03-02', '03-02', '04-02'],
    'Werkbon reistijd (Syntess)': ['1:30 uur', '0:45 uur', '0:20 uur'],
    'GPS rijtijd (C-Track)': ['1:25 uur', '0:48 uur', '0:18 uur'],
    'Verschil': ['-5 min', '+3 min', '-2 min'],
    'Status': ['OK', 'OK', 'OK'],
})
st.dataframe(vb_rt, use_container_width=True, hide_index=True)

st.markdown("**Voorbeeld 3: Kloktijd werkbon vs GPS vertrek/aankomst**")
st.caption("SSM Werkbonparagraaf.Arbeid begintijd vs C-Track tripstartutc/tripendutc (⚠️ Tijdregistraties view moet bij klant gevalideerd worden)")
vb_klok = pd.DataFrame({
    'Medewerker': ['Thomas Sievers', 'Thomas Sievers', 'Thomas Sievers'],
    'Werkbon-app': ['Begin: 07:48', 'Vertrek: 08:44', 'Gereed: 09:24'],
    'C-Track GPS': ['Rit start: 07:47', 'Rit start: 08:44', 'Rit eind: 09:24'],
    'Verschil': ['1 min', '0 min', '0 min'],
    'Conclusie': ['Klopt', 'Klopt', 'Klopt'],
})
st.dataframe(vb_klok, use_container_width=True, hide_index=True)

st.info(
    "Bovenstaande voorbeelden zijn illustratief. Na DWH-koppeling worden de "
    "SSM views automatisch vergeleken met de C-Track GPS-metingen. "
    "SSM Bedrijfsmedewerkers en SSM Werkbonparagraaf zijn bevestigd. "
    "Overige views (mobiliteit, werksessies) moeten bij de klant gevalideerd worden."
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


# =====================================================================
# OVER DEZE TOOL
# =====================================================================

st.markdown("---")
with st.expander("Over deze tool — wat is er gebouwd en waarom", expanded=False):
    st.markdown("""
    ### Wat is deze tool?

    Dit dashboard analyseert automatisch de C-Track GPS-ritdata van Wassink (1225)
    en classificeert elke rit als **woon-werk (LB km)**, **zakelijk (OB km)** of **prive**.
    Het doel is een sluitende rittenregistratie richting de Belastingdienst.

    ### Wat kan de tool nu (alleen C-Track GPS)?

    **5 dashboardpagina's:**
    1. **Home** — KPI's, dagelijkse km-trend, top voertuigen/bestuurders
    2. **Vlootoverzicht** — per voertuig: km, ritten, uren, kmstand
    3. **Kilometerregistratie** — per voertuig of bestuurder, activiteitsheatmap
    4. **Kaart** — bestemmingen, vertrekpunten en ritlijnen op de kaart
    5. **Ritclassificatie** — automatische LB/OB classificatie + Excel-export

    **Classificatielogica:** Op basis van C-Track locatielabels (Thuis, Vestiging,
    Project, Opdrachtgever) + tijdstip en weekdag. Onderscheidt eigen Thuis vs Thuis
    collega (ophalen/afzetten = zakelijk). Zie "Hoe worden ritten geclassificeerd?"
    bovenaan deze pagina voor alle regels.

    **Excel-export:** In het exacte kolomformat van Anne Wassink (Belastingdienst-format),
    met aparte sheets voor controleregels en databronnen.

    ### Wat wordt beter met Syntess DWH-koppeling?

    Door de C-Track GPS-data te combineren met het Syntess SSM datamodel ontstaat:

    - **Personeelsnummer** op elke rit (Belastingdienst-eis) — via `SSM Bedrijfsmedewerkers`
    - **Functie-specifieke controlevensters** (Projectmonteur 7:00-15:45, Servicemonteur 8:00-17:00)
    - **Werkbon arbeidstijden vs GPS** — vergelijk geboekte tijden met daadwerkelijke aanwezigheid
      via `SSM Werkbonparagraaf kosten en geboekte uren`
    - **Woon-werk km verificatie** — vergelijk Syntess-opgave met GPS-gemeten afstand
      (view moet bij klant gevalideerd worden)

    De combinatie C-Track + Syntess maakt de rittenregistratie **aantoonbaar sluitend**:
    wat zegt de werkbon aan reistijd, en wat zegt de GPS?

    ### Updates

    **v2 (2 maart 2026) — Feedback Arthur Gartz verwerkt:**
    - Classificatie verbeterd: "Thuis collega" (ophalen/afzetten) wordt nu correct
      als **Zakelijk** geclassificeerd in plaats van Woon-werk
    - SSM views gecorrigeerd: 2 bevestigd, 3 te valideren bij klant, SSM Geboekte uren
      verwijderd (te breed). Werkbonparagraaf is leidend.
    - Classificatieregels volledig gedocumenteerd (10 regels, LB/OB uitleg)
    - Volledige rittenreeks per dag zichtbaar (route-continuiteit, ook bij filters)
    - Personeelsnummer: Wassink plant dit via leeg C-Track veld te registreren
    - Notifica logo toegevoegd aan alle pagina's
    - UTF-8 encoding gefixed (speciale tekens zoals e, o correct weergegeven)

    **v1 (26 februari 2026) — Eerste versie:**
    - 5 dashboardpagina's gebouwd op C-Track GPS parquet data
    - Automatische ritclassificatie (Woon-werk/Zakelijk/Prive)
    - Excel-export in Belastingdienst-format
    - DWH-koppeling sectie met SSM datamodel als upsell
    """)

    # Huidige classificatie verdeling
    st.markdown("**Huidige classificatie verdeling (alle data):**")
    totals = trips.groupby('classificatie').agg(
        ritten=('afstand_km', 'count'),
        km=('afstand_km', 'sum'),
    ).reset_index()
    totals['km'] = totals['km'].round(0).astype(int)
    totals = totals.sort_values('ritten', ascending=False)
    totals.columns = ['Classificatie', 'Ritten', 'Kilometers']
    st.dataframe(totals, use_container_width=True, hide_index=True)
