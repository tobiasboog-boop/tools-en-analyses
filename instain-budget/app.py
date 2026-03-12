"""
Instain Budgetanalyse - Prototype
Interactief dashboard voor budgetbewaking onderhoudscontract Rentree.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

from data_loader import load_all, MAAND_NAMEN
from calculations import (
    realisatie_per_maand,
    totalen_per_blok,
    aantallen_per_type,
    detail_werkbonnen,
    onbenoemde_wb_posten,
)

# --- Page Config ---
st.set_page_config(
    page_title="Instain Budgetanalyse",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Styling ---
st.markdown("""
<style>
    .stMetric {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #16136F;
    }
    .block-header {
        background: linear-gradient(135deg, #16136F 0%, #3636A2 100%);
        color: white;
        padding: 8px 16px;
        border-radius: 6px;
        margin: 16px 0 8px 0;
        font-weight: 600;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.4rem;
    }
</style>
""", unsafe_allow_html=True)


# --- Data Loading ---
DATA_DIR = Path(__file__).parent / "data"
PARQUET_FILES = {
    "werkbonnen": DATA_DIR / "werkbonnen.parquet",
    "klantrekeningen": DATA_DIR / "klantrekeningen.parquet",
    "config": DATA_DIR / "rapportage_config.parquet",
}


@st.cache_data
def load_from_parquet() -> dict:
    """Laad data uit Parquet-bestanden (snel, standaard)."""
    return {
        "werkbonnen": pd.read_parquet(PARQUET_FILES["werkbonnen"]),
        "klantrekeningen": pd.read_parquet(PARQUET_FILES["klantrekeningen"]),
        "config": pd.read_parquet(PARQUET_FILES["config"]),
    }


@st.cache_data
def load_from_excel(file_path: str) -> dict:
    """Laad data uit Excel-bestand (bij nieuwe upload)."""
    return load_all(file_path)


@st.cache_data
def compute_realisatie(_wb, _kl, _cfg, jaar):
    """Bereken en cache realisatie per maand."""
    return realisatie_per_maand(_wb, _kl, _cfg, jaar)


def format_euro(val: float) -> str:
    """Format als euro bedrag."""
    if pd.isna(val) or val == 0:
        return "-"
    return f"\u20ac {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def parquet_available() -> bool:
    return all(p.exists() for p in PARQUET_FILES.values())


# --- Sidebar ---
logo_path = Path(__file__).parent / "assets" / "notifica-logo-kleur.svg"
if logo_path.exists():
    st.sidebar.image(str(logo_path), width=140)
st.sidebar.title("Budgetanalyse")

# Data laden: parquet als standaard, upload voor nieuwe data
if parquet_available():
    st.sidebar.success("Data geladen (Parquet)")

    with st.sidebar.expander("Nieuwe Syntess-export uploaden"):
        uploaded_file = st.file_uploader(
            "Vervangt de huidige dataset",
            type=["xlsm", "xlsx"],
            help="Upload een nieuw budgetanalyse Excel-bestand om de data bij te werken",
        )
else:
    uploaded_file = st.sidebar.file_uploader(
        "Upload Syntess-export (.xlsm/.xlsx)",
        type=["xlsm", "xlsx"],
        help="Upload je budgetanalyse Excel-bestand",
    )

if uploaded_file:
    # Sla Excel op en laad vanuit Excel
    DATA_DIR.mkdir(exist_ok=True)
    save_path = DATA_DIR / uploaded_file.name
    save_path.write_bytes(uploaded_file.getvalue())
    try:
        data = load_from_excel(str(save_path))
        st.sidebar.success(f"Nieuw bestand geladen: {uploaded_file.name}")
    except Exception as e:
        st.error(f"Fout bij laden bestand: {e}")
        st.stop()
elif parquet_available():
    try:
        data = load_from_parquet()
    except Exception as e:
        st.error(f"Fout bij laden Parquet-data: {e}")
        st.stop()
else:
    st.warning("Geen data beschikbaar. Upload een Syntess-export via de sidebar.")
    st.stop()

wb = data["werkbonnen"]
kl = data["klantrekeningen"]
cfg = data["config"]

# Jaar selectie
beschikbare_jaren = sorted(wb["jaar"].dropna().unique().astype(int), reverse=True)
jaar = st.sidebar.selectbox("Jaar", beschikbare_jaren, index=0)

# Blok filter
blokken = ["Alle"] + sorted(cfg["blok"].unique().tolist())
selected_blok = st.sidebar.selectbox("Categorie", blokken)

# Bereken realisatie
realisatie = compute_realisatie(wb, kl, cfg, jaar)

# Filter op blok
if selected_blok != "Alle":
    realisatie_filtered = realisatie[realisatie["blok"] == selected_blok]
else:
    realisatie_filtered = realisatie

# Bepaal beschikbare maanden (maanden met data > 0)
maand_cols = [m for m in MAAND_NAMEN if realisatie[m].sum() > 0]
if not maand_cols:
    maand_cols = MAAND_NAMEN[:2]  # Fallback

# --- Tabs ---
tab_dashboard, tab_rapportage, tab_analyse, tab_detail, tab_over = st.tabs([
    "Dashboard", "Rapportage", "Analyse", "Data & Detail", "Over dit prototype",
])


# ==========================================
# TAB 1: DASHBOARD
# ==========================================
with tab_dashboard:
    st.header("Budgetoverzicht")

    # KPI tegels
    totaal_realisatie = realisatie_filtered[maand_cols].sum().sum()
    totaal_realisatie_vorige = realisatie_filtered[maand_cols[:-1]].sum().sum() if len(maand_cols) > 1 else 0

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Totaal realisatie",
            format_euro(totaal_realisatie),
            help="Som van alle gefactureerde bedragen dit jaar",
        )

    with col2:
        if maand_cols:
            laatste_maand = maand_cols[-1]
            maand_totaal = realisatie_filtered[laatste_maand].sum()
            vorige_maand = realisatie_filtered[maand_cols[-2]].sum() if len(maand_cols) > 1 else 0
            delta = maand_totaal - vorige_maand if vorige_maand > 0 else None
            st.metric(
                f"Realisatie {laatste_maand}",
                format_euro(maand_totaal),
                delta=format_euro(delta) if delta else None,
            )

    with col3:
        wb_totaal = realisatie_filtered[realisatie_filtered["bron"] == "WB"][maand_cols].sum().sum()
        st.metric(
            "Variabele kosten (WB)",
            format_euro(wb_totaal),
            help="Werkbonnen - variabele kosten",
        )

    with col4:
        kl_totaal = realisatie_filtered[realisatie_filtered["bron"] == "KL"][maand_cols].sum().sum()
        st.metric(
            "Vaste kosten (KL)",
            format_euro(kl_totaal),
            help="Klantrekeningen - vaste contractkosten",
        )

    st.divider()

    # Grafiek: maandelijks per blok
    chart_data = totalen_per_blok(realisatie_filtered)
    chart_melted = chart_data.melt(
        id_vars=["blok"],
        value_vars=maand_cols,
        var_name="Maand",
        value_name="Bedrag",
    )

    fig = px.bar(
        chart_melted,
        x="Maand",
        y="Bedrag",
        color="blok",
        title="Realisatie per maand per categorie",
        labels={"Bedrag": "Bedrag incl. BTW (\u20ac)", "blok": "Categorie"},
        color_discrete_sequence=["#16136F", "#3636A2", "#5E5EC7", "#8B8BD4", "#B8B8E5"],
    )
    fig.update_layout(
        barmode="stack",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        yaxis_tickformat="\u20ac,.0f",
        height=450,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Verdeling per blok (donut)
    col_left, col_right = st.columns(2)

    with col_left:
        blok_totalen = totalen_per_blok(realisatie)
        blok_totalen["som"] = blok_totalen[maand_cols].sum(axis=1)
        fig_donut = px.pie(
            blok_totalen,
            values="som",
            names="blok",
            title="Verdeling per categorie",
            hole=0.4,
            color_discrete_sequence=["#16136F", "#3636A2", "#5E5EC7", "#8B8BD4", "#B8B8E5"],
        )
        fig_donut.update_traces(textposition="inside", textinfo="percent+label")
        fig_donut.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig_donut, use_container_width=True)

    with col_right:
        # Top 10 opdrachten
        top_opdrachten = (
            realisatie[["categorie", "blok"] + maand_cols]
            .assign(totaal=lambda df: df[maand_cols].sum(axis=1))
            .nlargest(10, "totaal")
        )
        fig_bar = px.bar(
            top_opdrachten,
            x="totaal",
            y="categorie",
            orientation="h",
            title="Top 10 opdrachten",
            color="blok",
            labels={"totaal": "Bedrag (\u20ac)", "categorie": ""},
            color_discrete_sequence=["#16136F", "#3636A2", "#5E5EC7", "#8B8BD4", "#B8B8E5"],
        )
        fig_bar.update_layout(
            height=400,
            yaxis=dict(autorange="reversed"),
            showlegend=False,
            xaxis_tickformat="\u20ac,.0f",
        )
        st.plotly_chart(fig_bar, use_container_width=True)


# ==========================================
# TAB 2: RAPPORTAGE
# ==========================================
with tab_rapportage:
    st.header("Rapportage - Budget vs Realisatie")

    # Bouw de rapportagetabel per blok
    blok_order = [
        "Preventief onderhoud",
        "Reparatie onderhoud",
        "Planmatig onderhoud",
        "Dagelijks onderhoud",
        "Specifieke opdrachten",
    ]

    for blok in blok_order:
        if selected_blok != "Alle" and blok != selected_blok:
            continue

        st.markdown(f'<div class="block-header">{blok}</div>', unsafe_allow_html=True)

        blok_data = realisatie[realisatie["blok"] == blok].copy()

        if blok_data.empty:
            st.info("Geen data voor dit blok.")
            continue

        # Maak display tabel
        display_cols = ["code", "categorie", "bron"] + maand_cols + ["totaal"]
        display_df = blok_data[display_cols].copy()

        # Totaalrij
        totaal_row = pd.DataFrame([{
            "code": "",
            "categorie": f"Totaal {blok}",
            "bron": "",
            **{m: blok_data[m].sum() for m in maand_cols},
            "totaal": blok_data["totaal"].sum(),
        }])
        display_df = pd.concat([display_df, totaal_row], ignore_index=True)

        # Format
        format_dict = {m: "{:,.2f}" for m in maand_cols}
        format_dict["totaal"] = "{:,.2f}"

        # Kleurcodering via styling
        def highlight_row(row):
            if row["categorie"].startswith("Totaal"):
                return ["font-weight: bold; background-color: #e8e8f0;"] * len(row)
            return [""] * len(row)

        styled = (
            display_df.style
            .apply(highlight_row, axis=1)
            .format(format_dict, na_rep="-")
        )

        st.dataframe(
            styled,
            use_container_width=True,
            hide_index=True,
            height=min(35 * (len(display_df) + 1), 500),
        )

    # Grand total
    st.markdown('<div class="block-header">Totaal alle categorieen</div>', unsafe_allow_html=True)
    grand_total = {m: realisatie[m].sum() for m in maand_cols}
    grand_total["totaal"] = sum(grand_total.values())
    gt_df = pd.DataFrame([{
        "": "TOTAAL",
        **{m: f"\u20ac {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") for m, v in grand_total.items()},
    }])
    st.dataframe(gt_df, use_container_width=True, hide_index=True)


# ==========================================
# TAB 3: ANALYSE
# ==========================================
with tab_analyse:
    st.header("Analyses")

    analyse_keuze = st.radio(
        "Kies analyse",
        ["Maandvergelijking", "Aantallen per storingstype", "Verdeling per opdracht"],
        horizontal=True,
    )

    if analyse_keuze == "Maandvergelijking":
        st.subheader("Maandelijkse vergelijking per categorie")

        # Lijngrafieken per blok
        for blok in blok_order:
            blok_data = realisatie[realisatie["blok"] == blok]
            if blok_data.empty:
                continue

            blok_totals = blok_data[maand_cols].sum()

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=maand_cols,
                y=blok_totals.values,
                mode="lines+markers",
                name="Realisatie",
                line=dict(color="#16136F", width=3),
                marker=dict(size=8),
            ))
            fig.update_layout(
                title=blok,
                yaxis_tickformat="\u20ac,.0f",
                height=300,
                margin=dict(t=40, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)

    elif analyse_keuze == "Aantallen per storingstype":
        st.subheader("Aantal werkbonnen per storingstype")

        aantallen = aantallen_per_type(wb, jaar)
        if aantallen.empty:
            st.info("Geen storingstype-data beschikbaar.")
        else:
            # Top 15 storingstypen
            top_types = aantallen.head(15)
            avail_maanden = [m for m in maand_cols if m in top_types.columns]

            fig = px.bar(
                top_types.melt(
                    id_vars=["Titel"],
                    value_vars=avail_maanden,
                    var_name="Maand",
                    value_name="Aantal",
                ),
                x="Maand",
                y="Aantal",
                color="Titel",
                title="Top 15 storingstypen per maand",
                barmode="stack",
                height=500,
            )
            st.plotly_chart(fig, use_container_width=True)

            # Tabel
            st.dataframe(top_types, use_container_width=True, hide_index=True)

    elif analyse_keuze == "Verdeling per opdracht":
        st.subheader("Verdeling per opdracht")

        # Treemap
        tree_data = realisatie[realisatie["totaal"] > 0].copy()
        if not tree_data.empty:
            fig = px.treemap(
                tree_data,
                path=["blok", "categorie"],
                values="totaal",
                title="Verdeling kosten per opdracht",
                color="blok",
                color_discrete_sequence=["#16136F", "#3636A2", "#5E5EC7", "#8B8BD4", "#B8B8E5"],
            )
            fig.update_layout(height=600)
            st.plotly_chart(fig, use_container_width=True)


# ==========================================
# TAB 4: DATA & DETAIL
# ==========================================
with tab_detail:
    st.header("Data & Detail")

    detail_keuze = st.radio(
        "Weergave",
        ["Drill-down per opdracht", "Ruwe werkbonnen", "Data-kwaliteit"],
        horizontal=True,
    )

    if detail_keuze == "Drill-down per opdracht":
        st.subheader("Drill-down: bekijk onderliggende werkbonnen")

        # Selecteer opdracht
        wb_opdrachten = cfg[cfg["bron"] == "WB"].copy()
        opdracht_opties = {
            f"{row['code']} - {row['categorie'][:50]}": idx
            for idx, row in wb_opdrachten.iterrows()
        }

        selected_opdracht = st.selectbox(
            "Selecteer opdracht",
            list(opdracht_opties.keys()),
        )

        if selected_opdracht:
            idx = opdracht_opties[selected_opdracht]
            config_row = cfg.loc[idx]

            # Optioneel maandfilter
            maand_filter = st.selectbox(
                "Filter op maand (optioneel)",
                ["Alle maanden"] + maand_cols,
            )
            maand_val = None if maand_filter == "Alle maanden" else maand_filter

            details = detail_werkbonnen(wb, config_row, maand=maand_val, jaar=jaar)

            if details.empty:
                st.info("Geen werkbonnen gevonden voor deze selectie.")
            else:
                st.write(f"**{len(details)} werkbonnen** | Totaal: {format_euro(details['bedrag_incl_btw'].sum())}")
                st.dataframe(
                    details.style.format({"bedrag_incl_btw": "{:,.2f}"}),
                    use_container_width=True,
                    hide_index=True,
                    height=min(35 * (len(details) + 1), 600),
                )

    elif detail_keuze == "Ruwe werkbonnen":
        st.subheader("Alle werkbonnen")

        # Zoekfunctie
        zoek = st.text_input("Zoek op adres, titel of werkbonnummer")

        wb_display = wb[wb["jaar"] == jaar].copy()
        if zoek:
            mask = (
                wb_display["Adres"].astype(str).str.contains(zoek, case=False, na=False)
                | wb_display["Titel"].astype(str).str.contains(zoek, case=False, na=False)
                | wb_display["Nummer"].astype(str).str.contains(zoek, case=False, na=False)
            )
            wb_display = wb_display[mask]

        display_cols_wb = [
            "Nummer", "Adres", "Titel", "Project", "Referentie",
            "Gereedmeld-datum", "bedrag_incl_btw", "maand_naam",
        ]
        available = [c for c in display_cols_wb if c in wb_display.columns]

        st.write(f"**{len(wb_display)} werkbonnen**")
        st.dataframe(
            wb_display[available].sort_values("Gereedmeld-datum", ascending=False),
            use_container_width=True,
            hide_index=True,
            height=600,
        )

    elif detail_keuze == "Data-kwaliteit":
        st.subheader("Data-kwaliteit controle")

        # Controle totalen
        wb_jaar = wb[wb["jaar"] == jaar]
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Werkbonnen (WB)**")
            wb_total = wb_jaar["bedrag_incl_btw"].sum()
            wb_rapport = realisatie[realisatie["bron"] == "WB"]["totaal"].sum()
            verschil_wb = wb_total - wb_rapport
            st.metric("Totaal uit WB-data", format_euro(wb_total))
            st.metric("Totaal in Rapportage", format_euro(wb_rapport))
            if abs(verschil_wb) > 10:
                st.warning(f"Verschil: {format_euro(verschil_wb)}")
            else:
                st.success("Totalen komen overeen")

        with col2:
            st.markdown("**Klantrekeningen (KL)**")
            kl_total = kl["bedrag_incl_btw"].sum()
            kl_rapport = realisatie[realisatie["bron"] == "KL"]["totaal"].sum()
            verschil_kl = kl_total - kl_rapport
            st.metric("Totaal uit KL-data", format_euro(kl_total))
            st.metric("Totaal in Rapportage", format_euro(kl_rapport))
            if abs(verschil_kl) > 10:
                st.warning(f"Verschil: {format_euro(verschil_kl)}")
            else:
                st.success("Totalen komen overeen")

        # Niet-gekoppelde werkbonnen
        st.divider()
        st.markdown("**Niet-gekoppelde werkbonnen**")
        st.caption("Werkbonnen die niet aan een bekende opdracht gekoppeld zijn")

        known_refs = set(cfg["opdracht_nr"].dropna().unique())
        known_refs.update(cfg["ref_2025"].dropna().unique())
        known_refs.discard("nan")

        unmatched = wb_jaar[
            ~(wb_jaar["Referentie"].isin(known_refs) | wb_jaar["Project"].isin(known_refs))
        ]

        if unmatched.empty:
            st.success("Alle werkbonnen zijn gekoppeld!")
        else:
            st.warning(f"{len(unmatched)} werkbonnen niet gekoppeld ({format_euro(unmatched['bedrag_incl_btw'].sum())})")
            display_cols_um = ["Nummer", "Adres", "Titel", "Project", "Referentie", "bedrag_incl_btw"]
            available_um = [c for c in display_cols_um if c in unmatched.columns]
            st.dataframe(
                unmatched[available_um].sort_values("bedrag_incl_btw", ascending=False),
                use_container_width=True,
                hide_index=True,
                height=400,
            )


# ==========================================
# TAB 5: OVER DIT PROTOTYPE
# ==========================================
with tab_over:
    st.header("Waarom deze tool?")

    st.markdown("""
    Jullie werken nu met een Excel-bestand dat maandelijks handmatig gevuld wordt met
    Syntess-exports. Dat werkt, maar het is kwetsbaar: formules kunnen breken, er sluipen
    fouten in bij het kopieren, en niemand durft de structuur aan te passen. Bovendien is
    het bestand alleen lokaal beschikbaar en is er geen versiebeheer.

    **Deze tool lost dat op.** Dezelfde budgetbewaking, maar dan:

    - **Betrouwbaar** — alle berekeningen zijn geautomatiseerd en getest tegen de Excel-uitkomsten
    - **Overal beschikbaar** — draait in de browser, geen installatie nodig
    - **Altijd actueel** — data wordt automatisch opgehaald uit Syntess
    - **Inzichtelijk** — drill-down op elk bedrag, interactieve grafieken, filters
    """)

    st.divider()

    st.subheader("Wat je nu ziet (prototype)")

    st.markdown("""
    Dit is een **werkend prototype** op basis van jullie eigen data (februari 2026).
    Alles wat je ziet is echt — geen mockups, geen dummy-data.

    | Tabblad | Wat het doet |
    |---------|-------------|
    | **Dashboard** | KPI-tegels, maandoverzicht per categorie, top 10 opdrachten |
    | **Rapportage** | De volledige budget-vs-realisatie matrix, per blok, met totalen |
    | **Analyse** | Maandvergelijking, storingstypen, treemap van kosten |
    | **Data & Detail** | Drill-down per opdracht, werkbonnen zoeken, datakwaliteit checks |

    De berekeningen zijn 1-op-1 nagerekend tegen het Excel-bestand. Daarbij zijn drie
    rekenfouten in het Excel-bestand gevonden (hardcoded waarden en dubbeltellingen
    door gedeelde referenties) — die zijn in deze tool gecorrigeerd.
    """)

    st.warning("""
    **Let op:** Dit prototype werkt op een eenmalige snapshot van jullie data.
    Nieuwe maanden vereisen nu nog een handmatige Excel-upload.
    In de productieversie vervalt dit volledig — zie hieronder.
    """)

    st.divider()

    st.subheader("Wat de productieversie toevoegt")

    st.markdown("---")
    st.markdown("#### Directe Syntess-koppeling")
    st.markdown("""
    De grootste winst zit in het wegvallen van handmatig werk. In de productieversie
    koppelen we **rechtstreeks op jullie Syntess data warehouse**. Dat betekent:

    - **Geen exports meer** — werkbonnen en klantrekeningen worden automatisch opgehaald
    - **Altijd actuele cijfers** — elke keer dat je de tool opent, zie je de laatste stand
    - **Geen uploadfouten** — niemand hoeft meer bestanden te kopieren of te slepen
    - **Meerdere contracten** — niet alleen Rentree, maar elk contract dat in Syntess staat

    De koppeling loopt via onze beveiligde Data API. Jullie Syntess-data verlaat
    het eigen netwerk niet — de tool leest mee, maar slaat niks op.
    """)

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        #### Uitgebreide analyses
        - **Prognose** — cumulatieve verwachting per opdracht tot jaareinde
        - **Eenheidsprijzen** — gemiddelde kosten per storingstype, trendlijn
        - **First Time Fix** — percentage eerste-bezoek-oplossingen (target 85%)
        - **Jaar-op-jaar** — vergelijk 2025 vs 2026 per categorie
        - **PDF-export** — maandrapportage als PDF, direct te delen
        """)

    with col2:
        st.markdown("""
        #### Beveiliging & beheer
        - **Inloggen met wachtwoord** — per gebruiker, niet een gedeeld bestand
        - **Budgetbeheer** — budgetten invoeren en aanpassen per opdracht
        - **Onderhanden werk** — kolom voor werk dat nog niet gefactureerd is
        - **Datavalidatie** — automatische controles bij elke sync
        - **Audit trail** — wie heeft wat bekeken of gewijzigd
        """)

    st.divider()

    st.subheader("Volgende stap")

    st.info("""
    We plannen een korte demo-sessie om dit prototype samen door te lopen. Daarin
    bespreken we welke onderdelen voor jullie het meest waardevol zijn, zodat we
    de productieversie daarop kunnen inrichten.
    """)


# --- Footer ---
st.sidebar.divider()
st.sidebar.caption("Instain Budgetanalyse v0.1 | Powered by Notifica")
