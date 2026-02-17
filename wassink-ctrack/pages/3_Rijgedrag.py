import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.database import load_trips
from src.auth import check_password

st.set_page_config(page_title="Rijgedrag", page_icon="⚡", layout="wide")
if not check_password():
    st.stop()
st.title("Rijgedrag Analyse")

try:
    trips = load_trips()
except Exception as e:
    st.error(f"Database fout: {e}")
    st.stop()

# --- KPIs ---
trips_with_speed = trips[trips['maxspeed'].notna()]
overspeed_trips = trips[trips['overspeedcount'].fillna(0) > 0]
idle_trips = trips[trips['excessidlecount'].fillna(0) > 0]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Ritten met overspeed", len(overspeed_trips),
            f"{len(overspeed_trips)/len(trips)*100:.1f}% van totaal")
col2.metric("Totaal overspeed minuten", f"{trips['overspeed_min'].sum():,.1f}")
col3.metric("Ritten met stationair draaien", len(idle_trips),
            f"{len(idle_trips)/len(trips)*100:.1f}% van totaal")
col4.metric("Totaal stationair (min)", f"{trips['stationair_min'].sum():,.1f}")

# --- Overspeed per bestuurder ---
st.markdown("---")
st.subheader("Snelheidsovertredingen per bestuurder")

driver_speed = (
    trips[trips['bestuurder'].notna()]
    .groupby('bestuurder')
    .agg(
        ritten=('afstand_km', 'count'),
        overspeed_ritten=('overspeedcount', lambda x: (x.fillna(0) > 0).sum()),
        totaal_overspeed_events=('overspeedcount', lambda x: x.fillna(0).sum()),
        overspeed_min=('overspeed_min', 'sum'),
        max_snelheid=('maxspeed', 'max'),
        totaal_km=('afstand_km', 'sum'),
    )
    .reset_index()
)
driver_speed['overspeed_pct'] = (driver_speed['overspeed_ritten'] / driver_speed['ritten'] * 100).round(1)
driver_speed = driver_speed.sort_values('overspeed_ritten', ascending=False)

# Chart
fig = go.Figure()
fig.add_trace(go.Bar(
    x=driver_speed.head(15)['bestuurder'],
    y=driver_speed.head(15)['overspeed_ritten'],
    name='Ritten met overspeed',
    marker_color='#E07A5F',
))
fig.add_trace(go.Bar(
    x=driver_speed.head(15)['bestuurder'],
    y=driver_speed.head(15)['ritten'] - driver_speed.head(15)['overspeed_ritten'],
    name='Normale ritten',
    marker_color='#81B29A',
))
fig.update_layout(
    barmode='stack',
    height=400,
    margin=dict(t=10),
    legend=dict(orientation='h', yanchor='bottom', y=1.02),
    xaxis_tickangle=-45,
)
st.plotly_chart(fig, use_container_width=True)

# Table
display_speed = driver_speed.rename(columns={
    'bestuurder': 'Bestuurder',
    'ritten': 'Ritten',
    'overspeed_ritten': 'Met overspeed',
    'overspeed_pct': '% overspeed',
    'totaal_overspeed_events': 'Events',
    'overspeed_min': 'Overspeed (min)',
    'max_snelheid': 'Max km/u',
    'totaal_km': 'Totaal km',
})
display_speed['Overspeed (min)'] = display_speed['Overspeed (min)'].round(1)
display_speed['Totaal km'] = display_speed['Totaal km'].round(0)

st.dataframe(display_speed, use_container_width=True, hide_index=True)

# --- Stationair draaien per bestuurder ---
st.markdown("---")
st.subheader("Stationair draaien per bestuurder")

driver_idle = (
    trips[trips['bestuurder'].notna()]
    .groupby('bestuurder')
    .agg(
        ritten=('afstand_km', 'count'),
        idle_ritten=('excessidlecount', lambda x: (x.fillna(0) > 0).sum()),
        stationair_min=('stationair_min', 'sum'),
        totaal_km=('afstand_km', 'sum'),
    )
    .reset_index()
)
driver_idle['idle_pct'] = (driver_idle['idle_ritten'] / driver_idle['ritten'] * 100).round(1)
driver_idle['min_per_100km'] = driver_idle.apply(
    lambda r: (r['stationair_min'] / r['totaal_km'] * 100) if r['totaal_km'] > 0 else 0, axis=1
).round(1)
driver_idle = driver_idle.sort_values('stationair_min', ascending=False)

fig2 = px.bar(
    driver_idle.head(15).sort_values('stationair_min'),
    x='stationair_min', y='bestuurder',
    orientation='h',
    labels={'stationair_min': 'Stationair draaien (min)', 'bestuurder': ''},
    color='min_per_100km',
    color_continuous_scale='OrRd',
)
fig2.update_coloraxes(colorbar_title='Min/100km')
fig2.update_layout(height=400, margin=dict(t=10))
st.plotly_chart(fig2, use_container_width=True)

# --- Max snelheid distributie ---
st.markdown("---")
st.subheader("Snelheidsdistributie (max snelheid per rit)")

speed_data = trips_with_speed['maxspeed'].dropna()
fig3 = px.histogram(
    speed_data, nbins=30,
    labels={'value': 'Max snelheid (km/u)', 'count': 'Aantal ritten'},
    color_discrete_sequence=['#457B9D'],
)
fig3.add_vline(x=130, line_dash='dash', line_color='red', annotation_text='Snelweg limiet (130)')
fig3.add_vline(x=80, line_dash='dash', line_color='orange', annotation_text='Buitenweg limiet (80)')
fig3.update_layout(height=350, margin=dict(t=10), showlegend=False)
st.plotly_chart(fig3, use_container_width=True)

# --- Overspeed trend ---
st.markdown("---")
st.subheader("Overspeed trend per dag")

daily_overspeed = (
    trips.groupby('datum')
    .agg(
        totaal_ritten=('afstand_km', 'count'),
        overspeed_ritten=('overspeedcount', lambda x: (x.fillna(0) > 0).sum()),
    )
    .reset_index()
)
daily_overspeed['datum'] = pd.to_datetime(daily_overspeed['datum'])
daily_overspeed['overspeed_pct'] = (
    daily_overspeed['overspeed_ritten'] / daily_overspeed['totaal_ritten'] * 100
).round(1)

fig4 = go.Figure()
fig4.add_trace(go.Scatter(
    x=daily_overspeed['datum'], y=daily_overspeed['overspeed_pct'],
    fill='tozeroy', fillcolor='rgba(224, 122, 95, 0.3)',
    line=dict(color='#E07A5F'),
    name='% ritten met overspeed',
))
fig4.update_layout(
    yaxis_title='% ritten met overspeed',
    height=300,
    margin=dict(t=10),
)
st.plotly_chart(fig4, use_container_width=True)
