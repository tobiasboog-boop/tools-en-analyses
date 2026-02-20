"""Main automation script - berekent en update lead scores in Pipedrive."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from datetime import datetime
from pipedrive_api import PipedriveAPI
from lead_scoring import LeadScorer
from utils.config import WARM_LEAD_THRESHOLD, LUKEWARM_LEAD_THRESHOLD
import json


def run_lead_scoring(dry_run: bool = False, export_csv: bool = True):
    """Hoofdscript - berekent lead scores en update Pipedrive.

    Args:
        dry_run: Als True, update Pipedrive NIET (alleen berekenen en tonen)
        export_csv: Als True, exporteer resultaten naar CSV
    """
    print("\n" + "="*60)
    print("  LEAD SCORING AUTOMATION")
    print("="*60 + "\n")

    # Initialize
    api = PipedriveAPI()
    scorer = LeadScorer(
        warm_threshold=WARM_LEAD_THRESHOLD,
        lukewarm_threshold=LUKEWARM_LEAD_THRESHOLD
    )

    # Stap 1: Haal alle personen op met details
    print("[1/4] Ophalen personen uit Pipedrive...")
    persons = api.get_persons(limit=500)
    print(f"      Gevonden: {len(persons)} personen")

    # Haal custom field IDs op
    print("\n[2/4] Ophalen custom field mappings...")
    all_fields = api.get_person_fields()
    field_mapping = {}
    for field in all_fields:
        name = field.get('name', '').lower()
        if 'lead score' in name:
            field_mapping['lead_score'] = field.get('key')
        elif 'lead segment' in name:
            field_mapping['lead_segment'] = field.get('key')
            # Haal ook de enum opties op
            options = field.get('options', [])
            field_mapping['segment_options'] = {
                'Warm': next((opt['id'] for opt in options if 'warm' in opt.get('label', '').lower()), None),
                'Lauw': next((opt['id'] for opt in options if 'lauw' in opt.get('label', '').lower()), None),
                'Koud': next((opt['id'] for opt in options if 'koud' in opt.get('label', '').lower()), None),
            }
        elif 'last scored' in name:
            field_mapping['last_scored_date'] = field.get('key')

    print(f"      Fields: {', '.join(field_mapping.keys())}")

    # Stap 2: Haal activiteiten en deals op voor scoring
    print("\n[3/4] Ophalen activiteiten en deals...")
    for i, person in enumerate(persons):
        if i % 10 == 0:
            print(f"      Progress: {i}/{len(persons)}")

        person_id = person['id']
        person['deals'] = api.get_person_deals(person_id)
        person['activities'] = api.get_person_activities(person_id)

    # Stap 3: Bereken scores
    print("\n[4/4] Berekenen lead scores...")
    scored_persons = scorer.score_all_persons(persons)

    # Segment statistieken
    segments = {'Warm': 0, 'Lauw': 0, 'Koud': 0}
    for person in scored_persons:
        segments[person['lead_segment']] += 1

    # Print resultaten
    print("\n" + "="*60)
    print("  RESULTATEN")
    print("="*60)
    print(f"\n[WARM] {segments['Warm']} leads (>= {WARM_LEAD_THRESHOLD} punten)")
    print(f"[LAUW] {segments['Lauw']} leads ({LUKEWARM_LEAD_THRESHOLD}-{WARM_LEAD_THRESHOLD-1} punten)")
    print(f"[KOUD] {segments['Koud']} leads (< {LUKEWARM_LEAD_THRESHOLD} punten)")

    # Top 10 warme leads
    print("\n" + "-"*60)
    print("  TOP 10 WARME LEADS")
    print("-"*60)
    print(f"{'Naam':<30} {'Score':>6} {'Segment':<8} {'Email':<30}")
    print("-"*60)

    for person in scored_persons[:10]:
        name = person.get('name', 'Onbekend')[:28]
        score = person['lead_score']
        segment = person['lead_segment']
        email = ''
        if person.get('email'):
            if isinstance(person['email'], list) and len(person['email']) > 0:
                email = person['email'][0].get('value', '')[:28]
            elif isinstance(person['email'], str):
                email = person['email'][:28]

        print(f"{name:<30} {score:>6} {segment:<8} {email:<30}")

    # Stap 4: Update Pipedrive (als niet dry_run)
    if not dry_run:
        print("\n" + "="*60)
        print("  UPDATE PIPEDRIVE")
        print("="*60)
        print("\n[UPDATE] Updating lead scores in Pipedrive...")

        today = datetime.now().strftime('%Y-%m-%d')
        updated_count = 0
        error_count = 0

        for i, person in enumerate(scored_persons):
            if i % 20 == 0 and i > 0:
                print(f"         Progress: {i}/{len(scored_persons)}")

            person_id = person['id']
            score = person['lead_score']
            segment = person['lead_segment']

            # Build update data
            update_data = {}

            if 'lead_score' in field_mapping:
                update_data[field_mapping['lead_score']] = score

            if 'lead_segment' in field_mapping and 'segment_options' in field_mapping:
                segment_option_id = field_mapping['segment_options'].get(segment)
                if segment_option_id:
                    update_data[field_mapping['lead_segment']] = segment_option_id

            if 'last_scored_date' in field_mapping:
                update_data[field_mapping['last_scored_date']] = today

            try:
                api.update_person(person_id, update_data)
                updated_count += 1
            except Exception as e:
                error_count += 1
                if error_count <= 5:  # Print eerste 5 fouten
                    print(f"         [ERROR] Fout bij updaten {person.get('name')}: {e}")

        print(f"\n[DONE] {updated_count} personen ge-update")
        if error_count > 0:
            print(f"[WARN] {error_count} fouten opgetreden")

    else:
        print("\n[DRY RUN] Pipedrive NIET ge-update (gebruik --live om te updaten)")

    # Export naar CSV
    if export_csv:
        print("\n" + "="*60)
        print("  EXPORT")
        print("="*60)

        filename = f"lead_scores_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = f"c:/projects/tools_en_analyses/funnel_automation/{filename}"

        with open(filepath, 'w', encoding='utf-8') as f:
            # Header
            f.write("Name,Email,Score,Segment,Company,Phone\n")

            # Data
            for person in scored_persons:
                name = person.get('name', '').replace(',', ' ')
                email = ''
                if person.get('email'):
                    if isinstance(person['email'], list) and len(person['email']) > 0:
                        email = person['email'][0].get('value', '')
                    elif isinstance(person['email'], str):
                        email = person['email']

                score = person['lead_score']
                segment = person['lead_segment']
                company = person.get('org_name', '').replace(',', ' ')
                phone = ''
                if person.get('phone'):
                    if isinstance(person['phone'], list) and len(person['phone']) > 0:
                        phone = person['phone'][0].get('value', '')

                f.write(f"{name},{email},{score},{segment},{company},{phone}\n")

        print(f"\n[EXPORT] CSV geexporteerd naar:")
        print(f"         {filepath}")

    print("\n" + "="*60)
    print("  KLAAR!")
    print("="*60 + "\n")

    return scored_persons


if __name__ == "__main__":
    import sys

    # Check command line arguments
    dry_run = "--live" not in sys.argv
    export_csv = "--no-export" not in sys.argv

    if dry_run:
        print("\n[DRY RUN MODE] - Pipedrive wordt NIET ge-update")
        print("Gebruik 'python run_lead_scoring.py --live' om Pipedrive te updaten\n")

    results = run_lead_scoring(dry_run=dry_run, export_csv=export_csv)

    if dry_run:
        print("\nTip: Run met '--live' om de scores naar Pipedrive te schrijven:")
        print("     python run_lead_scoring.py --live")
