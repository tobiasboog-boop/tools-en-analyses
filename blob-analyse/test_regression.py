"""
Regressietest: CSV vs DWH BLOB Ophaling
=========================================
Vergelijkt de oude DWH-based BLOB logica met de nieuwe CSV-based logica
op vulgraad en kwaliteit.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '_sdk'))

from notifica_sdk import NotificaClient
import pandas as pd
from datetime import datetime, timedelta
from csv_blob_helper import get_blob_notities_from_csv, get_latest_csv_batch

KLANTNUMMER = 1229  # Zenith

# Test parameters
TEST_START_DATE = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
TEST_END_DATE = datetime.now().strftime('%Y-%m-%d')

print("="*70)
print("REGRESSIETEST: CSV vs DWH BLOB Ophaling")
print("="*70)
print(f"Periode: {TEST_START_DATE} tot {TEST_END_DATE}")
print()

client = NotificaClient()

# ==============================================================================
# STAP 1: Haal testset werkbonnen op
# ==============================================================================
print("STAP 1: Testset werkbonnen ophalen...")

werkbonnen = client.query(KLANTNUMMER, f'''
    SELECT
        wb."WerkbonDocumentKey"
    FROM werkbonnen."Werkbonnen" wb
    WHERE wb."MeldDatum" >= '{TEST_START_DATE}'
      AND wb."MeldDatum" <= '{TEST_END_DATE}'
    LIMIT 50
''')

print(f"  -> {len(werkbonnen)} werkbonnen geselecteerd voor test")

wb_keys = werkbonnen['WerkbonDocumentKey'].tolist()
wb_keys_str = ','.join(str(k) for k in wb_keys)

# ==============================================================================
# STAP 2: Haal sessies op (beide methoden gebruiken dit)
# ==============================================================================
print("\nSTAP 2: Mobiele uitvoersessies ophalen...")

sessies = client.query(KLANTNUMMER, f'''
    SELECT
        s."DocumentKey" AS "WerkbonDocumentKey",
        s."MobieleuitvoersessieRegelKey"
    FROM werkbonnen."Mobiele uitvoersessies" s
    WHERE s."DocumentKey" IN ({wb_keys_str})
''')

print(f"  -> {len(sessies)} sessies gevonden")

if sessies.empty:
    print("\nFOUT Geen sessies gevonden, kan test niet uitvoeren")
    sys.exit(1)

sessie_keys = sessies['MobieleuitvoersessieRegelKey'].tolist()
sessie_keys_str = ','.join(str(k) for k in sessie_keys)

# ==============================================================================
# METHODE A: OUDE DWH AANPAK
# ==============================================================================
print("\n" + "="*70)
print("METHODE A: OUDE DWH (maatwerk.stg_at_*_clobs)")
print("="*70)

try:
    # BLOB tabel 1
    blob1_dwh = client.query(KLANTNUMMER, f'''
        SELECT
            m.gc_id AS "MobieleuitvoersessieRegelKey",
            m.notitie
        FROM maatwerk.stg_at_mwbsess_clobs m
        WHERE m.gc_id IN ({sessie_keys_str})
          AND m.notitie IS NOT NULL
    ''')
    print(f"  -> stg_at_mwbsess_clobs: {len(blob1_dwh)} notities")

    # BLOB tabel 2
    blob2_dwh = client.query(KLANTNUMMER, f'''
        SELECT
            u.gc_id AS "MobieleuitvoersessieRegelKey",
            u.tekst as notitie
        FROM maatwerk.stg_at_uitvbest_clobs u
        WHERE u.gc_id IN ({sessie_keys_str})
          AND u.tekst IS NOT NULL
    ''')
    print(f"  -> stg_at_uitvbest_clobs: {len(blob2_dwh)} notities")

    # BLOB tabel 3
    blob3_dwh = client.query(KLANTNUMMER, f'''
        SELECT
            d.gc_id AS "MobieleuitvoersessieRegelKey",
            COALESCE(d.gc_notitie_extern, d.gc_informatie) as notitie
        FROM maatwerk.stg_at_document_clobs d
        WHERE d.gc_id IN ({sessie_keys_str})
          AND (d.gc_notitie_extern IS NOT NULL OR d.gc_informatie IS NOT NULL)
    ''')
    print(f"  -> stg_at_document_clobs: {len(blob3_dwh)} notities")

    # Combineer
    blob_raw_dwh = pd.concat([blob1_dwh, blob2_dwh, blob3_dwh], ignore_index=True)

    # Merge met sessies
    blob_dwh = sessies.merge(blob_raw_dwh, on='MobieleuitvoersessieRegelKey', how='inner')
    blob_dwh = blob_dwh.groupby('WerkbonDocumentKey').agg({
        'notitie': lambda x: '\n\n'.join(x.dropna().astype(str))
    }).reset_index()

    print(f"\nOK DWH Totaal: {len(blob_dwh)} werkbonnen met notities")
    print(f"  Gemiddelde lengte: {blob_dwh['notitie'].str.len().mean():.0f} karakters")

except Exception as e:
    print(f"\nFOUT DWH methode gefaald: {e}")
    blob_dwh = pd.DataFrame()

# ==============================================================================
# METHODE B: NIEUWE CSV AANPAK
# ==============================================================================
print("\n" + "="*70)
print("METHODE B: NIEUWE CSV (BlobMwbsessNotitie.csv etc.)")
print("="*70)

try:
    batch_info = get_latest_csv_batch(client, KLANTNUMMER, days=7)

    if batch_info:
        blob_raw_csv = get_blob_notities_from_csv(client, KLANTNUMMER, sessie_keys, batch_info)

        # Merge met sessies
        blob_csv = sessies.merge(blob_raw_csv, on='MobieleuitvoersessieRegelKey', how='inner')
        blob_csv = blob_csv.groupby('WerkbonDocumentKey').agg({
            'notitie': lambda x: '\n\n'.join(x.dropna().astype(str))
        }).reset_index()

        print(f"\nOK CSV Totaal: {len(blob_csv)} werkbonnen met notities")
        print(f"  Gemiddelde lengte: {blob_csv['notitie'].str.len().mean():.0f} karakters")
    else:
        print("\nFOUT Geen recente CSV batch gevonden")
        blob_csv = pd.DataFrame()

except Exception as e:
    print(f"\nFOUT CSV methode gefaald: {e}")
    import traceback
    traceback.print_exc()
    blob_csv = pd.DataFrame()

# ==============================================================================
# VERGELIJKING
# ==============================================================================
print("\n" + "="*70)
print("VERGELIJKING")
print("="*70)

if not blob_dwh.empty and not blob_csv.empty:
    print(f"\nAantal werkbonnen met notities:")
    print(f"  DWH: {len(blob_dwh)}")
    print(f"  CSV: {len(blob_csv)}")
    print(f"  Verschil: {len(blob_csv) - len(blob_dwh)} ({(len(blob_csv)/len(blob_dwh)-1)*100:+.1f}%)")

    print(f"\nGemiddelde notitie lengte:")
    print(f"  DWH: {blob_dwh['notitie'].str.len().mean():.0f} karakters")
    print(f"  CSV: {blob_csv['notitie'].str.len().mean():.0f} karakters")

    # Vulgraad per werkbon
    merged = werkbonnen.merge(blob_dwh[['WerkbonDocumentKey']], on='WerkbonDocumentKey', how='left', indicator='dwh')
    merged = merged.merge(blob_csv[['WerkbonDocumentKey']], on='WerkbonDocumentKey', how='left', indicator='csv')

    dwh_fill = (merged['dwh'] == 'both').sum() / len(merged) * 100
    csv_fill = (merged['csv'] == 'both').sum() / len(merged) * 100

    print(f"\nVulgraad (% werkbonnen met notitie):")
    print(f"  DWH: {dwh_fill:.1f}%")
    print(f"  CSV: {csv_fill:.1f}%")
    print(f"  Verschil: {csv_fill - dwh_fill:+.1f} procentpunten")

    # Sample vergelijking
    print(f"\nSample vergelijking (eerste werkbon met notitie):")
    if len(blob_dwh) > 0:
        sample_wb = blob_dwh.iloc[0]['WerkbonDocumentKey']
        dwh_sample = blob_dwh[blob_dwh['WerkbonDocumentKey'] == sample_wb]['notitie'].iloc[0][:200]
        csv_sample = blob_csv[blob_csv['WerkbonDocumentKey'] == sample_wb]['notitie'].iloc[0][:200] if sample_wb in blob_csv['WerkbonDocumentKey'].values else "NIET GEVONDEN"

        print(f"\n  Werkbon: {sample_wb}")
        print(f"  DWH: {dwh_sample}...")
        print(f"  CSV: {csv_sample}...")
        print(f"  Match: {'OK' if dwh_sample == csv_sample else 'X'}")

else:
    print("\nFOUT Kan geen vergelijking maken - een of beide methoden gefaald")

print("\n" + "="*70)
print("CONCLUSIE")
print("="*70)

if not blob_csv.empty:
    if not blob_dwh.empty:
        diff_pct = (len(blob_csv)/len(blob_dwh)-1)*100
        if abs(diff_pct) < 5:
            print("OK CSV methode geeft vergelijkbare resultaten als DWH (<5% verschil)")
        else:
            print(f"WAARSCHUWING CSV methode geeft {diff_pct:+.1f}% verschil t.o.v. DWH")
    else:
        print("OK CSV methode werkt, DWH methode gefaald")
else:
    print("FOUT CSV methode gefaald - app kan niet gebruikt worden")
