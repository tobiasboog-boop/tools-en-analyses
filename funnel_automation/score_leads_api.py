"""Complete lead scoring met Pipedrive + MailerLite API (geen CSV)."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from datetime import datetime
from pipedrive_api import PipedriveAPI
from lead_scoring import LeadScorer
from mailerlite_api_v2 import MailerLiteAPI

print("\n" + "="*70)
print("  LEAD SCORING - Pipedrive + MailerLite API")
print("="*70 + "\n")

# Initialize
print("[1/7] Initializing APIs...")
pipedrive = PipedriveAPI()
scorer = LeadScorer(warm_threshold=80, lukewarm_threshold=40)
mailerlite = MailerLiteAPI()

# Get MailerLite data
print("[2/7] Loading MailerLite data...")
print("        Fetching account stats...")
ml_stats = mailerlite.get_account_stats()
print(f"        Campaigns: {ml_stats['campaigns']}")
print(f"        Sent emails: {ml_stats['sent_emails']}")
print(f"        Open rate: {ml_stats['open_rate']*100:.1f}%")
print(f"        Click rate: {ml_stats['click_rate']*100:.1f}%")

print("\n        Fetching all subscribers (this may take a minute)...")
ml_subscribers = mailerlite.get_all_subscribers(limit=2000)
print(f"        Loaded {len(ml_subscribers)} subscribers")

print("\n        Building email lookup...")
ml_lookup = mailerlite.build_subscriber_lookup(ml_subscribers)
print(f"        Lookup dict: {len(ml_lookup)} unique emails")

# Get Pipedrive persons
print("\n[3/7] Fetching persons from Pipedrive...")
persons = pipedrive.get_persons(limit=500)
print(f"        Found {len(persons)} persons")

# Get activities and deals
print("\n[4/7] Fetching activities and deals...")
print("        NOTE: This uses Pipedrive API quota (currently at 75%)")
print("        Processing...")

for i, person in enumerate(persons):
    if (i+1) % 50 == 0:
        print(f"        Progress: {i+1}/{len(persons)}")

    person_id = person['id']
    person['deals'] = pipedrive.get_person_deals(person_id)
    person['activities'] = pipedrive.get_person_activities(person_id)

print(f"        Complete!")

# Calculate base scores
print("\n[5/7] Calculating base lead scores (Pipedrive data)...")
scored_persons = scorer.score_all_persons(persons)

# Add MailerLite email engagement scores
print("\n[6/7] Adding email engagement scores (MailerLite API)...")
ml_matched = 0
ml_not_found = 0
ml_total_engagement = 0

for person in scored_persons:
    # Get email from person
    email = None
    if person.get('email'):
        if isinstance(person['email'], list) and len(person['email']) > 0:
            email = person['email'][0].get('value', '').lower()
        elif isinstance(person['email'], str):
            email = person['email'].lower()

    if email and email in ml_lookup:
        # Use pre-fetched subscriber data (no extra API calls!)
        subscriber = ml_lookup[email]
        engagement = mailerlite.get_engagement_score(email, subscriber_data=subscriber)

        # Store engagement data
        person['email_engagement'] = engagement

        # Add engagement score to total
        person['lead_score'] += engagement['engagement_score']
        ml_total_engagement += engagement['engagement_score']

        # Re-cap at 100
        person['lead_score'] = min(person['lead_score'], 100)

        # Re-calculate segment
        if person['lead_score'] >= 80:
            person['lead_segment'] = 'Warm'
        elif person['lead_score'] >= 40:
            person['lead_segment'] = 'Lauw'
        else:
            person['lead_segment'] = 'Koud'

        ml_matched += 1
    else:
        person['email_engagement'] = {
            'found': False,
            'engagement_score': 0,
            'opens': 0,
            'clicks': 0,
            'sent': 0
        }
        ml_not_found += 1

print(f"        Matched: {ml_matched}")
print(f"        Not found: {ml_not_found}")
print(f"        Avg engagement score: {ml_total_engagement/ml_matched:.1f}/30" if ml_matched > 0 else "        No matches")

# Re-sort by score
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
print(f"{'#':<3} {'Name':<26} {'Score':>5} {'Seg':<5} {'CRM':>3} {'Email':>5} {'Opens':>5} {'Clicks':>6}")
print("-"*70)

for i, person in enumerate(scored_persons[:20], 1):
    name = person.get('name', 'Unknown')[:24]
    score = person['lead_score']
    segment = person['lead_segment']

    crm_score = score - person['email_engagement']['engagement_score']
    email_score = person['email_engagement']['engagement_score']
    opens = person['email_engagement'].get('opens', 0)
    clicks = person['email_engagement'].get('clicks', 0)

    print(f"{i:<3} {name:<26} {score:>5} {segment:<5} {crm_score:>3} {email_score:>5} {opens:>5} {clicks:>6}")

# Export CSV
filename = f"leads_api_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
filepath = f"c:/projects/tools_en_analyses/funnel_automation/{filename}"

print(f"\n[EXPORT] Exporting to: {filename}")
with open(filepath, 'w', encoding='utf-8-sig') as f:
    f.write("Name,Email,Total Score,Segment,CRM Score,Email Score,Opens,Clicks,Sent,Open Rate,Click Rate,Company,Phone\n")

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
        sent = person['email_engagement'].get('sent', 0)
        open_rate = person['email_engagement'].get('open_rate', 0)
        click_rate = person['email_engagement'].get('click_rate', 0)

        company = (person.get('org_name') or '').replace(',', ' ')
        phone = ''
        if person.get('phone') and isinstance(person['phone'], list) and len(person['phone']) > 0:
            phone = person['phone'][0].get('value', '')

        f.write(f"{name},{email},{total_score},{segment},{crm_score},{email_score},{opens},{clicks},{sent},{open_rate},{click_rate},{company},{phone}\n")

print(f"\n[DONE] Results exported to:")
print(f"       {filepath}")

# Campaign stats summary
print("\n" + "="*70)
print("  MAILERLITE CAMPAIGN PERFORMANCE")
print("="*70)

campaign_summary = mailerlite.get_campaign_stats_summary()
print(f"\nTotaal verzonden campaigns: {campaign_summary['total_campaigns']}")
print(f"Gemiddelde open rate: {campaign_summary['avg_open_rate']:.1f}%")
print(f"Gemiddelde click rate: {campaign_summary['avg_click_rate']:.1f}%")

if campaign_summary['best_campaign']:
    best = campaign_summary['best_campaign']
    print(f"\nBest presterende campaign:")
    print(f"  Naam: {best['name']}")
    print(f"  Open rate: {best['open_rate']:.1f}%")
    print(f"  Click rate: {best['click_rate']:.1f}%")

print("\n" + "="*70)
print("  COMPLETE!")
print("="*70 + "\n")

print("Data bronnen:")
print("  - Pipedrive API: CRM activiteiten, deals, contacten")
print("  - MailerLite API: Email engagement, campaigns, subscribers")
print()

print("Next steps:")
print("  1. Review top leads in CSV")
print("  2. Update Pipedrive: python update_pipedrive_scores.py")
print("  3. View dashboard: streamlit run dashboard.py")
print()
