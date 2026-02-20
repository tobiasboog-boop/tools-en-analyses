"""Simplified lead scoring script."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from datetime import datetime
from pipedrive_api import PipedriveAPI
from lead_scoring import LeadScorer

print("\n===== LEAD SCORING =====\n")

# Initialize
print("[1] Initializing...")
api = PipedriveAPI()
scorer = LeadScorer(warm_threshold=80, lukewarm_threshold=40)

# Get persons
print("[2] Fetching persons from Pipedrive...")
persons = api.get_persons(limit=100)
print(f"    Found {len(persons)} persons")

# Get activities and deals
print("[3] Fetching activities and deals (this may take a moment)...")
for i, person in enumerate(persons):
    if (i+1) % 10 == 0:
        print(f"    Progress: {i+1}/{len(persons)}")

    person_id = person['id']
    person['deals'] = api.get_person_deals(person_id)
    person['activities'] = api.get_person_activities(person_id)

# Calculate scores
print("[4] Calculating lead scores...")
scored_persons = scorer.score_all_persons(persons)

# Count segments
segments = {'Warm': 0, 'Lauw': 0, 'Koud': 0}
for person in scored_persons:
    segments[person['lead_segment']] += 1

# Print results
print("\n===== RESULTS =====\n")
print(f"Warm leads:  {segments['Warm']}")
print(f"Lauw leads:  {segments['Lauw']}")
print(f"Koud leads:  {segments['Koud']}")

print("\n===== TOP 10 LEADS =====\n")
for i, person in enumerate(scored_persons[:10], 1):
    name = person.get('name', 'Unknown')[:30]
    score = person['lead_score']
    segment = person['lead_segment']
    print(f"{i:2}. {name:<30} Score: {score:3} ({segment})")

# Export CSV
filename = f"leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
filepath = f"c:/projects/tools_en_analyses/funnel_automation/{filename}"

print(f"\n[5] Exporting to CSV: {filename}")
with open(filepath, 'w', encoding='utf-8') as f:
    f.write("Name,Email,Score,Segment\n")
    for person in scored_persons:
        name = person.get('name', '').replace(',', ' ')
        email = ''
        if person.get('email') and isinstance(person['email'], list) and len(person['email']) > 0:
            email = person['email'][0].get('value', '')

        f.write(f"{name},{email},{person['lead_score']},{person['lead_segment']}\n")

print(f"\n[DONE] Results exported to: {filepath}\n")
