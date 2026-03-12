"""
Calculatie-engine voor Instain Budgetanalyse.
Vervangt alle SUMIFS/COUNTIFS uit het Excel-bestand.
"""

import pandas as pd
import numpy as np
from data_loader import MAAND_NAMEN


def realisatie_per_maand(
    wb: pd.DataFrame,
    kl: pd.DataFrame,
    config: pd.DataFrame,
    jaar: int = 2026,
) -> pd.DataFrame:
    """
    Bereken realisatie per opdracht per maand.
    Vervangt alle SUMIFS-formules uit het Rapportage sheet.

    Elke rapportageregel is de SOM van twee matches:
    - WB: SUMIFS op Referentie=opdracht_nr + SUMIFS op Referentie=ref_2025
    - KL: SUMIFS op Klantrekening referentie=opdracht_nr + ref_2025
    - Dagelijks/Specifiek: SUMIFS op Project=opdracht_nr + Project=ref_2025
    """
    wb_jaar = wb[wb["jaar"] == jaar].copy()

    # Detecteer KL opdrachtnummers die door meerdere config-rijen gedeeld worden
    kl_cfg = config[config["bron"] == "KL"]
    duplicate_kl_refs = set(
        kl_cfg.loc[kl_cfg["opdracht_nr"].duplicated(keep=False), "opdracht_nr"]
    )

    results = []

    for _, row in config.iterrows():
        opdracht_nr = row["opdracht_nr"]
        ref_2025 = row["ref_2025"]
        bron = row["bron"]
        blok = row["blok"]
        code = row["code"]

        # Skip de "onbenoemd" config-rij - die berekenen we apart
        if opdracht_nr == "onbenoemd":
            continue

        maand_bedragen = {}

        for maand_naam in MAAND_NAMEN:
            bedrag = 0.0

            if bron == "KL":
                # KL matching: op opdracht_nr (kolom B)
                mask = (
                    (kl["Klantrekening referentie"] == opdracht_nr)
                    & (kl["maand_naam"] == maand_naam)
                )

                # Als meerdere config-rijen dezelfde opdracht_nr delen,
                # filter dan ook op KL Project omschrijving via de code
                if opdracht_nr in duplicate_kl_refs and code:
                    # Match code (bijv. "COH.3" of "COH3") in KL Project omschrijving
                    # Verwijder punten uit zowel code als omschrijving voor fuzzy match
                    code_clean = code.replace(".", "")  # COH.3 -> COH3
                    mask = mask & (
                        kl["Project omschrijving"]
                        .astype(str)
                        .str.replace(".", "", regex=False)
                        .str.contains(code_clean, case=False, na=False)
                    )

                bedrag += kl.loc[mask, "bedrag_incl_btw"].sum()

            elif bron == "WB":
                maand_mask = wb_jaar["maand_naam"] == maand_naam

                if blok in ("Reparatie onderhoud", "Planmatig onderhoud"):
                    # Reparatie/Planmatig: SUMIFS(WB.Referentie==B) + SUMIFS(WB.Referentie==C)
                    bedrag += wb_jaar.loc[
                        (wb_jaar["Referentie"] == opdracht_nr) & maand_mask,
                        "bedrag_incl_btw",
                    ].sum()
                    if ref_2025 and ref_2025 != "nan" and ref_2025 != opdracht_nr:
                        bedrag += wb_jaar.loc[
                            (wb_jaar["Referentie"] == ref_2025) & maand_mask,
                            "bedrag_incl_btw",
                        ].sum()

                elif blok == "Dagelijks onderhoud":
                    # Dagelijks: SUMIFS(WB.Project==C) + SUMIFS(WB.Project==B)
                    bedrag += wb_jaar.loc[
                        (wb_jaar["Project"] == opdracht_nr) & maand_mask,
                        "bedrag_incl_btw",
                    ].sum()
                    if ref_2025 and ref_2025 != "nan" and ref_2025 != opdracht_nr:
                        bedrag += wb_jaar.loc[
                            (wb_jaar["Project"] == ref_2025) & maand_mask,
                            "bedrag_incl_btw",
                        ].sum()

                else:
                    # Specifieke opdrachten: SUMIFS(WB.Project==C) + SUMIFS(WB.Referentie==B)
                    # NB: Hier worden TWEE kolommen gecombineerd!
                    if ref_2025 and ref_2025 != "nan":
                        bedrag += wb_jaar.loc[
                            (wb_jaar["Project"] == ref_2025) & maand_mask,
                            "bedrag_incl_btw",
                        ].sum()
                    bedrag += wb_jaar.loc[
                        (wb_jaar["Referentie"] == opdracht_nr) & maand_mask,
                        "bedrag_incl_btw",
                    ].sum()

            maand_bedragen[maand_naam] = round(bedrag, 2)

        result_row = {
            "code": row["code"],
            "opdracht_nr": opdracht_nr,
            "ref_2025": ref_2025,
            "bron": bron,
            "categorie": row["categorie"],
            "blok": blok,
        }
        result_row.update(maand_bedragen)
        result_row["totaal"] = round(sum(maand_bedragen.values()), 2)
        results.append(result_row)

    # Voeg "onbenoemde posten" rij toe (WB met Gemarkeerd==0)
    onb = onbenoemde_wb_posten(wb, jaar)
    onb_row = {
        "code": "",
        "opdracht_nr": "onbenoemd",
        "ref_2025": "",
        "bron": "WB",
        "categorie": "Overige, niet benoemde posten (WB)",
        "blok": "Specifieke opdrachten",
    }
    onb_row.update(onb)
    onb_row["totaal"] = round(sum(onb.values()), 2)
    results.append(onb_row)

    return pd.DataFrame(results)


def onbenoemde_wb_posten(
    wb: pd.DataFrame,
    jaar: int = 2026,
) -> dict[str, float]:
    """
    Bereken werkbonnen die niet aan een bekende opdracht gekoppeld zijn.
    Gebruikt de 'Gemarkeerd' kolom: waarde 0 = niet gekoppeld.
    Dit is identiek aan de Excel-formule: SUMIFS(WB!T, WB!V, 0, WB!R, maand)
    """
    wb_jaar = wb[(wb["jaar"] == jaar)].copy()

    # Gebruik Gemarkeerd kolom als die beschikbaar is
    if "Gemarkeerd" in wb_jaar.columns:
        onbenoemd = wb_jaar[wb_jaar["Gemarkeerd"] == 0]
    else:
        # Fallback: gebruik bekende refs
        onbenoemd = wb_jaar

    result = {}
    for maand_naam in MAAND_NAMEN:
        result[maand_naam] = round(
            onbenoemd[onbenoemd["maand_naam"] == maand_naam]["bedrag_incl_btw"].sum(), 2
        )
    return result


def totalen_per_blok(realisatie_df: pd.DataFrame) -> pd.DataFrame:
    """Bereken totalen per onderhoudscategorie (blok)."""
    maand_cols = [c for c in realisatie_df.columns if c in MAAND_NAMEN]
    totalen = realisatie_df.groupby("blok")[maand_cols + ["totaal"]].sum().reset_index()
    return totalen


def prognose_cumulatief(
    realisatie_df: pd.DataFrame,
    budget_per_opdracht: dict[str, float],
) -> pd.DataFrame:
    """
    Bereken cumulatieve prognose per opdracht.
    Waar realisatie 0 is, valt het terug op maandelijks budget (jaarbudget/12).
    """
    rows = []
    for _, row in realisatie_df.iterrows():
        key = row["opdracht_nr"]
        jaar_budget = budget_per_opdracht.get(key, 0)
        maand_budget = jaar_budget / 12

        budget_row = {"opdracht_nr": key, "categorie": row["categorie"], "type": "budget"}
        realisatie_row = {"opdracht_nr": key, "categorie": row["categorie"], "type": "realisatie"}
        prognose_row = {"opdracht_nr": key, "categorie": row["categorie"], "type": "prognose"}

        cumulatief = 0
        for maand in MAAND_NAMEN:
            realisatie_val = row.get(maand, 0)
            budget_row[maand] = maand_budget
            realisatie_row[maand] = realisatie_val
            # Prognose: gebruik realisatie als die er is, anders budget
            prognose_val = realisatie_val if realisatie_val > 0 else maand_budget
            cumulatief += prognose_val
            prognose_row[maand] = cumulatief

        rows.extend([budget_row, realisatie_row, prognose_row])

    return pd.DataFrame(rows)


def aantallen_per_type(
    wb: pd.DataFrame,
    jaar: int = 2026,
) -> pd.DataFrame:
    """
    Tel het aantal werkbonnen per storingstype per maand.
    Vervangt COUNTIFS uit Analyse aantallen sheet.
    """
    wb_jaar = wb[wb["jaar"] == jaar].copy()

    if "Titel" not in wb_jaar.columns:
        return pd.DataFrame()

    # Groepeer op Titel (storingstype) en maand
    counts = (
        wb_jaar.groupby(["Titel", "maand_naam"])
        .size()
        .reset_index(name="aantal")
    )

    # Pivot naar maand-kolommen
    pivot = counts.pivot_table(
        index="Titel",
        columns="maand_naam",
        values="aantal",
        fill_value=0,
    )

    # Herorden kolommen op maand
    existing_maanden = [m for m in MAAND_NAMEN if m in pivot.columns]
    pivot = pivot[existing_maanden]
    pivot["totaal"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("totaal", ascending=False)

    return pivot.reset_index()


def detail_werkbonnen(
    wb: pd.DataFrame,
    config_row: pd.Series,
    maand: str | None = None,
    jaar: int = 2026,
) -> pd.DataFrame:
    """
    Haal de onderliggende werkbonnen op voor een specifieke rapportageregel.
    Dit is de drill-down functie (vervangt de VBA dubbelklik).
    """
    wb_jaar = wb[wb["jaar"] == jaar].copy()

    opdracht_nr = config_row["opdracht_nr"]
    ref_2025 = config_row["ref_2025"]
    bron = config_row["bron"]
    blok = config_row["blok"]

    if bron == "KL":
        return pd.DataFrame()  # KL heeft geen werkbondetails

    if blok in ("Reparatie onderhoud", "Planmatig onderhoud"):
        match_col = "Referentie"
    else:
        match_col = "Project"

    mask = wb_jaar[match_col] == opdracht_nr
    if ref_2025 and ref_2025 != "nan" and ref_2025 != opdracht_nr:
        mask = mask | (wb_jaar[match_col] == ref_2025)

    result = wb_jaar[mask].copy()

    if maand:
        result = result[result["maand_naam"] == maand]

    display_cols = [
        "Nummer", "Adres", "Titel", "Gereedmeld-datum",
        "bedrag_incl_btw", "Verkoopfactuur nummers", "Notitie",
    ]
    available_cols = [c for c in display_cols if c in result.columns]
    return result[available_cols].sort_values("Gereedmeld-datum")
