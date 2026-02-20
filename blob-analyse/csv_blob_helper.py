"""
CSV BLOB Helper
================
Helper functies om BLOB/CLOB data op te halen uit CSV exports
in plaats van uit het oude DWH maatwerk schema.
"""

import pandas as pd
import io
from typing import Optional, Tuple
from functools import lru_cache
import unicodedata


def remove_accents(text):
    """
    Verwijder accenten uit tekst (José → Jose, etc.)

    Fix voor mojibake in Notifica CSV exports.
    """
    if not isinstance(text, str):
        return text

    # Normaliseer naar NFD (decompose accents)
    nfd = unicodedata.normalize('NFD', text)

    # Filter alles behalve de base characters
    without_accents = ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')

    return without_accents


def get_latest_csv_batch(client, klantnummer: int, days: int = 7) -> Optional[dict]:
    """
    Haal de meest recente CSV batch op.

    Args:
        client: NotificaClient instance
        klantnummer: Klantnummer
        days: Aantal dagen terug te kijken (default 7)

    Returns:
        Dict met batch info (date, folder, files) of None
    """
    try:
        batches = client.csv_batches(klantnummer, days=days)
        if not batches:
            return None

        # Neem de meest recente batch
        latest = batches[0]

        # Zorg dat we de juiste velden hebben
        return {
            'date': latest.get('date', latest.get('batch_date')),
            'folder': latest.get('folder', latest.get('batch_folder')),
            'files': latest.get('files', [])
        }
    except Exception as e:
        print(f"Fout bij ophalen CSV batches: {e}")
        return None


@lru_cache(maxsize=10)
def _download_and_parse_csv(klantnummer: int, date: str, folder: str, filename: str, base_url: str, token: str) -> str:
    """
    Cached CSV download (returns raw text).

    Separate functie voor caching omdat client object niet hashable is.
    Cache houdt laatste 10 CSV downloads in memory (ca. 1 uur geldig).
    """
    import requests

    url = f"{base_url}/api/data/csv/{klantnummer}/{date}/{folder}/{filename}"
    headers = {'Authorization': f'Bearer {token}'}

    resp = requests.get(url, headers=headers)

    if resp.status_code != 200:
        raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")

    return resp.text


def download_blob_csv(client, klantnummer: int, date: str, folder: str, filename: str) -> pd.DataFrame:
    """
    Download en parse een BLOB CSV bestand (met caching).

    CSV bestanden gebruiken pipe (|) als delimiter en quotes (") voor text fields.
    Download wordt gecached - herhaalde calls gebruiken cached data.

    Args:
        client: NotificaClient instance
        klantnummer: Klantnummer
        date: Batch datum (YYYY-MM-DD)
        folder: Batch folder naam
        filename: Bestandsnaam

    Returns:
        DataFrame met BLOB data
    """
    try:
        # Download via cached functie
        csv_text = _download_and_parse_csv(
            klantnummer,
            date,
            folder,
            filename,
            client.base_url,
            client.token
        )

        # Parse met pipe delimiter
        df = pd.read_csv(
            io.StringIO(csv_text),
            sep='|',
            quotechar='"',
            encoding='utf-8',
            on_bad_lines='skip'  # Skip malformed lines
        )

        return df

    except Exception as e:
        print(f"Fout bij downloaden {filename}: {e}")
        return pd.DataFrame()


def get_blob_notities_from_csv(
    client,
    klantnummer: int,
    sessie_keys: list,
    batch_info: Optional[dict] = None
) -> pd.DataFrame:
    """
    Haal BLOB notities op uit CSV exports in plaats van DWH queries.

    Vervangt de oude logica die maatwerk.stg_at_*_clobs tabellen gebruikte.

    Args:
        client: NotificaClient instance
        klantnummer: Klantnummer
        sessie_keys: List van MobieleuitvoersessieRegelKey waarden
        batch_info: Optional dict met batch info (anders wordt meest recente gebruikt)

    Returns:
        DataFrame met kolommen: MobieleuitvoersessieRegelKey, notitie
    """
    # Haal batch info op als niet meegegeven
    if batch_info is None:
        batch_info = get_latest_csv_batch(client, klantnummer, days=7)
        if batch_info is None:
            print("Geen recente CSV batch gevonden")
            return pd.DataFrame(columns=['MobieleuitvoersessieRegelKey', 'notitie'])

    date = batch_info['date']
    folder = batch_info['folder']

    # Download de 3 BLOB CSV bestanden
    print(f"  -> CSV batch: {date}")

    # BLOB 1: BlobMwbsessNotitie.csv (monteur notities)
    blob1 = download_blob_csv(client, klantnummer, date, folder, 'BlobMwbsessNotitie.csv')
    if not blob1.empty:
        blob1 = blob1.rename(columns={'GC_ID': 'MobieleuitvoersessieRegelKey', 'NOTITIE': 'notitie'})
        # Filter op sessie keys
        blob1 = blob1[blob1['MobieleuitvoersessieRegelKey'].isin(sessie_keys)]
        # Filter niet-lege notities
        blob1 = blob1[blob1['notitie'].notna()]
        # Strip accenten (José → Jose)
        blob1['notitie'] = blob1['notitie'].apply(remove_accents)
        print(f"  -> BlobMwbsessNotitie: {len(blob1)} notities")

    # BLOB 2: BlobUitvbestTekst.csv (uitvoerbestek tekst)
    blob2 = download_blob_csv(client, klantnummer, date, folder, 'BlobUitvbestTekst.csv')
    if not blob2.empty:
        blob2 = blob2.rename(columns={'GC_ID': 'MobieleuitvoersessieRegelKey', 'TEKST': 'notitie'})
        blob2 = blob2[blob2['MobieleuitvoersessieRegelKey'].isin(sessie_keys)]
        blob2 = blob2[blob2['notitie'].notna()]
        # Strip accenten (José → Jose)
        blob2['notitie'] = blob2['notitie'].apply(remove_accents)
        print(f"  -> BlobUitvbestTekst: {len(blob2)} notities")

    # BLOB 3: BlobDocumentNotities.csv (document notities)
    blob3 = download_blob_csv(client, klantnummer, date, folder, 'BlobDocumentNotities.csv')
    if not blob3.empty:
        # Gebruik COALESCE logica: eerst gc_notitie_extern, dan gc_informatie
        blob3['notitie'] = blob3['GC_NOTITIE_EXTERN'].fillna(blob3['GC_INFORMATIE'])
        blob3 = blob3.rename(columns={'GC_ID': 'MobieleuitvoersessieRegelKey'})
        blob3 = blob3[['MobieleuitvoersessieRegelKey', 'notitie']]
        blob3 = blob3[blob3['MobieleuitvoersessieRegelKey'].isin(sessie_keys)]
        blob3 = blob3[blob3['notitie'].notna()]
        # Strip accenten (José → Jose)
        blob3['notitie'] = blob3['notitie'].apply(remove_accents)
        print(f"  -> BlobDocumentNotities: {len(blob3)} notities")

    # Combineer alle BLOB bronnen (exact zoals oude code)
    blob_dfs = [df for df in [blob1, blob2, blob3] if not df.empty]

    if not blob_dfs:
        print("  -> Geen BLOB notities gevonden in CSV")
        return pd.DataFrame(columns=['MobieleuitvoersessieRegelKey', 'notitie'])

    blob_combined = pd.concat(blob_dfs, ignore_index=True)

    print(f"  -> Totaal: {len(blob_combined)} BLOB notities uit CSV")

    return blob_combined
