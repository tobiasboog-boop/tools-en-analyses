import streamlit as st
import pandas as pd
import pydeck as pdk
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.database import load_trips
from src.auth import check_password

# OpenStreetMap tile layer (geen Mapbox token nodig)
MAP_STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"

st.set_page_config(page_title="Kaart", page_icon="🗺️", layout="wide")
if not check_password():
    st.stop()
st.title("Kaartweergave")

try:
    trips = load_trips()
except Exception as e:
    st.error(f"Data fout: {e}")
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

# --- Nederland view state (gecentreerd op Winterswijk/Achterhoek) ---
NL_VIEW = pdk.ViewState(
    latitude=52.05,
    longitude=6.55,
    zoom=9,
    pitch=0,
    min_zoom=6,
    max_zoom=16,
)

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

# --- Bestemmingen / Vertrekpunten ---
if view_type in ["Bestemmingen", "Vertrekpunten"]:
    # Aggregate locations (rond af op ~100m voor clustering)
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

    # Radius schaalt met aantal bezoeken
    max_visits = agg['bezoeken'].max()
    agg['radius'] = 50 + (agg['bezoeken'] / max(max_visits, 1)) * 400
    # Kleur intensiteit op basis van bezoeken
    agg['color_a'] = 80 + (agg['bezoeken'] / max(max_visits, 1) * 175).astype(int)

    layer = pdk.Layer(
        'ScatterplotLayer',
        data=agg,
        get_position=['lon_r', 'lat_r'],
        get_radius='radius',
        get_fill_color='[30, 58, 95, color_a]',
        pickable=True,
        auto_highlight=True,
        highlight_color=[224, 122, 95, 200],
    )

    tooltip = {
        "html": "<b>{locatie}</b><br/>Bezoeken: {bezoeken}<br/>Voertuigen: {kentekens}",
        "style": {
            "backgroundColor": "#1E3A5F",
            "color": "white",
            "fontSize": "13px",
            "padding": "8px 12px",
            "borderRadius": "6px",
        },
    }

    # Centreer op data als er gefilterd is
    if selected and len(agg) > 0:
        view = pdk.ViewState(
            latitude=agg['lat_r'].mean(),
            longitude=agg['lon_r'].mean(),
            zoom=11,
            pitch=0,
        )
    else:
        view = NL_VIEW

    st.pydeck_chart(pdk.Deck(
        layers=[layer],
        initial_view_state=view,
        tooltip=tooltip,
        map_style=MAP_STYLE,
    ), height=600)

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

# --- Ritlijnen ---
else:
    arc_data = map_data[['startlatitude', 'startlongitude', 'endlatitude', 'endlongitude',
                          'kenteken', 'afstand_km']].copy()
    arc_data.columns = ['start_lat', 'start_lon', 'end_lat', 'end_lon', 'kenteken', 'km']
    arc_data['km'] = arc_data['km'].round(1)

    # Limit voor performance
    display_data = arc_data.head(500)

    layer = pdk.Layer(
        'ArcLayer',
        data=display_data,
        get_source_position=['start_lon', 'start_lat'],
        get_target_position=['end_lon', 'end_lat'],
        get_source_color=[30, 58, 95, 140],
        get_target_color=[224, 122, 95, 140],
        get_width=2,
        pickable=True,
        auto_highlight=True,
    )

    tooltip = {
        "html": "<b>{kenteken}</b><br/>Afstand: {km} km",
        "style": {
            "backgroundColor": "#1E3A5F",
            "color": "white",
            "fontSize": "13px",
            "padding": "8px 12px",
            "borderRadius": "6px",
        },
    }

    if selected and len(arc_data) > 0:
        view = pdk.ViewState(
            latitude=arc_data['start_lat'].mean(),
            longitude=arc_data['start_lon'].mean(),
            zoom=11,
            pitch=30,
        )
    else:
        view = NL_VIEW._replace(pitch=30) if hasattr(NL_VIEW, '_replace') else pdk.ViewState(
            latitude=52.05, longitude=6.55, zoom=9, pitch=30,
        )

    st.pydeck_chart(pdk.Deck(
        layers=[layer],
        initial_view_state=view,
        tooltip=tooltip,
        map_style=MAP_STYLE,
    ), height=600)

    if len(arc_data) > 500:
        st.info(f"Weergave beperkt tot 500 van {len(arc_data)} ritten. Filter op voertuig voor meer detail.")
