import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.database import load_trips
from src.auth import check_password

st.set_page_config(page_title="Kilometerregistratie", page_icon="📊", layout="wide")
if not check_password():
    st.stop()
st.title("Kilometerregistratie")

try:
    trips = load_trips()
except Exception as e:
    st.error(f"Database fout: {e}")
    st.stop()

# --- View toggle ---
view = st.radio("Weergave", ["Per voertuig", "Per bestuurder"], horizontal=True)

group_col = 'kenteken' if view == "Per voertuig" else 'bestuurder'
group_label = 'Kenteken' if view == "Per voertuig" else 'Bestuurder'

# Filter out rows without group value
data = trips[trips[group_col].notna()].copy()

# --- Daily summary ---
st.markdown("---")
st.subheader("Dagelijkse kilometers")

daily_pivot = (
    data.groupby(['datum', group_col])['afstand_km']
    .sum()
    .reset_index()
)

fig = px.bar(
    daily_pivot,
    x='datum', y='afstand_km', color=group_col,
    labels={'datum': 'Datum', 'afstand_km': 'Kilometers', group_col: group_label},
    color_discrete_sequence=px.colors.qualitative.Set2,
)
fig.update_layout(
    height=450,
    margin=dict(t=10),
    legend=dict(orientation='h', yanchor='bottom', y=1.02),
    barmode='stack',
)
st.plotly_chart(fig, use_container_width=True)

# --- Summary table ---
st.markdown("---")
st.subheader(f"Samenvatting per {group_label.lower()}")

summary = (
    data.groupby(group_col)
    .agg(
        dagen_actief=('datum', 'nunique'),
        ritten=('afstand_km', 'count'),
        totaal_km=('afstand_km', 'sum'),
        gem_km_per_dag=('afstand_km', lambda x: x.sum() / data[data[group_col] == x.name].datum.nunique() if len(x) > 0 else 0),
        gem_km_per_rit=('afstand_km', 'mean'),
        totaal_rijtijd_uur=('rijtijd_min', lambda x: x.sum() / 60),
        langste_rit_km=('afstand_km', 'max'),
    )
    .reset_index()
    .sort_values('totaal_km', ascending=False)
)

# Fix gem_km_per_dag calculation
summary['gem_km_per_dag'] = summary['totaal_km'] / summary['dagen_actief']

display = summary.rename(columns={
    group_col: group_label,
    'dagen_actief': 'Dagen actief',
    'ritten': 'Ritten',
    'totaal_km': 'Totaal km',
    'gem_km_per_dag': 'Gem. km/dag',
    'gem_km_per_rit': 'Gem. km/rit',
    'totaal_rijtijd_uur': 'Rijuren',
    'langste_rit_km': 'Langste rit (km)',
})

for col in ['Totaal km', 'Gem. km/dag', 'Gem. km/rit', 'Rijuren', 'Langste rit (km)']:
    display[col] = display[col].round(1)

st.dataframe(display, use_container_width=True, hide_index=True)

# --- Heatmap: activity per weekday and hour ---
st.markdown("---")
st.subheader("Activiteitenpatroon (weekdag x uur)")

data['weekdag'] = data['start'].dt.day_name()
data['uur'] = data['start'].dt.hour

weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
weekday_nl = {'Monday': 'Maandag', 'Tuesday': 'Dinsdag', 'Wednesday': 'Woensdag',
              'Thursday': 'Donderdag', 'Friday': 'Vrijdag', 'Saturday': 'Zaterdag', 'Sunday': 'Zondag'}

heatmap_data = (
    data.groupby(['weekdag', 'uur'])['afstand_km']
    .sum()
    .reset_index()
)
heatmap_data['weekdag_nl'] = heatmap_data['weekdag'].map(weekday_nl)
heatmap_data['weekdag_sort'] = heatmap_data['weekdag'].map({d: i for i, d in enumerate(weekday_order)})
heatmap_data = heatmap_data.sort_values('weekdag_sort')

heatmap_pivot = heatmap_data.pivot(index='weekdag_nl', columns='uur', values='afstand_km').fillna(0)

# Ensure correct weekday order
nl_order = [weekday_nl[d] for d in weekday_order if weekday_nl[d] in heatmap_pivot.index]
heatmap_pivot = heatmap_pivot.reindex(nl_order)

fig_heat = px.imshow(
    heatmap_pivot,
    labels=dict(x="Uur", y="Weekdag", color="Km"),
    color_continuous_scale='Blues',
    aspect='auto',
)
fig_heat.update_layout(height=350, margin=dict(t=10))
st.plotly_chart(fig_heat, use_container_width=True)

# --- Download ---
st.markdown("---")
st.subheader("Data exporteren")

export_data = (
    data.groupby(['datum', group_col])
    .agg(
        ritten=('afstand_km', 'count'),
        km=('afstand_km', 'sum'),
        rijtijd_min=('rijtijd_min', 'sum'),
    )
    .reset_index()
)
export_data['km'] = export_data['km'].round(1)
export_data['rijtijd_min'] = export_data['rijtijd_min'].round(1)

csv = export_data.to_csv(index=False, sep=';', decimal=',')
st.download_button(
    "Download als CSV",
    csv,
    file_name=f"kilometerregistratie_{group_col}.csv",
    mime="text/csv",
)
