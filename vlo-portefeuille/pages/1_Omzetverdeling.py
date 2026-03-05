import streamlit as st
import pandas as pd
import numpy as np
from datetime import date
from src.data_loader import load_portfolio, get_years
from src.termijnschemas import (
    BUILTIN_SCHEMAS, DEFAULT_USER_SCHEMAS, MAX_USER_SCHEMAS,
    get_all_schema_namen, distribute_all_projects, distribute_revenue,
)
from src.charts import area_maandelijkse_omzet
from config import (
    APP_TITLE, APP_ICON, APP_LAYOUT, format_eur, format_eur_full,
    NAVY_PRIMARY, NAVY_SECONDARY, ACCENT, CHART_COLORS,
)
import plotly.express as px
import plotly.graph_objects as go

st.title("Omzetverdeling")
st.caption("Definieer termijnschema's, kies een standaard, en pas individuele projecten aan waar nodig")

# --- Load data ---
@st.cache_data
def get_data():
    return load_portfolio()

df = get_data()
years = get_years(df)

# --- Sidebar: Filters ---
st.sidebar.header("Filters")

vestigingen = sorted(df["vestiging"].unique())
sel_vestigingen = st.sidebar.multiselect(
    "Vestiging", vestigingen, default=vestigingen, key="omzet_vestiging"
)

show_wederkerend = st.sidebar.checkbox("Toon wederkerend", value=True, key="show_wederkerend")
show_eenmalig = st.sidebar.checkbox("Toon eenmalig", value=True, key="show_eenmalig")

mask = df["vestiging"].isin(sel_vestigingen)
if not show_wederkerend:
    mask &= ~df["is_wederkerend"]
if not show_eenmalig:
    mask &= df["is_wederkerend"]
df_filtered = df[mask].copy()

eenmalig = df_filtered[~df_filtered["is_wederkerend"]].sort_values("totaal", ascending=False).copy()
wederkerend = df_filtered[df_filtered["is_wederkerend"]].copy()

# ============================================================
# 1. TERMIJNSCHEMA'S DEFINIËREN
# ============================================================
st.markdown("---")
st.subheader("Termijnschema's")
st.caption(
    f"Definieer tot {MAX_USER_SCHEMAS} termijnschema's met eigen fasen en percentages. "
    "Daarnaast zijn **Lineair** en **S-curve** altijd beschikbaar."
)

# Initialize user schemas in session state
if "user_schemas" not in st.session_state:
    st.session_state.user_schemas = dict(DEFAULT_USER_SCHEMAS)

# How many schemas does the user want?
n_schemas = st.number_input(
    "Aantal termijnschema's",
    min_value=1,
    max_value=MAX_USER_SCHEMAS,
    value=len(st.session_state.user_schemas),
    key="n_schemas",
)

# Build schema editors
user_schemas = {}
schema_cols = st.columns(min(n_schemas, 3))

# Get existing schema names/values for defaults
existing_names = list(st.session_state.user_schemas.keys())
existing_values = list(st.session_state.user_schemas.values())

for i in range(n_schemas):
    col_idx = i % min(n_schemas, 3)
    with schema_cols[col_idx]:
        # Default name and phases from existing or template
        default_name = existing_names[i] if i < len(existing_names) else f"Schema {i + 1}"
        default_phases = existing_values[i] if i < len(existing_values) else [25, 25, 25, 25]

        naam = st.text_input(
            f"Naam schema {i + 1}",
            value=default_name,
            key=f"schema_naam_{i}",
        )

        n_fasen = st.slider(
            "Fasen",
            min_value=2,
            max_value=6,
            value=len(default_phases),
            key=f"schema_fasen_{i}",
        )

        # Phase percentage inputs
        fasen_pct = []
        remaining = 100.0
        for j in range(n_fasen):
            if j < n_fasen - 1:
                default_val = default_phases[j] if j < len(default_phases) else round(remaining / (n_fasen - j), 1)
                default_val = min(default_val, remaining)
                val = st.number_input(
                    f"Fase {j + 1} (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(default_val),
                    step=5.0,
                    key=f"schema_{i}_fase_{j}",
                )
                fasen_pct.append(val)
                remaining -= val
            else:
                remaining = max(0.0, remaining)
                st.caption(f"Fase {j + 1} (%) — rest")
                st.code(f"{remaining:.1f}")
                fasen_pct.append(remaining)

        total_pct = sum(fasen_pct)
        if abs(total_pct - 100) > 0.5:
            st.warning(f"Totaal: {total_pct:.0f}%")

        # Preview bar
        st.caption(f"**{naam}:** {' / '.join(f'{p:.0f}%' for p in fasen_pct)}")

        if naam.strip():
            user_schemas[naam.strip()] = fasen_pct

# Save to session state
st.session_state.user_schemas = user_schemas

# Combined schema list for dropdowns
all_schema_namen = get_all_schema_namen(user_schemas)

# ============================================================
# 2. STANDAARD SCHEMA KIEZEN
# ============================================================
st.markdown("---")
st.subheader("Standaard schema")

col_default, col_preview = st.columns([1, 2])

with col_default:
    default_schema = st.selectbox(
        "Standaard voor alle eenmalige projecten",
        all_schema_namen,
        index=0,
        key="default_schema",
    )

with col_preview:
    if default_schema in user_schemas:
        pcts = user_schemas[default_schema]
        st.info(f"**{default_schema}:** {' / '.join(f'{p:.0f}%' for p in pcts)} over {len(pcts)} fasen")
    elif default_schema in BUILTIN_SCHEMAS:
        st.info(BUILTIN_SCHEMAS[default_schema])
    st.caption("Wederkerende projecten worden altijd lineair verdeeld.")

# ============================================================
# 3. PER-PROJECT AANPASSINGEN
# ============================================================
st.markdown("---")
st.subheader("Aanpassingen per project")
st.caption(
    f"Alle eenmalige projecten gebruiken **{default_schema}**. "
    "Wijzig hieronder alleen projecten die een ander schema of startdatum nodig hebben."
)

if "project_overrides" not in st.session_state:
    st.session_state.project_overrides = {}

if len(eenmalig) > 0:
    edit_data = []
    for _, row in eenmalig.iterrows():
        pid = row["project_id"]
        override = st.session_state.project_overrides.get(pid, {})

        # Truncate long project names for table readability
        naam_kort = row["naam"] if len(row["naam"]) <= 25 else row["naam"][:23] + ".."

        edit_data.append({
            "project_id": pid,
            "Project": naam_kort,
            "Vest.": row["vestiging"][:8] if len(row["vestiging"]) > 8 else row["vestiging"],
            "Totaal": format_eur_full(row["totaal"]),
            "Totaal_raw": row["totaal"],
            "orig_start": row["originele_start"],
            "Schema": override.get("schema", default_schema),
            "Start": override.get("start_date", row["originele_start"]),
            "Eind": override.get("end_date", row["originele_eind"]),
        })

    edit_df = pd.DataFrame(edit_data)
    edit_df = edit_df.sort_values("Totaal_raw", ascending=False)

    edit_df["Delta"] = edit_df.apply(
        lambda r: (r["Start"].year - r["orig_start"].year) * 12
                  + (r["Start"].month - r["orig_start"].month),
        axis=1,
    )

    column_config = {
        "project_id": None,
        "Totaal_raw": None,
        "orig_start": None,
        "Project": st.column_config.TextColumn("Project", disabled=True, width="small"),
        "Vest.": st.column_config.TextColumn("Vest.", disabled=True, width="small"),
        "Totaal": st.column_config.TextColumn("Totaal", disabled=True, width="small"),
        "Schema": st.column_config.SelectboxColumn("Schema", options=all_schema_namen, required=True, width="small"),
        "Start": st.column_config.DateColumn("Start", format="DD-MM-YYYY", width="small"),
        "Eind": st.column_config.DateColumn("Eind", format="DD-MM-YYYY", width="small"),
        "Delta": st.column_config.NumberColumn(
            "Δ",
            disabled=True,
            width="small",
            help="Verschil in maanden t.o.v. originele start (+ = later, - = eerder)",
        ),
    }

    edited_df = st.data_editor(
        edit_df,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        key="project_tbl_v3",
    )

    # Process overrides
    project_settings = {}
    n_overrides = 0
    for _, row in edited_df.iterrows():
        pid = row["project_id"]
        orig_row = eenmalig[eenmalig["project_id"] == pid].iloc[0]

        aangepaste_start = row["Start"]
        eind = row["Eind"]
        schema = row["Schema"]

        if isinstance(aangepaste_start, pd.Timestamp):
            aangepaste_start = aangepaste_start.date()
        if isinstance(eind, pd.Timestamp):
            eind = eind.date()

        has_override = (
            schema != default_schema
            or aangepaste_start != orig_row["originele_start"]
            or eind != orig_row["originele_eind"]
        )

        if has_override:
            project_settings[pid] = {
                "schema": schema,
                "start_date": aangepaste_start,
                "end_date": eind,
            }
            st.session_state.project_overrides[pid] = project_settings[pid]
            n_overrides += 1
        else:
            st.session_state.project_overrides.pop(pid, None)

else:
    project_settings = {}
    n_overrides = 0
    st.info("Geen eenmalige projecten in de huidige selectie.")

# --- Calculate distributions ---
monthly_df = distribute_all_projects(
    df_filtered,
    project_settings=project_settings,
    default_schema=default_schema,
    user_schemas=user_schemas,
)

if monthly_df.empty:
    st.warning("Geen projecten geselecteerd.")
    st.stop()

# --- KPI's ---
st.markdown("---")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Totaal gefilterd", format_eur(df_filtered["totaal"].sum()))
with col2:
    st.metric("Eenmalige projecten", len(eenmalig))
with col3:
    st.metric("Wederkerende projecten", len(wederkerend))
with col4:
    st.metric("Projecten aangepast", n_overrides)

# --- Main Charts ---
st.markdown("---")

group_by = st.radio(
    "Groeperen op",
    ["vestiging", "categorie"],
    horizontal=True,
    key="group_by",
)

col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.plotly_chart(
        area_maandelijkse_omzet(monthly_df, group_by=group_by, cumulative=False),
        use_container_width=True,
    )

with col_chart2:
    st.plotly_chart(
        area_maandelijkse_omzet(monthly_df, group_by=group_by, cumulative=True),
        use_container_width=True,
    )

# --- Monthly totals bar ---
st.markdown("---")
st.subheader("Maandtotalen")

monthly_totals = monthly_df.groupby("maand")["bedrag"].sum().reset_index()
monthly_totals = monthly_totals.sort_values("maand")

fig_bar = px.bar(
    monthly_totals,
    x="maand",
    y="bedrag",
    color_discrete_sequence=[NAVY_PRIMARY],
    labels={"bedrag": "Omzet (€)", "maand": "Maand"},
)
fig_bar.update_layout(
    plot_bgcolor="white",
    paper_bgcolor="white",
    yaxis=dict(tickprefix="€ ", tickformat=",.0f"),
    margin=dict(l=40, r=20, t=20, b=40),
    separators=",.",
)
st.plotly_chart(fig_bar, use_container_width=True)

# --- Jaaroverzicht ---
st.markdown("---")
st.subheader("Jaaroverzicht: Origineel vs Aangepast")
st.caption("Vergelijk de originele jaarverdeling (uit Excel) met de aangepaste verdeling")

origineel_per_jaar = {}
for y in years:
    origineel_per_jaar[y] = df_filtered[f"jaar_{y}"].sum()

monthly_df["jaar"] = monthly_df["maand"].dt.year
aangepast_per_jaar = monthly_df.groupby("jaar")["bedrag"].sum().to_dict()

jaar_overzicht = []
for y in years:
    orig = origineel_per_jaar.get(y, 0)
    aanp = aangepast_per_jaar.get(y, 0)
    jaar_overzicht.append({
        "Jaar": y,
        "Origineel (Excel)": orig,
        "Aangepast (Schema)": aanp,
        "Verschil": aanp - orig,
    })

jaar_df = pd.DataFrame(jaar_overzicht)

fig_jaar = go.Figure()
fig_jaar.add_trace(go.Bar(
    x=jaar_df["Jaar"],
    y=jaar_df["Origineel (Excel)"],
    name="Origineel (Excel)",
    marker_color=NAVY_PRIMARY,
    text=[format_eur(v) for v in jaar_df["Origineel (Excel)"]],
    textposition="outside",
    textfont=dict(size=10),
))
fig_jaar.add_trace(go.Bar(
    x=jaar_df["Jaar"],
    y=jaar_df["Aangepast (Schema)"],
    name="Aangepast (Schema)",
    marker_color=ACCENT,
    text=[format_eur(v) for v in jaar_df["Aangepast (Schema)"]],
    textposition="outside",
    textfont=dict(size=10),
))
fig_jaar.update_layout(
    barmode="group",
    plot_bgcolor="white",
    paper_bgcolor="white",
    yaxis=dict(tickprefix="€ ", tickformat=",.0f"),
    xaxis=dict(dtick=1),
    margin=dict(l=40, r=20, t=40, b=40),
    legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="center", x=0.5),
    separators=",.",
)
st.plotly_chart(fig_jaar, use_container_width=True)

jaar_display = jaar_df.copy()
for col in ["Origineel (Excel)", "Aangepast (Schema)", "Verschil"]:
    jaar_display[col] = jaar_df[col].apply(
        lambda x: format_eur_full(x) if abs(x) > 0 else "-"
    )
st.dataframe(jaar_display, use_container_width=True, hide_index=True)

# --- Monthly pivot ---
st.markdown("---")
st.subheader("Maandelijks overzicht per vestiging")

pivot = monthly_df.pivot_table(
    index="vestiging",
    columns=monthly_df["maand"].dt.strftime("%Y-%m"),
    values="bedrag",
    aggfunc="sum",
    fill_value=0,
)
pivot = pivot.reindex(sorted(pivot.columns), axis=1)
pivot["Totaal"] = pivot.sum(axis=1)
pivot = pivot.sort_values("Totaal", ascending=False)

pivot_display = pivot.map(lambda x: format_eur(x) if x > 0 else "-")
st.dataframe(pivot_display, use_container_width=True)

# --- Export ---
st.markdown("---")
if st.button("Exporteer naar Excel"):
    export_df = monthly_df[["maand", "naam", "vestiging", "categorie", "bedrag"]].copy()
    export_df["maand"] = export_df["maand"].dt.strftime("%Y-%m")
    export_df = export_df.sort_values(["maand", "vestiging", "naam"])

    # Schema definitions sheet
    schema_def = []
    for naam, pcts in user_schemas.items():
        for i, p in enumerate(pcts):
            schema_def.append({"Schema": naam, "Fase": i + 1, "Percentage": p})
    schema_def_df = pd.DataFrame(schema_def) if schema_def else pd.DataFrame()

    import io
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        export_df.to_excel(writer, sheet_name="Maandverdeling", index=False)
        pivot.to_excel(writer, sheet_name="Pivot per vestiging")
        jaar_df.to_excel(writer, sheet_name="Jaaroverzicht", index=False)
        if not schema_def_df.empty:
            schema_def_df.to_excel(writer, sheet_name="Schema definities", index=False)
    buffer.seek(0)

    st.download_button(
        label="Download Excel",
        data=buffer,
        file_name="omzetverdeling_vlo.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
