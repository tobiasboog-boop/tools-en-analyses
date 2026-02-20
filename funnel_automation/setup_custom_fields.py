"""Setup script om custom fields in Pipedrive aan te maken."""
from pipedrive_api import PipedriveAPI


def setup_lead_scoring_fields():
    """Maak custom fields aan in Pipedrive voor lead scoring."""
    api = PipedriveAPI()

    print("[SETUP] Pipedrive Custom Fields voor Lead Scoring\n")

    # Haal bestaande fields op
    print("[CHECK] Checking bestaande custom fields...")
    existing_fields = api.get_person_fields()
    existing_field_names = {field.get('name', '').lower(): field for field in existing_fields}

    fields_to_create = [
        {
            'name': 'Lead Score',
            'field_type': 'double',  # Number field
            'key': 'lead_score'
        },
        {
            'name': 'Lead Segment',
            'field_type': 'enum',  # Dropdown
            'key': 'lead_segment',
            'options': [
                {'label': '🔥 Warm'},
                {'label': '🟡 Lauw'},
                {'label': '🧊 Koud'}
            ]
        },
        {
            'name': 'Last Scored Date',
            'field_type': 'date',
            'key': 'last_scored_date'
        }
    ]

    created = []
    skipped = []

    for field in fields_to_create:
        field_name_lower = field['name'].lower()

        if field_name_lower in existing_field_names:
            print(f"[SKIP] '{field['name']}' bestaat al - overslaan")
            skipped.append(field['name'])
            continue

        try:
            print(f"[CREATE] Aanmaken: '{field['name']}'...")

            if field['field_type'] == 'enum':
                # Dropdown field met opties
                result = api._post('personFields', {
                    'name': field['name'],
                    'field_type': 'enum',
                    'options': field['options']
                })
            else:
                # Normale field (double of date)
                result = api.create_person_field(field['name'], field['field_type'])

            if result:
                created.append(field['name'])
                print(f"   [OK] Aangemaakt met ID: {result.get('id')}")
            else:
                print(f"   [ERROR] Fout bij aanmaken")

        except Exception as e:
            print(f"   [ERROR] Fout: {e}")

    # Summary
    print(f"\n[SUMMARY] Results:")
    print(f"   [OK] Aangemaakt: {len(created)} fields")
    if created:
        for name in created:
            print(f"      - {name}")

    print(f"   [SKIP] Overgeslagen: {len(skipped)} fields (bestaan al)")
    if skipped:
        for name in skipped:
            print(f"      - {name}")

    print("\n[DONE] Custom fields setup compleet!")
    print("\n[INFO] Je kunt deze fields nu zien in Pipedrive:")
    print("   Settings → Data fields → Person")


if __name__ == "__main__":
    setup_lead_scoring_fields()
