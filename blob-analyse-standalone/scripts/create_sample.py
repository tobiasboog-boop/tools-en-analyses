"""
Maak een sample dataset van de blobvelden voor de Streamlit app.
Dit script extraheert een beperkte set records om in de repo te zetten.
"""

import json
import random
from pathlib import Path
from datetime import datetime

# Import de parsers
from rtf_parser import parse_rtf_file
from xml_parser import parse_uurregels_file, summarize_uurregels

# Configuratie
BASE_PATH = Path(r"C:\Users\tobia\OneDrive - Notifica B.V\Documenten - Sharepoint Notifica intern\106. Development\GRIP\AI\1229")
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "sample_data.json"

# Sample grootte per blobveld type
SAMPLE_SIZE = 200  # per type


def get_random_files(folder: Path, pattern: str, n: int) -> list:
    """Haal N willekeurige bestanden op."""
    files = list(folder.glob(pattern))
    if len(files) <= n:
        return files
    return random.sample(files, n)


def extract_sample():
    """Extraheer sample data uit alle relevante blobvelden."""

    print("=" * 60)
    print("SAMPLE EXTRACTIE - ZENITH SECURITY BLOBVELDEN")
    print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    data = {
        "metadata": {
            "klant": "Zenith Security",
            "klant_id": "1229",
            "extracted_at": datetime.now().isoformat(),
            "sample_size_per_type": SAMPLE_SIZE
        },
        "monteur_notities": [],
        "storing_meldingen": [],
        "werk_context": [],
        "uren_registraties": []
    }

    # 1. Monteur notities (AT_MWBSESS/NOTITIE.txt)
    print("\n[1/4] Extraheren monteur notities...")
    notitie_path = BASE_PATH / "AT_MWBSESS"
    notitie_files = get_random_files(notitie_path, "*.NOTITIE.txt", SAMPLE_SIZE)

    for f in notitie_files:
        text = parse_rtf_file(f)
        if text and len(text.strip()) > 10:  # Filter lege/korte notities
            werkbon_id = f.stem.split('.')[0]
            data["monteur_notities"].append({
                "id": werkbon_id,
                "tekst": text[:2000],  # Max 2000 chars
                "type": "monteur_notitie"
            })

    print(f"   Gevonden: {len(data['monteur_notities'])} notities")

    # 2. Storingsmeldingen (AT_UITVBEST/TEKST.txt)
    print("\n[2/4] Extraheren storingsmeldingen...")
    storing_path = BASE_PATH / "AT_UITVBEST"
    storing_files = get_random_files(storing_path, "*.TEKST.txt", SAMPLE_SIZE)

    for f in storing_files:
        text = parse_rtf_file(f)
        if text and len(text.strip()) > 10:
            werkbon_id = f.stem.split('.')[0]
            data["storing_meldingen"].append({
                "id": werkbon_id,
                "tekst": text[:2000],
                "type": "storing_melding"
            })

    print(f"   Gevonden: {len(data['storing_meldingen'])} meldingen")

    # 3. Werk context (AT_WERK/GC_INFORMATIE.txt)
    print("\n[3/4] Extraheren werk context...")
    werk_path = BASE_PATH / "AT_WERK"
    werk_files = get_random_files(werk_path, "*.GC_INFORMATIE.txt", SAMPLE_SIZE)

    for f in werk_files:
        text = parse_rtf_file(f)
        if text and len(text.strip()) > 10:
            werkbon_id = f.stem.split('.')[0]
            data["werk_context"].append({
                "id": werkbon_id,
                "tekst": text[:2000],
                "type": "werk_context"
            })

    print(f"   Gevonden: {len(data['werk_context'])} cases")

    # 4. Urenregistraties (AT_MWBSESS/INGELEVERDE_URENREGELS.txt)
    print("\n[4/4] Extraheren urenregistraties...")
    uren_path = BASE_PATH / "AT_MWBSESS"
    uren_files = get_random_files(uren_path, "*.INGELEVERDE_URENREGELS.txt", SAMPLE_SIZE)

    for f in uren_files:
        registratie = parse_uurregels_file(f)
        if registratie and registratie.uurregels:
            samenvatting = summarize_uurregels(registratie)
            data["uren_registraties"].append({
                "id": registratie.werkbon_id,
                "tekst": samenvatting,
                "totaal_uren": registratie.totaal_uren,
                "type": "uren_registratie"
            })

    print(f"   Gevonden: {len(data['uren_registraties'])} registraties")

    # Update metadata met totalen
    data["metadata"]["totals"] = {
        "monteur_notities": len(data["monteur_notities"]),
        "storing_meldingen": len(data["storing_meldingen"]),
        "werk_context": len(data["werk_context"]),
        "uren_registraties": len(data["uren_registraties"])
    }

    # Sla op als JSON
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    file_size = OUTPUT_PATH.stat().st_size / 1024

    print("\n" + "=" * 60)
    print("EXTRACTIE VOLTOOID")
    print(f"Output: {OUTPUT_PATH}")
    print(f"Bestandsgrootte: {file_size:.1f} KB")
    print("=" * 60)

    return data


if __name__ == "__main__":
    extract_sample()
