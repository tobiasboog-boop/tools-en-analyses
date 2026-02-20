#!/usr/bin/env python3
"""Export batch van werkbonnen voor pilot.

Exporteert werkbonnen met complete verhalen naar JSON.
Maakt PER DEBITEUR een apart bestand, zodat:
- Je tussentijds resultaat hebt
- Bij problemen niet alles opnieuw hoeft

Criteria:
- Status = Uitgevoerd
- Documentstatus = Historisch
- Type (paragraaf) = Storing
- Gereedmelddatum in laatste 4 maanden
- Alleen debiteuren met actief contract
"""
import sys
import json
from pathlib import Path
from datetime import date, timedelta, datetime
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from src.models.database import SessionLocal
from src.services.werkbon_keten_service import WerkbonKetenService, WerkbonVerhaalBuilder


# Configuratie
BATCH_SIZE = 500
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "pilot_batch"

# Verdeling (proportioneel aan beschikbare werkbonnen)
# Trivire 51%, Thuisvester 34%, Bazalt 15%
VERDELING = {
    "005102": 256,  # Trivire
    "177460": 168,  # Thuisvester
    "007453": 76,   # Bazalt
}


def get_debiteuren_met_contract(db) -> List[Dict[str, str]]:
    """Haal debiteuren op die een actief contract hebben."""
    query = text("""
        SELECT
            cr.client_id as debiteur_code,
            cr.client_name as debiteur_naam,
            c.filename as contract_bestand
        FROM contract_checker.contract_relatie cr
        JOIN contract_checker.contracts c ON c.id = cr.contract_id
        WHERE c.active = true
        ORDER BY cr.client_id
    """)
    result = db.execute(query)
    return [
        {"code": row[0], "naam": row[1], "contract": row[2]}
        for row in result
    ]


def get_werkbon_keys(
    db,
    debiteur_code: str,
    start_date: date,
    end_date: date,
    limit: int
) -> List[Dict[str, Any]]:
    """Haal hoofdwerkbon keys op voor een debiteur."""
    query = text("""
        SELECT DISTINCT
            w."HoofdwerkbonDocumentKey" as hoofdwerkbon_key,
            d."Gereedmelddatum"::date as gereedmelddatum
        FROM werkbonnen."Werkbonnen" w
        INNER JOIN werkbonnen."Werkbonparagrafen" wp
            ON w."WerkbonDocumentKey" = wp."WerkbonDocumentKey"
        INNER JOIN stam."Documenten" d
            ON d."DocumentKey" = w."WerkbonDocumentKey"
        WHERE w."Debiteur" LIKE :debiteur_pattern
          AND w."HoofdwerkbonDocumentKey" = w."WerkbonDocumentKey"
          AND TRIM(w."Status") = 'Uitgevoerd'
          AND TRIM(w."Documentstatus") = 'Historisch'
          AND TRIM(wp."Type") = 'Storing'
          AND d."Gereedmelddatum"::date >= :start_date
          AND d."Gereedmelddatum"::date <= :end_date
        ORDER BY d."Gereedmelddatum"::date DESC
        LIMIT :limit
    """)
    result = db.execute(query, {
        "debiteur_pattern": f"{debiteur_code} - %",
        "start_date": start_date,
        "end_date": end_date,
        "limit": limit
    })
    return [
        {"hoofdwerkbon_key": row[0], "gereedmelddatum": str(row[1])}
        for row in result
    ]


def json_serializer(obj):
    """Custom JSON encoder voor date/Decimal types."""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if hasattr(obj, '__float__'):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def export_debiteur(deb: Dict[str, str], aantal: int, start_date: date, end_date: date) -> int:
    """Exporteer werkbonnen voor een enkele debiteur. Returns aantal geexporteerd."""

    output_file = OUTPUT_DIR / f"werkbonnen_{deb['code']}_{deb['naam'].replace(' ', '_')[:20]}.json"

    # Check of bestand al bestaat
    if output_file.exists():
        print(f"\n  Bestand bestaat al: {output_file.name}")
        print(f"  Overslaan... (verwijder bestand om opnieuw te exporteren)")
        # Tel bestaande werkbonnen
        with open(output_file, 'r', encoding='utf-8') as f:
            existing = json.load(f)
            return len(existing.get('werkbonnen', []))

    print(f"\n{'='*60}")
    print(f"Export: {deb['code']} - {deb['naam']}")
    print(f"Aantal: {aantal} werkbonnen")
    print(f"{'='*60}")

    db = SessionLocal()
    keten_service = WerkbonKetenService()
    verhaal_builder = WerkbonVerhaalBuilder()

    try:
        # Haal keys op
        werkbon_keys = get_werkbon_keys(db, deb['code'], start_date, end_date, aantal)
        print(f"Gevonden: {len(werkbon_keys)} werkbonnen")

        werkbonnen = []
        start_time = datetime.now()
        errors = []

        for i, wb_info in enumerate(werkbon_keys):
            key = wb_info['hoofdwerkbon_key']
            try:
                # Haal complete keten op met alle details
                keten = keten_service.get_werkbon_keten(
                    key,
                    include_kosten_details=True,
                    include_opbrengsten_details=True,
                    include_opvolgingen=True,
                    include_oplossingen=True
                )

                if keten:
                    # Bouw verhaal
                    verhaal = verhaal_builder.build_verhaal(keten)

                    werkbonnen.append({
                        "hoofdwerkbon_key": key,
                        "gereedmelddatum": wb_info['gereedmelddatum'],
                        "debiteur_code": deb['code'],
                        "debiteur_naam": deb['naam'],
                        "contract_bestand": deb['contract'],
                        "keten": keten.to_dict(),
                        "verhaal": verhaal
                    })

                # Progress
                if (i + 1) % 25 == 0 or (i + 1) == len(werkbon_keys):
                    elapsed = (datetime.now() - start_time).total_seconds()
                    rate = (i + 1) / elapsed if elapsed > 0 else 0
                    print(f"  [{i+1}/{len(werkbon_keys)}] {rate:.1f} werkbonnen/s")

            except Exception as e:
                errors.append(f"{key}: {e}")
                if len(errors) <= 3:
                    print(f"  Fout bij {key}: {e}")

        if len(errors) > 3:
            print(f"  ... en {len(errors) - 3} andere fouten")

        # Schrijf naar bestand
        output_data = {
            "metadata": {
                "export_datum": datetime.now().isoformat(),
                "debiteur_code": deb['code'],
                "debiteur_naam": deb['naam'],
                "contract_bestand": deb['contract'],
                "criteria": {
                    "status": "Uitgevoerd",
                    "documentstatus": "Historisch",
                    "paragraaf_type": "Storing",
                    "gereedmelddatum_van": str(start_date),
                    "gereedmelddatum_tot": str(end_date)
                },
                "totaal_werkbonnen": len(werkbonnen),
                "fouten": len(errors)
            },
            "werkbonnen": werkbonnen
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False, default=json_serializer)

        file_size_mb = output_file.stat().st_size / (1024 * 1024)
        elapsed = (datetime.now() - start_time).total_seconds()

        print(f"\nOpgeslagen: {output_file.name}")
        print(f"  Werkbonnen: {len(werkbonnen)}")
        print(f"  Grootte: {file_size_mb:.1f} MB")
        print(f"  Tijd: {elapsed:.0f}s")

        return len(werkbonnen)

    finally:
        db.close()
        keten_service.close()


def main():
    # Zorg dat output directory bestaat
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("EXPORT: Werkbonnen Batch voor Pilot")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 70)

    # Datum range
    end_date = date.today()
    start_date = end_date - timedelta(days=120)
    print(f"\nDatum range: {start_date} t/m {end_date}")

    # Haal debiteuren op
    db = SessionLocal()
    debiteuren = get_debiteuren_met_contract(db)
    db.close()

    print(f"\nVerdeling (totaal {BATCH_SIZE}):")
    for deb in debiteuren:
        aantal = VERDELING.get(deb['code'], 0)
        print(f"  {deb['code']} {deb['naam']}: {aantal}")

    # Export per debiteur
    totaal = 0
    start_time = datetime.now()

    for deb in debiteuren:
        aantal = VERDELING.get(deb['code'], 0)
        if aantal > 0:
            exported = export_debiteur(deb, aantal, start_date, end_date)
            totaal += exported

    # Samenvatting
    elapsed = (datetime.now() - start_time).total_seconds()
    print("\n" + "=" * 70)
    print("SAMENVATTING")
    print("=" * 70)
    print(f"Totaal geexporteerd: {totaal} werkbonnen")
    print(f"Totale tijd: {elapsed:.0f} seconden")
    print(f"Bestanden in: {OUTPUT_DIR}")

    # List files
    for f in OUTPUT_DIR.glob("werkbonnen_*.json"):
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  - {f.name} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
