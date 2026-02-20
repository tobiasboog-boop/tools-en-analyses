"""Enhanced lead scoring with optional MailerLite API for recent activity."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from datetime import datetime
from pipedrive_api import PipedriveAPI
from lead_scoring import LeadScorer
from mailerlite_integration import MailerLiteData
from mailerlite_api import MailerLiteAPI

print("\n" + "="*70)
print("  ENHANCED LEAD SCORING - Pipedrive + MailerLite (CSV + API)")
print("="*70 + "\n")

# Initialize
print("[1/8] Initializing...")
api = PipedriveAPI()
scorer = LeadScorer(warm_threshold=80, lukewarm_threshold=40)
ml_api = MailerLiteAPI()

# Load MailerLite CSV data (for bulk stats)
print("[2/8] Loading MailerLite CSV data...")
ml_csv_path = r"C:\Users\tobia\OneDrive - Notifica B.V\Documenten - Sharepoint Notifica intern\105. Marketing\export mailer lite.csv"
mailerlite_csv = MailerLiteData(ml_csv_path)

ml_stats = mailerlite_csv.get_statistics()
print(f"        Loaded {ml_stats['total_subscribers']} subscribers from CSV")
print(f"        Avg open rate: {ml_stats['avg_open_rate']}%")

# Get persons
print("\n[3/8] Fetching persons from Pipedrive...")
persons = api.get_persons(limit=500)
print(f"        Found {len(persons)} persons")

# Get activities and deals
print("\n[4/8] Fetching activities and deals...")
for i, person in enumerate(persons):
    if (i+1) % 20 == 0:
        print(f"        Progress: {i+1}/{len(persons)}")

    person_id = person['id']
    person['deals'] = api.get_person_deals(person_id)
    person['activities'] = api.get_person_activities(person_id)

# Calculate base scores
print("\n[5/8] Calculating base lead scores (Pipedrive data)...")
scored_persons = scorer.score_all_persons(persons)

# Add CSV-based email engagement scores
print("\n[6/8] Adding email engagement scores from CSV...")
csv_matched = 0
csv_not_found = 0

for person in scored_persons:
    # Get email from person
    email = None
    if person.get('email'):
        if isinstance(person['email'], list) and len(person['email']) > 0:
            email = person['email'][0].get('value', '')
        elif isinstance(person['email'], str):
            email = person['email']

    if email:
        # Get CSV engagement
        csv_engagement = mailerlite_csv.get_engagement(email)

        # Add engagement score to total score
        person['email_engagement'] = csv_engagement
        person['lead_score'] += csv_engagement['engagement_score']

        # Re-cap at 100
        person['lead_score'] = min(person['lead_score'], 100)

        # Re-calculate segment with new score
        if person['lead_score'] >= 80:
            person['lead_segment'] = 'Warm'
        elif person['lead_score'] >= 40:
            person['lead_segment'] = 'Lauw'
        else:
            person['lead_segment'] = 'Koud'

        if csv_engagement['engagement_score'] > 0:
            csv_matched += 1
    else:
        person['email_engagement'] = {'engagement_score': 0}
        csv_not_found += 1

print(f"        CSV email matched: {csv_matched}")
print(f"        CSV email not found: {csv_not_found}")

# Re-sort by score
scored_persons.sort(key=lambda x: x['lead_score'], reverse=True)

# ENHANCEMENT: Check recent activity for top 20 leads via API
print("\n[7/8] Checking recent activity for top leads (API)...")
api_checked = 0
api_boosted = 0

for person in scored_persons[:20]:  # Only top 20 to avoid rate limits
    email = None
    if person.get('email'):
        if isinstance(person['email'], list) and len(person['email']) > 0:
            email = person['email'][0].get('value', '')
        elif isinstance(person['email'], str):
            email = person['email']

    if not email:
        continue

    try:
        # Check last 30 days of activity via API
        recent = ml_api.get_recent_engagement(email, days=30)

        if recent['found']:
            api_checked += 1

            # Calculate recency boost (0-10 bonus points)
            recency_boost = 0

            # Recent opens in last 30 days
            if recent['recent_opens'] >= 3:
                recency_boost += 5
            elif recent['recent_opens'] >= 1:
                recency_boost += 3

            # Recent clicks in last 30 days
            if recent['recent_clicks'] >= 2:
                recency_boost += 5
            elif recent['recent_clicks'] >= 1:
                recency_boost += 2

            if recency_boost > 0:
                api_boosted += 1
                old_score = person['lead_score']
                person['lead_score'] = min(person['lead_score'] + recency_boost, 100)

                # Update segment if score changed significantly
                if person['lead_score'] >= 80:
                    person['lead_segment'] = 'Warm'
                elif person['lead_score'] >= 40:
                    person['lead_segment'] = 'Lauw'

                # Store recency data
                person['recent_activity'] = {
                    'checked': True,
                    'recent_opens_30d': recent['recent_opens'],
                    'recent_clicks_30d': recent['recent_clicks'],
                    'recency_boost': recency_boost,
                    'old_score': old_score
                }
            else:
                person['recent_activity'] = {
                    'checked': True,
                    'recent_opens_30d': 0,
                    'recent_clicks_30d': 0,
                    'recency_boost': 0
                }

    except Exception as e:
        print(f"        Warning: API check failed for {email}: {e}")
        person['recent_activity'] = {'checked': False, 'error': str(e)}

print(f"        API checked: {api_checked}")
print(f"        Scores boosted: {api_boosted}")

# Re-sort after boosts
scored_persons.sort(key=lambda x: x['lead_score'], reverse=True)

# Count segments
print("\n[8/8] Final results...")
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
print("  TOP 20 LEADS (sorted by enhanced score)")
print("-"*70)
print(f"{'#':<3} {'Name':<24} {'Score':>5} {'Seg':<5} {'Recency':>7} {'Note':<20}")
print("-"*70)

for i, person in enumerate(scored_persons[:20], 1):
    name = person.get('name', 'Unknown')[:22]
    score = person['lead_score']
    segment = person['lead_segment']

    # Show recency info if available
    recency_info = ""
    note = ""
    if person.get('recent_activity', {}).get('checked'):
        boost = person['recent_activity'].get('recency_boost', 0)
        recency_info = f"+{boost}" if boost > 0 else "-"

        recent_opens = person['recent_activity'].get('recent_opens_30d', 0)
        recent_clicks = person['recent_activity'].get('recent_clicks_30d', 0)

        if recent_opens > 0 or recent_clicks > 0:
            note = f"{recent_opens}o {recent_clicks}c (30d)"
    else:
        recency_info = "-"

    print(f"{i:<3} {name:<24} {score:>5} {segment:<5} {recency_info:>7} {note:<20}")

# Export CSV
filename = f"leads_enhanced_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
filepath = f"c:/projects/tools_en_analyses/funnel_automation/{filename}"

print(f"\n[EXPORT] Exporting to: {filename}")
with open(filepath, 'w', encoding='utf-8-sig') as f:  # UTF-8 BOM for Excel
    f.write("Name,Email,Total Score,Segment,CRM Score,Email Score,Recent Opens 30d,Recent Clicks 30d,Recency Boost,Company,Phone\n")

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

        # Recent activity data
        recent_opens = person.get('recent_activity', {}).get('recent_opens_30d', '')
        recent_clicks = person.get('recent_activity', {}).get('recent_clicks_30d', '')
        recency_boost = person.get('recent_activity', {}).get('recency_boost', '')

        company = (person.get('org_name') or '').replace(',', ' ')
        phone = ''
        if person.get('phone') and isinstance(person['phone'], list) and len(person['phone']) > 0:
            phone = person['phone'][0].get('value', '')

        f.write(f"{name},{email},{total_score},{segment},{crm_score},{email_score},{recent_opens},{recent_clicks},{recency_boost},{company},{phone}\n")

print(f"\n[DONE] Results exported to:")
print(f"       {filepath}")

print("\n" + "="*70)
print("  COMPLETE!")
print("="*70 + "\n")

print("What's new in enhanced version:")
print("  - CSV data for bulk email engagement (all leads)")
print("  - API checks for recent activity on top 20 leads (30-day window)")
print("  - Recency boost: +0-10 points for very recent engagement")
print("  - Recent opens/clicks visible in export")
print()

print("Next steps:")
print("  1. Review top leads with recent activity")
print("  2. Update Pipedrive: python update_pipedrive_scores.py")
print("  3. View dashboard: streamlit run dashboard.py")
print()
