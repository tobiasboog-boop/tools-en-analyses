#!/usr/bin/env python3
"""Step 3: Beoordeling - Classificeer werkbonnen met AI.

Twee modi (overgenomen uit selectie):
- VALIDATIE: Classificeer en vergelijk met werkelijke factureerstatus (hit rate)
- CLASSIFICATIE: Classificeer openstaande werkbonnen
"""
import streamlit as st

from src.config import config
from src.models import db
from src.models.classification import Classification
from src.services.contract_loader import ContractLoader
from src.services.classifier import ClassificationService
from src.services.werkbon_keten_service import WerkbonKetenService, WerkbonVerhaalBuilder


# Configure page to use full width
st.set_page_config(layout="wide")

st.title("Beoordeling")

# Get selected werkbonnen from session state
werkbonnen = st.session_state.get("werkbonnen_for_beoordeling", [])
modus = st.session_state.get("selectie_modus", "validatie")

# Sidebar
with st.sidebar:
    st.header("Status")

    st.markdown(f"**Modus:** {'🔬 Validatie' if modus == 'validatie' else '📋 Classificatie'}")

    st.divider()

    st.markdown("**Geselecteerde werkbonnen:**")
    if werkbonnen:
        st.success(f"{len(werkbonnen)} werkbonnen")
    else:
        st.warning("Geen werkbonnen geselecteerd")
        st.caption("Ga naar Stap 2")

    st.divider()

    st.markdown("**API Configuratie:**")
    if config.ANTHROPIC_API_KEY:
        st.success("API key geconfigureerd")
    else:
        st.error("API key ontbreekt")
        st.caption("Stel ANTHROPIC_API_KEY in .env in")

    st.divider()

    st.markdown("**Confidence threshold:**")
    st.info(f"{config.CONFIDENCE_THRESHOLD}")
    st.caption("Scores hieronder → ONZEKER")


# Main content
if not werkbonnen:
    st.warning("Geen werkbonnen geselecteerd. Ga eerst naar Stap 2.")
    if st.button("Ga naar Werkbon Selectie"):
        st.switch_page("pages/2_Werkbon_Selectie.py")

elif not config.ANTHROPIC_API_KEY:
    st.error("Anthropic API key niet geconfigureerd. Stel ANTHROPIC_API_KEY in .env in.")

else:
    # Show mode info
    if modus == "validatie":
        st.info(f"""
        **🔬 Validatie modus** - {len(werkbonnen)} werkbonnen geselecteerd

        De AI classificeert elke werkbon **zonder** de facturatiegegevens te zien.
        Pas **na** de classificatie halen we de factureerstatus uit de database
        om de voorspelling te controleren en de **hit rate** te berekenen.
        """)
    else:
        st.warning(f"""
        **📋 Classificatie modus** - {len(werkbonnen)} werkbonnen geselecteerd

        De AI classificeert elke werkbon om te bepalen of kosten binnen of
        buiten contract vallen. Facturatiestatus is nog niet bekend.
        """)

    # Options
    col1, col2, col3 = st.columns(3)
    with col1:
        save_to_db = st.checkbox("Resultaten opslaan in database", value=True)
    with col2:
        show_verhaal = st.checkbox("Toon verhaal per werkbon", value=False)
    with col3:
        debug_mode = st.checkbox("Debug modus", value=False)

    st.divider()

    # Preview werkbonnen met hun contracten
    with st.expander(f"📋 Preview werkbonnen en contracten ({len(werkbonnen)} werkbonnen)"):
        try:
            loader = ContractLoader()

            # Group werkbonnen by debiteur
            debiteur_groups = {}
            for wb in werkbonnen:
                debiteur = wb.get("debiteur", "Onbekend")
                if debiteur not in debiteur_groups:
                    debiteur_groups[debiteur] = []
                debiteur_groups[debiteur].append(wb)

            # Show per debiteur
            for debiteur, wbs in debiteur_groups.items():
                st.markdown(f"### {debiteur}")

                # Extract debiteur code and find contract
                debiteur_code = None
                if debiteur and " - " in debiteur:
                    parts = debiteur.split(" - ")
                    if parts and parts[0].strip().isdigit():
                        debiteur_code = parts[0].strip()

                contract = None
                if debiteur_code:
                    contract = loader.get_contract_for_debiteur(debiteur_code)

                if contract:
                    llm_badge = "🤖 LLM-ready" if contract.get("llm_ready") else "📄 Raw"
                    st.success(f"✅ Contract: **{contract['filename']}** {llm_badge}")
                    st.caption(f"Content: {len(contract['content'])} characters")
                else:
                    st.error(f"❌ Geen contract gevonden voor debiteur {debiteur_code or debiteur}")

                # Show werkbonnen
                st.markdown(f"**{len(wbs)} werkbonnen:**")
                for wb in wbs:
                    st.text(f"  • {wb.get('werkbon', '?')} - {wb.get('omschrijving', '')[:50]}...")

                st.divider()

        except Exception as e:
            st.error(f"Fout bij preview: {e}")
            st.exception(e)

    st.divider()

    # Initialize services
    keten_service = WerkbonKetenService()
    verhaal_builder = WerkbonVerhaalBuilder()

    # Process each werkbon
    if st.button("▶️ Start Beoordeling", type="primary"):
        try:
            # Initialize classifier (haalt per werkbon het juiste contract op via debiteur)
            classifier = ClassificationService()

            # Progress
            progress_bar = st.progress(0)
            status_text = st.empty()

            all_results = []
            total = len(werkbonnen)

            for i, wb in enumerate(werkbonnen):
                werkbon_nummer = wb.get("werkbon", f"Werkbon {i+1}")
                status_text.text(f"Beoordelen: {werkbon_nummer} ({i+1}/{total})...")

                # Load keten for this werkbon
                try:
                    keten = keten_service.get_werkbon_keten(
                        wb["hoofdwerkbon_key"],
                        include_kosten_details=True,
                        include_opvolgingen=True,
                        include_oplossingen=True
                    )
                except Exception as e:
                    st.error(f"Fout bij laden keten voor {werkbon_nummer}: {e}")
                    continue

                if not keten:
                    st.warning(f"Kon keten niet laden voor {werkbon_nummer} (key={wb['hoofdwerkbon_key']})")
                    if debug_mode:
                        # Verify key in database
                        from sqlalchemy import text
                        debug_db = db()
                        try:
                            # Check if key exists as WerkbonDocumentKey
                            check1 = debug_db.execute(text("""
                                SELECT COUNT(*) FROM werkbonnen."Werkbonnen"
                                WHERE "WerkbonDocumentKey" = :key
                            """), {"key": wb["hoofdwerkbon_key"]}).scalar()

                            # Check if key exists as HoofdwerkbonDocumentKey
                            check2 = debug_db.execute(text("""
                                SELECT COUNT(*) FROM werkbonnen."Werkbonnen"
                                WHERE "HoofdwerkbonDocumentKey" = :key
                            """), {"key": wb["hoofdwerkbon_key"]}).scalar()

                            st.code(f"""Debug info:
- hoofdwerkbon_key type: {type(wb.get('hoofdwerkbon_key'))}
- hoofdwerkbon_key value: {wb.get('hoofdwerkbon_key')}
- werkbon_document_key: {wb.get('werkbon_document_key')}
- Bestaat als WerkbonDocumentKey: {check1} rijen
- Bestaat als HoofdwerkbonDocumentKey: {check2} rijen
""")
                        except Exception as debug_e:
                            st.error(f"Debug query fout: {debug_e}")
                        finally:
                            debug_db.close()
                    continue

                # Build verhaal for classification
                verhaal = verhaal_builder.build_verhaal(keten)

                # Create werkbon dict for classifier
                werkbon_for_classifier = {
                    "werkbon_id": werkbon_nummer,
                    "hoofdwerkbon_key": wb["hoofdwerkbon_key"],
                    "client_id": keten.relatie_code,  # Key for contract lookup via ContractRelatie
                    "klant_naam": wb.get("klant", ""),
                    "debiteur": wb.get("debiteur", ""),
                    "omschrijving": verhaal,
                    "bedrag": keten.totaal_kosten,
                }

                # Classify
                result = classifier.classify_werkbon(werkbon_for_classifier)
                result["werkbon_nummer"] = werkbon_nummer
                result["werkbon_data"] = wb
                result["keten"] = keten

                # For validation mode: analyse factureerstatus per kostenregel
                if modus == "validatie":
                    # Analyseer factureerstatus van alle kostenregels
                    gefactureerd_bedrag = 0.0
                    niet_factureren_bedrag = 0.0
                    totaal_bedrag = 0.0

                    for wbon in keten.werkbonnen:
                        for p in wbon.paragrafen:
                            for k in p.kosten:
                                totaal_bedrag += k.kostprijs
                                status = (k.factureerstatus or "").strip().lower()
                                # "Gefactureerd" of "Te factureren" = buiten contract
                                if "gefactureerd" in status or "te factureren" in status:
                                    gefactureerd_bedrag += k.kostprijs
                                # "Niet te factureren" = binnen contract
                                elif "niet" in status and "factureren" in status:
                                    niet_factureren_bedrag += k.kostprijs

                    result["facturatie_detail"] = {
                        "gefactureerd": gefactureerd_bedrag,
                        "niet_factureren": niet_factureren_bedrag,
                        "totaal": totaal_bedrag,
                    }

                    # Bepaal "werkelijk" op basis van factureerstatus
                    # Als er gefactureerd is of moet worden → buiten contract (NEE)
                    if gefactureerd_bedrag > 0:
                        result["werkelijk"] = "NEE"  # Was/wordt gefactureerd = buiten contract
                    else:
                        result["werkelijk"] = "JA"  # Niet gefactureerd = binnen contract

                all_results.append(result)

                # Update progress
                progress_bar.progress((i + 1) / total)

                # Show result inline
                with st.container():
                    color = {
                        "JA": "green",
                        "NEE": "red",
                        "ONZEKER": "orange"
                    }.get(result["classificatie"], "gray")

                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(
                            f"**{werkbon_nummer}**: "
                            f":{color}[{result['classificatie']}] "
                            f"(score: {result['mapping_score']:.2f})"
                        )

                        if modus == "validatie":
                            werkelijk = result.get("werkelijk", "?")
                            match = "✅" if result["classificatie"] == werkelijk else "❌"
                            detail = result.get("facturatie_detail", {})
                            st.caption(
                                f"Werkelijk: {werkelijk} {match} — "
                                f"Gefactureerd: €{detail.get('gefactureerd', 0):,.2f} | "
                                f"Niet te fact.: €{detail.get('niet_factureren', 0):,.2f}"
                            )

                    with col2:
                        if show_verhaal:
                            with st.expander("Verhaal"):
                                st.markdown(verhaal[:1000] + "..." if len(verhaal) > 1000 else verhaal)

                st.divider()

            status_text.text("Beoordeling voltooid!")
            keten_service.close()

            # Save to database
            if save_to_db and all_results:
                session = db()
                try:
                    for result in all_results:
                        classification = Classification(
                            werkbon_id=result.get("werkbon_nummer"),
                            hoofdwerkbon_key=result["werkbon_data"].get("hoofdwerkbon_key"),
                            modus=modus,  # "validatie" of "classificatie"
                            classificatie=result["classificatie"],
                            mapping_score=result["mapping_score"],
                            contract_referentie=result.get("contract_referentie"),
                            toelichting=result.get("toelichting"),
                            werkbon_bedrag=result.get("werkbon_bedrag"),
                            # Bij validatie: werkelijke classificatie direct invullen
                            werkelijke_classificatie=result.get("werkelijk") if modus == "validatie" else None,
                        )
                        session.add(classification)
                    session.commit()
                    st.success(f"✅ {len(all_results)} resultaten opgeslagen in database")
                except Exception as e:
                    session.rollback()
                    st.error(f"Fout bij opslaan: {e}")
                finally:
                    session.close()

            # Summary
            st.divider()
            st.subheader("Samenvatting")

            ja = sum(1 for r in all_results if r["classificatie"] == "JA")
            nee = sum(1 for r in all_results if r["classificatie"] == "NEE")
            onzeker = sum(1 for r in all_results if r["classificatie"] == "ONZEKER")

            col1, col2, col3 = st.columns(3)
            col1.metric("Binnen contract (JA)", ja, delta=f"{ja/total*100:.1f}%")
            col2.metric("Te factureren (NEE)", nee, delta=f"{nee/total*100:.1f}%")
            col3.metric("Onzeker", onzeker, delta=f"{onzeker/total*100:.1f}%")

            # Validation mode: show hit rate
            if modus == "validatie":
                st.divider()
                st.subheader("🎯 Hit Rate (Validatie)")

                correct = sum(
                    1 for r in all_results
                    if r.get("werkelijk") and r["classificatie"] == r["werkelijk"]
                )
                incorrect = sum(
                    1 for r in all_results
                    if r.get("werkelijk") and r["classificatie"] != r["werkelijk"]
                    and r["classificatie"] != "ONZEKER"
                )
                uncertain = sum(1 for r in all_results if r["classificatie"] == "ONZEKER")

                total_definitive = correct + incorrect
                hit_rate = (correct / total_definitive * 100) if total_definitive > 0 else 0

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Hit Rate", f"{hit_rate:.1f}%")
                col2.metric("Correct", correct)
                col3.metric("Incorrect", incorrect)
                col4.metric("Onzeker", uncertain)

                # False positives / negatives
                false_neg = sum(
                    1 for r in all_results
                    if r.get("werkelijk") == "NEE" and r["classificatie"] == "JA"
                )
                false_pos = sum(
                    1 for r in all_results
                    if r.get("werkelijk") == "JA" and r["classificatie"] == "NEE"
                )

                st.caption(f"False negatives (gemiste facturatie): {false_neg}")
                st.caption(f"False positives (onterecht gefactureerd): {false_pos}")

                if hit_rate >= 80:
                    st.success(f"✅ Hit rate {hit_rate:.1f}% voldoet aan doel (>80%)")
                else:
                    st.warning(f"⚠️ Hit rate {hit_rate:.1f}% onder doel (>80%)")

            # Store results in session
            st.session_state.beoordeling_results = all_results

            st.divider()
            if st.button("Ga naar Resultaten →"):
                st.switch_page("pages/4_Results.py")

        except Exception as e:
            st.error(f"Fout bij beoordeling: {e}")
            st.exception(e)
