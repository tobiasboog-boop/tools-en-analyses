import streamlit as st
import pandas as pd
import pydeck as pdk
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.database import load_trips
from src.auth import check_password

st.set_page_config(page_title="Kaart", page_icon="🗺️", layout="wide")
if not check_password():
    st.stop()
st.title("Kaartweergave")

try:
    trips = load_trips()
except Exception as e:
    st.error(f"Database fout: {e}")
    st.stop()

# --- Filters ---
col1, col2 = st.columns(2)
with col1:
    view_type = st.radio("Weergave", ["Bestemmingen", "Vertrekpunten", "Ritlijnen"], horizontal=True)
with col2:
    kentekens = sorted(trips['kenteken'].dropna().unique())
    selected = st.multiselect("Filter voertuig", kentekens, default=[])

data = trips.copy()
if selected:
    data = data[data['kenteken'].isin(selected)]

# Filter rows with valid coordinates
if view_type == "Bestemmingen":
    map_data = data[data['endlatitude'].notna() & data['endlongitude'].notna()].copy()
    map_data['lat'] = map_data['endlatitude']
    map_data['lon'] = map_data['endlongitude']
    map_data['locatie'] = map_data['endlocation']
elif view_type == "Vertrekpunten":
    map_data = data[data['startlatitude'].notna() & data['startlongitude'].notna()].copy()
    map_data['lat'] = map_data['startlatitude']
    map_data['lon'] = map_data['startlongitude']
    map_data['locatie'] = map_data['startlocation']
else:
    map_data = data[
        data['startlatitude'].notna() & data['endlatitude'].notna()
    ].copy()

# --- Location frequency ---
if view_type in ["Bestemmingen", "Vertrekpunten"]:
    # Aggregate locations (round to ~100m)
    map_data['lat_r'] = map_data['lat'].round(3)
    map_data['lon_r'] = map_data['lon'].round(3)

    agg = (
        map_data.groupby(['lat_r', 'lon_r'])
        .agg(
            bezoeken=('lat', 'count'),
            locatie=('locatie', 'first'),
            kentekens=('kenteken', lambda x: ', '.join(sorted(x.dropna().unique())[:3])),
        )
        .reset_index()
    )
    agg['radius'] = (agg['bezoeken'] ** 0.5) * 40 + 30

    layer = pdk.Layer(
        'ScatterplotLayer',
        data=agg,
        get_position=['lon_r', 'lat_r'],
        get_radius='radius',
        get_fill_color=[30, 58, 95, 160],
        pickable=True,
        auto_highlight=True,
    )

    tooltip = {
        "html": "<b>{locatie}</b><br>Bezoeken: {bezoeken}<br>Voertuigen: {kentekens}",
        "style": {"backgroundColor": "#1E3A5F", "color": "white"},
    }

    st.pydeck_chart(pdk.Deck(
        layers=[layer],
        initial_view_state=pdk.ViewState(
            latitude=agg['lat_r'].mean(),
            longitude=agg['lon_r'].mean(),
            zoom=10,
            pitch=0,
        ),
        tooltip=tooltip,
        map_style='mapbox://styles/mapbox/light-v10',
    ))

    # Top locations table
    st.markdown("---")
    label = "bestemmingen" if view_type == "Bestemmingen" else "vertrekpunten"
    st.subheader(f"Top 20 {label}")

    top_locs = agg.sort_values('bezoeken', ascending=False).head(20)
    st.dataframe(
        top_locs[['locatie', 'bezoeken', 'kentekens']].rename(columns={
            'locatie': 'Locatie', 'bezoeken': 'Bezoeken', 'kentekens': 'Voertuigen'
        }),
        use_container_width=True,
        hide_index=True,
    )

else:
    # Arc layer for trip lines
    arc_data = map_data[['startlatitude', 'startlongitude', 'endlatitude', 'endlongitude',
                          'kenteken', 'afstand_km']].copy()
    arc_data.columns = ['start_lat', 'start_lon', 'end_lat', 'end_lon', 'kenteken', 'km']

    layer = pdk.Layer(
        'ArcLayer',
        data=arc_data.head(500),  # Limit for performance
        get_source_position=['start_lon', 'start_lat'],
        get_target_position=['end_lon', 'end_lat'],
        get_source_color=[30, 58, 95, 120],
        get_target_color=[224, 122, 95, 120],
        get_width=2,
        pickable=True,
    )

    tooltip = {
        "html": "<b>{kenteken}</b><br>Afstand: {km:.1f} km",
        "style": {"backgroundColor": "#1E3A5F", "color": "white"},
    }

    center_lat = arc_data['start_lat'].mean()
    center_lon = arc_data['start_lon'].mean()

    st.pydeck_chart(pdk.Deck(
        layers=[layer],
        initial_view_state=pdk.ViewState(
            latitude=center_lat,
            longitude=center_lon,
            zoom=10,
            pitch=30,
        ),
        tooltip=tooltip,
        map_style='mapbox://styles/mapbox/light-v10',
    ))

    st.info("Weergave beperkt tot 500 ritten voor performance. Filter op voertuig voor meer detail.")
