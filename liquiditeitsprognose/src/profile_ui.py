"""
Forecast Profiel — Streamlit UI Component
==========================================
Profielkiezer + knoppen-paneel voor klant-specifieke forecast instellingen.
"""

import streamlit as st
from datetime import datetime
from typing import Optional, Dict

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    ForecastProfile,
    PROFIEL_LABELS,
    PROFIEL_BESCHRIJVINGEN,
    PROFIEL_DEFAULTS,
    KNOPPEN,
    KNOP_LABELS,
    KNOP_TOOLTIPS,
    KNOP_OPTIES,
)


def render_profile_selector(
    db,
    hist_cashflow=None,
    debiteuren=None,
    klantnummer: str = "",
) -> Optional[ForecastProfile]:
    """Render het profielkiezer-paneel in de sidebar.

    Args:
        db: Database instance (met load/save_forecast_profile methods)
        hist_cashflow: Historische cashflow DataFrame (voor auto-detectie)
        debiteuren: Debiteuren DataFrame (voor auto-detectie)
        klantnummer: Klantnummer

    Returns:
        ForecastProfile met effectieve instellingen, of None.
    """
    st.sidebar.markdown("---")
    st.sidebar.header("Bedrijfsprofiel")

    # === Auto-detectie uitvoeren ===
    suggestion = None
    if hist_cashflow is not None and not hist_cashflow.empty:
        try:
            from src.forecast_v7 import auto_suggest_profile
            suggestion = auto_suggest_profile(hist_cashflow, debiteuren, klantnummer)
        except Exception as e:
            st.sidebar.caption(f"Auto-detectie niet beschikbaar: {e}")

    # === Opgeslagen profiel laden ===
    saved_profile = None
    if db and hasattr(db, 'load_forecast_profile'):
        try:
            saved_profile = db.load_forecast_profile()
        except Exception:
            pass

    # === Modelvoorstel tonen ===
    if suggestion:
        auto_label = PROFIEL_LABELS.get(suggestion['profiel_naam'], suggestion['profiel_naam'])
        det = suggestion['detectie_data']
        st.sidebar.info(
            f"**Modelvoorstel: {auto_label}**\n\n"
            f"{suggestion['reden']}\n\n"
            f"CV: {det['income_cv']:.2f} | "
            f"Frequentie: {det['income_frequency']:.1f}/week | "
            f"Kostenratio: {det['cost_ratio']:.0%}"
        )

    # === Profiel kiezen ===
    profiel_opties = list(PROFIEL_LABELS.keys())
    profiel_labels_list = [PROFIEL_LABELS[k] for k in profiel_opties]

    # Default: opgeslagen > auto-detectie > gemengd
    if saved_profile and saved_profile.manually_set:
        default_idx = profiel_opties.index(saved_profile.profiel_naam) if saved_profile.profiel_naam in profiel_opties else 1
    elif suggestion:
        default_idx = profiel_opties.index(suggestion['profiel_naam']) if suggestion['profiel_naam'] in profiel_opties else 1
    else:
        default_idx = 1  # gemengd

    selected_idx = st.sidebar.selectbox(
        "Profiel",
        range(len(profiel_opties)),
        index=default_idx,
        format_func=lambda i: profiel_labels_list[i],
        help="Kies het bedrijfsprofiel dat het beste past. Dit bepaalt de standaard forecast-instellingen.",
    )
    selected_profiel = profiel_opties[selected_idx]
    st.sidebar.caption(PROFIEL_BESCHRIJVINGEN[selected_profiel])

    # Bepaal of er handmatig is gewijzigd
    is_manual = True
    if suggestion and selected_profiel == suggestion['profiel_naam']:
        is_manual = False  # Klant volgt het voorstel

    # === Geavanceerde instellingen ===
    profile = ForecastProfile(
        klantnummer=klantnummer,
        profiel_naam=selected_profiel,
        auto_detected=suggestion['profiel_naam'] if suggestion else '',
        manually_set=is_manual,
    )

    with st.sidebar.expander("Geavanceerde instellingen", expanded=False):
        defaults = PROFIEL_DEFAULTS[selected_profiel]

        # Laad opgeslagen overrides als het profiel overeenkomt
        saved_overrides = {}
        if saved_profile and saved_profile.profiel_naam == selected_profiel:
            for knop in KNOPPEN:
                val = getattr(saved_profile, knop, None)
                if val is not None:
                    saved_overrides[knop] = val

        # --- Realiteit-horizon (slider) ---
        knop = "realiteit_horizon_weken"
        opts = KNOP_OPTIES[knop]
        saved_val = saved_overrides.get(knop, defaults[knop])
        val = st.slider(
            KNOP_LABELS[knop],
            min_value=opts["min"],
            max_value=opts["max"],
            value=saved_val,
            step=opts["step"],
            help=KNOP_TOOLTIPS[knop],
        )
        if val != defaults[knop]:
            profile.realiteit_horizon_weken = val
            profile.manually_set = True

        # --- Outlier-gevoeligheid (selectbox) ---
        knop = "outlier_iqr_multiplier"
        opts = KNOP_OPTIES[knop]
        choices_vals = [c[0] for c in opts["choices"]]
        choices_labels = [c[1] for c in opts["choices"]]
        saved_val = saved_overrides.get(knop, defaults[knop])
        default_choice_idx = choices_vals.index(saved_val) if saved_val in choices_vals else 1
        choice_idx = st.selectbox(
            KNOP_LABELS[knop],
            range(len(choices_vals)),
            index=default_choice_idx,
            format_func=lambda i: choices_labels[i],
            help=KNOP_TOOLTIPS[knop],
        )
        val = choices_vals[choice_idx]
        if val != defaults[knop]:
            profile.outlier_iqr_multiplier = val
            profile.manually_set = True

        # --- Run rate methode (selectbox) ---
        knop = "run_rate_methode"
        opts = KNOP_OPTIES[knop]
        choices_vals = [c[0] for c in opts["choices"]]
        choices_labels = [c[1] for c in opts["choices"]]
        saved_val = saved_overrides.get(knop, defaults[knop])
        default_choice_idx = choices_vals.index(saved_val) if saved_val in choices_vals else 0
        choice_idx = st.selectbox(
            KNOP_LABELS[knop],
            range(len(choices_vals)),
            index=default_choice_idx,
            format_func=lambda i: choices_labels[i],
            help=KNOP_TOOLTIPS[knop],
        )
        val = choices_vals[choice_idx]
        if val != defaults[knop]:
            profile.run_rate_methode = val
            profile.manually_set = True

        # --- Nieuwe facturatie (slider) ---
        knop = "nieuwe_facturatie_pct"
        opts = KNOP_OPTIES[knop]
        saved_val = saved_overrides.get(knop, defaults[knop])
        val = st.slider(
            KNOP_LABELS[knop],
            min_value=opts["min"],
            max_value=opts["max"],
            value=saved_val,
            step=opts["step"],
            format="%.0f%%",
            help=KNOP_TOOLTIPS[knop],
        )
        if val != defaults[knop]:
            profile.nieuwe_facturatie_pct = val
            profile.manually_set = True

        # --- Orderportefeuille (toggle) ---
        knop = "gebruik_pijplijn"
        saved_val = saved_overrides.get(knop, defaults[knop])
        val = st.toggle(
            KNOP_LABELS[knop],
            value=saved_val,
            help=KNOP_TOOLTIPS[knop],
        )
        if val != defaults[knop]:
            profile.gebruik_pijplijn = val
            profile.manually_set = True

        # --- Servicecontracten (toggle) ---
        knop = "gebruik_recurring_revenue"
        saved_val = saved_overrides.get(knop, defaults[knop])
        val = st.toggle(
            KNOP_LABELS[knop],
            value=saved_val,
            help=KNOP_TOOLTIPS[knop],
        )
        if val != defaults[knop]:
            profile.gebruik_recurring_revenue = val
            profile.manually_set = True

        # === Opslaan / Reset knoppen ===
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Opslaan", use_container_width=True, type="primary"):
                profile.laatst_gewijzigd = datetime.now().isoformat()
                profile.gewijzigd_door = "gebruiker"
                if db and hasattr(db, 'save_forecast_profile'):
                    if db.save_forecast_profile(profile):
                        st.success("Profiel opgeslagen")
                        st.rerun()
                    else:
                        st.error("Opslaan mislukt")
                else:
                    st.warning("Geen database verbinding")

        with col2:
            if st.button("Reset", use_container_width=True):
                if db and hasattr(db, 'delete_forecast_profile'):
                    db.delete_forecast_profile()
                    st.info("Profiel gereset naar modelvoorstel")
                    st.rerun()

    # Toon actief profiel samenvatting
    if profile.manually_set:
        st.sidebar.caption(f"Profiel: **{PROFIEL_LABELS[selected_profiel]}** (aangepast)")
    else:
        st.sidebar.caption(f"Profiel: **{PROFIEL_LABELS[selected_profiel]}** (modelvoorstel)")

    return profile


def render_profile_info_card(metadata: dict):
    """Toon een info-card met het actieve profiel in de main content area.

    Args:
        metadata: Forecast metadata dict (uit create_forecast_v7)
    """
    bp = metadata.get('business_profile', {})
    if not bp:
        return

    effective = bp.get('effective_settings', {})
    auto_type = bp.get('auto_detected', '')
    is_overridden = bp.get('manually_overridden', False)

    type_labels = {
        'project_based': 'Projectmatig',
        'stable': 'Onderhoud & Service',
        'mixed': 'Gemengd',
    }
    profiel_label = type_labels.get(bp.get('type', ''), bp.get('type', 'Onbekend'))
    auto_label = type_labels.get(auto_type, auto_type)

    with st.expander("Actief bedrijfsprofiel", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"**Actief profiel:** {profiel_label}")
            if is_overridden:
                st.caption(f"Modelvoorstel was: {auto_label} — handmatig aangepast")
            else:
                st.caption("Automatisch gedetecteerd op basis van uw administratie")

            st.markdown(f"""
| Instelling | Waarde |
|------------|--------|
| Realiteit-horizon | {effective.get('realiteit_horizon_weken', '?')} weken |
| Outlier-filter | {effective.get('outlier_iqr_multiplier', '?')}x IQR |
| Run rate methode | {effective.get('run_rate_methode', '?')} |
| Nieuwe facturatie | {effective.get('nieuwe_facturatie_pct', 0):.0%} |
| Orderportefeuille | {'Aan' if effective.get('gebruik_pijplijn') else 'Uit'} |
| Servicecontracten | {'Aan' if effective.get('gebruik_recurring_revenue') else 'Uit'} |
""")

        with col2:
            st.markdown("**Detectie-statistieken:**")
            cv = bp.get('income_cv', 0)
            freq = bp.get('income_frequency', 0)
            cost = bp.get('cost_ratio', 0)

            # Visuele indicatoren
            if cv < 0.25:
                cv_bar = "🟢 Laag"
            elif cv < 0.50:
                cv_bar = "🟡 Gemiddeld"
            else:
                cv_bar = "🔴 Hoog"

            st.markdown(f"""
| Metric | Waarde | Beoordeling |
|--------|--------|-------------|
| Volatiliteit (CV) | {cv:.2f} | {cv_bar} |
| Facturatiefrequentie | {freq:.1f}/week | {'Regelmatig' if freq > 3.5 else 'Wisselend' if freq > 2 else 'Onregelmatig'} |
| Kostenratio | {cost:.0%} | {'Gezond' if cost < 0.90 else 'Hoog' if cost < 1.0 else 'Boven 100%'} |
""")
