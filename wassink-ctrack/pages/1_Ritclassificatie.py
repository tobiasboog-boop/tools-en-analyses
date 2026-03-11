import streamlit as st
import pandas as pd
import io
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.database import load_trips, load_medewerker_mapping, load_verlof_dagen, VERLOF_TAAK_CODES
from src.auth import check_password
from src.sidebar import show_logo

st.set_page_config(page_title="Ritclassificatie", page_icon="📋", layout="wide")
if not check_password():
    st.stop()
show_logo()
st.title("Ritclassificatie (Belastingdienst)")
st.caption("LB km (prive) vs OB km (woon-werk) — doel: prive < 500 km/jaar")

try:
    trips = load_trips()
    medewerker_map = load_medewerker_mapping()
    verlof_dagen = load_verlof_dagen()
except Exception as e:
    st.error(f"Data fout: {e}")
    st.stop()

# Merge medewerkerdata op trips
merge_cols = ['bestuurder', 'personeelsnummer', 'functie']
if 'functie_categorie' in medewerker_map.columns:
    merge_cols.append('functie_categorie')
for col in ['straat', 'huisnummer', 'postcode', 'plaats']:
    if col in medewerker_map.columns:
        merge_cols.append(col)

if not medewerker_map.empty:
    trips = trips.merge(
        medewerker_map[[c for c in merge_cols if c in medewerker_map.columns]],
        on='bestuurder',
        how='left',
    )
else:
    trips['personeelsnummer'] = ''
    trips['functie'] = ''

trips['personeelsnummer'] = trips['personeelsnummer'].fillna('')
trips['functie'] = trips['functie'].fillna('')
if 'functie_categorie' not in trips.columns:
    trips['functie_categorie'] = ''
else:
    trips['functie_categorie'] = trips['functie_categorie'].fillna('')

# Verlof-lookup: set van (personeelsnummer, datum) → verlof_type
_verlof_set = set()
_verlof_type_lookup = {}
if not verlof_dagen.empty:
    for _, vr in verlof_dagen.iterrows():
        key = (str(vr['personeelsnummer']), vr['datum'])
        _verlof_set.add(key)
        _verlof_type_lookup[key] = vr['verlof_type']

# Markeer verlofdag op trips
trips['is_verlofdag'] = trips.apply(
    lambda r: (str(r['personeelsnummer']), r['datum']) in _verlof_set, axis=1
)
trips['verlof_type'] = trips.apply(
    lambda r: _verlof_type_lookup.get((str(r['personeelsnummer']), r['datum']), ''), axis=1
)

_verlof_count = trips['is_verlofdag'].sum()


# Tabs: Classificatie | Uitleg
tab_classificatie, tab_uitleg, tab_methode = st.tabs(["Ritclassificatie", "Uitleg & aannames", "Methode"])


# =====================================================================
# CLASSIFICATIELOGICA
# =====================================================================

# Wassink vestigingen (bron: https://wassink.nl/contact/)
WASSINK_VESTIGINGEN = [
    {'naam': 'Winterswijk', 'adres': 'Snelliusstraat 11', 'postcode': '7102 ED',
     'lat': 51.9710, 'lon': 6.7185, 'zoektermen': ['snelliusstraat', 'winterswijk']},
    {'naam': 'Doetinchem', 'adres': 'Fabrieksstraat 39-07', 'postcode': '7005 AP',
     'lat': 51.9650, 'lon': 6.2890, 'zoektermen': ['fabrieksstraat', 'doetinchem']},
]

# Werktijden per functie
WERKTIJDEN = {
    'Projectmonteur': {'start': 7, 'eind': 15.75, 'controle_ochtend': (5.75, 7.5), 'controle_middag': (15.25, 17)},
    'Servicemonteur': {'start': 8, 'eind': 17, 'controle_ochtend': (7.5, 8.5), 'controle_middag': (16.5, 17.5)},
}
DEFAULT_WERKTIJD = {'start': 8, 'eind': 16.5, 'controle_ochtend': (7, 8.5), 'controle_middag': (16, 17)}


def _is_wassink_vestiging(locatie: str) -> bool:
    """Check of een locatie overeenkomt met een Wassink-vestiging (adres-matching)."""
    loc_lower = locatie.lower()
    for vestiging in WASSINK_VESTIGINGEN:
        if any(term in loc_lower for term in vestiging['zoektermen']):
            return True
    return False


def locatie_type(locatie: str, bestuurder: str = '') -> str:
    """Bepaal het type locatie op basis van C-Track labels + Wassink vestigingen."""
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
    if loc.startswith('Vestiging') or _is_wassink_vestiging(loc):
        return 'Vestiging'
    if loc.startswith('Project'):
        return 'Project'
    if loc.startswith('Opdrachtgever'):
        return 'Opdrachtgever'
    return 'Overig'


def classificeer_rit(row: pd.Series) -> str:
    """Classificeer een rit: Woon-werk (OB), Prive (LB), Zakelijk, of Te beoordelen.

    LB km = prive (doel <500/jaar)
    OB km = woon-werk
    """
    start_type = row['start_type']
    eind_type = row['eind_type']
    uur = row['start'].hour + row['start'].minute / 60.0
    weekdag = row['start'].dayofweek  # 0=ma, 6=zo

    werk_types = {'Vestiging', 'Project', 'Opdrachtgever'}

    # Verlofdag = alle ritten zijn prive (Syntess: ziek, snipper, ADV, etc.)
    if row.get('is_verlofdag', False):
        return 'Prive'

    # Thuis collega = altijd zakelijk (ophalen/afzetten)
    if start_type == 'Thuis collega' or eind_type == 'Thuis collega':
        return 'Zakelijk'

    # Eigen Thuis -> eigen Thuis (parkeren, korte rit)
    if start_type == 'Thuis' and eind_type == 'Thuis':
        return 'Prive'

    # Weekend: alle ritten zonder werklocatie = prive
    if weekdag >= 5:
        if start_type not in werk_types and eind_type not in werk_types:
            return 'Prive'

    # Eigen Thuis <-> werklocatie = woon-werk (OB)
    if start_type == 'Thuis' and eind_type in werk_types:
        return 'Woon-werk'
    if eind_type == 'Thuis' and start_type in werk_types:
        return 'Woon-werk'

    # Tussen werklocaties = zakelijk
    if start_type in werk_types and eind_type in werk_types:
        return 'Zakelijk'

    # Werklocatie <-> Overig = zakelijk (serviceadres)
    if start_type in werk_types and eind_type == 'Overig':
        return 'Zakelijk'
    if eind_type in werk_types and start_type == 'Overig':
        return 'Zakelijk'

    # Buiten werktijd (16:30-08:00) zonder werklocatie = prive
    if weekdag < 5 and (uur >= 16.5 or uur < 8):
        if start_type not in werk_types and eind_type not in werk_types:
            return 'Prive'

    # Overig <-> Overig doordeweeks tijdens werktijd = zakelijk
    if weekdag < 5 and 8 <= uur < 16.5:
        if start_type == 'Overig' and eind_type == 'Overig':
            return 'Zakelijk'

    # Eigen Thuis <-> Overig doordeweeks tijdens werktijd = woon-werk
    if weekdag < 5 and uur < 16.5:
        if start_type == 'Thuis' and eind_type == 'Overig':
            return 'Woon-werk'
        if eind_type == 'Thuis' and start_type == 'Overig':
            return 'Woon-werk'

    return 'Te beoordelen'


def bepaal_route_type(row: pd.Series) -> str:
    """Bepaal of rit rechtstreeks naar huis is, via vestiging, of overig."""
    start_type = row['start_type']
    eind_type = row['eind_type']

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


def controle_flag(row: pd.Series) -> str:
    """Flag ritten die extra controle vereisen op basis van Wassink-regels.

    Controlevensters per functie:
    - Projectmonteur: 05:45-07:30 en 15:15-17:00
    - Servicemonteur: 07:30-08:30 en 16:30-17:30
    """
    uur = row['start'].hour + row['start'].minute / 60.0
    weekdag = row['start'].dayofweek

    # Verlofdag = altijd controle
    if row.get('is_verlofdag', False):
        verlof = row.get('verlof_type', 'Verlof')
        return f'Verlofdag ({verlof})'

    # Weekend = altijd controle
    if weekdag >= 5:
        return 'Weekend'

    # Gebruik functie_categorie (Projectmonteur/Servicemonteur) voor controlevensters
    categorie = row.get('functie_categorie', '')
    wt = WERKTIJDEN.get(categorie, DEFAULT_WERKTIJD)

    ochtend = wt['controle_ochtend']
    middag = wt['controle_middag']

    if ochtend[0] <= uur < ochtend[1]:
        return f'Controlevenster ochtend ({categorie or "onbekend"})'
    if middag[0] <= uur < middag[1]:
        return f'Controlevenster middag ({categorie or "onbekend"})'

    # Buiten werktijd helemaal
    if uur < ochtend[0] or uur >= middag[1]:
        return 'Buiten werktijd'

    return ''


def detecteer_tussenstops(df: pd.DataFrame) -> list:
    """Detecteer prive-tussenstops in dagelijkse ritketens.

    Een tussenstop is wanneer een bestuurder op weg van/naar werk stopt bij
    een niet-werkgerelateerde locatie ('Overig'). De omweg-rit wordt Prive.

    Patronen:
    - Ochtend: Thuis → [Overig] → Werklocatie  →  Thuis→Overig = Prive
    - Avond:   Werklocatie → [Overig] → Thuis  →  Werk→Overig = Prive

    Returns: lijst van (index, flag_tekst) tuples
    """
    werk_types = {'Vestiging', 'Project', 'Opdrachtgever'}
    results = []

    for (_bestuurder, _datum), dag in df.groupby(['bestuurder', 'datum']):
        dag_sorted = dag.sort_values('start')
        idxs = dag_sorted.index.tolist()

        for i in range(len(idxs) - 1):
            curr = df.loc[idxs[i]]
            nxt = df.loc[idxs[i + 1]]

            # Ochtend: Thuis → Overig, gevolgd door rit naar Werklocatie
            if (curr['start_type'] == 'Thuis'
                    and curr['eind_type'] == 'Overig'
                    and nxt['eind_type'] in werk_types):
                results.append((idxs[i], 'Prive-tussenstop (ochtend)'))

            # Avond: Werklocatie → Overig, gevolgd door rit naar Thuis
            if (curr['start_type'] in werk_types
                    and curr['eind_type'] == 'Overig'
                    and nxt['eind_type'] == 'Thuis'):
                results.append((idxs[i], 'Prive-tussenstop (avond)'))

    return results


# Bouw lookup: bestuurder → thuisadres (straat uit Syntess)
_thuis_lookup = {}
if 'straat' in trips.columns:
    for _, row in medewerker_map.iterrows():
        straat = str(row.get('straat', '')).lower().strip()
        if straat:
            _thuis_lookup[row['bestuurder']] = straat


def _locatie_is_thuisadres(locatie: str, bestuurder: str) -> bool:
    """Check of locatie het Syntess-thuisadres van de bestuurder bevat."""
    if bestuurder not in _thuis_lookup:
        return False
    return _thuis_lookup[bestuurder] in locatie.lower()


# Classificatie toepassen
trips['start_type'] = trips.apply(
    lambda r: locatie_type(r['startlocation'], r['bestuurder']), axis=1
)
trips['eind_type'] = trips.apply(
    lambda r: locatie_type(r['endlocation'], r['bestuurder']), axis=1
)

# Extra thuisadres-herkenning op basis van Syntess-adresgegevens
# Als C-Track een locatie als 'Overig' labelt maar het straatnaam matcht → Thuis
for col, loc_col in [('start_type', 'startlocation'), ('eind_type', 'endlocation')]:
    mask_overig = trips[col] == 'Overig'
    mask_thuis = trips.apply(
        lambda r: _locatie_is_thuisadres(str(r[loc_col]), r['bestuurder'])
        if pd.notna(r[loc_col]) else False, axis=1
    )
    trips.loc[mask_overig & mask_thuis, col] = 'Thuis'

# Aanname: eerste rit van de dag per bestuurder = vertrek vanuit huis
# Als C-Track het startpunt niet als "Thuis" herkent maar het IS de eerste rit,
# behandelen we het als thuisvertrek.
trips = trips.sort_values(['bestuurder', 'start'])
trips['_eerste_rit'] = ~trips.duplicated(subset=['bestuurder', 'datum'], keep='first')
mask_eerste = (trips['_eerste_rit']) & (trips['start_type'] == 'Overig')
trips.loc[mask_eerste, 'start_type'] = 'Thuis'

# Idem: laatste rit van de dag die eindigt op 'Overig' = aankomst thuis
trips['_laatste_rit'] = ~trips.duplicated(subset=['bestuurder', 'datum'], keep='last')
mask_laatste = (trips['_laatste_rit']) & (trips['eind_type'] == 'Overig')
trips.loc[mask_laatste, 'eind_type'] = 'Thuis'

trips = trips.drop(columns=['_eerste_rit', '_laatste_rit'])

trips['classificatie'] = trips.apply(classificeer_rit, axis=1)
trips['route_type'] = trips.apply(bepaal_route_type, axis=1)
trips['controle'] = trips.apply(controle_flag, axis=1)

# Tussenstop-detectie: overschrijft classificatie naar Prive waar nodig
_tussenstops = detecteer_tussenstops(trips)
_tussenstop_count = len(_tussenstops)
for _ts_idx, _ts_flag in _tussenstops:
    trips.loc[_ts_idx, 'classificatie'] = 'Prive'
    trips.loc[_ts_idx, 'route_type'] = 'Tussenstop'
    # Controle-flag: combineer met bestaande flag als die er al is
    bestaand = trips.loc[_ts_idx, 'controle']
    trips.loc[_ts_idx, 'controle'] = _ts_flag if not bestaand else f'{bestaand} + {_ts_flag}'

# LB/OB km berekenen (na tussenstop-correctie)
trips['lb_km'] = trips.apply(
    lambda r: r['afstand_km'] if r['classificatie'] == 'Prive' else 0, axis=1
)
trips['ob_km'] = trips.apply(
    lambda r: r['afstand_km'] if r['classificatie'] == 'Woon-werk' else 0, axis=1
)


with tab_classificatie:

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
    # KPI'S + 500 KM GRENS
    # =====================================================================

    st.markdown("---")
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.metric("Totaal ritten", f"{len(data):,}")
    with k2:
        st.metric("Totaal km", f"{data['afstand_km'].sum():,.0f}")
    with k3:
        prive_km = data['lb_km'].sum()
        st.metric("LB km (prive)", f"{prive_km:,.0f}")
    with k4:
        st.metric("OB km (woon-werk)", f"{data['ob_km'].sum():,.0f}")
    with k5:
        te_beoordelen = len(data[data['classificatie'] == 'Te beoordelen'])
        st.metric("Te beoordelen", f"{te_beoordelen}")


    # =====================================================================
    # PRIVE KM OVERZICHT PER BESTUURDER (500 km grens)
    # =====================================================================

    st.markdown("---")
    st.subheader("Prive km per bestuurder (500 km grens)")

    prive_per_bestuurder = trips.groupby('bestuurder').agg(
        personeelsnr=('personeelsnummer', 'first'),
        functie=('functie', 'first'),
        prive_km=('lb_km', 'sum'),
        woonwerk_km=('ob_km', 'sum'),
        totaal_km=('afstand_km', 'sum'),
        ritten=('afstand_km', 'count'),
    ).reset_index()

    # Bereken percentage van 500 km grens
    prive_per_bestuurder['prive_km'] = prive_per_bestuurder['prive_km'].round(1)
    prive_per_bestuurder['woonwerk_km'] = prive_per_bestuurder['woonwerk_km'].round(1)
    prive_per_bestuurder['totaal_km'] = prive_per_bestuurder['totaal_km'].round(0)
    prive_per_bestuurder['% van 500 km'] = (prive_per_bestuurder['prive_km'] / 500 * 100).round(0)

    # Bepaal aantal maanden in dataset voor maandgemiddelde
    datum_range = trips['datum']
    if len(datum_range) > 0:
        import datetime
        min_d = min(datum_range)
        max_d = max(datum_range)
        dagen = (max_d - min_d).days + 1
        maanden = max(dagen / 30.44, 1)
        prive_per_bestuurder['gem/maand'] = (prive_per_bestuurder['prive_km'] / maanden).round(1)
        prive_per_bestuurder['prognose jaar'] = (prive_per_bestuurder['gem/maand'] * 12).round(0)

    prive_per_bestuurder = prive_per_bestuurder.sort_values('prive_km', ascending=False)

    def highlight_prive(row):
        """Markeer rijen waar prive km te hoog is."""
        prognose = row.get('prognose jaar', 0)
        if prognose > 500:
            return ['background-color: #ffcccc'] * len(row)
        elif prognose > 400:
            return ['background-color: #fff3cd'] * len(row)
        return [''] * len(row)

    display_prive = prive_per_bestuurder.rename(columns={
        'bestuurder': 'Bestuurder',
        'personeelsnr': 'Pers.nr',
        'functie': 'Functie',
        'prive_km': 'Prive km (LB)',
        'woonwerk_km': 'Woon-werk km (OB)',
        'totaal_km': 'Totaal km',
        'ritten': 'Ritten',
        '% van 500 km': '% van 500',
        'gem/maand': 'Gem/maand',
        'prognose jaar': 'Prognose jaar',
    })

    st.dataframe(
        display_prive.style.apply(highlight_prive, axis=1),
        use_container_width=True,
        hide_index=True,
    )
    st.caption("Rood = jaarprognose > 500 km prive. Geel = > 400 km. Grens Belastingdienst: max 500 km prive/jaar (~41 km/maand).")


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
        st.bar_chart(class_counts.set_index('classificatie')['ritten'], horizontal=True)

    with col_table:
        st.subheader("Samenvatting")
        summary = class_counts.rename(columns={
            'classificatie': 'Type', 'ritten': 'Ritten', 'km': 'Kilometers',
        })
        st.dataframe(summary, use_container_width=True, hide_index=True)


    # =====================================================================
    # CONTROLE-OVERZICHT (geflagde ritten)
    # =====================================================================

    st.markdown("---")
    st.subheader("Controle-ritten (buiten werktijd / weekend / verlofdag)")

    controle_ritten = data[data['controle'] != ''].copy()
    if not controle_ritten.empty:
        controle_summary = controle_ritten.groupby('controle').agg(
            ritten=('afstand_km', 'count'),
            km=('afstand_km', 'sum'),
        ).reset_index().sort_values('ritten', ascending=False)
        controle_summary['km'] = controle_summary['km'].round(1)
        st.dataframe(
            controle_summary.rename(columns={
                'controle': 'Controle type', 'ritten': 'Ritten', 'km': 'Kilometers',
            }),
            use_container_width=True,
            hide_index=True,
        )

        with st.expander(f"Alle controle-ritten ({len(controle_ritten)})", expanded=False):
            ctrl_display = controle_ritten[[
                'bestuurder', 'personeelsnummer', 'functie', 'datum',
                'start', 'eind', 'startlocation', 'endlocation',
                'afstand_km', 'classificatie', 'controle',
            ]].copy()
            ctrl_display['start'] = ctrl_display['start'].dt.strftime('%H:%M')
            ctrl_display['eind'] = ctrl_display['eind'].dt.strftime('%H:%M')
            ctrl_display['afstand_km'] = ctrl_display['afstand_km'].round(1)
            ctrl_display['startlocation'] = ctrl_display['startlocation'].str.split(';').str[0]
            ctrl_display['endlocation'] = ctrl_display['endlocation'].str.split(';').str[0]
            st.dataframe(
                ctrl_display.rename(columns={
                    'bestuurder': 'Bestuurder', 'personeelsnummer': 'Pers.nr',
                    'functie': 'Functie', 'datum': 'Datum',
                    'start': 'Start', 'eind': 'Eind',
                    'startlocation': 'Van', 'endlocation': 'Naar',
                    'afstand_km': 'Km', 'classificatie': 'Type', 'controle': 'Controle',
                }).sort_values(['Datum', 'Bestuurder', 'Start']),
                use_container_width=True,
                hide_index=True,
                height=400,
            )
    else:
        st.info("Geen ritten gevonden die extra controle vereisen.")


    # =====================================================================
    # DAGOVERZICHT PER BESTUURDER
    # =====================================================================

    st.markdown("---")
    st.subheader("Dagoverzicht per bestuurder")

    if sel_bestuurder != "Alle":
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
                'datum': 'Datum', 'ritten': 'Ritten',
                'totaal_km': 'Totaal km', 'lb_km': 'LB km', 'ob_km': 'OB km',
                'eerste_start': 'Start', 'laatste_eind': 'Eind',
                'eerste_locatie': 'Vertrek', 'laatste_locatie': 'Aankomst',
            }),
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("Volledige rittenreeks (route-continuiteit)", expanded=False):
            if sel_class != "Alle":
                st.caption(f"Alle ritten getoond voor route-continuiteit. Ritten buiten filter '{sel_class}' zijn grijs.")
            for datum, dag_trips in dag_data.groupby('datum'):
                dag_sorted = dag_trips.sort_values('start')
                st.markdown(f"**{datum}** ({len(dag_sorted)} ritten)")
                rows = []
                for _, r in dag_sorted.iterrows():
                    sp = str(r['startlocation']).split(';')[0].strip()
                    ep = str(r['endlocation']).split(';')[0].strip()
                    rows.append({
                        'Tijd': f"{r['start'].strftime('%H:%M')}-{r['eind'].strftime('%H:%M')}",
                        'Startpunt': sp, 'Eindpunt': ep,
                        'Km': round(r['afstand_km'], 1),
                        'Type': r['classificatie'], 'Route': r['route_type'],
                        'Controle': r['controle'],
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
                'bestuurder': 'Bestuurder', 'ritten': 'Ritten',
                'totaal_km': 'Totaal km', 'lb_km': 'LB km (prive)', 'ob_km': 'OB km (woon-werk)',
            }),
            use_container_width=True,
            hide_index=True,
        )


    # =====================================================================
    # GEDETAILLEERDE RITTENTABEL
    # =====================================================================

    st.markdown("---")
    st.subheader("Ritten detail")

    detail = data[[
        'bestuurder', 'personeelsnummer', 'functie', 'datum', 'start', 'eind',
        'startlocation', 'endlocation', 'afstand_km',
        'start_type', 'eind_type', 'classificatie', 'route_type', 'controle',
        'lb_km', 'ob_km', 'kenteken',
    ]].copy()

    detail['start_tijd'] = detail['start'].dt.strftime('%H:%M')
    detail['eind_tijd'] = detail['eind'].dt.strftime('%H:%M')
    detail['afstand_km'] = detail['afstand_km'].round(1)
    detail['lb_km'] = detail['lb_km'].round(1)
    detail['ob_km'] = detail['ob_km'].round(1)
    detail['startpunt'] = detail['startlocation'].str.split(';').str[0]
    detail['eindpunt'] = detail['endlocation'].str.split(';').str[0]

    display_cols = {
        'personeelsnummer': 'Pers.nr',
        'bestuurder': 'Bestuurder',
        'functie': 'Functie',
        'datum': 'Datum',
        'start_tijd': 'Start',
        'eind_tijd': 'Eind',
        'startpunt': 'Startpunt',
        'eindpunt': 'Eindpunt',
        'afstand_km': 'Km',
        'classificatie': 'Classificatie',
        'route_type': 'Route',
        'controle': 'Controle',
        'lb_km': 'LB km',
        'ob_km': 'OB km',
    }

    st.dataframe(
        detail[list(display_cols.keys())].rename(columns=display_cols).sort_values(
            ['Datum', 'Bestuurder', 'Start']
        ),
        use_container_width=True,
        hide_index=True,
        height=500,
    )


    # =====================================================================
    # EXCEL EXPORT (Belastingdienst format)
    # =====================================================================

    st.markdown("---")
    st.subheader("Excel export (Belastingdienst format)")

    st.markdown("Export conform `wassink sheet.xlsx`. Personeelsnummer wordt gevuld vanuit Syntess/CSV mapping.")

    # Bouw export dataframe
    export = data[[
        'bestuurder', 'personeelsnummer', 'start', 'eind',
        'startlocation', 'endlocation', 'afstand_km',
        'classificatie', 'route_type', 'lb_km', 'ob_km',
    ]].copy()

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

    # Kolomvolgorde conform wassink sheet.xlsx
    excel_df = export[[
        'personeelsnummer', 'bestuurder', 'starttijd', 'eindtijd',
        'startlocation', 'endlocation', 'afstand_km',
        'rechtstreeks_nr_huis', 'via_vestiging', 'tussenstop_prive',
        'lb_km', 'ob_km',
    ]].copy()

    excel_df.columns = [
        'Personeelsnummer', 'Naam medewerker', 'Starttijd', 'Eindtijd',
        'Startpunt', 'Eindpunt', 'Aantal km',
        'Rechtstreeks nr huis', 'Via vestiging', 'Tussenstop overig (prive)',
        'LB KM', 'OB km',
    ]
    excel_df = excel_df.sort_values(['Naam medewerker', 'Starttijd'])

    # Excel met meerdere sheets
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        excel_df.to_excel(writer, sheet_name='Ritclassificatie', index=False)

        # Controles sheet: geflagde ritten
        controle_export = data[data['controle'] != ''][[
            'personeelsnummer', 'bestuurder', 'functie', 'datum',
            'start', 'eind', 'startlocation', 'endlocation',
            'afstand_km', 'classificatie', 'controle',
        ]].copy()
        controle_export['start'] = controle_export['start'].dt.strftime('%Y-%m-%d %H:%M')
        controle_export['eind'] = controle_export['eind'].dt.strftime('%Y-%m-%d %H:%M')
        controle_export['startlocation'] = controle_export['startlocation'].str.split(';').str[0]
        controle_export['endlocation'] = controle_export['endlocation'].str.split(';').str[0]
        controle_export.columns = [
            'Personeelsnummer', 'Naam medewerker', 'Functie', 'Datum',
            'Starttijd', 'Eindtijd', 'Startpunt', 'Eindpunt',
            'Aantal km', 'Classificatie', 'Controle',
        ]
        controle_export.to_excel(writer, sheet_name='Controles', index=False)

        # Samenvatting: prive km per bestuurder per maand
        trips_met_maand = trips.copy()
        trips_met_maand['maand'] = trips_met_maand['start'].dt.to_period('M').astype(str)
        prive_maand = trips_met_maand.groupby(['bestuurder', 'personeelsnummer', 'maand']).agg(
            prive_km=('lb_km', 'sum'),
            woonwerk_km=('ob_km', 'sum'),
            totaal_km=('afstand_km', 'sum'),
        ).reset_index()
        prive_maand['prive_km'] = prive_maand['prive_km'].round(1)
        prive_maand['woonwerk_km'] = prive_maand['woonwerk_km'].round(1)
        prive_maand['totaal_km'] = prive_maand['totaal_km'].round(0)
        prive_maand.columns = [
            'Naam medewerker', 'Personeelsnummer', 'Maand',
            'Prive km (LB)', 'Woon-werk km (OB)', 'Totaal km',
        ]
        prive_maand.to_excel(writer, sheet_name='Samenvatting per maand', index=False)

        # Controleregels referentie
        regels_sheet = pd.DataFrame({
            'Controle': [
                'Prive na werktijd',
                'Projectmonteurs controlevenster',
                'Servicemonteurs controlevenster',
                'Weekend',
                '500 km grens',
            ],
            'Omschrijving': [
                'Ritten van huis naar adres en terug na 16:30 doordeweeks',
                'Werktijd 7:00-15:45. Controle ritten 05:45-07:30 en 15:15-17:00',
                'Werktijd 8:00-17:00. Controle ritten 07:30-08:30 en 16:30-17:30',
                'Alle ritten op zaterdag en zondag',
                'Max 500 prive km per kalenderjaar (~41 km/maand)',
            ],
            'Bron': [
                'Email Wassink 11 mrt 2026',
                'Excel wassink sheet.xlsx',
                'Excel wassink sheet.xlsx',
                'Email Wassink 11 mrt 2026',
                'Brief regels verklaring privegebruik',
            ],
        })
        regels_sheet.to_excel(writer, sheet_name='Controleregels', index=False)

    buffer.seek(0)

    st.download_button(
        label="Download Excel (Belastingdienst format)",
        data=buffer,
        file_name="ritclassificatie_wassink.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    with st.expander("Preview export (eerste 20 rijen)"):
        st.dataframe(excel_df.head(20), use_container_width=True, hide_index=True)


# =====================================================================
# TAB: UITLEG & AANNAMES
# =====================================================================

with tab_uitleg:

    # --- WERKING ---
    st.header("Werking")

    st.markdown("""
    **Dataflow:**
    1. Ritgegevens worden opgehaald uit de **C-Track DWH** (PostgreSQL) — tabel `stg.stg_vehicle_trips_detailed`
    2. Medewerkergegevens (personeelsnummer, functie, thuisadres) komen uit de **Syntess DWH** (Azure SQL) — tabel `stam.Medewerkers`
    3. Verlof- en ziektedagen komen uit Syntess — tabel `uren.Geboekte Uren` (gefilterd op verlof-taakcodes)
    4. De koppeling bestuurder ↔ medewerker loopt via fuzzy matching op achternaam + voornaam

    **Locatieherkenning (3 lagen):**
    1. **C-Track labels** — locaties met prefix `Thuis`, `Vestiging`, `Project`, `Opdrachtgever`
    2. **Syntess thuisadres** — als C-Track een locatie als 'Overig' labelt maar het straatnaam (uit Syntess) matcht → `Thuis`
    3. **Eerste/laatste rit** — de eerste rit van de dag per bestuurder wordt als vertrek vanuit huis behandeld; de laatste rit als aankomst thuis

    **Verlofdag-integratie:**
    - Verlof- en ziektedagen worden opgehaald uit Syntess op basis van taakcodes (snipper, ADV, ziek, etc.)
    - Alle ritten op een verlofdag worden automatisch als **Prive** geclassificeerd
    - Deze ritten krijgen een controle-flag met het verloftype
    """)

    # --- KADERS WASSINK ---
    st.header("Kaders Wassink")

    st.markdown("""
    **Bron:** Email Wassink 11 maart 2026 + Excel `wassink sheet.xlsx`

    **Werktijden per functie:**
    | Functie | Werktijd | Controlevenster ochtend | Controlevenster middag |
    |---------|----------|------------------------|----------------------|
    | Projectmonteur | 07:00 - 15:45 | 05:45 - 07:30 | 15:15 - 17:00 |
    | Servicemonteur | 08:00 - 17:00 | 07:30 - 08:30 | 16:30 - 17:30 |

    **Regels:**
    - Vertrek ochtend is altijd vanaf huis
    - LB km = prive-kilometers (doel: < 500 km/jaar, ~41 km/maand)
    - OB km = woon-werk kilometers
    - Weekenden: alle ritten zonder werklocatie zijn prive
    - Prive-tussenstop maakt de volledige rit prive (brief regels)
    - Controle buiten werktijd: 16:30 - 08:00

    **Wassink vestigingen:**
    - Winterswijk — Snelliusstraat 11, 7102 ED
    - Doetinchem — Fabrieksstraat 39-07, 7005 AP
    """)

    # --- LIJSTWERK ---
    st.header("Lijstwerk")

    st.subheader("Classificatieregels")
    st.dataframe(pd.DataFrame({
        'Prioriteit': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        'Regel': [
            'Verlofdag → Prive',
            'Thuis collega → Zakelijk',
            'Thuis → Thuis → Prive',
            'Weekend zonder werklocatie → Prive',
            'Thuis ↔ Werklocatie → Woon-werk',
            'Werklocatie ↔ Werklocatie → Zakelijk',
            'Werklocatie ↔ Overig → Zakelijk',
            'Buiten werktijd zonder werklocatie → Prive',
            'Overig ↔ Overig doordeweeks → Zakelijk',
            'Thuis ↔ Overig doordeweeks → Woon-werk',
        ],
        'Toelichting': [
            'Syntess verlof/ziekte → alle ritten prive',
            'Ophalen/afzetten collega = dienst',
            'Korte rit rondom huis = prive',
            'Za/zo zonder project/vestiging = prive',
            'Thuis naar vestiging/project/opdrachtgever',
            'Vestiging ↔ project, project ↔ project',
            'Serviceadres, klantbezoek',
            'Na 16:30 of voor 08:00 zonder werklocatie',
            'Onbekend adres tijdens werktijd = zakelijk',
            'Naar serviceadres vanuit huis',
        ],
    }), use_container_width=True, hide_index=True)

    st.subheader("Verlof-taakcodes (Syntess)")
    verlof_codes = pd.DataFrame({
        'Code': list(VERLOF_TAAK_CODES.keys()),
        'Omschrijving': list(VERLOF_TAAK_CODES.values()),
    })
    st.dataframe(verlof_codes, use_container_width=True, hide_index=True)

    st.subheader("Aannames")
    st.markdown("""
    1. De eerste rit van de dag per bestuurder is altijd vertrek vanuit huis
    2. De laatste rit van de dag eindigt altijd thuis
    3. Locaties die niet door C-Track als 'Thuis' worden herkend maar wel matchen op Syntess-thuisadres worden als 'Thuis' behandeld
    4. Monteur / Elektromonteur / Hulpmonteur worden behandeld als **Projectmonteur** (werktijd 07:00-15:45)
    5. Bestuurders zonder functie-koppeling krijgen het standaard controlevenster (08:00-16:30)
    6. Prive-km teller loopt per kalenderjaar (reset 1 januari)
    7. Fuzzy matching op achternaam: als dezelfde achternaam in C-Track en Syntess voorkomt, worden ze gekoppeld
    """)

    st.subheader("Databronnen")
    st.dataframe(pd.DataFrame({
        'Bron': ['C-Track DWH', 'C-Track DWH', 'Syntess DWH', 'Syntess DWH'],
        'Tabel': [
            'stg.stg_vehicle_trips_detailed',
            'stg.stg_ctrack_vehicles',
            'stam.Medewerkers',
            'uren.Geboekte Uren',
        ],
        'Gegevens': [
            'Ritten (start, eind, locatie, km, bestuurder)',
            'Voertuigen (kenteken, nodeid)',
            'Medewerkers (personeelsnummer, naam, functie, adres)',
            'Verlof- en ziektedagen (taakcodes, datum)',
        ],
        'Frequentie': ['Dagelijks', 'Dagelijks', 'Dagelijks', 'Dagelijks'],
    }), use_container_width=True, hide_index=True)


# =====================================================================
# TAB: METHODE
# =====================================================================

with tab_methode:

    st.header("Methode: classificatie en tussenstop-detectie")

    st.subheader("1. Classificatie per rit (stap 1)")

    st.markdown("""
    Elke rit wordt **individueel** geclassificeerd op basis van startlocatie, eindlocatie, tijdstip en weekdag.
    De regels worden in vaste prioriteitsvolgorde doorlopen — de eerste match wint.

    **Locatietypen** (bepaald door C-Track labels + Syntess adres):
    - **Thuis** — C-Track label `Thuis <naam>` met achternaam-match, of Syntess straatnaam-match, of eerste/laatste rit van de dag
    - **Thuis collega** — C-Track label `Thuis <naam>` waar de naam NIET matcht met de bestuurder
    - **Vestiging** — C-Track label `Vestiging` of adres-match op Wassink-vestigingen (Snelliusstraat, Fabrieksstraat)
    - **Project / Opdrachtgever** — C-Track labels
    - **Overig** — alles wat niet in bovenstaande valt (serviceadressen, winkels, tankstations, etc.)

    **Classificatie-uitkomsten:**
    | Uitkomst | Betekenis | Belastingdienst |
    |----------|-----------|-----------------|
    | Woon-werk | Huis ↔ werklocatie | OB km |
    | Prive | Privégebruik | LB km (max 500/jaar) |
    | Zakelijk | Dienstritten tussen werklocaties | Niet belast |
    | Te beoordelen | Geen regel matcht — handmatige beoordeling nodig | — |
    """)

    st.subheader("2. Tussenstop-detectie (stap 2)")

    st.markdown(f"""
    Na de individuele classificatie wordt een **tweede pass** gedaan op dagketen-niveau.
    Hierbij wordt per bestuurder per dag de volledige rittenreeks in chronologische volgorde geanalyseerd.

    **Regel uit brief Wassink:** *"Een prive-tussenstop maakt de volledige rit prive."*

    **Detectiemethode:**
    Voor elke twee opeenvolgende ritten (A → B) op dezelfde dag:

    **Ochtendpatroon:**
    ```
    Rit A: Thuis → [Overig]     (bijv. supermarkt, school, tankstation)
    Rit B: [Overig] → Werklocatie
    → Rit A wordt herclassificeerd als Prive (de omweg)
    → Rit B blijft Woon-werk (het daadwerkelijke woon-werktraject)
    ```

    **Avondpatroon:**
    ```
    Rit A: Werklocatie → [Overig]  (bijv. boodschappen na werk)
    Rit B: [Overig] → Thuis
    → Rit A wordt herclassificeerd als Prive (de omweg)
    → Rit B blijft Woon-werk
    ```

    **Resultaat in deze dataset:** {_tussenstop_count} tussenstops gedetecteerd.
    """)

    st.subheader("3. Controlevensters (stap 3)")

    st.markdown("""
    Ritten in de controlevensters krijgen een **controle-flag** voor handmatige beoordeling.
    De controlevensters zijn de overgangsperiodes tussen werktijd en vrije tijd.

    **Logica:**
    1. **Verlofdag** → altijd geflagd (met verloftype uit Syntess)
    2. **Weekend** (za/zo) → altijd geflagd
    3. **Controlevenster ochtend/middag** → per functiecategorie (zie werktijden)
    4. **Buiten werktijd** → voor de ochtendvenster of na het middagvenster

    Ritten die niet in een controlevenster vallen krijgen geen flag en worden niet apart gecontroleerd.
    """)

    st.subheader("4. Aannames en beperkingen")

    st.markdown("""
    **Aannames:**
    - De eerste rit van de dag is vertrek vanuit huis (ook als C-Track het startpunt niet als 'Thuis' herkent)
    - De laatste rit van de dag eindigt thuis
    - Bestuurders zonder functie in Syntess krijgen het standaard controlevenster (08:00-16:30)
    - Monteur / Elektromonteur / Hulpmonteur = Projectmonteur (werktijd 07:00-15:45)

    **Beperkingen tussenstop-detectie:**
    - Alleen **enkelvoudige tussenstops** worden gedetecteerd (A→B paren). Meerdere tussenstops achter elkaar
      (Thuis → Overig₁ → Overig₂ → Werk) worden niet volledig herkend — alleen de eerste omweg-rit.
    - De detectie kijkt naar **locatietypen**, niet naar adressen. Een "Overig" locatie naast het werk
      (bijv. tankstation om de hoek) wordt ook als tussenstop gedetecteerd.
    - Ritten die C-Track als één doorlopende rit registreert (zonder stop) worden niet opgepikt —
      er moet een daadwerkelijke stop zijn (motor uit, nieuwe rit gestart).
    - Tussenstops op **verlof-** en **weekenddagen** worden niet apart gedetecteerd
      (die ritten zijn al volledig Prive).

    **Niet geïmplementeerd:**
    - Tussenstop-detectie op basis van route-afwijking (GPS-trace vs directe route)
    - Automatische detectie of een "Overig" adres een prive-adres of zakelijk adres is
    - Ketens van 3+ tussenstops in één commute
    """)

    st.subheader("5. LB/OB berekening")

    st.markdown("""
    Na alle classificatie-stappen (individueel + tussenstops):
    - **LB km** (loonbelasting) = som van km voor ritten met classificatie `Prive`
    - **OB km** (omzetbelasting) = som van km voor ritten met classificatie `Woon-werk`
    - **Zakelijke km** worden niet belast en niet meegerekend

    **500 km grens:** Per kalenderjaar mag een medewerker maximaal 500 km prive rijden.
    De jaarprognose wordt berekend als: `(prive_km / aantal_maanden_in_data) × 12`.
    Rood = prognose > 500 km, Geel = prognose > 400 km.
    """)
