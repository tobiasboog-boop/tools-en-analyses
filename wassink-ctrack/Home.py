import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta
import sys, os

sys.path.insert(0, os.path.dirname(__file__))
from src.database import load_trips, load_vehicles
from src.auth import check_password

st.set_page_config(
    page_title="Wassink Vlootbeheer",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded",
)

if not check_password():
    st.stop()

st.title("Wassink Vlootbeheer Dashboard")
st.caption("C-Track voertuig- en ritdata | Wassink 1225")

# Load data
try:
    trips = load_trips()
    vehicles = load_vehicles()
except Exception as e:
    st.error(f"Kan data niet laden: {e}")
    st.stop()

# --- Sidebar filters ---
st.sidebar.header("Filters")

min_date = trips['datum'].min()
max_date = trips['datum'].max()
date_range = st.sidebar.date_input(
    "Periode",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)
if len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date, max_date

# Filter trips
mask = (trips['datum'] >= start_date) & (trips['datum'] <= end_date)
filtered = trips[mask].copy()

# Vehicle filter
kentekens = sorted(filtered['kenteken'].dropna().unique())
selected_kentekens = st.sidebar.multiselect("Voertuigen", kentekens, default=[])
if selected_kentekens:
    filtered = filtered[filtered['kenteken'].isin(selected_kentekens)]

# Driver filter
bestuurders = sorted(filtered['bestuurder'].dropna().unique())
selected_bestuurders = st.sidebar.multiselect("Bestuurders", bestuurders, default=[])
if selected_bestuurders:
    filtered = filtered[filtered['bestuurder'].isin(selected_bestuurders)]

# --- KPI cards ---
st.markdown("---")

col1, col2, col3, col4, col5 = st.columns(5)

total_km = filtered['afstand_km'].sum()
total_trips = len(filtered)
total_hours = filtered['rijtijd_min'].sum() / 60
active_vehicles = filtered['kenteken'].nunique()
active_drivers = filtered['bestuurder'].nunique()

col1.metric("Totaal km", f"{total_km:,.0f} km")
col2.metric("Aantal ritten", f"{total_trips:,}")
col3.metric("Rijuren", f"{total_hours:,.1f} uur")
col4.metric("Actieve voertuigen", f"{active_vehicles}")
col5.metric("Actieve bestuurders", f"{active_drivers}")

# --- Row 2: Charts ---
st.markdown("---")

left, right = st.columns(2)

with left:
    st.subheader("Kilometers per dag")
    daily = filtered.groupby('datum').agg(
        km=('afstand_km', 'sum'),
        ritten=('afstand_km', 'count')
    ).reset_index()
    daily['datum'] = pd.to_datetime(daily['datum'])

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=daily['datum'], y=daily['km'],
        name='Km', marker_color='#1E3A5F',
    ))
    fig.add_trace(go.Scatter(
        x=daily['datum'], y=daily['ritten'],
        name='Ritten', yaxis='y2',
        line=dict(color='#E07A5F', width=2),
    ))
    fig.update_layout(
        yaxis=dict(title='Kilometers'),
        yaxis2=dict(title='Ritten', overlaying='y', side='right'),
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
        margin=dict(t=30, b=30),
        height=350,
    )
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Top 10 voertuigen (km)")
    top_vehicles = (
        filtered.groupby('kenteken')['afstand_km']
        .sum()
        .sort_values(ascending=True)
        .tail(10)
        .reset_index()
    )
    fig2 = px.bar(
        top_vehicles, x='afstand_km', y='kenteken',
        orientation='h',
        labels={'afstand_km': 'Kilometers', 'kenteken': ''},
        color_discrete_sequence=['#1E3A5F'],
    )
    fig2.update_layout(margin=dict(t=10, b=30), height=350)
    st.plotly_chart(fig2, use_container_width=True)

# --- Row 3 ---
left2, right2 = st.columns(2)

with left2:
    st.subheader("Top 10 bestuurders (km)")
    top_drivers = (
        filtered[filtered['bestuurder'].notna()]
        .groupby('bestuurder')['afstand_km']
        .sum()
        .sort_values(ascending=True)
        .tail(10)
        .reset_index()
    )
    fig3 = px.bar(
        top_drivers, x='afstand_km', y='bestuurder',
        orientation='h',
        labels={'afstand_km': 'Kilometers', 'bestuurder': ''},
        color_discrete_sequence=['#3D5A80'],
    )
    fig3.update_layout(margin=dict(t=10, b=30), height=350)
    st.plotly_chart(fig3, use_container_width=True)

with right2:
    st.subheader("Ritten per uur van de dag")
    filtered_with_hour = filtered.copy()
    filtered_with_hour['uur'] = filtered_with_hour['start'].dt.hour
    hourly = filtered_with_hour.groupby('uur').size().reset_index(name='ritten')

    fig4 = px.bar(
        hourly, x='uur', y='ritten',
        labels={'uur': 'Uur', 'ritten': 'Aantal ritten'},
        color_discrete_sequence=['#457B9D'],
    )
    fig4.update_layout(
        margin=dict(t=10, b=30), height=350,
        xaxis=dict(dtick=1),
    )
    st.plotly_chart(fig4, use_container_width=True)

# --- Recent trips table ---
st.markdown("---")
st.subheader("Recente ritten")

recent = filtered.sort_values('start', ascending=False).head(50)
display_cols = {
    'kenteken': 'Kenteken',
    'bestuurder': 'Bestuurder',
    'start': 'Start',
    'eind': 'Eind',
    'afstand_km': 'Km',
    'rijtijd_min': 'Rijtijd (min)',
    'startlocation': 'Van',
    'endlocation': 'Naar',
    'maxspeed': 'Max snelheid',
}
display = recent[list(display_cols.keys())].rename(columns=display_cols)
display['Km'] = display['Km'].round(1)
display['Rijtijd (min)'] = display['Rijtijd (min)'].round(1)
display['Start'] = display['Start'].dt.strftime('%d-%m %H:%M')
display['Eind'] = display['Eind'].dt.strftime('%d-%m %H:%M')

st.dataframe(display, use_container_width=True, hide_index=True)
