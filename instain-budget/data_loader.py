"""
Data loader voor Instain Budgetanalyse.
Leest Syntess ERP-exports (werkbonnen en klantrekeningen) uit Excel.
"""

import pandas as pd
import numpy as np
from pathlib import Path

MAAND_NAMEN = [
    "Januari", "Februari", "Maart", "April", "Mei", "Juni",
    "Juli", "Augustus", "September", "Oktober", "November", "December",
]

MAAND_MAP = {naam.lower(): i + 1 for i, naam in enumerate(MAAND_NAMEN)}


def load_werkbonnen(path: str | Path) -> pd.DataFrame:
    """Laad werkbonnen (WB) sheet uit het budgetanalyse Excel-bestand."""
    df = pd.read_excel(
        path,
        sheet_name="Syntess invoer WB",
        engine="openpyxl",
    )

    # Standaardiseer kolomnamen
    df.columns = df.columns.str.strip()

    # Zorg dat datumkolommen datetime zijn
    for col in ["Aanmaakdatum", "Laatste uitvoerdatum", "Gereedmeld-datum"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Bereken periode en jaar uit gereedmelddatum
    if "Gereedmeld-datum" in df.columns:
        df["maand_nr"] = df["Gereedmeld-datum"].dt.month
        df["maand_naam"] = df["maand_nr"].map(
            lambda m: MAAND_NAMEN[int(m) - 1] if pd.notna(m) else None
        )
        df["jaar"] = df["Gereedmeld-datum"].dt.year

    # Factuurbedrag incl. BTW (opbrengst is excl. BTW in sommige gevallen)
    if "Opbrengst incl.Btw" in df.columns:
        df["bedrag_incl_btw"] = pd.to_numeric(df["Opbrengst incl.Btw"], errors="coerce") * 1.21
    elif "Opbrengst excl. Btw" in df.columns:
        df["bedrag_incl_btw"] = pd.to_numeric(df["Opbrengst excl. Btw"], errors="coerce") * 1.21

    # Standaardiseer referentie- en projectkolommen
    for col in ["Referentie", "Project", "Nummer"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df


def load_klantrekeningen(path: str | Path) -> pd.DataFrame:
    """Laad klantrekeningen (KL) sheet uit het budgetanalyse Excel-bestand."""
    df = pd.read_excel(
        path,
        sheet_name="Syntess invoer KL",
        engine="openpyxl",
    )

    df.columns = df.columns.str.strip()

    # Boekdatum als datetime
    if "Verkoopfactuur boekdatum" in df.columns:
        df["Verkoopfactuur boekdatum"] = pd.to_datetime(
            df["Verkoopfactuur boekdatum"], errors="coerce"
        )
        df["maand_nr"] = df["Verkoopfactuur boekdatum"].dt.month
        df["maand_naam"] = df["maand_nr"].map(
            lambda m: MAAND_NAMEN[int(m) - 1] if pd.notna(m) else None
        )
        df["jaar"] = df["Verkoopfactuur boekdatum"].dt.year

    # Factuurbedrag incl. BTW
    if "Opbrengst ex btw" in df.columns:
        df["bedrag_incl_btw"] = pd.to_numeric(df["Opbrengst ex btw"], errors="coerce") * 1.21
    elif "Opbrengst incl. btw" in df.columns:
        df["bedrag_incl_btw"] = pd.to_numeric(df["Opbrengst incl. btw"], errors="coerce") * 1.21

    # Standaardiseer referentie (verwijder .0 suffix van numerieke conversie)
    if "Klantrekening referentie" in df.columns:
        df["Klantrekening referentie"] = (
            df["Klantrekening referentie"]
            .astype(str)
            .str.strip()
            .str.replace(r"\.0$", "", regex=True)
        )

    return df


def load_rapportage_config(path: str | Path) -> pd.DataFrame:
    """
    Laad de rapportage-configuratie: opdrachtnummers, categorieen, brontype.
    Extraheert de structuur uit het Rapportage sheet.
    """
    df = pd.read_excel(
        path,
        sheet_name="Rapportage",
        engine="openpyxl",
        header=None,
    )

    rows = []
    current_block = None
    block_start_row = None

    for i in range(df.shape[0]):
        # Detecteer blokheaders (rij 7=0-indexed: "Contract Onderhoud...", etc.)
        b_val = str(df.iloc[i, 1]) if pd.notna(df.iloc[i, 1]) else ""

        if "Contract Onderhoud" in b_val and "Preventief" in b_val:
            current_block = "Preventief onderhoud"
            block_start_row = i + 2  # skip header row
            continue
        elif "Reparatie onderhoud" in b_val:
            current_block = "Reparatie onderhoud"
            block_start_row = i + 2
            continue
        elif "Planmatig onderhoud" in b_val:
            current_block = "Planmatig onderhoud"
            block_start_row = i + 2
            continue
        elif "Dagelijks onderhoud" in b_val:
            current_block = "Dagelijks onderhoud"
            block_start_row = i + 2
            continue
        elif "Specifieke Opdrachten" in b_val:
            current_block = "Specifieke opdrachten"
            block_start_row = i + 2
            continue

        if current_block is None:
            continue

        # Check of dit een header-rij is (Opdracht, Categorie, etc.)
        if str(df.iloc[i, 1]).strip() in ("Opdracht", ""):
            if str(df.iloc[i, 4]).strip() == "Categorie":
                continue

        # Check of dit een totaalrij is
        e_val = str(df.iloc[i, 4]) if pd.notna(df.iloc[i, 4]) else ""
        if e_val.lower().startswith("totaal") or e_val.lower().startswith("totaaltelling"):
            continue

        # Check of er een opdrachtnummer is (kolom B=1 of kolom A=0)
        opdracht_nr = df.iloc[i, 1]  # kolom B
        if pd.isna(opdracht_nr) or str(opdracht_nr).strip() == "":
            # Soms staat het opdrachtnummer in kolom A
            opdracht_nr = df.iloc[i, 0]
            if pd.isna(opdracht_nr) or str(opdracht_nr).strip() == "":
                continue

        opdracht_nr = str(opdracht_nr).strip()
        code = str(df.iloc[i, 0]).strip() if pd.notna(df.iloc[i, 0]) else ""
        ref_2025 = str(df.iloc[i, 2]).strip() if pd.notna(df.iloc[i, 2]) else ""
        bron = str(df.iloc[i, 3]).strip() if pd.notna(df.iloc[i, 3]) else ""
        categorie = str(df.iloc[i, 4]).strip() if pd.notna(df.iloc[i, 4]) else ""

        if bron not in ("WB", "KL"):
            continue

        rows.append({
            "code": code,
            "opdracht_nr": opdracht_nr,
            "ref_2025": ref_2025,
            "bron": bron,
            "categorie": categorie,
            "blok": current_block,
            "excel_rij": i + 1,
        })

    return pd.DataFrame(rows)


def load_all(path: str | Path) -> dict:
    """Laad alle data uit het budgetanalyse bestand."""
    path = Path(path)
    return {
        "werkbonnen": load_werkbonnen(path),
        "klantrekeningen": load_klantrekeningen(path),
        "config": load_rapportage_config(path),
    }
