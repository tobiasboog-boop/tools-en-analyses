import streamlit as st
import pandas as pd
import plotly.express as px
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.database import load_trips, load_vehicles
from src.auth import check_password

st.set_page_config(page_title="Vlootoverzicht", page_icon="🚛", layout="wide")
if not check_password():
    st.stop()
st.title("Vlootoverzicht")

try:
    trips = load_trips()
    vehicles = load_vehicles()
except Exception as e:
    st.error(f"Database fout: {e}")
    st.stop()

# Vehicle summary
vehicle_stats = (
    trips.groupby(['nodeid', 'kenteken'])
    .agg(
        ritten=('afstand_km', 'count'),
        totaal_km=('afstand_km', 'sum'),
        totaal_uren=('rijtijd_min', 'sum'),
        gem_afstand=('afstand_km', 'mean'),
        max_snelheid=('maxspeed', 'max'),
        eerste_rit=('datum', 'min'),
        laatste_rit=('datum', 'max'),
        bestuurders=('bestuurder', 'nunique'),
        overspeed_events=('overspeedcount', lambda x: x.fillna(0).astype(int).sum()),
        stationair_min=('stationair_min', 'sum'),
    )
    .reset_index()
)
vehicle_stats['totaal_uren'] = vehicle_stats['totaal_uren'] / 60
vehicle_stats['gem_snelheid_kmh'] = vehicle_stats.apply(
    lambda r: (r['totaal_km'] / r['totaal_uren']) if r['totaal_uren'] > 0 else 0, axis=1
)

# Latest odometer per vehicle
latest_odo = (
    trips.sort_values('start')
    .groupby('nodeid')['km_stand_eind']
    .last()
    .reset_index()
    .rename(columns={'km_stand_eind': 'kilometerstand'})
)
vehicle_stats = vehicle_stats.merge(latest_odo, on='nodeid', how='left')

# KPIs
col1, col2, col3 = st.columns(3)
col1.metric("Voertuigen in vloot", len(vehicles))
col2.metric("Actief in periode", vehicle_stats['kenteken'].nunique())
col3.metric("Totale vloot-km", f"{vehicle_stats['totaal_km'].sum():,.0f} km")

st.markdown("---")

# Sort options
sort_by = st.selectbox(
    "Sorteer op",
    ['totaal_km', 'ritten', 'totaal_uren', 'max_snelheid', 'kilometerstand', 'overspeed_events'],
    format_func=lambda x: {
        'totaal_km': 'Kilometers',
        'ritten': 'Aantal ritten',
        'totaal_uren': 'Rijuren',
        'max_snelheid': 'Max snelheid',
        'kilometerstand': 'Kilometerstand',
        'overspeed_events': 'Snelheidsovertredingen',
    }[x]
)

vehicle_stats_sorted = vehicle_stats.sort_values(sort_by, ascending=False)

# Display table
st.subheader("Voertuigstatistieken")

display = vehicle_stats_sorted[[
    'kenteken', 'ritten', 'totaal_km', 'totaal_uren', 'gem_afstand',
    'gem_snelheid_kmh', 'max_snelheid', 'kilometerstand',
    'bestuurders', 'overspeed_events', 'stationair_min',
    'eerste_rit', 'laatste_rit',
]].rename(columns={
    'kenteken': 'Kenteken',
    'ritten': 'Ritten',
    'totaal_km': 'Totaal km',
    'totaal_uren': 'Rijuren',
    'gem_afstand': 'Gem. km/rit',
    'gem_snelheid_kmh': 'Gem. km/u',
    'max_snelheid': 'Max km/u',
    'kilometerstand': 'Km-stand',
    'bestuurders': 'Bestuurders',
    'overspeed_events': 'Overspeed',
    'stationair_min': 'Stationair (min)',
    'eerste_rit': 'Eerste rit',
    'laatste_rit': 'Laatste rit',
})

for col in ['Totaal km', 'Rijuren', 'Gem. km/rit', 'Gem. km/u', 'Km-stand', 'Stationair (min)']:
    display[col] = display[col].round(1)

st.dataframe(display, use_container_width=True, hide_index=True)

# Chart: km per vehicle
st.markdown("---")
st.subheader("Kilometers per voertuig")

fig = px.bar(
    vehicle_stats_sorted.head(20).sort_values('totaal_km'),
    x='totaal_km', y='kenteken',
    orientation='h',
    color='totaal_uren',
    color_continuous_scale='Blues',
    labels={'totaal_km': 'Totaal km', 'kenteken': '', 'totaal_uren': 'Rijuren'},
)
fig.update_layout(height=500, margin=dict(t=10))
st.plotly_chart(fig, use_container_width=True)

# Vehicle detail expander
st.markdown("---")
st.subheader("Voertuig detail")

selected_vehicle = st.selectbox(
    "Selecteer voertuig",
    vehicle_stats_sorted['kenteken'].tolist(),
)

if selected_vehicle:
    vtrips = trips[trips['kenteken'] == selected_vehicle].sort_values('start', ascending=False)

    vc1, vc2, vc3, vc4 = st.columns(4)
    vc1.metric("Ritten", len(vtrips))
    vc2.metric("Totaal km", f"{vtrips['afstand_km'].sum():,.1f}")
    vc3.metric("Km-stand", f"{vtrips['km_stand_eind'].max():,.0f}")
    vc4.metric("Bestuurders", vtrips['bestuurder'].nunique())

    # Daily km for this vehicle
    vdaily = vtrips.groupby('datum')['afstand_km'].sum().reset_index()
    vdaily['datum'] = pd.to_datetime(vdaily['datum'])

    fig_v = px.bar(
        vdaily, x='datum', y='afstand_km',
        labels={'datum': 'Datum', 'afstand_km': 'Km'},
        color_discrete_sequence=['#1E3A5F'],
    )
    fig_v.update_layout(height=300, margin=dict(t=10))
    st.plotly_chart(fig_v, use_container_width=True)

    # Trips for this vehicle
    st.write(f"**Laatste 30 ritten van {selected_vehicle}:**")
    vdisp = vtrips.head(30)[['start', 'eind', 'bestuurder', 'afstand_km', 'rijtijd_min',
                              'startlocation', 'endlocation', 'maxspeed']].copy()
    vdisp.columns = ['Start', 'Eind', 'Bestuurder', 'Km', 'Min', 'Van', 'Naar', 'Max km/u']
    vdisp['Km'] = vdisp['Km'].round(1)
    vdisp['Min'] = vdisp['Min'].round(1)
    vdisp['Start'] = vdisp['Start'].dt.strftime('%d-%m %H:%M')
    vdisp['Eind'] = vdisp['Eind'].dt.strftime('%d-%m %H:%M')
    st.dataframe(vdisp, use_container_width=True, hide_index=True)
