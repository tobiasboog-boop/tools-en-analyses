"""
Analyse Zenith Storingslijst - Input van Sebastiaan
=====================================================
Vergelijkt de storingslijst van Zenith met onze app output.
"""
import pandas as pd
import numpy as np

FILE = r"C:\Users\tobia\Downloads\Storingslijst kopie tbv Tobias.xlsx"

print("="*70)
print("ZENITH STORINGSLIJST ANALYSE")
print("="*70)

# Lees alle sheets
xls = pd.ExcelFile(FILE)
print(f"\nSheets in bestand: {xls.sheet_names}")

for sheet in xls.sheet_names:
    df = pd.read_excel(FILE, sheet_name=sheet)
    print(f"\n{'='*70}")
    print(f"SHEET: '{sheet}'")
    print(f"{'='*70}")
    print(f"Rijen: {len(df)}")
    print(f"Kolommen: {len(df.columns)}")

    print(f"\nKolomnamen:")
    for i, col in enumerate(df.columns, 1):
        non_null = df[col].notna().sum()
        pct = (non_null / len(df)) * 100 if len(df) > 0 else 0

        # Sample waarde
        sample = ''
        if non_null > 0:
            sample_val = df[col].dropna().iloc[0]
            sample = str(sample_val)[:60]

        print(f"  {i:2}. {str(col):40} | {non_null:4}/{len(df):4} ({pct:5.1f}%) | Sample: {sample}")

    print(f"\nEerste 5 rijen:")
    print(df.head(5).to_string())

    # Check unieke waarden voor categorische kolommen
    print(f"\nUnieke waarden per kolom (max 10):")
    for col in df.columns:
        nunique = df[col].nunique()
        if 1 < nunique <= 20:
            uniques = df[col].dropna().unique()[:10]
            print(f"  {str(col):40} ({nunique} uniek): {list(uniques)}")
