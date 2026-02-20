"""Update lead scores in Pipedrive custom fields."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from datetime import datetime
from pipedrive_api import PipedriveAPI
from lead_scoring import LeadScorer

print("\n===== UPDATE PIPEDRIVE LEAD SCORES =====\n")

# Initialize
print("[1] Initializing...")
api = PipedriveAPI()
scorer = LeadScorer(warm_threshold=80, lukewarm_threshold=40)

# Get field mappings
print("[2] Getting custom field IDs...")
all_fields = api.get_person_fields()
field_mapping = {}

for field in all_fields:
    name = field.get('name', '').lower()
    if 'lead score' in name:
        field_mapping['lead_score'] = field.get('key')
        print(f"    Found: Lead Score field (key: {field.get('key')})")
    elif 'lead segment' in name:
        field_mapping['lead_segment'] = field.get('key')
        # Get enum options
        options = field.get('options', [])
        field_mapping['segment_options'] = {
            'Warm': next((opt['id'] for opt in options if 'warm' in opt.get('label', '').lower()), None),
            'Lauw': next((opt['id'] for opt in options if 'lauw' in opt.get('label', '').lower()), None),
            'Koud': next((opt['id'] for opt in options if 'koud' in opt.get('label', '').lower()), None),
        }
        print(f"    Found: Lead Segment field (key: {field.get('key')})")
    elif 'last scored' in name:
        field_mapping['last_scored_date'] = field.get('key')
        print(f"    Found: Last Scored Date field (key: {field.get('key')})")

if not field_mapping:
    print("\n[ERROR] No custom fields found!")
    print("Run: python setup_custom_fields.py first")
    exit(1)

# Get persons
print("\n[3] Fetching persons from Pipedrive...")
persons = api.get_persons(limit=500)
print(f"    Found {len(persons)} persons")

# Get activities and deals
print("\n[4] Fetching activities and deals...")
for i, person in enumerate(persons):
    if (i+1) % 20 == 0:
        print(f"    Progress: {i+1}/{len(persons)}")

    person_id = person['id']
    person['deals'] = api.get_person_deals(person_id)
    person['activities'] = api.get_person_activities(person_id)

# Calculate scores
print("\n[5] Calculating lead scores...")
scored_persons = scorer.score_all_persons(persons)

# Count segments
segments = {'Warm': 0, 'Lauw': 0, 'Koud': 0}
for person in scored_persons:
    segments[person['lead_segment']] += 1

print(f"\n    Results:")
print(f"    - Warm: {segments['Warm']}")
print(f"    - Lauw: {segments['Lauw']}")
print(f"    - Koud: {segments['Koud']}")

# Update Pipedrive
print("\n[6] Updating Pipedrive...")
today = datetime.now().strftime('%Y-%m-%d')
updated = 0
errors = 0

for i, person in enumerate(scored_persons):
    if (i+1) % 50 == 0:
        print(f"    Progress: {i+1}/{len(scored_persons)}")

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
        updated += 1
    except Exception as e:
        errors += 1
        if errors <= 3:  # Print first 3 errors
            print(f"    [ERROR] Failed to update {person.get('name')}: {e}")

print(f"\n[DONE] Updated {updated} persons")
if errors > 0:
    print(f"[WARN] {errors} errors occurred")

print("\n===== COMPLETE =====\n")
print("You can now view lead scores in Pipedrive!")
print("Go to: Contacts -> Persons -> Check the custom fields\n")
