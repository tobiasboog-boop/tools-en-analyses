import pandas as pd
import numpy as np
from pathlib import Path
from datetime import date


def load_portfolio(file_path: str | Path = None) -> pd.DataFrame:
    """Load and parse the VLO Orderportefeuille Excel."""
    if file_path is None:
        file_path = Path(__file__).parent.parent / "data" / "Orderportefeuille.xlsx"

    df = pd.read_excel(file_path, sheet_name="Totaal", header=7)

    # Clean column names
    df.columns = df.columns.astype(str).str.strip()

    # Rename year columns to ensure they're strings
    year_cols = []
    rename_map = {}
    for col in df.columns:
        try:
            year = int(float(col))
            if 2020 <= year <= 2035:
                rename_map[col] = str(year)
                year_cols.append(str(year))
        except (ValueError, TypeError):
            pass
    df = df.rename(columns=rename_map)

    # Standard column mapping
    expected_cols = {
        "Categorie": "categorie",
        "Meerwerk": "meerwerk",
        "Vestiging": "vestiging",
        "Projectnummer": "projectnummer",
        "Naam": "naam",
        "Plaatsnaam": "plaatsnaam",
        "Opdrachtgever": "opdrachtgever",
        "TOTAAL": "totaal",
    }

    col_map = {}
    for orig, new in expected_cols.items():
        matches = [c for c in df.columns if orig.lower() in c.lower()]
        if matches:
            col_map[matches[0]] = new
    for y in year_cols:
        col_map[y] = f"jaar_{y}"

    df = df.rename(columns=col_map)

    # Drop rows where all year columns are NaN/0
    jaar_cols = [f"jaar_{y}" for y in year_cols]
    df = df.dropna(subset=["naam"], how="all")
    df = df[df[jaar_cols].fillna(0).sum(axis=1) > 0].copy()

    # Fill NaN in year columns with 0
    for col in jaar_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Calculate totaal if not present or recalculate
    df["totaal"] = df[jaar_cols].sum(axis=1)

    # Clean text columns
    for col in ["categorie", "meerwerk", "vestiging", "naam", "plaatsnaam", "opdrachtgever"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # Normalize meerwerk
    df["is_meerwerk"] = df["meerwerk"].str.lower().str.contains("meerwerk", na=False)

    # Normalize categorie
    df["is_wederkerend"] = df["categorie"].str.lower().str.contains("wederkerend", na=False)

    # Determine project start/end year from data
    df["start_jaar"] = None
    df["eind_jaar"] = None
    for _, row in df.iterrows():
        for y in year_cols:
            if row[f"jaar_{y}"] > 0:
                if df.at[row.name, "start_jaar"] is None:
                    df.at[row.name, "start_jaar"] = int(y)
                df.at[row.name, "eind_jaar"] = int(y)

    df["start_jaar"] = df["start_jaar"].astype("Int64")
    df["eind_jaar"] = df["eind_jaar"].astype("Int64")

    # Originele start/eind datums (referentiepunt, wordt NOOIT overschreven)
    df["originele_start"] = df["start_jaar"].apply(
        lambda y: date(int(y), 1, 1) if pd.notna(y) else date(2026, 1, 1)
    )
    df["originele_eind"] = df["eind_jaar"].apply(
        lambda y: date(int(y), 12, 1) if pd.notna(y) else date(2026, 12, 1)
    )

    # Create a unique project ID
    df = df.reset_index(drop=True)
    df["project_id"] = df.index

    # Detect available years
    df.attrs["year_columns"] = jaar_cols
    df.attrs["years"] = [int(y) for y in year_cols]

    return df


def get_year_columns(df: pd.DataFrame) -> list[str]:
    """Get the jaar_YYYY column names from the dataframe."""
    return [c for c in df.columns if c.startswith("jaar_")]


def get_years(df: pd.DataFrame) -> list[int]:
    """Get the available years as integers."""
    return sorted([int(c.replace("jaar_", "")) for c in get_year_columns(df)])


def unpivot_years(df: pd.DataFrame) -> pd.DataFrame:
    """Unpivot year columns into rows for charting."""
    jaar_cols = get_year_columns(df)
    id_cols = [c for c in df.columns if c not in jaar_cols]

    melted = df.melt(
        id_vars=id_cols,
        value_vars=jaar_cols,
        var_name="jaar_col",
        value_name="omzet",
    )
    melted["jaar"] = melted["jaar_col"].str.replace("jaar_", "").astype(int)
    melted = melted.drop(columns=["jaar_col"])
    melted = melted[melted["omzet"] > 0]

    return melted
