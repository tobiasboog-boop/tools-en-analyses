#!/usr/bin/env python3
"""Step 1: Contracten - Beheer contract bestanden en koppelingen."""
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import config
from src.models import db, Contract, ContractRelatie
from src.services.relatie_service import RelatieService, ContractMatcher
from src.services.contract_generator import ContractLLMGenerator


# Configure page to use full width
st.set_page_config(layout="wide")

st.title("Contracten")


def get_contracts_from_db() -> list[Contract]:
    """Get all contracts from the database."""
    session = db()
    try:
        contracts = session.query(Contract).filter(
            Contract.active == True
        ).order_by(Contract.filename).all()
        # Detach from session to avoid issues
        for c in contracts:
            session.expunge(c)
        return contracts
    finally:
        session.close()


def save_contract_to_db(
    filename: str,
    content: str,
    source_file: str = None,
    source_sheet: str = None
) -> Contract:
    """Save or update a contract in the database."""
    session = db()
    try:
        # Check if contract with this filename exists
        existing = session.query(Contract).filter(
            Contract.filename == filename
        ).first()

        if existing:
            existing.content = content
            existing.source_file = source_file
            existing.source_sheet = source_sheet
            existing.updated_at = datetime.utcnow()
            contract = existing
        else:
            contract = Contract(
                filename=filename,
                content=content,
                source_file=source_file,
                source_sheet=source_sheet,
                active=True
            )
            session.add(contract)

        session.commit()
        session.refresh(contract)
        session.expunge(contract)
        return contract
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()


def update_contract_llm_context(contract_id: int, llm_context: str) -> bool:
    """Update contract with LLM interpretation context/instructions."""
    session = db()
    try:
        contract = session.query(Contract).filter(Contract.id == contract_id).first()
        if contract:
            contract.llm_context = llm_context if llm_context else None
            contract.updated_at = datetime.utcnow()
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()


def update_contract_llm_ready(contract_id: int, llm_ready: str) -> bool:
    """Update contract with LLM-ready version."""
    session = db()
    try:
        contract = session.query(Contract).filter(Contract.id == contract_id).first()
        if contract:
            contract.llm_ready = llm_ready if llm_ready else None
            contract.updated_at = datetime.utcnow()
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()


def get_contract_relaties(contract_id: int) -> list[ContractRelatie]:
    """Get all relaties linked to a contract."""
    session = db()
    try:
        links = session.query(ContractRelatie).filter(
            ContractRelatie.contract_id == contract_id
        ).order_by(ContractRelatie.client_name).all()
        for link in links:
            session.expunge(link)
        return links
    finally:
        session.close()


def get_all_contract_relaties() -> dict[int, list[ContractRelatie]]:
    """Get all contract-relatie links in one query, grouped by contract_id."""
    session = db()
    try:
        links = session.query(ContractRelatie).order_by(
            ContractRelatie.contract_id, ContractRelatie.client_name
        ).all()
        for link in links:
            session.expunge(link)

        # Group by contract_id
        result = {}
        for link in links:
            if link.contract_id not in result:
                result[link.contract_id] = []
            result[link.contract_id].append(link)
        return result
    finally:
        session.close()


def add_contract_relatie(contract_id: int, client_id: str, client_name: str) -> bool:
    """Add a relatie to a contract."""
    session = db()
    try:
        # Check if link already exists
        existing = session.query(ContractRelatie).filter(
            ContractRelatie.contract_id == contract_id,
            ContractRelatie.client_id == client_id
        ).first()
        if existing:
            return False  # Already linked

        link = ContractRelatie(
            contract_id=contract_id,
            client_id=client_id,
            client_name=client_name
        )
        session.add(link)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()


def remove_contract_relatie(contract_id: int, client_id: str) -> bool:
    """Remove a relatie from a contract."""
    session = db()
    try:
        link = session.query(ContractRelatie).filter(
            ContractRelatie.contract_id == contract_id,
            ContractRelatie.client_id == client_id
        ).first()
        if link:
            session.delete(link)
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()


# Sidebar
with st.sidebar:
    st.header("Status")

    try:
        session = db()
        total_contracts = session.query(Contract).filter(Contract.active == True).count()
        # Count contracts that have at least one relatie linked
        linked_contract_ids = session.query(ContractRelatie.contract_id).distinct().subquery()
        linked_contracts = session.query(Contract).filter(
            Contract.active == True,
            Contract.id.in_(linked_contract_ids)
        ).count()
        unlinked_contracts = total_contracts - linked_contracts
        session.close()
        st.metric("Contracten", total_contracts)
        st.metric("Gekoppeld", linked_contracts)
        st.metric("Niet gekoppeld", unlinked_contracts)
    except Exception as e:
        st.error(f"DB Error: {e}")

# Main content - 3 substappen
tab1, tab2, tab3 = st.tabs([
    "📁 Files",
    "🔄 Conversie",
    "🔗 Register"
])

# =============================================================================
# TAB 1: FILES - Upload en beheer contract bestanden
# =============================================================================
with tab1:
    st.subheader("📤 Upload Contract Bestand")

    # Import upload services
    from src.models.database import SessionLocal
    from src.services.file_upload_service import (
        upload_file, FileUploadError, ALLOWED_EXTENSIONS, MAX_FILE_SIZE
    )
    from src.services.text_extraction_service import (
        extract_text, save_extracted_text, TextExtractionError
    )

    # Info box
    st.info(f"""
    **Toegestane bestandstypes:** {', '.join(ALLOWED_EXTENSIONS)}
    **Maximum bestandsgrootte:** {MAX_FILE_SIZE / (1024*1024):.0f} MB
    """)

    # File uploader
    uploaded_file = st.file_uploader(
        "Selecteer een contract bestand",
        type=['pdf', 'docx', 'xlsx'],
        help="Kies één bestand om te uploaden"
    )

    if uploaded_file is not None:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Bestandsnaam", uploaded_file.name)
        with col2:
            file_size_mb = uploaded_file.size / (1024 * 1024)
            st.metric("Grootte", f"{file_size_mb:.2f} MB")
        with col3:
            ext = Path(uploaded_file.name).suffix.lower()
            st.metric("Type", ext)

        # Read file content
        file_content = uploaded_file.read()

        # Upload button
        if st.button("✅ Upload en Verwerk", type="primary"):
            with st.spinner("Bezig met uploaden..."):
                db_session = SessionLocal()
                try:
                    # Upload file
                    upload_result = upload_file(
                        db=db_session,
                        filename=uploaded_file.name,
                        file_content=file_content,
                        uploaded_by="WVC User"
                    )

                    if upload_result['is_duplicate']:
                        st.warning(f"⚠️ Duplicaat gedetecteerd! (file_id: {upload_result['duplicate_of']})")
                    else:
                        st.success(f"✅ Bestand geüpload! (file_id: {upload_result['file_id']})")

                    # Extract text
                    try:
                        extracted_text = extract_text(file_content, uploaded_file.name)
                        save_extracted_text(db_session, upload_result['file_id'], extracted_text)
                        st.success(f"✅ Tekst geëxtraheerd ({len(extracted_text)} karakters)")
                    except TextExtractionError as e:
                        st.warning(f"⚠️ Tekst extractie fout: {e}")

                    st.rerun()

                except FileUploadError as e:
                    st.error(f"❌ Upload fout: {e}")
                except Exception as e:
                    st.error(f"❌ Onverwachte fout: {e}")
                finally:
                    db_session.close()

    st.divider()

    # List uploaded files
    st.subheader("📋 Geüploade Bestanden")

    db_session = SessionLocal()
    try:
        from sqlalchemy import text
        result = db_session.execute(text("""
            SELECT id, filename, file_size, mime_type, uploaded_at, uploaded_by,
                   LENGTH(extracted_text) as text_length
            FROM contract_checker.contract_files
            WHERE active = true
            ORDER BY uploaded_at DESC
        """))

        rows = result.fetchall()

        if rows:
            df = pd.DataFrame(rows, columns=[
                'ID', 'Bestandsnaam', 'Grootte (bytes)', 'Type',
                'Geüpload op', 'Door', 'Tekst lengte'
            ])
            df['Grootte (MB)'] = (df['Grootte (bytes)'] / (1024 * 1024)).round(2)
            df = df.drop(columns=['Grootte (bytes)'])
            st.dataframe(df, use_container_width=True, hide_index=True)

            col1, col2, col3 = st.columns(3)
            col1.metric("PDF", len([r for r in rows if 'pdf' in r[3].lower()]))
            col2.metric("Word", len([r for r in rows if 'word' in r[3].lower()]))
            col3.metric("Excel", len([r for r in rows if 'spreadsheet' in r[3].lower()]))
        else:
            st.info("Nog geen bestanden geüpload.")

    except Exception as e:
        st.error(f"Kan bestanden niet laden: {e}")
    finally:
        db_session.close()

# =============================================================================
# TAB 2: CONVERSIE - Omzetten naar LLM-leesbare tekst en opslaan in database
# =============================================================================
with tab2:
    # Get contracts already in database
    db_contracts = get_contracts_from_db()

    # Try to load folder for import functionality
    try:
        from extract_contracts import extract_docx, extract_xlsx_per_sheet
        folder = config.CONTRACTS_FOLDER
        folder_path = Path(folder) if folder else None
        has_folder = folder_path and folder_path.exists()
    except:
        has_folder = False
        folder_path = None

    if has_folder:
        # Get source files
        docx_files = list(folder_path.glob("*.docx"))
        xlsx_files = list(folder_path.glob("*.xlsx"))
        source_files = docx_files + xlsx_files
    else:
        source_files = []
    db_source_files = {c.source_file for c in db_contracts if c.source_file}

    # Calculate which source files are already processed
    files_to_import = []
    files_imported = []

    for source_file in source_files:
        if source_file.name in db_source_files:
            files_imported.append(source_file)
        else:
            files_to_import.append(source_file)

    # Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Bronbestanden", len(source_files))
    col2.metric("Geïmporteerd", len(files_imported))
    col3.metric("Nog te importeren", len(files_to_import))

    st.divider()

    # Import section
    st.subheader("Bronbestanden importeren")

    if files_to_import:
        st.warning(f"{len(files_to_import)} bestand(en) nog niet geïmporteerd")

        with st.expander("Bekijk bestanden"):
            for f in files_to_import:
                st.write(f"- {f.name}")

        if st.button("Importeer naar database", type="primary", key="import_btn"):
            progress = st.progress(0)
            status = st.empty()
            total_contracts = 0

            for i, source_file in enumerate(files_to_import):
                status.text(f"Verwerken: {source_file.name}")
                try:
                    ext = source_file.suffix.lower()

                    if ext == ".docx":
                        # Word: één contract per bestand
                        content = extract_docx(source_file)
                        filename = f"{source_file.stem}.txt"
                        save_contract_to_db(
                            filename=filename,
                            content=content,
                            source_file=source_file.name,
                            source_sheet=None
                        )
                        total_contracts += 1

                    elif ext == ".xlsx":
                        # Excel: één contract per sheet
                        sheet_contents = extract_xlsx_per_sheet(source_file)
                        for sheet_name, content in sheet_contents.items():
                            safe_name = re.sub(r'[^\w\s-]', '', sheet_name).strip()
                            safe_name = re.sub(r'\s+', '_', safe_name)
                            filename = f"{safe_name}.txt"
                            save_contract_to_db(
                                filename=filename,
                                content=content,
                                source_file=source_file.name,
                                source_sheet=sheet_name
                            )
                            total_contracts += 1

                except Exception as e:
                    st.error(f"Fout bij {source_file.name}: {e}")

                progress.progress((i + 1) / len(files_to_import))

            status.empty()
            progress.empty()
            st.success(f"{total_contracts} contract(en) geïmporteerd!")
            st.rerun()
    else:
        st.success("Alle bronbestanden zijn geïmporteerd")

    st.divider()

    # Show contracts in database
    st.subheader("Contracten in database")
    if db_contracts:
        for contract in sorted(db_contracts, key=lambda x: x.filename.lower()):
            label = contract.filename
            if contract.source_sheet:
                label += f"  (sheet: {contract.source_sheet})"

            with st.expander(label):
                st.caption(f"Bron: {contract.source_file or '-'}")

                if contract.content:
                    st.text_area(
                        "LLM tekst (platte conversie)",
                        contract.content,
                        height=250,
                        key=f"content_{contract.id}",
                        disabled=True
                    )

                st.divider()

                # LLM Context - interpretation instructions
                st.write("**LLM Interpretatie Context**")
                st.caption("Instructies voor de LLM over hoe dit contract te interpreteren. "
                          "Bijv: 'Dit is een all-in tarief', 'Staffelkorting bij >10 werkbonnen', etc.")

                current_llm_context = contract.llm_context or ""
                new_llm_context = st.text_area(
                    "LLM Context",
                    value=current_llm_context,
                    height=150,
                    key=f"llm_context_{contract.id}",
                    placeholder="Voeg hier instructies toe voor de LLM over hoe dit contract te begrijpen..."
                )

                if st.button("💾 Opslaan", key=f"save_llm_context_{contract.id}", type="primary"):
                    update_contract_llm_context(contract.id, new_llm_context)
                    st.success("LLM context opgeslagen!")
                    st.rerun()

                st.divider()

                # LLM Ready - generated improved version
                st.write("**LLM Ready**")
                with st.expander("ℹ️ Wat doet LLM Ready?"):
                    st.markdown("""
De LLM Ready versie wordt gegenereerd door Claude AI op basis van:
1. **Platte tekst** - de geëxtraheerde contract tekst hierboven
2. **LLM Context** - jouw instructies over hoe het contract te interpreteren

De LLM structureert het contract met duidelijke secties (dekking, uitsluitingen, tarieven)
en markeert belangrijke voorwaarden. Je kunt de gegenereerde tekst daarna handmatig aanvullen
met inzichten uit werkbonnen.
                    """)

                current_llm_ready = contract.llm_ready or ""
                new_llm_ready = st.text_area(
                    "LLM Ready tekst",
                    value=current_llm_ready,
                    height=250,
                    key=f"llm_ready_{contract.id}",
                    placeholder="Genereer eerst een LLM Ready versie, of schrijf handmatig..."
                )

                # Action buttons
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("💾 Opslaan", key=f"save_llm_ready_{contract.id}", type="primary"):
                        update_contract_llm_ready(contract.id, new_llm_ready)
                        st.success("LLM Ready tekst opgeslagen!")
                        st.rerun()
                with col2:
                    btn_label = "🔄 Opnieuw genereren" if contract.llm_ready else "✨ Genereer"
                    confirm_key = f"confirm_regen_{contract.id}"

                    if contract.llm_ready and confirm_key not in st.session_state:
                        # First click: ask for confirmation
                        if st.button(btn_label, key=f"gen_llm_ready_{contract.id}"):
                            st.session_state[confirm_key] = True
                            st.rerun()
                    elif contract.llm_ready and confirm_key in st.session_state:
                        # Show confirmation
                        st.warning("Bestaande tekst wordt overschreven!")
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("✅ Bevestig", key=f"confirm_yes_{contract.id}"):
                                del st.session_state[confirm_key]
                                if not config.ANTHROPIC_API_KEY:
                                    st.error("Anthropic API key niet geconfigureerd.")
                                elif not contract.content:
                                    st.error("Contract heeft geen content.")
                                else:
                                    with st.spinner("Genereren LLM Ready versie..."):
                                        try:
                                            generator = ContractLLMGenerator()
                                            llm_ready_content = generator.generate_llm_ready(contract.id)
                                            update_contract_llm_ready(contract.id, llm_ready_content)
                                            st.success("LLM Ready versie gegenereerd!")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Fout bij genereren: {e}")
                        with c2:
                            if st.button("❌ Annuleer", key=f"confirm_no_{contract.id}"):
                                del st.session_state[confirm_key]
                                st.rerun()
                    else:
                        # No existing content, generate directly
                        if st.button(btn_label, key=f"gen_llm_ready_{contract.id}"):
                            if not config.ANTHROPIC_API_KEY:
                                st.error("Anthropic API key niet geconfigureerd. Stel ANTHROPIC_API_KEY in .env in.")
                            elif not contract.content:
                                st.error("Contract heeft geen content om te verwerken.")
                            else:
                                with st.spinner("Genereren LLM Ready versie..."):
                                    try:
                                        generator = ContractLLMGenerator()
                                        llm_ready_content = generator.generate_llm_ready(contract.id)
                                        update_contract_llm_ready(contract.id, llm_ready_content)
                                        st.success("LLM Ready versie gegenereerd!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Fout bij genereren: {e}")
                with col3:
                    if contract.llm_ready:
                        if st.button("🗑️ Verwijderen", key=f"del_llm_ready_{contract.id}"):
                            update_contract_llm_ready(contract.id, None)
                            st.rerun()
    else:
        st.info("Nog geen contracten in de database")

# =============================================================================
# TAB 3: REGISTER - Koppelen aan relaties
# =============================================================================
with tab3:
    # Load contracts and relaties
    contracts = get_contracts_from_db()

    # Load relaties with caching (v2 - forced refresh)
    @st.cache_data(ttl=300)
    def load_relaties_v2():
        service = RelatieService()
        try:
            return service.get_relaties()
        finally:
            service.close()

    with st.spinner("Laden relaties..."):
        relaties = load_relaties_v2()

    if not relaties:
        st.error("Kan geen relaties laden uit de database")
        st.stop()

    # Create matcher for suggestions
    matcher = ContractMatcher(relaties)

    # Build contract links lookup (contract_id -> list of links) - single query
    contract_links_map = get_all_contract_relaties()

    # Statistics
    linked = [c for c in contracts if contract_links_map.get(c.id)]
    unlinked = [c for c in contracts if not contract_links_map.get(c.id)]

    col1, col2, col3 = st.columns(3)
    col1.metric("Contracten", len(contracts))
    col2.metric("Gekoppeld", len(linked))
    col3.metric("Niet gekoppeld", len(unlinked))

    st.divider()

    # ==========================================================================
    # SECTION 1: Contract overzicht met suggesties
    # ==========================================================================
    st.subheader("Contract overzicht")

    if not contracts:
        st.info("Geen contracten in database. Ga eerst naar de Conversie tab.")
    else:
        # Build table with match suggestions
        table_data = []
        auto_match_candidates = []

        for c in sorted(contracts, key=lambda x: x.filename.lower()):
            links = contract_links_map.get(c.id, [])
            suggestions = matcher.find_matches(c.filename, top_n=1, min_score=0.4)
            best_match = suggestions[0] if suggestions else None

            # Show linked clients
            if links:
                if len(links) == 1:
                    client_display = f"{links[0].client_id} - {links[0].client_name}"
                else:
                    client_display = f"{len(links)} relaties"
            else:
                client_display = "-"

            row = {
                "Contract": c.filename,
                "Bron": c.source_file or "-",
                "Gekoppelde klant(en)": client_display,
                "Suggestie": "",
                "Score": "",
            }

            # Only show suggestions for unlinked contracts
            if best_match and not links:
                row["Suggestie"] = f"{best_match['client_id']} - {best_match['client_name']}"
                row["Score"] = f"{int(best_match['score'] * 100)}%"
                auto_match_candidates.append({
                    "contract": c,
                    "match": best_match
                })

            table_data.append(row)

        st.dataframe(table_data, use_container_width=True, hide_index=True)

        # Auto-match section with individual selection
        if auto_match_candidates:
            st.divider()
            st.subheader("Automatisch koppelen")
            st.write(f"**{len(auto_match_candidates)}** contract(en) met suggesties. Selecteer welke je wilt koppelen:")

            # Checkboxes per candidate
            selected_items = []
            for item in auto_match_candidates:
                c = item["contract"]
                m = item["match"]
                score_pct = int(m['score'] * 100)

                col1, col2, col3 = st.columns([0.5, 3, 1])
                with col1:
                    is_selected = st.checkbox(
                        "Selecteer",
                        value=True,  # Default selected
                        key=f"auto_select_{c.id}",
                        label_visibility="collapsed"
                    )
                with col2:
                    st.write(f"**{c.filename}** → {m['client_id']} - {m['client_name']}")
                with col3:
                    st.write(f"{score_pct}%")

                if is_selected:
                    selected_items.append(item)

            st.divider()

            # Action buttons
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                if st.button(
                    f"Koppel geselecteerde ({len(selected_items)})",
                    type="primary",
                    key="auto_match_btn",
                    disabled=len(selected_items) == 0
                ):
                    progress = st.progress(0)
                    for i, item in enumerate(selected_items):
                        c = item["contract"]
                        m = item["match"]
                        add_contract_relatie(c.id, m["client_id"], m["client_name"])
                        progress.progress((i + 1) / len(selected_items))
                    progress.empty()
                    st.success(f"{len(selected_items)} contracten gekoppeld!")
                    st.rerun()
            with col2:
                if len(selected_items) < len(auto_match_candidates):
                    st.caption(f"{len(auto_match_candidates) - len(selected_items)} overgeslagen")

    st.divider()

    # ==========================================================================
    # SECTION 2: Handmatig koppelen per contract (meerdere relaties mogelijk)
    # ==========================================================================
    st.subheader("Relaties koppelen")
    st.caption("Een contract kan aan meerdere relaties gekoppeld worden")

    if not contracts:
        st.info("Geen contracten beschikbaar")
    else:
        for contract in sorted(contracts, key=lambda x: x.filename.lower()):
            # Get existing links for this contract
            contract_links = get_contract_relaties(contract.id)
            link_count = len(contract_links)

            # Get match suggestions
            suggestions = matcher.find_matches(contract.filename, top_n=3, min_score=0.3)

            # Build label
            if link_count == 0:
                label = f" {contract.filename}"
            elif link_count == 1:
                label = f" {contract.filename} → {contract_links[0].client_id}"
            else:
                label = f" {contract.filename} → {link_count} relaties"

            with st.expander(label, expanded=False):
                col1, col2 = st.columns([2, 1])

                with col1:
                    # Show existing links
                    if contract_links:
                        st.write("**Gekoppelde relaties:**")
                        for link in contract_links:
                            link_col1, link_col2 = st.columns([4, 1])
                            with link_col1:
                                st.write(f"- {link.client_id} - {link.client_name}")
                            with link_col2:
                                if st.button("❌", key=f"remove_{contract.id}_{link.client_id}", help="Verwijder koppeling"):
                                    remove_contract_relatie(contract.id, link.client_id)
                                    st.success(f"Koppeling met {link.client_id} verwijderd")
                                    st.rerun()
                        st.write("")

                    # Show suggestions for contracts with no or few links
                    linked_client_ids = {link.client_id for link in contract_links}
                    available_suggestions = [s for s in suggestions if s["client_id"] not in linked_client_ids]

                    if available_suggestions:
                        st.write("**Suggesties:**")
                        for sug in available_suggestions:
                            score_pct = int(sug["score"] * 100)
                            if st.button(
                                f"+ {sug['client_id']} - {sug['client_name']} ({score_pct}%)",
                                key=f"sug_{contract.id}_{sug['client_id']}"
                            ):
                                add_contract_relatie(contract.id, sug["client_id"], sug["client_name"])
                                st.success(f"Relatie {sug['client_id']} toegevoegd")
                                st.rerun()
                        st.write("")

                    # Search to add new relatie
                    st.write("**Nieuwe relatie toevoegen:**")
                    search_term = st.text_input(
                        "Zoek klant (nummer of naam)",
                        key=f"search_{contract.id}",
                        placeholder="Bijv: 12345 of Aannemer..."
                    )

                    if search_term:
                        search_lower = search_term.lower()
                        filtered_relaties = [
                            r for r in relaties
                            if (search_lower in r["client_id"].lower()
                                or search_lower in (r["client_name"] or "").lower())
                            and r["client_id"] not in linked_client_ids
                        ]

                        if filtered_relaties:
                            st.caption(f"{len(filtered_relaties)} resultaten (max 20 getoond)")
                            for r in sorted(filtered_relaties, key=lambda x: x["client_name"] or "")[:20]:
                                if st.button(
                                    f"+ {r['client_id']} - {r['client_name']}",
                                    key=f"add_{contract.id}_{r['client_id']}"
                                ):
                                    add_contract_relatie(contract.id, r["client_id"], r["client_name"])
                                    st.success(f"Relatie {r['client_id']} toegevoegd")
                                    st.rerun()
                        else:
                            st.info("Geen resultaten gevonden")

                with col2:
                    st.write("**Contract info:**")
                    st.write(f"Bron: {contract.source_file or '-'}")
                    st.write(f"Sheet: {contract.source_sheet or '-'}")
                    st.write(f"Koppelingen: {link_count}")
