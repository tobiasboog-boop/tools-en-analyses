import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from config import CHART_COLORS, NAVY_PRIMARY, NAVY_SECONDARY, ACCENT, format_eur, format_eur_full


LAYOUT_DEFAULTS = dict(
    font=dict(family="Segoe UI, Arial, sans-serif", color="#1A1A2E"),
    plot_bgcolor="white",
    paper_bgcolor="white",
    margin=dict(l=40, r=20, t=40, b=40),
    hoverlabel=dict(bgcolor="white", font_size=12),
    separators=",.",  # Dutch: comma for decimal, dot for thousands
)


def bar_omzet_per_jaar(df_unpivot: pd.DataFrame) -> go.Figure:
    """Stacked bar chart: revenue per year, stacked by vestiging."""
    grouped = df_unpivot.groupby(["jaar", "vestiging"])["omzet"].sum().reset_index()

    fig = px.bar(
        grouped,
        x="jaar",
        y="omzet",
        color="vestiging",
        color_discrete_sequence=CHART_COLORS,
        labels={"omzet": "Omzet (€)", "jaar": "Jaar", "vestiging": "Vestiging"},
    )
    fig.update_layout(
        **LAYOUT_DEFAULTS,
        title="Omzet per jaar",
        barmode="stack",
        xaxis=dict(dtick=1),
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5),
    )
    fig.update_yaxes(tickprefix="€ ", tickformat=",.0f")
    return fig


def donut_categorie(df: pd.DataFrame) -> go.Figure:
    """Donut chart: eenmalig vs wederkerend."""
    grouped = df.groupby("categorie")["totaal"].sum().reset_index()

    fig = px.pie(
        grouped,
        values="totaal",
        names="categorie",
        hole=0.5,
        color_discrete_sequence=[NAVY_PRIMARY, ACCENT],
    )
    fig.update_traces(textinfo="percent+label", textposition="outside")
    fig.update_layout(
        **LAYOUT_DEFAULTS,
        title="Eenmalig vs Wederkerend",
        showlegend=False,
    )
    return fig


def bar_top_projecten(df: pd.DataFrame, top_n: int = 10) -> go.Figure:
    """Horizontal bar chart: top N projects by total revenue."""
    top = df.nlargest(top_n, "totaal").sort_values("totaal")

    fig = go.Figure(go.Bar(
        x=top["totaal"],
        y=top["naam"],
        orientation="h",
        marker_color=NAVY_PRIMARY,
        text=[format_eur(v) for v in top["totaal"]],
        textposition="outside",
    ))
    fig.update_layout(
        **LAYOUT_DEFAULTS,
        title=f"Top {top_n} projecten",
        height=max(300, top_n * 40),
    )
    fig.update_xaxes(tickprefix="€ ", tickformat=",.0f")
    return fig


def bar_omzet_per_vestiging(df: pd.DataFrame) -> go.Figure:
    """Bar chart: total revenue per vestiging."""
    grouped = df.groupby("vestiging")["totaal"].sum().sort_values(ascending=True).reset_index()

    fig = go.Figure(go.Bar(
        x=grouped["totaal"],
        y=grouped["vestiging"],
        orientation="h",
        marker_color=NAVY_PRIMARY,
        text=[format_eur(v) for v in grouped["totaal"]],
        textposition="outside",
    ))
    fig.update_layout(
        **LAYOUT_DEFAULTS,
        title="Omzet per vestiging",
        height=max(400, len(grouped) * 28),
    )
    fig.update_xaxes(tickprefix="€ ", tickformat=",.0f")
    return fig


def area_maandelijkse_omzet(
    monthly_df: pd.DataFrame,
    group_by: str = "vestiging",
    cumulative: bool = False,
) -> go.Figure:
    """Stacked area chart: monthly revenue across all projects."""
    grouped = monthly_df.groupby(["maand", group_by])["bedrag"].sum().reset_index()
    grouped = grouped.sort_values("maand")

    if cumulative:
        # Calculate cumulative per group
        grouped["bedrag"] = grouped.groupby(group_by)["bedrag"].cumsum()
        title = "Cumulatieve omzet per maand"
    else:
        title = "Omzet per maand"

    fig = px.area(
        grouped,
        x="maand",
        y="bedrag",
        color=group_by,
        color_discrete_sequence=CHART_COLORS,
        labels={"bedrag": "Omzet (€)", "maand": "Maand", group_by: group_by.capitalize()},
    )
    fig.update_layout(
        **LAYOUT_DEFAULTS,
        title=title,
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5),
    )
    fig.update_yaxes(tickprefix="€ ", tickformat=",.0f")
    return fig


def line_schema_vergelijking(
    total_amount: float,
    start_date,
    end_date,
    schemas: list[str],
    user_schemas: dict | None = None,
) -> go.Figure:
    """Line chart comparing different distribution schemas for a single project."""
    from src.termijnschemas import distribute_revenue

    fig = go.Figure()
    colors = [NAVY_PRIMARY, ACCENT, NAVY_SECONDARY, "#00B894", "#E17055",
              "#2D9CDB", "#7B61FF", "#636E72"]

    for i, schema in enumerate(schemas):
        dist = distribute_revenue(total_amount, start_date, end_date, schema, user_schemas)
        fig.add_trace(go.Scatter(
            x=dist["maand"],
            y=dist["bedrag"],
            mode="lines+markers",
            name=schema,
            line=dict(color=colors[i % len(colors)], width=2),
            marker=dict(size=4),
        ))

    fig.update_layout(
        **LAYOUT_DEFAULTS,
        title="Vergelijking termijnschema's",
        xaxis=dict(title="Maand"),
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5),
    )
    fig.update_yaxes(tickprefix="€ ", tickformat=",.0f", title="Maandbedrag (€)")
    return fig


def line_schema_cumulatief(
    total_amount: float,
    start_date,
    end_date,
    schemas: list[str],
    user_schemas: dict | None = None,
) -> go.Figure:
    """Cumulative line chart comparing schemas."""
    from src.termijnschemas import distribute_revenue

    fig = go.Figure()
    colors = [NAVY_PRIMARY, ACCENT, NAVY_SECONDARY, "#00B894", "#E17055",
              "#2D9CDB", "#7B61FF", "#636E72"]

    for i, schema in enumerate(schemas):
        dist = distribute_revenue(total_amount, start_date, end_date, schema, user_schemas)
        dist["cumulatief"] = dist["bedrag"].cumsum()
        fig.add_trace(go.Scatter(
            x=dist["maand"],
            y=dist["cumulatief"],
            mode="lines",
            name=schema,
            line=dict(color=colors[i % len(colors)], width=2),
        ))

    fig.add_hline(
        y=total_amount,
        line_dash="dash",
        line_color="gray",
        annotation_text=f"Totaal: {format_eur(total_amount)}",
    )

    fig.update_layout(
        **LAYOUT_DEFAULTS,
        title="Cumulatieve verdeling",
        xaxis=dict(title="Maand"),
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5),
    )
    fig.update_yaxes(tickprefix="€ ", tickformat=",.0f", title="Cumulatief (€)")
    return fig
