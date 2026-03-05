import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date
from src.data_loader import load_portfolio, get_years, get_year_columns
from src.termijnschemas import (
    BUILTIN_SCHEMAS, DEFAULT_USER_SCHEMAS,
    get_all_schema_namen, distribute_revenue,
)
from src.charts import line_schema_vergelijking, line_schema_cumulatief
from config import APP_TITLE, APP_ICON, APP_LAYOUT, format_eur, format_eur_full, NAVY_PRIMARY, ACCENT

# Page config handled by app.py router

st.title("Project Detail")
st.caption("Bekijk de omzetverdeling per project — instellingen worden op de Omzetverdeling-pagina beheerd")

# Load data
@st.cache_data
def get_data():
    return load_portfolio()

df = get_data()
years = get_years(df)
jaar_cols = get_year_columns(df)

# Get settings from session state (set on Omzetverdeling page)
user_schemas = st.session_state.get("user_schemas", dict(DEFAULT_USER_SCHEMAS))
all_schema_namen = get_all_schema_namen(user_schemas)
project_overrides = st.session_state.get("project_overrides", {})
default_schema = st.session_state.get("default_schema", all_schema_namen[0])

# --- Project Selection ---
project_options = df.sort_values("totaal", ascending=False).apply(
    lambda r: f"{r['naam']} — {r['vestiging']} ({format_eur(r['totaal'])})", axis=1
).tolist()

selected_idx = st.selectbox(
    "Selecteer project",
    range(len(project_options)),
    format_func=lambda i: project_options[i],
)

project = df.sort_values("totaal", ascending=False).iloc[selected_idx]
pid = project["project_id"]

# Get override settings for this project (or defaults)
override = project_overrides.get(pid, {})
schema = override.get("schema", default_schema)
originele_start = project["originele_start"]
originele_eind = project["originele_eind"]
aangepaste_start = override.get("start_date", originele_start)
aangepaste_eind = override.get("end_date", originele_eind)

# Recurring projects always linear
if project.get("is_wederkerend", False):
    schema = "Lineair"

# --- Project Info ---
st.markdown("---")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Totaalbedrag", format_eur(project["totaal"]))
with col2:
    st.metric("Vestiging", project["vestiging"])
with col3:
    st.metric("Categorie", project["categorie"])
with col4:
    st.metric("Meerwerk", "Ja" if project["is_meerwerk"] else "Nee")

# Year breakdown from Excel
st.markdown("##### Omzet per jaar (Excel)")
year_display_cols = st.columns(len(years))
for i, y in enumerate(years):
    col_name = f"jaar_{y}"
    val = project[col_name]
    with year_display_cols[i]:
        st.metric(str(y), format_eur(val) if val > 0 else "-")

# --- Schema & Planning Info (read-only) ---
st.markdown("---")
st.subheader("Instellingen")

col_schema, col_dates = st.columns([1, 1])

with col_schema:
    st.markdown("##### Termijnschema")
    if schema in user_schemas:
        pcts = user_schemas[schema]
        st.info(f"**{schema}:** {' / '.join(f'{p:.0f}%' for p in pcts)} over {len(pcts)} fasen")
    elif schema in BUILTIN_SCHEMAS:
        st.info(f"**{schema}:** {BUILTIN_SCHEMAS[schema]}")

with col_dates:
    st.markdown("##### Planning")
    st.text(f"Originele start:   {originele_start.strftime('%d-%m-%Y')}")
    st.text(f"Originele eind:    {originele_eind.strftime('%d-%m-%Y')}")
    st.text(f"Aangepaste start:  {aangepaste_start.strftime('%d-%m-%Y')}")
    st.text(f"Aangepaste eind:   {aangepaste_eind.strftime('%d-%m-%Y')}")

    # Delta calculation
    delta_months = (aangepaste_start.year - originele_start.year) * 12 + (aangepaste_start.month - originele_start.month)
    if delta_months == 0:
        st.success("Op schema — geen verschuiving")
    elif delta_months > 0:
        st.warning(f"{delta_months} maand(en) later dan origineel gepland")
    else:
        st.info(f"{abs(delta_months)} maand(en) eerder dan origineel gepland")

    duration_months = (aangepaste_eind.year - aangepaste_start.year) * 12 + (aangepaste_eind.month - aangepaste_start.month) + 1
    st.text(f"Looptijd: {duration_months} maanden")

st.caption("Wijzigingen aanbrengen? Ga naar de **Omzetverdeling**-pagina.")

# --- Distribution Calculations ---
st.markdown("---")
st.subheader("Verdeling")

# Originele verdeling (lineair, originele datums)
dist_origineel = distribute_revenue(
    project["totaal"], originele_start, originele_eind, "Lineair"
)

# Aangepaste verdeling (gekozen schema, aangepaste datums)
dist_aangepast = distribute_revenue(
    project["totaal"], aangepaste_start, aangepaste_eind, schema, user_schemas
)

# --- Comparison: Original vs Adjusted ---
st.markdown("##### Origineel (lineair) vs Aangepast")

fig_compare = go.Figure()
fig_compare.add_trace(go.Scatter(
    x=dist_origineel["maand"],
    y=dist_origineel["bedrag"],
    mode="lines+markers",
    name="Origineel (lineair)",
    line=dict(color=NAVY_PRIMARY, width=2, dash="dash"),
    marker=dict(size=4),
))
fig_compare.add_trace(go.Scatter(
    x=dist_aangepast["maand"],
    y=dist_aangepast["bedrag"],
    mode="lines+markers",
    name=f"Aangepast ({schema})",
    line=dict(color=ACCENT, width=2),
    marker=dict(size=4),
))
fig_compare.update_layout(
    plot_bgcolor="white",
    paper_bgcolor="white",
    yaxis=dict(tickprefix="€ ", tickformat=",.0f", title="Maandbedrag (€)"),
    xaxis=dict(title="Maand"),
    margin=dict(l=40, r=20, t=40, b=40),
    legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5),
    separators=",.",
)
st.plotly_chart(fig_compare, use_container_width=True)

# --- Schema Comparison Charts (all schemas) ---
st.markdown("---")
st.subheader("Vergelijking alle schema's")

col_c1, col_c2 = st.columns(2)

with col_c1:
    fig = line_schema_vergelijking(
        project["totaal"], aangepaste_start, aangepaste_eind, all_schema_namen, user_schemas,
    )
    st.plotly_chart(fig, use_container_width=True)

with col_c2:
    fig = line_schema_cumulatief(
        project["totaal"], aangepaste_start, aangepaste_eind, all_schema_namen, user_schemas,
    )
    st.plotly_chart(fig, use_container_width=True)

# --- Year Impact ---
st.markdown("---")
st.subheader("Impact op kalenderjaren")
st.caption("Hoe verschuift de omzet tussen jaren door de aanpassing?")

orig_per_jaar = {}
for y in years:
    orig_per_jaar[y] = project[f"jaar_{y}"]

dist_aangepast["jaar"] = dist_aangepast["maand"].dt.year
aanp_per_jaar = dist_aangepast.groupby("jaar")["bedrag"].sum().to_dict()

all_years = sorted(set(list(orig_per_jaar.keys()) + list(aanp_per_jaar.keys())))
jaar_impact = []
for y in all_years:
    orig = orig_per_jaar.get(y, 0)
    aanp = aanp_per_jaar.get(y, 0)
    jaar_impact.append({
        "Jaar": y,
        "Origineel (Excel)": orig,
        "Aangepast": aanp,
        "Verschil": aanp - orig,
    })

jaar_impact_df = pd.DataFrame(jaar_impact)

fig_impact = go.Figure()
fig_impact.add_trace(go.Bar(
    x=jaar_impact_df["Jaar"],
    y=jaar_impact_df["Origineel (Excel)"],
    name="Origineel (Excel)",
    marker_color=NAVY_PRIMARY,
    text=[format_eur(v) for v in jaar_impact_df["Origineel (Excel)"]],
    textposition="outside",
    textfont=dict(size=10),
))
fig_impact.add_trace(go.Bar(
    x=jaar_impact_df["Jaar"],
    y=jaar_impact_df["Aangepast"],
    name=f"Aangepast ({schema})",
    marker_color=ACCENT,
    text=[format_eur(v) for v in jaar_impact_df["Aangepast"]],
    textposition="outside",
    textfont=dict(size=10),
))
fig_impact.update_layout(
    barmode="group",
    plot_bgcolor="white",
    paper_bgcolor="white",
    yaxis=dict(tickprefix="€ ", tickformat=",.0f"),
    xaxis=dict(dtick=1),
    margin=dict(l=40, r=20, t=20, b=40),
    legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="center", x=0.5),
    separators=",.",
)
st.plotly_chart(fig_impact, use_container_width=True)

impact_display = jaar_impact_df.copy()
for col in ["Origineel (Excel)", "Aangepast", "Verschil"]:
    impact_display[col] = jaar_impact_df[col].apply(
        lambda x: format_eur_full(x) if abs(x) > 0 else "-"
    )
st.dataframe(impact_display, use_container_width=True, hide_index=True)

# --- Monthly Detail Table ---
st.markdown("---")
st.subheader(f"Maandelijkse bedragen — {schema}")

table_df = dist_aangepast[["maand", "bedrag"]].copy()
table_df["maand_display"] = table_df["maand"].dt.strftime("%B %Y")
table_df["bedrag_fmt"] = table_df["bedrag"].apply(format_eur_full)
table_df["cumulatief"] = table_df["bedrag"].cumsum()
table_df["cumulatief_fmt"] = table_df["cumulatief"].apply(format_eur_full)
table_df["% van totaal"] = (table_df["cumulatief"] / project["totaal"] * 100).round(1).astype(str) + "%"

display = table_df[["maand_display", "bedrag_fmt", "cumulatief_fmt", "% van totaal"]].rename(columns={
    "maand_display": "Maand",
    "bedrag_fmt": "Bedrag",
    "cumulatief_fmt": "Cumulatief",
})
st.dataframe(display, use_container_width=True, hide_index=True)
