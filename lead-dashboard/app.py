"""
Notifica Sales Dashboard
========================
Leads bellen, klanten bellen, campagneresultaten bekijken.
"""
import streamlit as st
import pandas as pd
import io
import os
from datetime import datetime
from dotenv import load_dotenv

from config import FUNNEL_CONFIG, INTERNE_MEDEWERKERS
from data import (
    get_secret,
    fetch_emailoctopus_subscribers, fetch_pipedrive_persons,
    fetch_pipedrive_deals, fetch_pipedrive_stages,
    fetch_emailoctopus_campaign_activity,
    load_web_visitors, load_powerbi_data, save_powerbi_cache, validate_powerbi_data,
    build_leads_df, calculate_customer_health, get_customer_contacts,
    load_campaign_data, load_campaign_activity, fetch_leadfeeder_leads,
    save_pipedrive_note, update_pipedrive_deal_stage,
    fetch_pipedrive_person_notes, generate_nid,
    load_manual_bellijst, save_manual_bellijst, update_pipedrive_person_phone,
    POWERBI_EXCEL_DEFAULT, POWERBI_CACHE_PATH,
)

load_dotenv()

st.set_page_config(
    page_title="Notifica Sales Dashboard",
    page_icon="N",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Custom CSS ---
st.markdown("""
<style>
    .main .block-container { padding-top: 1.5rem; }

    /* Metric cards */
    [data-testid="metric-container"] {
        background: linear-gradient(135deg, #f8f9fc 0%, #fff 100%);
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 0.8rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-size: 1.6rem;
        font-weight: 700;
    }

    /* Status dots */
    .status-rood { color: #dc2626; font-weight: bold; }
    .status-oranje { color: #ea580c; font-weight: bold; }
    .status-groen { color: #16a34a; font-weight: bold; }

</style>
""", unsafe_allow_html=True)


# --- Authentication ---

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if st.session_state.authenticated:
        return True

    st.markdown("""
    <div style="text-align: center; padding: 60px 0 20px 0;">
        <h1 style="color: #16136F;">Notifica Sales Dashboard</h1>
        <p style="color: #666; font-size: 1.1rem;">Login om verder te gaan</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        password = st.text_input("Wachtwoord", type="password")
        if st.button("Inloggen", use_container_width=True):
            expected = get_secret("APP_PASSWORD")
            if expected and password == expected:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Onjuist wachtwoord")
    return False


if not check_password():
    st.stop()


# --- Microsoft Clarity ---
st.components.v1.html("""
<script type="text/javascript">
    (function(c,l,a,r,i,t,y){
        c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};
        t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
        y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
    })(window, document, "clarity", "script", "vmymrfb2j3");
</script>
""", height=0)


# ============================================================
#  SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 10px 0 20px 0;">
        <h2 style="color: #16136F; margin: 0;">Notifica</h2>
        <p style="color: #666; font-size: 0.85rem; margin: 4px 0 0 0;">Sales Dashboard</p>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    rol = st.radio(
        "Wie ben je?",
        ["Tobias", "Arthur", "Overzicht"],
        index=0,
        key="rol_sidebar",
    )

    st.divider()

    pagina = st.radio(
        "Pagina",
        ["Mijn Week", "Overzicht", "Data & Details"],
        index=0,
        key="pagina_sidebar",
    )

    st.divider()

    # Compacte data status
    st.caption("Databronnen")


# ============================================================
#  LOAD DATA
# ============================================================

with st.spinner("Data ophalen..."):
    ml_df, ml_status = fetch_emailoctopus_subscribers()
    pd_df = fetch_pipedrive_persons()
    deals_dict = fetch_pipedrive_deals()
    stages_dict = fetch_pipedrive_stages()  # {stage_id: stage_name}
    web_mapping, web_source, web_summary, web_df, identified_df = load_web_visitors()
    pbi_df, pbi_source, pbi_status = load_powerbi_data()
    lf_df = fetch_leadfeeder_leads(days=30)

# Status in sidebar
with st.sidebar:
    status_items = [
        ("EmailOctopus", ml_status == "ok", f"{len(ml_df)}" if ml_status == "ok" else ml_status),
        ("Pipedrive", not pd_df.empty, f"{len(pd_df)}" if not pd_df.empty else "geen"),
        ("Power BI", pbi_df is not None and not pbi_df.empty,
         f"{pbi_df['Pipedrive organisatie'].nunique()}" if pbi_df is not None and not pbi_df.empty else "geen (upload Excel)"),
        ("Deals", bool(deals_dict), f"{len(deals_dict)}" if deals_dict else "geen"),
        ("Leadfeeder", not lf_df.empty, f"{len(lf_df)}" if not lf_df.empty else "geen"),
    ]
    for name, ok, detail in status_items:
        st.caption(f"{'[OK]' if ok else '[--]'} {name}: {detail}")

# Build data
leads_df = build_leads_df(ml_df, pd_df, web_mapping,
                          deals_dict=deals_dict,
                          identified_df=identified_df,
                          lf_df=lf_df)
health_df = calculate_customer_health(pbi_df)
if not health_df.empty:
    health_df = get_customer_contacts(health_df, pd_df)


# Handmatige bellijst — load eenmalig per sessie
if "manual_bellijst" not in st.session_state:
    st.session_state["manual_bellijst"] = load_manual_bellijst()

# Huidige ISO-week
_iso = datetime.now().isocalendar()
current_week = f"{_iso[0]}-W{_iso[1]:02d}"


# ============================================================
#  PAGINA 1: MIJN WEEK
# ============================================================

def _get_manual_leads_for_role(leads_df, rol, week):
    """Haal handmatig toegevoegde leads op als DataFrame + email-set."""
    entries = [
        e for e in st.session_state.get("manual_bellijst", [])
        if e.get("week") == week and e.get("rol") == rol
    ]
    if not entries or leads_df.empty:
        return pd.DataFrame(), set()
    emails = {e["email"].lower() for e in entries}
    manual_df = leads_df[leads_df["Email"].str.lower().isin(emails)].copy()
    return manual_df, emails


def _split_leads_for_roles(leads_df, n_per_person=5):
    """Split top leads: even indices voor Tobias, oneven voor Arthur."""
    if leads_df.empty:
        return pd.DataFrame(), pd.DataFrame()
    top = leads_df.head(n_per_person * 2)
    tobias_leads = top.iloc[0::2].head(n_per_person)
    arthur_leads = top.iloc[1::2].head(n_per_person)
    return tobias_leads, arthur_leads


def _get_klant_opvolging(health_df, n_per_person=5):
    """Split klant-opvolging over Tobias en Arthur.

    Mix van twee typen:
    - Reactiveren: klanten met weinig/dalende views (Rood/Oranje) - meer gebruik stimuleren
    - Upsell: goed presterende klanten (Groen) met weinig rapporten - verleiden tot meer

    Elke persoon krijgt een mix van beide typen.
    """
    if health_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    df = health_df.copy()

    # Type 1: Reactiveren (Rood + Oranje - weinig views)
    reactiveren = df[df["Status"].isin(["Rood", "Oranje"])].sort_values(
        "Views (recent)", ascending=True
    ).head(n_per_person)
    reactiveren = reactiveren.copy()
    reactiveren["Actie"] = reactiveren["Status"].apply(
        lambda s: "Reactiveren - geen gebruik" if s == "Rood" else "Reactiveren - dalend"
    )

    # Type 2: Upsell (Groen met weinig rapporten of hoog gebruik)
    groen = df[df["Status"] == "Groen"].copy()
    upsell = groen.sort_values("Rapporten", ascending=True).head(n_per_person)
    upsell = upsell.copy()
    upsell["Actie"] = "Upsell - actief maar weinig rapporten"

    # Combineer en verdeel afwisselend
    combined = pd.concat([reactiveren, upsell], ignore_index=True)
    combined = combined.drop_duplicates(subset=["Klant"]).head(n_per_person * 2)

    tobias_klanten = combined.iloc[0::2].head(n_per_person)
    arthur_klanten = combined.iloc[1::2].head(n_per_person)
    return tobias_klanten, arthur_klanten


def _render_call_table(df, label, key_prefix, mail_history=None, manual_emails=None):
    """Render een bellijst tabel met relevante kolommen incl. signalen."""
    if manual_emails is None:
        manual_emails = set()
    if df.empty:
        st.caption(f"Geen {label.lower()} beschikbaar.")
        return

    display = df.copy()

    # Signalen samenvoegen in één leesbare kolom
    def _signalen(row):
        parts = []
        if row.get("Deal Fase"):
            parts.append(f"📋 {row['Deal Fase']}")
        if row.get("LF Bezocht"):
            parts.append("🔍 Leadfeeder")
        return " | ".join(parts) if parts else ""

    display["Signalen"] = display.apply(_signalen, axis=1)

    cols = []
    for c in ["Naam", "Bedrijf", "Telefoon", "Totaal", "Segment", "Signalen"]:
        if c in display.columns:
            cols.append(c)

    st.dataframe(
        display[cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Totaal": st.column_config.ProgressColumn("Score", min_value=0, max_value=50, format="%d"),
        }
    )

    # Bel-reden expanders per lead
    for i, (_, row) in enumerate(df.iterrows()):
        email_lower = str(row.get("Email", "")).lower()
        is_manual = email_lower in manual_emails
        handmatig_label = " 📅" if is_manual else ""
        with st.expander(f"📞 {row['Naam']} — {row.get('Bedrijf', '')}{handmatig_label}"):
            if is_manual:
                st.caption("Handmatig toegevoegd aan bellijst")
            st.markdown("**Waarom bellen?**")
            reasons = []
            if row.get("Opens", 0) > 0:
                reasons.append(f"✉️ {int(row['Opens'])} opens, {int(row.get('Clicks', 0))} clicks")
            if row.get("LF Bezocht"):
                reasons.append("🔍 Zichtbaar via Leadfeeder")
            if row.get("Deal Fase"):
                waarde = f" – €{int(row['Deal Waarde']):,}" if row.get("Deal Waarde") else ""
                reasons.append(f"📋 Open deal: {row['Deal Fase']}{waarde}")

            if reasons:
                for r in reasons:
                    st.write(r)
            else:
                st.caption("Geen specifieke signalen — lead staat in de lijst op basis van algemene score.")

            # Pipedrive notities (HTML strippen, automatische bezoek-notities overslaan)
            person_id = row.get("Pipedrive ID")
            if person_id:
                import re
                notes = fetch_pipedrive_person_notes(int(person_id))
                handmatige_notities = []
                for note in notes[:10]:
                    tekst_raw = (note.get("content") or "").strip()
                    # HTML tags verwijderen
                    tekst = re.sub(r'<[^>]+>', ' ', tekst_raw).strip()
                    tekst = re.sub(r'\s+', ' ', tekst)
                    # Automatische Leadbooster/bezoek-notities overslaan
                    if any(kw in tekst_raw.lower() for kw in ["visited the website", "page_table", "leadbooster"]):
                        continue
                    datum = (note.get("add_time") or "")[:10]
                    if tekst:
                        handmatige_notities.append((datum, tekst))
                if handmatige_notities:
                    st.markdown("**Eerdere notities:**")
                    for datum, tekst in handmatige_notities[:3]:
                        st.caption(f"{datum} — {tekst[:300]}")

            # Telefoonnummer invullen als ontbreekt
            telefoon = row.get("Telefoon")
            if not telefoon or str(telefoon).strip() in ("", "nan", "None"):
                st.markdown("**Telefoonnummer:**")
                col_ph, col_ph_save = st.columns([3, 1])
                with col_ph:
                    new_phone = st.text_input(
                        "Telefoonnummer", key=f"{key_prefix}_phone_{i}",
                        placeholder="+31 6 ..."
                    )
                with col_ph_save:
                    st.write("")
                    person_id = row.get("Pipedrive ID")
                    if st.button("Opslaan", key=f"{key_prefix}_phone_save_{i}"):
                        if new_phone.strip() and person_id:
                            ok = update_pipedrive_person_phone(int(person_id), new_phone)
                            st.success("Opgeslagen in Pipedrive") if ok else st.error("Opslaan mislukt")
                        else:
                            st.warning("Vul een telefoonnummer in")

            # Verwijder uit bellijst (alleen voor handmatig toegevoegde leads)
            if is_manual:
                if st.button("🗑️ Verwijder uit bellijst", key=f"{key_prefix}_remove_{i}"):
                    st.session_state["manual_bellijst"] = [
                        e for e in st.session_state["manual_bellijst"]
                        if not (e["email"] == email_lower and e["week"] == current_week)
                    ]
                    save_manual_bellijst(st.session_state["manual_bellijst"])
                    st.rerun()


def _render_klant_table(df, key_prefix):
    """Render een klant-opvolging tabel met actie-type."""
    if df.empty:
        st.caption("Geen klantdata beschikbaar.")
        return
    display_cols = []
    for c in ["Klant", "Actie", "Status", "Views (recent)", "Trend", "Gebruikers", "Contact", "Contact Telefoon"]:
        if c in df.columns:
            display_cols.append(c)
    st.dataframe(df[display_cols], use_container_width=True, hide_index=True)


if pagina == "Mijn Week":

    tobias_auto, arthur_auto = _split_leads_for_roles(leads_df, 5)
    tobias_klanten, arthur_klanten = _get_klant_opvolging(health_df, 5)

    # Handmatig toegevoegde leads voor deze week
    manual_t_df, manual_t_emails = _get_manual_leads_for_role(leads_df, "Tobias", current_week)
    manual_a_df, manual_a_emails = _get_manual_leads_for_role(leads_df, "Arthur", current_week)

    # Combineer: handmatig eerst, daarna auto (zonder duplicaten)
    def _merge_leads(manual_df, auto_df, manual_emails_set):
        if manual_df.empty:
            return auto_df, manual_emails_set
        auto_filtered = auto_df[~auto_df["Email"].str.lower().isin(manual_emails_set)]
        return pd.concat([manual_df, auto_filtered], ignore_index=True), manual_emails_set

    tobias_leads, t_manual_set = _merge_leads(manual_t_df, tobias_auto, manual_t_emails)
    arthur_leads, a_manual_set = _merge_leads(manual_a_df, arthur_auto, manual_a_emails)

    if rol in ("Tobias", "Overzicht"):
        st.subheader("Tobias")

        st.markdown("**Leads bellen**")
        if not tobias_leads.empty:
            _render_call_table(tobias_leads, "leads", "t_leads", manual_emails=t_manual_set)
        else:
            st.info("Geen leads beschikbaar.")

        st.markdown("**Klanten bellen**")
        if not tobias_klanten.empty:
            _render_klant_table(tobias_klanten, "t_klant")
        else:
            st.info("Geen klant health data. Upload Power BI Excel in Data & Details.")

        if rol == "Overzicht":
            st.divider()

    if rol in ("Arthur", "Overzicht"):
        st.subheader("Arthur")

        st.markdown("**Leads bellen**")
        if not arthur_leads.empty:
            _render_call_table(arthur_leads, "leads", "a_leads", manual_emails=a_manual_set)
        else:
            st.info("Geen leads beschikbaar.")

        st.markdown("**Klanten bellen**")
        if not arthur_klanten.empty:
            _render_klant_table(arthur_klanten, "a_klant")
        else:
            st.info("Geen klant health data beschikbaar.")

    # ---- Belnotitie opslaan ----
    st.divider()
    st.subheader("Belnotitie opslaan in Pipedrive")

    pip_leads = leads_df[leads_df["Pipedrive ID"].notna()] if not leads_df.empty else pd.DataFrame()
    if pip_leads.empty:
        st.caption("Geen leads met Pipedrive-koppeling beschikbaar.")
    else:
        options = [f"{r['Naam']} – {r.get('Bedrijf', '')}" for _, r in pip_leads.iterrows()]
        selected = st.selectbox("Selecteer lead", options, key="feedback_lead_select")
        idx = options.index(selected)
        sel_row = pip_leads.iloc[idx]

        note_text = st.text_area(
            "Belnotitie",
            placeholder="Wat is besproken? Wat is de vervolgstap?",
            key="feedback_note",
        )

        new_stage = "— geen wijziging —"
        if sel_row.get("Deal ID") and stages_dict:
            stage_names = ["— geen wijziging —"] + [v for v in stages_dict.values()]
            new_stage = st.selectbox(
                "Deal fase bijwerken (optioneel)",
                stage_names,
                key="feedback_stage",
            )

        if st.button("Opslaan in Pipedrive", key="feedback_save"):
            if note_text.strip():
                ok = save_pipedrive_note(
                    int(sel_row["Pipedrive ID"]),
                    sel_row.get("Deal ID"),
                    note_text.strip(),
                )
                if ok and new_stage != "— geen wijziging —" and sel_row.get("Deal ID"):
                    stage_id = next((k for k, v in stages_dict.items() if v == new_stage), None)
                    if stage_id:
                        update_pipedrive_deal_stage(int(sel_row["Deal ID"]), stage_id)
                if ok:
                    st.success(f"Notitie opgeslagen voor {sel_row['Naam']}.")
                else:
                    st.error("Opslaan mislukt. Controleer de Pipedrive API-sleutel.")
            else:
                st.warning("Voer een notitie in voordat je opslaat.")


# ============================================================
#  PAGINA 2: FUNNEL COCKPIT
# ============================================================

elif pagina == "Overzicht":

    # --- PIPELINE OVERZICHT ---
    st.subheader("Pipeline")

    if not leads_df.empty:
        pipe_cols = st.columns(3)
        hot_count = len(leads_df[leads_df["Segment"] == "HOT"])
        warm_count = len(leads_df[leads_df["Segment"] == "Warm"])
        cold_count = len(leads_df[leads_df["Segment"] == "Cold"])

        pipe_cols[0].metric("HOT leads (18+)", hot_count)
        pipe_cols[1].metric("Warm (9-17)", warm_count)
        pipe_cols[2].metric("Cold (<9)", cold_count)
    else:
        st.info("Geen lead data beschikbaar.")

    st.divider()

    # --- KLANT HEALTH ---
    st.subheader("Klant Health (compact)")

    if not health_df.empty:
        rood = health_df[health_df["Status"] == "Rood"]
        oranje = health_df[health_df["Status"] == "Oranje"]
        groen = health_df[health_df["Status"] == "Groen"]

        h_cols = st.columns(3)
        h_cols[0].metric("At-risk", len(rood), help="Geen views in laatste periode")
        h_cols[1].metric("Aandacht", len(oranje), help="Dalende trend of 1 gebruiker")
        h_cols[2].metric("Gezond", len(groen), help="Stabiel of stijgend gebruik")

        # Top 12 status
        top12_names = FUNNEL_CONFIG["top_12"]
        top12_health = health_df[
            health_df["Klant"].apply(
                lambda k: any(t.lower() in str(k).lower() for t in top12_names)
            )
        ]
        if not top12_health.empty:
            st.markdown("**Top 12 klanten**")
            top12_display = top12_health[["Klant", "Status", "Views (recent)", "Trend", "Gebruikers"]].copy()
            st.dataframe(top12_display, use_container_width=True, hide_index=True)

        # At-risk detail
        if not rood.empty:
            with st.expander(f"At-risk klanten ({len(rood)})"):
                risk_cols = ["Klant", "Status", "Views (recent)", "Trend"]
                if "Contact Telefoon" in rood.columns:
                    risk_cols.append("Contact Telefoon")
                st.dataframe(rood[risk_cols], use_container_width=True, hide_index=True)

        # Upsell kansen
        if not groen.empty:
            low_reports = groen[groen["Rapporten"] <= 3].head(5)
            if not low_reports.empty:
                with st.expander("Upsell-kansen (actief maar weinig rapporten)"):
                    st.dataframe(
                        low_reports[["Klant", "Rapporten", "Views (recent)", "Gebruikers"]],
                        use_container_width=True, hide_index=True,
                    )
    else:
        st.info("Geen Power BI data. Upload een Excel in Data & Details.")


# ============================================================
#  PAGINA 3: DATA & DETAILS
# ============================================================

elif pagina == "Data & Details":

    tab_leads, tab_health, tab_revenue, tab_analyse = st.tabs([
        "Lead Details",
        "Klant Health",
        "Revenue",
        "Campagnes & Analyse",
    ])

    # --- TAB: LEAD DETAILS ---
    with tab_leads:
        st.header("Lead Analyse")

        if leads_df.empty:
            st.info("Geen lead data beschikbaar.")
        else:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Totaal Leads", len(leads_df))
            m2.metric("HOT", len(leads_df[leads_df["Segment"] == "HOT"]))
            m3.metric("Warm", len(leads_df[leads_df["Segment"] == "Warm"]))
            m4.metric("Cold", len(leads_df[leads_df["Segment"] == "Cold"]))

            st.divider()

            col_f1, col_f2 = st.columns([1, 2])
            with col_f1:
                filter_seg = st.multiselect(
                    "Segment", ["HOT", "Warm", "Cold"],
                    default=["HOT", "Warm", "Cold"],
                    key="lead_filter_seg",
                )
            with col_f2:
                search = st.text_input("Zoek op naam, email of bedrijf", key="lead_search")

            filtered = leads_df[leads_df["Segment"].isin(filter_seg)]
            if search:
                mask = (
                    filtered["Naam"].str.contains(search, case=False, na=False) |
                    filtered["Email"].str.contains(search, case=False, na=False) |
                    filtered["Bedrijf"].str.contains(search, case=False, na=False)
                )
                filtered = filtered[mask]

            # Doelgroep indicator
            top12_names = FUNNEL_CONFIG["top_12"]
            klant_names = health_df["Klant"].tolist() if not health_df.empty else []

            def classify_doelgroep(bedrijf):
                if not bedrijf:
                    return "Lead"
                b = str(bedrijf).lower()
                if any(t.lower() in b for t in top12_names):
                    return "Top 12"
                if any(k.lower() in b or b in k.lower() for k in klant_names if k):
                    return "Klant"
                return "Lead"

            filtered = filtered.copy()
            filtered["Doelgroep"] = filtered["Bedrijf"].apply(classify_doelgroep)

            all_possible = ["Naam", "Email", "Bedrijf", "Doelgroep", "Telefoon",
                            "Opens", "Clicks", "Open Score", "Click Score",
                            "LF Score", "Deal Fase", "Deal Bonus",
                            "Totaal", "Segment"]
            display_cols = [c for c in all_possible if c in filtered.columns]
            st.dataframe(
                filtered[display_cols],
                use_container_width=True, hide_index=True, height=500,
            )

            csv_all = filtered[display_cols].to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "Download leads (CSV)", csv_all,
                f"leads_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv", key="download_leads",
            )

            with st.expander("📅 Voeg lead handmatig toe aan bellijst"):
                lead_options = [
                    f"{r['Naam']} – {r.get('Bedrijf', '')}"
                    for _, r in filtered.iterrows()
                ]
                if lead_options:
                    col_l, col_r, col_b = st.columns([4, 1, 1])
                    with col_l:
                        selected_lead = st.selectbox("Lead", lead_options, key="manual_add_lead")
                    with col_r:
                        selected_rol = st.selectbox("Voor", ["Tobias", "Arthur"], key="manual_add_rol")
                    with col_b:
                        st.write("")
                        if st.button("Voeg toe", key="manual_add_btn"):
                            idx = lead_options.index(selected_lead)
                            sel_row = filtered.iloc[idx]
                            entry = {
                                "email": sel_row["Email"].lower(),
                                "naam": sel_row["Naam"],
                                "bedrijf": sel_row.get("Bedrijf", ""),
                                "week": current_week,
                                "rol": selected_rol,
                            }
                            existing = st.session_state["manual_bellijst"]
                            already = any(
                                e["email"] == entry["email"]
                                and e["week"] == current_week
                                and e["rol"] == selected_rol
                                for e in existing
                            )
                            if not already:
                                existing.append(entry)
                                save_manual_bellijst(existing)
                                st.success(f"✅ {sel_row['Naam']} toegevoegd aan bellijst van {selected_rol}")
                            else:
                                st.info(f"{sel_row['Naam']} staat al in de bellijst van {selected_rol}")

            with st.expander("Kolommen & scoring uitleg"):
                st.markdown("""
**Kolommen**

| Kolom | Wat het betekent |
|-------|-----------------|
| Opens | Aantal e-mails geopend (alle campagnes) |
| Clicks | Aantal keer geklikt op een link in een mail |
| Open Score | Punten op basis van opens: 1+=3, 3+=6, 5+=9, 10+=12, 20+=15 |
| Click Score | Punten op basis van clicks: 1+=3, 2+=6, 3+=9, 5+=12, 10+=15 |
| LF Score | +5 als het bedrijf via Leadfeeder/Leadbooster op de website is gezien |
| Deal Fase | Huidige fase in Pipedrive (als er een open deal is) of "Webinar aangemeld" via EmailOctopus |
| Deal Bonus | Punten op basis van deal fase: Webinar aangemeld=15, Offerte verstuurd=10, Offerte aanmaken=8, Interesse getoond=5, Contact gehad=3 |
| Totaal | Open Score + Click Score + LF Score + Deal Bonus |
| Segment | HOT (≥18) · Warm (9–17) · Cold (<9) |
                """)

    # --- TAB: KLANT HEALTH ---
    with tab_health:
        st.header("Klant Health - Power BI Gebruik")

        uploaded = st.file_uploader(
            "Upload Power BI Activity Report Views (Excel)",
            type=["xlsx", "xls"],
            key="pbi_upload",
        )
        if uploaded is not None:
            file_bytes = uploaded.read()
            saved = save_powerbi_cache(file_bytes)
            pbi_df = pd.read_excel(io.BytesIO(file_bytes))
            health_df = calculate_customer_health(pbi_df)
            if not health_df.empty:
                health_df = get_customer_contacts(health_df, pd_df)
            msg = f"Excel opgeslagen en geladen: {len(pbi_df)} rijen, {pbi_df['Pipedrive organisatie'].nunique()} klanten"
            if not saved:
                msg += " (opslaan mislukt — wordt niet onthouden)"
            st.success(msg)
        elif pbi_source == "cache":
            import os as _os
            cache_date = datetime.fromtimestamp(_os.path.getmtime(POWERBI_CACHE_PATH)).strftime("%d-%m-%Y %H:%M")
            st.info(f"Gebruik opgeslagen cache van {cache_date}. Upload een nieuwere Excel om te verversen.")

        if health_df.empty:
            st.info(
                "Geen Power BI data. Upload een Excel bestand hierboven, "
                f"of plaats het bestand op: `{POWERBI_EXCEL_DEFAULT}`"
            )
        else:
            top12_names = FUNNEL_CONFIG["top_12"]
            health_df["Top 12"] = health_df["Klant"].apply(
                lambda k: "***" if any(t.lower() in str(k).lower() for t in top12_names) else ""
            )

            rood = health_df[health_df["Status"] == "Rood"]
            oranje = health_df[health_df["Status"] == "Oranje"]
            groen = health_df[health_df["Status"] == "Groen"]
            top12_count = len(health_df[health_df["Top 12"] == "***"])

            hc1, hc2, hc3, hc4, hc5 = st.columns(5)
            hc1.metric("Totaal Klanten", len(health_df))
            hc2.metric("Rood (at-risk)", len(rood))
            hc3.metric("Oranje (aandacht)", len(oranje))
            hc4.metric("Groen (gezond)", len(groen))
            hc5.metric("Top 12", top12_count)

            st.divider()

            fc1, fc2 = st.columns(2)
            with fc1:
                status_filter = st.multiselect(
                    "Filter op status",
                    ["Rood", "Oranje", "Groen"],
                    default=["Rood", "Oranje", "Groen"],
                    key="health_status_filter",
                )
            with fc2:
                top12_only = st.checkbox("Alleen Top 12 klanten", key="top12_filter")

            health_filtered = health_df[health_df["Status"].isin(status_filter)]
            if top12_only:
                health_filtered = health_filtered[health_filtered["Top 12"] == "***"]

            health_cols = ["Top 12", "Klant", "Status", "Views (totaal)", "Views (recent)",
                           "Views (vorig)", "Trend", "Trend %", "Gebruikers",
                           "Rapporten", "Contact", "Contact Telefoon"]
            health_cols = [c for c in health_cols if c in health_filtered.columns]

            st.dataframe(
                health_filtered[health_cols],
                use_container_width=True, hide_index=True, height=500,
            )

            csv_health = health_filtered[health_cols].to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "Download klant health (CSV)", csv_health,
                f"klant_health_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv", key="download_health",
            )

            with st.expander("Klant detail (views per gebruiker)"):
                if pbi_df is not None:
                    klant_keuze = st.selectbox(
                        "Selecteer klant",
                        health_df["Pipedrive organisatie"].tolist(),
                        key="klant_detail",
                    )
                    if klant_keuze:
                        detail = pbi_df[pbi_df["Pipedrive organisatie"] == klant_keuze]
                        detail = detail[~detail["Name"].str.lower().apply(
                            lambda n: any(intern in str(n).lower() for intern in INTERNE_MEDEWERKERS)
                        )]
                        st.dataframe(
                            detail[["Name", "Report name", "Aantal activity reportviews",
                                    "Maand", "Jaar"]].sort_values(
                                "Aantal activity reportviews", ascending=False
                            ),
                            use_container_width=True, hide_index=True,
                        )

            with st.expander("Data bron info"):
                if pbi_source == "cache":
                    import os as _os2
                    cache_date = datetime.fromtimestamp(_os2.path.getmtime(POWERBI_CACHE_PATH)).strftime("%d-%m-%Y %H:%M")
                    st.info(f"Data uit opgeslagen cache ({cache_date}). Upload een nieuwere Excel om te verversen.")
                elif pbi_source == "excel":
                    st.info(f"Data uit Excel bestand: `{POWERBI_EXCEL_DEFAULT}`")
                else:
                    st.info("Geen data beschikbaar.")

            with st.expander("Health Scoring uitleg"):
                st.markdown("""
**Status op basis van Power BI rapport-gebruik:**

| Status | Criteria |
|--------|----------|
| **Rood** | Geen views in de laatste periode |
| **Oranje** | Dalende trend (>25% minder) of 1 gebruiker |
| **Groen** | Stabiel of stijgend gebruik, meerdere gebruikers |

**Acties per status:**
- **Rood**: Direct bellen - waarom geen gebruik meer?
- **Oranje**: Proactief contact - hulp nodig?
- **Groen**: Upsell-kansen identificeren
                """)

    # --- TAB: REVENUE ---
    with tab_revenue:
        st.header("Klantomzet 2025 (WeFact)")

        omzet_data = FUNNEL_CONFIG.get("klant_omzet", {})
        omzet_totalen = FUNNEL_CONFIG.get("omzet_totalen", {})

        if omzet_data:
            ot1, ot2, ot3, ot4 = st.columns(4)
            ot1.metric("Consultancy", f"\u20ac{omzet_totalen.get('consultancy', 0):,.0f}")
            ot2.metric("Projecten", f"\u20ac{omzet_totalen.get('projecten', 0):,.0f}")
            ot3.metric("Abonnementen", f"\u20ac{omzet_totalen.get('abonnement', 0):,.0f}")
            ot4.metric("Totaal", f"\u20ac{omzet_totalen.get('totaal', 0):,.0f}")

            # Build omzet DataFrame
            top12_names = FUNNEL_CONFIG["top_12"]
            omzet_rows = []
            for naam, bedragen in omzet_data.items():
                cons = bedragen["consultancy"]
                proj = bedragen["projecten"]
                abo = bedragen["abonnement"]
                omzet = cons + proj
                totaal = cons + proj + abo
                is_top12 = any(t.lower() in naam.lower() for t in top12_names)
                omzet_rows.append({
                    "Top 12": "***" if is_top12 else "",
                    "Klant": naam,
                    "Consultancy": cons,
                    "Projecten": proj,
                    "Omzet": omzet,
                    "Abonnement": abo,
                    "Totaal": totaal,
                })
            omzet_df = pd.DataFrame(omzet_rows).sort_values("Omzet", ascending=False).reset_index(drop=True)

            st.markdown("**Top 12 klanten** (consultancy + projecten)")
            top12_df = omzet_df[omzet_df["Top 12"] == "***"].copy()
            top12_df.index = range(1, len(top12_df) + 1)

            st.dataframe(
                top12_df[["Klant", "Consultancy", "Projecten", "Omzet", "Abonnement", "Totaal"]],
                use_container_width=True,
                column_config={
                    "Consultancy": st.column_config.NumberColumn(format="\u20ac%,.0f"),
                    "Projecten": st.column_config.NumberColumn(format="\u20ac%,.0f"),
                    "Omzet": st.column_config.NumberColumn(format="\u20ac%,.0f"),
                    "Abonnement": st.column_config.NumberColumn(format="\u20ac%,.0f"),
                    "Totaal": st.column_config.NumberColumn(format="\u20ac%,.0f"),
                },
            )

            with st.expander(f"Alle {len(omzet_df)} klanten"):
                omzet_df.index = range(1, len(omzet_df) + 1)
                st.dataframe(
                    omzet_df,
                    use_container_width=True, height=600,
                    column_config={
                        "Consultancy": st.column_config.NumberColumn(format="\u20ac%,.0f"),
                        "Projecten": st.column_config.NumberColumn(format="\u20ac%,.0f"),
                        "Omzet": st.column_config.NumberColumn(format="\u20ac%,.0f"),
                        "Abonnement": st.column_config.NumberColumn(format="\u20ac%,.0f"),
                        "Totaal": st.column_config.NumberColumn(format="\u20ac%,.0f"),
                    },
                )

            with st.expander("Abonnementsinkomsten detail"):
                abo_df = omzet_df[omzet_df["Abonnement"] > 0].sort_values("Abonnement", ascending=False).copy()
                abo_df.index = range(1, len(abo_df) + 1)
                st.caption(f"{len(abo_df)} klanten met abonnement, totaal \u20ac{abo_df['Abonnement'].sum():,.0f} per jaar")
                st.dataframe(
                    abo_df[["Top 12", "Klant", "Abonnement"]],
                    use_container_width=True, height=400,
                    column_config={
                        "Abonnement": st.column_config.NumberColumn(format="\u20ac%,.0f"),
                    },
                )
        else:
            st.info("Geen omzetdata beschikbaar.")

    # --- TAB: CAMPAGNES & ANALYSE ---
    with tab_analyse:

        st.header("Campagnes & Score Herleiding")

        # Data laden
        camp_df = load_campaign_data()
        act_df = load_campaign_activity()

        analyse_sub1, analyse_sub2, analyse_sub3 = st.tabs([
            "E-mailcampagnes",
            "Website Bezoekers",
            "Score Herleiding",
        ])

        # ── SUB-TAB 1: E-MAILCAMPAGNES ─────────────────────────

        with analyse_sub1:

            if camp_df.empty:
                st.info("Geen campagnedata gevonden. Check docs/mailerlite_export/campaigns.csv")
            else:
                st.subheader("Campagne Performance")

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Campagnes", len(camp_df))
                if "Verstuurd" in camp_df.columns:
                    m2.metric("Totaal verstuurd", f"{camp_df['Verstuurd'].sum():,.0f}")
                if "Opens" in camp_df.columns:
                    m3.metric("Totaal opens", f"{camp_df['Opens'].sum():,.0f}")
                if "Clicks" in camp_df.columns:
                    m4.metric("Totaal clicks", f"{camp_df['Clicks'].sum():,.0f}")

                display_cols = [c for c in [
                    "Campagne", "Verzonden", "Verstuurd",
                    "Unieke Opens", "Open Rate", "Unieke Clicks", "Click Rate",
                    "Hard Bounces", "Soft Bounces", "Uitschrijvingen",
                ] if c in camp_df.columns]

                st.dataframe(
                    camp_df[display_cols],
                    use_container_width=True, hide_index=True, height=400,
                    column_config={
                        "Verzonden": st.column_config.DatetimeColumn(format="DD-MM-YYYY HH:mm"),
                    },
                )

                if not act_df.empty:
                    st.subheader("Detail per campagne")
                    camp_names = camp_df["Campagne"].tolist() if "Campagne" in camp_df.columns else []
                    selected_camp = st.selectbox("Selecteer campagne", camp_names, key="camp_select")

                    if selected_camp and "Campagne" in act_df.columns:
                        camp_detail = act_df[act_df["Campagne"] == selected_camp].copy()

                        detail_openers, detail_clickers, detail_all = st.tabs([
                            f"Geopend ({len(camp_detail[camp_detail['Opens'] > 0])})",
                            f"Geklikt ({len(camp_detail[camp_detail['Clicks'] > 0])})",
                            f"Alle ontvangers ({len(camp_detail)})",
                        ])

                        detail_cols = [c for c in ["Naam", "Email", "Bedrijf", "Opens", "Clicks"] if c in camp_detail.columns]

                        with detail_openers:
                            openers = camp_detail[camp_detail["Opens"] > 0].sort_values("Opens", ascending=False)
                            if not openers.empty:
                                st.dataframe(openers[detail_cols], use_container_width=True, hide_index=True, height=400)
                            else:
                                st.info("Niemand heeft deze campagne geopend.")

                        with detail_clickers:
                            clickers = camp_detail[camp_detail["Clicks"] > 0].sort_values("Clicks", ascending=False)
                            if not clickers.empty:
                                st.dataframe(clickers[detail_cols], use_container_width=True, hide_index=True, height=400)
                            else:
                                st.info("Niemand heeft op een link geklikt.")

                        with detail_all:
                            st.dataframe(
                                camp_detail[detail_cols].sort_values("Opens", ascending=False),
                                use_container_width=True, hide_index=True, height=400,
                            )

        # ── SUB-TAB 2: WEBSITE BEZOEKERS (Leadfeeder) ──────────

        with analyse_sub2:
            st.subheader("Website Bezoekers — Leadfeeder")
            st.caption("Bedrijven die notifica.nl bezochten, geïdentificeerd via Leadfeeder (Dealfront).")

            lf_days = st.selectbox("Periode", [7, 14, 30, 60], index=1, key="lf_days", format_func=lambda d: f"Laatste {d} dagen")

            with st.spinner("Leadfeeder data ophalen..."):
                lf_df = fetch_leadfeeder_leads(days=lf_days)

            if lf_df.empty:
                st.warning("Geen Leadfeeder data. Controleer API token in .env (LEADFEEDER_API_TOKEN).")
            else:
                # Metrics
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Bedrijven", len(lf_df))
                m2.metric("Totaal bezoeken", int(lf_df["Bezoeken"].sum()))

                bouw_mask = lf_df["Industrie"].str.contains("Construct|Install|Bouw|Build", case=False, na=False)
                m3.metric("Bouwbedrijven", int(bouw_mask.sum()))
                m4.metric("Gem. kwaliteitsscore", f"{lf_df['Kwaliteit'].mean():.1f}")

                # Filter
                col_filter1, col_filter2 = st.columns([2, 1])
                with col_filter1:
                    industrie_filter = st.multiselect(
                        "Filter op industrie",
                        options=sorted(lf_df["Industrie"].dropna().unique()),
                        default=[],
                        key="lf_industrie",
                    )
                with col_filter2:
                    alleen_bouw = st.checkbox("Alleen bouw/installatie", value=False, key="lf_bouw")

                filtered = lf_df.copy()
                if industrie_filter:
                    filtered = filtered[filtered["Industrie"].isin(industrie_filter)]
                if alleen_bouw:
                    filtered = filtered[filtered["Industrie"].str.contains(
                        "Construct|Install|Bouw|Build", case=False, na=False
                    )]

                # Tabel
                display_cols = [c for c in ["Bedrijf", "Industrie", "Stad", "Bezoeken", "Laatste Bezoek", "Kwaliteit", "Bron", "Website"] if c in filtered.columns]
                st.dataframe(
                    filtered[display_cols].reset_index(drop=True),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Kwaliteit": st.column_config.ProgressColumn("Kwaliteit", min_value=0, max_value=5, format="%d"),
                        "Bezoeken": st.column_config.NumberColumn("Bezoeken"),
                        "Website": st.column_config.LinkColumn("Website"),
                    }
                )

                st.caption(f"Data via [Leadfeeder/Dealfront](https://app.dealfront.com) — {len(filtered)} bedrijven weergegeven")

        # ── SUB-TAB 3: SCORE HERLEIDING ────────────────────────

        with analyse_sub3:
            st.subheader("Score Herleiding per Lead")
            st.caption("Selecteer een lead om te zien waar de score vandaan komt.")

            if not leads_df.empty:
                lead_options = leads_df.sort_values("Totaal", ascending=False).apply(
                    lambda r: f"{r['Naam']} ({r.get('Bedrijf', '-')}) - Score: {r['Totaal']}", axis=1
                ).tolist()
                selected_lead = st.selectbox("Selecteer lead", lead_options, key="score_lead_select")

                if selected_lead:
                    idx = lead_options.index(selected_lead)
                    lead = leads_df.sort_values("Totaal", ascending=False).iloc[idx]

                    # NID + Clarity link
                    lead_email = str(lead.get("Email", "")).lower().strip()
                    nid = generate_nid(lead_email) if lead_email else ""
                    if nid:
                        clarity_url = f"https://clarity.microsoft.com/projects/view/vmymrfb2j3/recordings?CustomUserId={nid}"
                        st.markdown(
                            f"**NID:** `{nid}` &nbsp;&nbsp; "
                            f"[🎥 Bekijk Clarity sessies]({clarity_url})",
                            unsafe_allow_html=True,
                        )

                    col1, col2, col3 = st.columns(3)
                    col1.metric("Open Score", f"{int(lead.get('Open Score', 0))}/15")
                    col2.metric("Click Score", f"{int(lead.get('Click Score', 0))}/15")
                    col3.metric("TOTAAL", f"{int(lead.get('Totaal', 0))}/30", delta=lead.get("Segment", ""))

                    st.markdown("---")

                    opens = int(lead.get("Opens", 0))
                    clicks = int(lead.get("Clicks", 0))
                    open_score = int(lead.get("Open Score", 0))
                    click_score = int(lead.get("Click Score", 0))

                    st.markdown(f"""
| Metric | Waarde | Score |
|--------|--------|-------|
| Campagne opens | {opens}x geopend | {open_score}/15 |
| Link clicks | {clicks}x geklikt | {click_score}/15 |
| **Totaal** | | **{open_score + click_score}/30** |
""")
                    st.caption("Schaal opens: 0=0pt, 1+=3, 3+=6, 5+=9, 10+=12, 20+=15 | Schaal clicks: 1+=3, 2+=6, 3+=9, 5+=12, 10+=15")

                    # Campagne-detail voor deze lead
                    if not act_df.empty and "Email" in act_df.columns:
                        lead_camps = act_df[act_df["Email"].str.lower().str.strip() == lead_email]
                        if not lead_camps.empty:
                            active_camps = lead_camps[
                                (lead_camps["Opens"] > 0) | (lead_camps["Clicks"] > 0)
                            ]
                            if not active_camps.empty:
                                st.markdown("**Campagnes met activiteit:**")
                                camp_cols = [c for c in ["Campagne", "Opens", "Clicks"] if c in active_camps.columns]
                                st.dataframe(active_camps[camp_cols], use_container_width=True, hide_index=True)
                            else:
                                st.info("Geen campagne-interactie gevonden voor deze lead.")

            else:
                st.info("Geen lead data beschikbaar.")


# --- Footer ---
st.divider()
st.caption(
    f"Laatste update: {datetime.now().strftime('%d-%m-%Y %H:%M')} | "
    "Databronnen: EmailOctopus, Pipedrive, Power BI"
)
