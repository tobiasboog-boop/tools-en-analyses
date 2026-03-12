"""
Converteer het Excel-bronbestand naar Parquet-bestanden.
Snellere laadtijd en geen afhankelijkheid van het .xlsm bestand at runtime.
"""

import sys
from pathlib import Path
from data_loader import load_werkbonnen, load_klantrekeningen, load_rapportage_config

import pandas as pd
import numpy as np

DEFAULT_EXCEL = Path(r"C:\Users\tobia\Downloads\Budget analyse februari 26 V2.xlsm")
OUTPUT_DIR = Path(__file__).parent / "data"


def _clean_for_parquet(df):
    """Maak DataFrame parquet-compatibel: verwijder nan-kolommen, fix mixed types."""
    # Verwijder kolommen zonder naam
    df = df.loc[:, df.columns.notna()]
    df = df.loc[:, ~df.columns.duplicated()]

    # Fix mixed-type object-kolommen zodat pyarrow ze kan serialiseren
    for col in df.columns:
        if df[col].dtype == object:
            # Cast niet-null waarden naar string, houd nulls als echte null
            df[col] = df[col].astype("string")

    return df


def convert(excel_path: Path = DEFAULT_EXCEL):
    OUTPUT_DIR.mkdir(exist_ok=True)

    print(f"Lezen van: {excel_path}")

    print("  Werkbonnen laden...")
    wb = load_werkbonnen(excel_path)
    wb = _clean_for_parquet(wb)
    wb_path = OUTPUT_DIR / "werkbonnen.parquet"
    wb.to_parquet(wb_path, index=False)
    print(f"    {len(wb)} rijen -> {wb_path}")

    print("  Klantrekeningen laden...")
    kl = load_klantrekeningen(excel_path)
    kl = _clean_for_parquet(kl)
    kl_path = OUTPUT_DIR / "klantrekeningen.parquet"
    kl.to_parquet(kl_path, index=False)
    print(f"    {len(kl)} rijen -> {kl_path}")

    print("  Rapportage config laden...")
    config = load_rapportage_config(excel_path)
    config_path = OUTPUT_DIR / "rapportage_config.parquet"
    config.to_parquet(config_path, index=False)
    print(f"    {len(config)} rijen -> {config_path}")

    print("\nKlaar! Parquet-bestanden staan in:", OUTPUT_DIR)


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_EXCEL
    if not path.exists():
        print(f"Bestand niet gevonden: {path}")
        sys.exit(1)
    convert(path)
