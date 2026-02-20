"""Complete lead scoring met Pipedrive + MailerLite data."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from datetime import datetime
from pipedrive_api import PipedriveAPI
from lead_scoring import LeadScorer
from mailerlite_integration import MailerLiteData

print("\n" + "="*70)
print("  COMPLETE LEAD SCORING - Pipedrive + MailerLite")
print("="*70 + "\n")

# Initialize
print("[1/7] Initializing...")
api = PipedriveAPI()
scorer = LeadScorer(warm_threshold=80, lukewarm_threshold=40)

# Load MailerLite data
print("[2/7] Loading MailerLite email engagement data...")
ml_csv_path = r"C:\Users\tobia\OneDrive - Notifica B.V\Documenten - Sharepoint Notifica intern\105. Marketing\export mailer lite.csv"
mailerlite = MailerLiteData(ml_csv_path)

ml_stats = mailerlite.get_statistics()
print(f"        Loaded {ml_stats['total_subscribers']} subscribers")
print(f"        Avg open rate: {ml_stats['avg_open_rate']}%")

# Get persons
print("\n[3/7] Fetching persons from Pipedrive...")
persons = api.get_persons(limit=500)
print(f"        Found {len(persons)} persons")

# Get activities and deals
print("\n[4/7] Fetching activities and deals...")
for i, person in enumerate(persons):
    if (i+1) % 20 == 0:
        print(f"        Progress: {i+1}/{len(persons)}")

    person_id = person['id']
    person['deals'] = api.get_person_deals(person_id)
    person['activities'] = api.get_person_activities(person_id)

# Calculate base scores
print("\n[5/7] Calculating base lead scores (Pipedrive data)...")
scored_persons = scorer.score_all_persons(persons)

# Add MailerLite email engagement scores
print("\n[6/7] Adding email engagement scores (MailerLite data)...")
email_matched = 0
email_not_found = 0

for person in scored_persons:
    # Get email from person
    email = None
    if person.get('email'):
        if isinstance(person['email'], list) and len(person['email']) > 0:
            email = person['email'][0].get('value', '')
        elif isinstance(person['email'], str):
            email = person['email']

    if email:
        # Get MailerLite engagement
        ml_engagement = mailerlite.get_engagement(email)

        # Add engagement score to total score
        person['email_engagement'] = ml_engagement
        person['lead_score'] += ml_engagement['engagement_score']

        # Re-cap at 100
        person['lead_score'] = min(person['lead_score'], 100)

        # Re-calculate segment with new score
        if person['lead_score'] >= 80:
            person['lead_segment'] = 'Warm'
        elif person['lead_score'] >= 40:
            person['lead_segment'] = 'Lauw'
        else:
            person['lead_segment'] = 'Koud'

        if ml_engagement['engagement_score'] > 0:
            email_matched += 1
    else:
        person['email_engagement'] = {'engagement_score': 0}
        email_not_found += 1

print(f"        Email matched: {email_matched}")
print(f"        Email not found: {email_not_found}")

# Re-sort by new scores
scored_persons.sort(key=lambda x: x['lead_score'], reverse=True)

# Count segments
print("\n[7/7] Final results...")
segments = {'Warm': 0, 'Lauw': 0, 'Koud': 0}
for person in scored_persons:
    segments[person['lead_segment']] += 1

# Print results
print("\n" + "="*70)
print("  RESULTS")
print("="*70)
print(f"\nWarm leads:  {segments['Warm']} (score >= 80)")
print(f"Lauw leads:  {segments['Lauw']} (score 40-79)")
print(f"Koud leads:  {segments['Koud']} (score < 40)")

print("\n" + "-"*70)
print("  TOP 20 LEADS (sorted by score)")
print("-"*70)
print(f"{'#':<3} {'Name':<28} {'Score':>5} {'Seg':<5} {'CRM':>3} {'Email':>3} {'Total':>5}")
print("-"*70)

for i, person in enumerate(scored_persons[:20], 1):
    name = person.get('name', 'Unknown')[:26]
    score = person['lead_score']
    segment = person['lead_segment']
    crm_score = score - person['email_engagement']['engagement_score']
    email_score = person['email_engagement']['engagement_score']

    print(f"{i:<3} {name:<28} {score:>5} {segment:<5} {crm_score:>3} {email_score:>3} {score:>5}")

# Export CSV
filename = f"leads_complete_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
filepath = f"c:/projects/tools_en_analyses/funnel_automation/{filename}"

print(f"\n[EXPORT] Exporting to: {filename}")
with open(filepath, 'w', encoding='utf-8-sig') as f:  # UTF-8 BOM for Excel
    f.write("Name,Email,Total Score,Segment,CRM Score,Email Score,Opens,Clicks,Company,Phone\n")

    for person in scored_persons:
        name = person.get('name', '').replace(',', ' ')
        email = ''
        if person.get('email'):
            if isinstance(person['email'], list) and len(person['email']) > 0:
                email = person['email'][0].get('value', '')
            elif isinstance(person['email'], str):
                email = person['email']

        total_score = person['lead_score']
        segment = person['lead_segment']
        crm_score = total_score - person['email_engagement']['engagement_score']
        email_score = person['email_engagement']['engagement_score']
        opens = person['email_engagement'].get('opens', 0)
        clicks = person['email_engagement'].get('clicks', 0)

        company = (person.get('org_name') or '').replace(',', ' ')
        phone = ''
        if person.get('phone') and isinstance(person['phone'], list) and len(person['phone']) > 0:
            phone = person['phone'][0].get('value', '')

        f.write(f"{name},{email},{total_score},{segment},{crm_score},{email_score},{opens},{clicks},{company},{phone}\n")

print(f"\n[DONE] Results exported to:")
print(f"       {filepath}")

print("\n" + "="*70)
print("  COMPLETE!")
print("="*70 + "\n")

print("Next steps:")
print("  1. Review top leads in CSV")
print("  2. Update Pipedrive: python update_pipedrive_scores.py")
print("  3. View dashboard: streamlit run dashboard.py")
print()
