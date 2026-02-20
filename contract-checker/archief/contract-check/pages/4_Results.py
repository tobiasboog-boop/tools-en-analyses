#!/usr/bin/env python3
"""Step 4: Results - View, analyze, and validate classification results."""
import pandas as pd
import streamlit as st

from src.config import config
from src.models import db
from src.models.classification import Classification


# Configure page to use full width
st.set_page_config(layout="wide")

st.title("Resultaten")
st.markdown("Bekijk en analyseer classificatie resultaten.")


def get_classification_results() -> pd.DataFrame:
    """Get all classification results from database."""
    session = db()
    try:
        results = session.query(Classification).order_by(
            Classification.created_at.desc()
        ).all()

        if not results:
            return pd.DataFrame()

        data = [{
            "id": r.id,
            "werkbon_id": r.werkbon_id,
            "hoofdwerkbon_key": r.hoofdwerkbon_key,
            "modus": r.modus or "classificatie",  # Default for old records
            "classificatie": r.classificatie,
            "mapping_score": r.mapping_score,
            "contract_referentie": r.contract_referentie,
            "toelichting": r.toelichting,
            "werkbon_bedrag": r.werkbon_bedrag,
            "werkelijke_classificatie": r.werkelijke_classificatie,
            "created_at": r.created_at,
        } for r in results]
        return pd.DataFrame(data)
    finally:
        session.close()


def get_stats(df: pd.DataFrame) -> dict:
    """Calculate statistics from results dataframe."""
    if df.empty:
        return {}

    total = len(df)
    by_class = df["classificatie"].value_counts()

    return {
        "total": total,
        "ja": by_class.get("JA", 0),
        "nee": by_class.get("NEE", 0),
        "onzeker": by_class.get("ONZEKER", 0),
        "ja_pct": by_class.get("JA", 0) / total * 100,
        "nee_pct": by_class.get("NEE", 0) / total * 100,
        "onzeker_pct": by_class.get("ONZEKER", 0) / total * 100,
        "avg_score": df["mapping_score"].mean(),
    }


# Sidebar
with st.sidebar:
    st.header("Quick Stats")

    df = get_classification_results()
    if not df.empty:
        stats = get_stats(df)
        st.metric("Totaal", stats["total"])

        # Split by modus
        validatie_count = len(df[df["modus"] == "validatie"])
        classificatie_count = len(df[df["modus"] == "classificatie"])

        st.divider()
        st.markdown("**Per modus:**")
        col1, col2 = st.columns(2)
        col1.metric("🔬 Validatie", validatie_count)
        col2.metric("📋 Classificatie", classificatie_count)

        st.divider()
        st.metric("Gem. Score", f"{stats['avg_score']:.2f}")
        st.metric("Onzeker Rate", f"{stats['onzeker_pct']:.1f}%")
    else:
        st.info("Nog geen resultaten")

    st.divider()

    st.markdown("**Doelmetrieken (pilot):**")
    st.caption("Hit rate > 80%")
    st.caption("False negatives < 5%")
    st.caption("Onzeker < 15%")


# Main content
tab1, tab2, tab3, tab4 = st.tabs(["Overzicht", "Alle Resultaten", "Validatie", "Export"])

with tab1:
    st.subheader("Classificatie Overzicht")

    if st.button("Vernieuwen", key="refresh_overview"):
        st.rerun()

    df = get_classification_results()

    if df.empty:
        st.info("Nog geen classificatie resultaten. Voer eerst Stap 3 uit.")
        if st.button("Ga naar Beoordeling"):
            st.switch_page("pages/3_Beoordeling.py")
    else:
        # Filter by modus
        modus_filter = st.radio(
            "Filter op modus",
            options=["Alle", "🔬 Validatie", "📋 Classificatie"],
            horizontal=True,
            index=0
        )

        if modus_filter == "🔬 Validatie":
            df = df[df["modus"] == "validatie"]
        elif modus_filter == "📋 Classificatie":
            df = df[df["modus"] == "classificatie"]

        if df.empty:
            st.info(f"Geen resultaten voor {modus_filter}")
        else:
            stats = get_stats(df)

            # Main metrics
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Totaal", stats["total"])
            col2.metric("Binnen Contract (JA)", stats["ja"], delta=f"{stats['ja_pct']:.1f}%")
            col3.metric("Te Factureren (NEE)", stats["nee"], delta=f"{stats['nee_pct']:.1f}%")
            col4.metric("Onzeker", stats["onzeker"], delta=f"{stats['onzeker_pct']:.1f}%")

            st.divider()

            # Distribution chart
            st.subheader("Classificatie Verdeling")
            chart_data = pd.DataFrame({
                "Classificatie": ["JA", "NEE", "ONZEKER"],
                "Aantal": [stats["ja"], stats["nee"], stats["onzeker"]]
            })
            st.bar_chart(chart_data.set_index("Classificatie"))

            st.divider()

            # Score distribution
            st.subheader("Confidence Score Verdeling")
            # Filter numeric scores and create bins
            numeric_scores = pd.to_numeric(df["mapping_score"], errors='coerce').dropna()
            if not numeric_scores.empty:
                score_bins = pd.cut(numeric_scores, bins=10)
                # Convert interval index to strings for st.bar_chart compatibility
                score_counts = score_bins.value_counts().sort_index()
                score_counts.index = score_counts.index.astype(str)
                st.bar_chart(score_counts)
            else:
                st.info("Geen numerieke scores beschikbaar voor verdeling.")

            st.divider()

            # Hit rate for validation results
            if modus_filter in ["Alle", "🔬 Validatie"]:
                validatie_df = df[df["modus"] == "validatie"] if modus_filter == "Alle" else df
                if not validatie_df.empty and validatie_df["werkelijke_classificatie"].notna().any():
                    st.subheader("🎯 Hit Rate (Validatie)")

                    # Calculate hit rate
                    with_actual = validatie_df[validatie_df["werkelijke_classificatie"].notna()]
                    comparable = with_actual[with_actual["classificatie"].isin(["JA", "NEE"])]

                    if not comparable.empty:
                        correct = (comparable["classificatie"] == comparable["werkelijke_classificatie"]).sum()
                        total = len(comparable)
                        hit_rate = correct / total * 100 if total > 0 else 0

                        # False negatives/positives
                        fn = len(comparable[(comparable["classificatie"] == "JA") & (comparable["werkelijke_classificatie"] == "NEE")])
                        fp = len(comparable[(comparable["classificatie"] == "NEE") & (comparable["werkelijke_classificatie"] == "JA")])
                        fn_rate = fn / total * 100 if total > 0 else 0
                        fp_rate = fp / total * 100 if total > 0 else 0

                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Hit Rate", f"{hit_rate:.1f}%", delta="OK" if hit_rate >= 80 else "< doel")
                        col2.metric("Correct", correct)
                        col3.metric("False Neg", fn, delta=f"{fn_rate:.1f}%", delta_color="inverse" if fn_rate > 5 else "normal")
                        col4.metric("False Pos", fp, delta=f"{fp_rate:.1f}%")

                        if hit_rate >= 80:
                            st.success(f"✅ Hit rate {hit_rate:.1f}% voldoet aan pilot doel (>80%)")
                        else:
                            st.warning(f"⚠️ Hit rate {hit_rate:.1f}% onder pilot doel (>80%)")

            st.divider()

            # Target comparison
            st.subheader("Onzeker Rate")
            target_ok = stats["onzeker_pct"] < 15
            if target_ok:
                st.success(f"Onzeker rate ({stats['onzeker_pct']:.1f}%) onder doel (<15%)")
            else:
                st.warning(f"Onzeker rate ({stats['onzeker_pct']:.1f}%) boven doel (<15%) - verbeter contracten of verlaag threshold")

with tab2:
    st.subheader("Alle Resultaten")

    if st.button("Vernieuwen", key="refresh_all"):
        st.rerun()

    df = get_classification_results()

    if df.empty:
        st.info("Nog geen classificatie resultaten.")
    else:
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            filter_modus = st.multiselect(
                "Filter op modus",
                ["validatie", "classificatie"],
                default=["validatie", "classificatie"]
            )
        with col2:
            filter_class = st.multiselect(
                "Filter op classificatie",
                ["JA", "NEE", "ONZEKER"],
                default=["JA", "NEE", "ONZEKER"]
            )
        with col3:
            min_score = st.slider("Minimum score", 0.0, 1.0, 0.0, 0.05)

        filtered_df = df[
            (df["modus"].isin(filter_modus)) &
            (df["classificatie"].isin(filter_class)) &
            (df["mapping_score"] >= min_score)
        ]

        st.dataframe(
            filtered_df,
            use_container_width=True,
            column_config={
                "modus": st.column_config.TextColumn("Modus"),
                "mapping_score": st.column_config.ProgressColumn(
                    "Score",
                    min_value=0,
                    max_value=1,
                ),
                "created_at": st.column_config.DatetimeColumn("Aangemaakt"),
                "werkelijke_classificatie": st.column_config.TextColumn("Werkelijk"),
            },
            column_order=["werkbon_id", "modus", "classificatie", "werkelijke_classificatie", "mapping_score", "toelichting", "created_at"]
        )
        st.caption(f"Toont {len(filtered_df)} van {len(df)} resultaten")

with tab3:
    st.subheader("Validatie Overzicht")

    st.markdown("""
    **Validatie vs Classificatie:**
    - **Validatie modus**: Werkelijke classificatie automatisch ingevuld (uit opbrengsten)
    - **Classificatie modus**: Werkelijke classificatie nog onbekend (werkbon was openstaand)

    Classificaties van openstaande werkbonnen kunnen later gevalideerd worden
    als de werkbon historisch wordt (retroactieve validatie - fase 2).
    """)

    df = get_classification_results()

    if df.empty:
        st.info("Nog geen classificatie resultaten.")
    else:
        # Split by modus
        validatie_df = df[df["modus"] == "validatie"]
        classificatie_df = df[df["modus"] == "classificatie"]

        col1, col2, col3 = st.columns(3)
        col1.metric("🔬 Validatie runs", len(validatie_df))
        col2.metric("📋 Classificatie runs", len(classificatie_df))
        col3.metric("Te valideren (later)", len(classificatie_df[classificatie_df["werkelijke_classificatie"].isna()]))

        st.divider()

        # Validatie results with hit rate
        if not validatie_df.empty:
            st.subheader("🔬 Validatie Resultaten")
            with_actual = validatie_df[validatie_df["werkelijke_classificatie"].notna()]
            comparable = with_actual[with_actual["classificatie"].isin(["JA", "NEE"])]

            if not comparable.empty:
                correct = (comparable["classificatie"] == comparable["werkelijke_classificatie"]).sum()
                total = len(comparable)
                hit_rate = correct / total * 100 if total > 0 else 0

                fn = len(comparable[(comparable["classificatie"] == "JA") & (comparable["werkelijke_classificatie"] == "NEE")])
                fp = len(comparable[(comparable["classificatie"] == "NEE") & (comparable["werkelijke_classificatie"] == "JA")])

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Hit Rate", f"{hit_rate:.1f}%")
                col2.metric("Correct", correct)
                col3.metric("False Neg (gemiste fact.)", fn)
                col4.metric("False Pos (onterecht fact.)", fp)

                if hit_rate >= 80:
                    st.success(f"✅ Hit rate voldoet aan pilot doel (>80%)")
                else:
                    st.warning(f"⚠️ Hit rate onder pilot doel - verbeter contracten")
            else:
                st.info("Nog geen vergelijkbare validatie resultaten (alleen JA/NEE)")

        st.divider()

        # Classificaties that can be validated later
        needs_validation = classificatie_df[classificatie_df["werkelijke_classificatie"].isna()]
        if not needs_validation.empty:
            st.subheader("📋 Classificaties (nog te valideren)")
            st.info(f"""
            **{len(needs_validation)} classificaties** van openstaande werkbonnen.

            Deze kunnen later gevalideerd worden als de werkbonnen historisch worden
            (retroactieve validatie - fase 2).
            """)

            st.dataframe(
                needs_validation[["werkbon_id", "classificatie", "mapping_score", "toelichting", "created_at"]],
                use_container_width=True,
                column_config={
                    "mapping_score": st.column_config.ProgressColumn("Score", min_value=0, max_value=1),
                    "created_at": st.column_config.DatetimeColumn("Aangemaakt"),
                }
            )

with tab4:
    st.subheader("Export")

    df = get_classification_results()

    if df.empty:
        st.info("Geen resultaten om te exporteren.")
    else:
        st.markdown("Exporteer classificatie resultaten voor verdere analyse of rapportage.")

        # CSV export
        csv = df.to_csv(index=False, sep=";")
        st.download_button(
            "Download as CSV",
            data=csv,
            file_name="classification_results.csv",
            mime="text/csv"
        )

        # Excel export
        try:
            import io
            buffer = io.BytesIO()
            df.to_excel(buffer, index=False, engine="openpyxl")
            buffer.seek(0)

            st.download_button(
                "Download as Excel",
                data=buffer,
                file_name="classification_results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            st.warning(f"Excel export not available: {e}")

        st.divider()

        # Summary report
        st.subheader("Samenvatting Rapport")

        stats = get_stats(df)
        validatie_count = len(df[df["modus"] == "validatie"])
        classificatie_count = len(df[df["modus"] == "classificatie"])

        report = f"""# Classificatie Resultaten Samenvatting

## Overzicht
- Totaal classificaties: {stats['total']}
- Gemiddelde confidence score: {stats['avg_score']:.2f}

## Per Modus
- Validatie runs: {validatie_count}
- Classificatie runs: {classificatie_count}

## Verdeling
- Binnen Contract (JA): {stats['ja']} ({stats['ja_pct']:.1f}%)
- Te Factureren (NEE): {stats['nee']} ({stats['nee_pct']:.1f}%)
- Onzeker: {stats['onzeker']} ({stats['onzeker_pct']:.1f}%)

## Pilot Doelen
- Onzeker rate doel: <15%
- Huidig: {stats['onzeker_pct']:.1f}%
- Status: {'OK' if stats['onzeker_pct'] < 15 else 'Boven doel'}
"""

        st.text_area("Rapport", report, height=300)
        st.download_button(
            "Download Rapport",
            data=report,
            file_name="classificatie_rapport.md",
            mime="text/markdown"
        )
