"""
Blob Analyse - Zenith Security
Streamlit App voor AI-analyse van werkbon blobvelden
"""

import streamlit as st
import json
from pathlib import Path

# Page config
st.set_page_config(
    page_title="Blob Analyse - Zenith Security",
    page_icon="🔍",
    layout="wide"
)


@st.cache_data
def load_blob_data():
    """Laad de blobvelden sample data."""
    data_path = Path(__file__).parent / "data" / "sample_data.json"
    if not data_path.exists():
        return None
    with open(data_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@st.cache_data
def load_werkbonnen_data():
    """Laad de werkbonnen data uit DWH extract."""
    data_path = Path(__file__).parent / "data" / "werkbonnen_zenith.json"
    if not data_path.exists():
        return None
    with open(data_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def search_in_blobs(data, query, selected_types):
    """Zoek in de blobvelden data."""
    results = []
    query_lower = query.lower()

    type_mapping = {
        "Monteur Notities": "monteur_notities",
        "Storingsmeldingen": "storing_meldingen",
        "Casebeschrijvingen": "werk_context",
        "Urenregistraties": "uren_registraties"
    }

    for display_name, data_key in type_mapping.items():
        if display_name in selected_types:
            for item in data.get(data_key, []):
                if query_lower in item.get("tekst", "").lower():
                    results.append({
                        "id": item.get("id"),
                        "type": display_name,
                        "tekst": item.get("tekst"),
                        "totaal_uren": item.get("totaal_uren")
                    })

    return results


def find_blob_for_werkbon(blob_data, werkbon_id):
    """Zoek blobvelden die mogelijk bij een werkbon horen."""
    results = {
        "monteur_notities": [],
        "storing_meldingen": [],
        "werk_context": [],
        "uren_registraties": []
    }

    # Zoek in alle blob types naar het werkbon ID
    werkbon_id_str = str(werkbon_id)

    for blob_type in results.keys():
        for item in blob_data.get(blob_type, []):
            item_id = str(item.get("id", ""))
            # Check of de ID overeenkomt of in de tekst voorkomt
            if item_id == werkbon_id_str or werkbon_id_str in item.get("tekst", ""):
                results[blob_type].append(item)

    return results


def search_werkbonnen(werkbonnen_data, query):
    """Zoek in werkbonnen."""
    results = []
    query_lower = query.lower()

    for wb in werkbonnen_data.get("werkbonnen", []):
        # Zoek in meerdere velden
        searchable = " ".join([
            str(wb.get("Werkbon", "")),
            str(wb.get("Klant", "")),
            str(wb.get("Monteur", "")),
            str(wb.get("Status", "")),
            str(wb.get("Referentie", "")),
            str(wb.get("Werkorder", ""))
        ]).lower()

        if query_lower in searchable:
            results.append(wb)

    return results


# Load data
blob_data = load_blob_data()
werkbonnen_data = load_werkbonnen_data()

# Header
st.title("🔍 Blob Analyse - Zenith Security")
st.markdown("**Pilot:** AI-analyse van werkbon blobvelden")

st.divider()

# Sidebar
with st.sidebar:
    st.header("Over deze app")
    st.markdown("""
    Deze app analyseert ongestructureerde blobvelden
    uit Syntess werkbonnen voor Zenith Security.

    **Relevante blobvelden:**
    - Monteur notities
    - Storingsmeldingen
    - Casebeschrijvingen
    - Urenregistraties
    """)

    st.divider()
    st.markdown("**Klant:** Zenith Security (1229)")
    st.markdown("**Status:** Pilot / Prototype")

    if blob_data:
        st.divider()
        st.markdown("**Blobvelden:**")
        totals = blob_data.get("metadata", {}).get("totals", {})
        st.caption(f"Notities: {totals.get('monteur_notities', 0)}")
        st.caption(f"Storingen: {totals.get('storing_meldingen', 0)}")
        st.caption(f"Cases: {totals.get('werk_context', 0)}")
        st.caption(f"Uren: {totals.get('uren_registraties', 0)}")

    if werkbonnen_data:
        st.divider()
        st.markdown("**Werkbonnen (DWH):**")
        wb_totals = werkbonnen_data.get("metadata", {}).get("totals", {})
        st.caption(f"Werkbonnen: {wb_totals.get('werkbonnen', 0)}")
        st.caption(f"Paragrafen: {wb_totals.get('paragrafen', 0)}")

# Main content
tab1, tab2, tab3, tab4 = st.tabs(["📊 Overzicht", "📋 Werkbonnen", "🔎 Zoeken", "🤖 AI Analyse"])

with tab1:
    st.header("Dataset Overzicht")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Blobvelden")
        if blob_data:
            totals = blob_data.get("metadata", {}).get("totals", {})
            metrics_col1, metrics_col2 = st.columns(2)
            with metrics_col1:
                st.metric("Monteur Notities", totals.get('monteur_notities', 0))
                st.metric("Casebeschrijvingen", totals.get('werk_context', 0))
            with metrics_col2:
                st.metric("Storingsmeldingen", totals.get('storing_meldingen', 0))
                st.metric("Urenregistraties", totals.get('uren_registraties', 0))
        else:
            st.warning("Geen blobvelden data geladen")

    with col2:
        st.subheader("Werkbonnen (DWH)")
        if werkbonnen_data:
            wb_totals = werkbonnen_data.get("metadata", {}).get("totals", {})
            metrics_col1, metrics_col2 = st.columns(2)
            with metrics_col1:
                st.metric("Werkbonnen", wb_totals.get('werkbonnen', 0))
            with metrics_col2:
                st.metric("Paragrafen", wb_totals.get('paragrafen', 0))

            # Toon extract datum
            extracted_at = werkbonnen_data.get("metadata", {}).get("extracted_at", "Onbekend")
            st.caption(f"Laatste extract: {extracted_at[:10] if extracted_at else 'Onbekend'}")
        else:
            st.warning("Geen werkbonnen data geladen")

    st.divider()

    st.subheader("Blobveld Types")
    table_data = {
        "Blobveld": ["NOTITIE.txt", "TEKST.txt", "GC_INFORMATIE.txt", "INGELEVERDE_URENREGELS.txt"],
        "Bron": ["AT_MWBSESS", "AT_UITVBEST", "AT_WERK", "AT_MWBSESS"],
        "Type": ["RTF", "RTF", "RTF", "XML"],
        "Inhoud": [
            "Vrije notities van monteurs",
            "Storingsmeldingen en werkbeschrijvingen",
            "Casebeschrijvingen en werkbon-context",
            "Gestructureerde urenregistratie"
        ]
    }
    st.table(table_data)

with tab2:
    st.header("Werkbonnen Browser")

    if werkbonnen_data:
        # Zoekbalk
        wb_search = st.text_input("🔍 Zoek werkbon", placeholder="Zoek op werkbon, klant, monteur, status...")

        # Filter opties
        col1, col2, col3 = st.columns(3)

        with col1:
            # Status filter
            all_statuses = list(set(wb.get("Status", "Onbekend") for wb in werkbonnen_data.get("werkbonnen", [])))
            status_filter = st.multiselect("Status", all_statuses, default=[])

        with col2:
            # Monteur filter
            all_monteurs = list(set(wb.get("Monteur", "Onbekend") for wb in werkbonnen_data.get("werkbonnen", []) if wb.get("Monteur")))
            monteur_filter = st.multiselect("Monteur", sorted(all_monteurs)[:20], default=[])

        with col3:
            max_wb = st.slider("Max resultaten", 10, 100, 25)

        # Filter werkbonnen
        filtered_wb = werkbonnen_data.get("werkbonnen", [])

        if wb_search:
            filtered_wb = search_werkbonnen(werkbonnen_data, wb_search)

        if status_filter:
            filtered_wb = [wb for wb in filtered_wb if wb.get("Status") in status_filter]

        if monteur_filter:
            filtered_wb = [wb for wb in filtered_wb if wb.get("Monteur") in monteur_filter]

        st.divider()
        st.markdown(f"**{len(filtered_wb)} werkbonnen** gevonden")

        # Toon werkbonnen
        for wb in filtered_wb[:max_wb]:
            werkbon_titel = wb.get("Werkbon", "Onbekend")
            status = wb.get("Status", "")
            monteur = wb.get("Monteur", "")
            melddatum = wb.get("MeldDatum", "")[:10] if wb.get("MeldDatum") else ""

            with st.expander(f"📋 {werkbon_titel} | {status} | {melddatum}"):
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Werkbon details:**")
                    st.write(f"**Status:** {status}")
                    st.write(f"**Monteur:** {monteur}")
                    st.write(f"**Klant:** {wb.get('Klant', '')}")
                    st.write(f"**Melddatum:** {melddatum}")
                    st.write(f"**Type:** {wb.get('Type', '')}")
                    st.write(f"**Prioriteit:** {wb.get('Prioriteit', '')}")

                with col2:
                    st.markdown("**Extra info:**")
                    st.write(f"**Referentie:** {wb.get('Referentie', '')}")
                    st.write(f"**Werkorder:** {wb.get('Werkorder', '')}")
                    st.write(f"**Postcode:** {wb.get('Postcode', '')} {wb.get('Plaats', '')}")
                    st.write(f"**Hoofdwerkbon:** {wb.get('Hoofdwerkbon', '')}")

                # Zoek gekoppelde blobvelden
                if blob_data:
                    wb_id = wb.get("WerkbonDocumentKey")
                    if wb_id:
                        st.divider()
                        st.markdown("**Gekoppelde blobvelden:**")

                        blobs = find_blob_for_werkbon(blob_data, wb_id)
                        total_blobs = sum(len(v) for v in blobs.values())

                        if total_blobs > 0:
                            for blob_type, items in blobs.items():
                                if items:
                                    type_labels = {
                                        "monteur_notities": "📝 Monteur Notities",
                                        "storing_meldingen": "⚠️ Storingsmeldingen",
                                        "werk_context": "📄 Casebeschrijvingen",
                                        "uren_registraties": "⏱️ Urenregistraties"
                                    }
                                    st.markdown(f"**{type_labels.get(blob_type, blob_type)}:** {len(items)}")
                                    for item in items[:3]:
                                        st.text(item.get("tekst", "")[:200] + "...")
                        else:
                            st.info("Geen direct gekoppelde blobvelden gevonden voor deze werkbon ID")

                # Toon paragrafen
                paragrafen = [p for p in werkbonnen_data.get("paragrafen", [])
                              if p.get("WerkbonDocumentKey") == wb.get("WerkbonDocumentKey")]

                if paragrafen:
                    st.divider()
                    st.markdown(f"**Paragrafen ({len(paragrafen)}):**")
                    for p in paragrafen[:5]:
                        st.write(f"- {p.get('Werkbonparagraaf omschrijving', 'Geen omschrijving')}")
                        if p.get("Storing"):
                            st.caption(f"  Storing: {p.get('Storing')}")
    else:
        st.warning("Geen werkbonnen data geladen. Run `scripts/dwh_extract.py` om data op te halen.")

with tab3:
    st.header("Zoeken in Blobvelden")

    if blob_data:
        search_query = st.text_input("🔍 Zoekterm", placeholder="Bijv. storing, alarm, preventie, sleutel...", key="blob_search")

        col1, col2 = st.columns(2)
        with col1:
            blobveld_filter = st.multiselect(
                "Filter op blobveld",
                ["Monteur Notities", "Storingsmeldingen", "Casebeschrijvingen", "Urenregistraties"],
                default=["Monteur Notities", "Storingsmeldingen", "Casebeschrijvingen"]
            )
        with col2:
            max_results = st.slider("Max resultaten", 10, 100, 25, key="blob_max")

        if search_query:
            results = search_in_blobs(blob_data, search_query, blobveld_filter)

            st.divider()

            if results:
                st.success(f"**{len(results)} resultaten** gevonden voor '{search_query}'")

                for i, result in enumerate(results[:max_results], 1):
                    with st.expander(f"{result['type']} - ID: {result['id']}"):
                        st.text(result['tekst'])
                        if result.get('totaal_uren'):
                            st.caption(f"Totaal uren: {result['totaal_uren']}")

                if len(results) > max_results:
                    st.info(f"Toont {max_results} van {len(results)} resultaten.")
            else:
                st.warning(f"Geen resultaten gevonden voor '{search_query}'")
        else:
            st.info("Voer een zoekterm in om te zoeken in de blobvelden.")

            st.markdown("**Suggesties:**")
            suggestions = ["storing", "alarm", "sleutel", "camera", "defect", "monteur", "klant"]
            cols = st.columns(len(suggestions))
            for i, suggestion in enumerate(suggestions):
                with cols[i]:
                    if st.button(suggestion, key=f"sug_{suggestion}"):
                        st.session_state.blob_search = suggestion
                        st.rerun()
    else:
        st.warning("Geen blobvelden data geladen.")

with tab4:
    st.header("AI Analyse")

    st.info("🚧 **Coming soon:** AI-analyse met OpenAI/Claude voor:")

    st.markdown("""
    - **Samenvatten** van lange notities
    - **Categoriseren** van storingstypes
    - **Extractie** van keywords en thema's
    - **Sentiment** analyse van klantcommunicatie
    """)

    st.divider()

    st.subheader("Voorbeeld: Notitie Analyse")

    if blob_data:
        example_texts = [item["tekst"][:500] for item in blob_data.get("monteur_notities", [])[:5]]

        input_method = st.radio("Invoer methode", ["Selecteer voorbeeld", "Eigen tekst"])

        if input_method == "Selecteer voorbeeld" and example_texts:
            selected_example = st.selectbox("Kies een voorbeeld notitie", example_texts)
            example_text = selected_example
        else:
            example_text = st.text_area(
                "Plak een notitie:",
                value="Nog niet klaar geen patchingen gemaakt. Verdere info bij Tim bekend. Klant was niet aanwezig, nieuwe afspraak maken.",
                height=100
            )
    else:
        example_text = st.text_area(
            "Plak een notitie:",
            value="Nog niet klaar geen patchingen gemaakt. Verdere info bij Tim bekend. Klant was niet aanwezig, nieuwe afspraak maken.",
            height=100
        )

    if st.button("🤖 Analyseer met AI", type="primary"):
        with st.spinner("Analyseren..."):
            st.success("**AI Analyse Resultaat:**")
            st.markdown("""
            - **Status:** Werk niet afgerond
            - **Reden:** Klant afwezig
            - **Actie nodig:** Nieuwe afspraak inplannen
            - **Contactpersoon:** Tim (voor meer info)
            - **Keywords:** patchingen, afspraak, klant afwezig
            """)
            st.caption("*Dit is een placeholder. Echte AI-analyse wordt later toegevoegd.*")

# Footer
st.divider()
st.caption("Blob Analyse v0.3 | Zenith Security Pilot | © Notifica B.V.")
