import streamlit as st
import pandas as pd
from src.data_loader import load_portfolio, get_years, get_year_columns, unpivot_years
from src.charts import bar_omzet_per_jaar, donut_categorie, bar_top_projecten, bar_omzet_per_vestiging
from config import APP_TITLE, APP_ICON, APP_LAYOUT, format_eur, format_eur_full, NAVY_PRIMARY

st.title("Overzicht")
st.caption("Orderportefeuille — totaaloverzicht per vestiging, categorie en jaar")

# Load data
@st.cache_data
def get_data():
    return load_portfolio()

df = get_data()
years = get_years(df)
jaar_cols = get_year_columns(df)

# --- Sidebar Filters ---
st.sidebar.header("Filters")

vestigingen = sorted(df["vestiging"].unique())
sel_vestigingen = st.sidebar.multiselect(
    "Vestiging", vestigingen, default=vestigingen, key="filter_vestiging"
)

categorieen = sorted(df["categorie"].unique())
sel_categorieen = st.sidebar.multiselect(
    "Categorie", categorieen, default=categorieen, key="filter_categorie"
)

sel_meerwerk = st.sidebar.selectbox(
    "Meerwerk", ["Alle", "Alleen regulier", "Alleen meerwerk"], key="filter_meerwerk"
)

# Apply filters
mask = df["vestiging"].isin(sel_vestigingen) & df["categorie"].isin(sel_categorieen)
if sel_meerwerk == "Alleen regulier":
    mask &= ~df["is_meerwerk"]
elif sel_meerwerk == "Alleen meerwerk":
    mask &= df["is_meerwerk"]

df_filtered = df[mask].copy()

# --- KPI Cards ---
st.markdown("---")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Totaal Portfolio", format_eur(df_filtered["totaal"].sum()))
with col2:
    if years:
        current_year = years[0]
        col_name = f"jaar_{current_year}"
        st.metric(f"Omzet {current_year}", format_eur(df_filtered[col_name].sum()))
with col3:
    st.metric("Projecten", len(df_filtered))
with col4:
    st.metric("Vestigingen", df_filtered["vestiging"].nunique())

# --- Year breakdown ---
st.markdown("---")
st.subheader("Omzet per jaar")

year_totals = {}
for y in years:
    col_name = f"jaar_{y}"
    year_totals[y] = df_filtered[col_name].sum()

year_cols_display = st.columns(len(years))
for i, y in enumerate(years):
    with year_cols_display[i]:
        st.metric(str(y), format_eur(year_totals[y]))

# --- Charts ---
st.markdown("---")
col_left, col_right = st.columns(2)

df_unpivot = unpivot_years(df_filtered)

with col_left:
    st.plotly_chart(bar_omzet_per_jaar(df_unpivot), use_container_width=True)

with col_right:
    st.plotly_chart(donut_categorie(df_filtered), use_container_width=True)

st.markdown("---")
col_left2, col_right2 = st.columns(2)

with col_left2:
    st.plotly_chart(bar_omzet_per_vestiging(df_filtered), use_container_width=True)

with col_right2:
    st.plotly_chart(bar_top_projecten(df_filtered), use_container_width=True)

# --- Project Table ---
st.markdown("---")
st.subheader("Projectoverzicht")

display_cols = ["naam", "vestiging", "categorie", "meerwerk", "opdrachtgever", "totaal", "originele_start", "originele_eind"] + jaar_cols
display_df = df_filtered[display_cols].copy()
display_df = display_df.sort_values("totaal", ascending=False)

# Format date columns
display_df["originele_start"] = display_df["originele_start"].apply(lambda d: d.strftime("%d-%m-%Y"))
display_df["originele_eind"] = display_df["originele_eind"].apply(lambda d: d.strftime("%d-%m-%Y"))

# Format currency columns
for col in ["totaal"] + jaar_cols:
    display_df[col] = display_df[col].apply(lambda x: format_eur_full(x) if x > 0 else "-")

# Rename columns for display
rename = {"naam": "Project", "vestiging": "Vestiging", "categorie": "Categorie",
          "meerwerk": "Meerwerk", "opdrachtgever": "Opdrachtgever", "totaal": "Totaal",
          "originele_start": "Start", "originele_eind": "Eind"}
for y in years:
    rename[f"jaar_{y}"] = str(y)
display_df = display_df.rename(columns=rename)

st.dataframe(display_df, use_container_width=True, hide_index=True)
