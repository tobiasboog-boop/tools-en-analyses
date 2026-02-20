"""Export GA4 historische data naar CSV voor analyse.

Gebruik: python ga4_export_historical.py
Output: ga4_export_YYYYMMDD.csv
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
from datetime import datetime
import csv
from ga4_data_api import GA4DataAPI

print("\n" + "="*70)
print("  GA4 HISTORISCHE DATA EXPORT")
print("="*70 + "\n")

try:
    # Initialize GA4 client
    print("[1/4] Connecting to GA4 Data API...")
    ga4 = GA4DataAPI()
    print("        ✓ Connected")

    # Export 1: User sessions met emails (laatste 90 dagen)
    print("\n[2/4] Exporting user sessions...")
    users = ga4.get_user_sessions(days=90)
    print(f"        Found {len(users)} users with email tracking")

    # Export 2: High-intent pages (laatste 90 dagen)
    print("\n[3/4] Exporting high-intent pages...")
    pages = ga4.get_high_intent_pages(days=90)
    print(f"        Found {len(pages)} high-intent page views")

    # Generate filename
    filename = f"ga4_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(
        os.path.dirname(__file__),
        filename
    )

    # Export to CSV
    print(f"\n[4/4] Writing to CSV: {filename}")

    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow([
            'Email',
            'Sessions (90d)',
            'Page Views (90d)',
            'Total Events (90d)',
            'Engagement Rate (%)',
            'High-Intent Pages Viewed',
            'Last Activity'
        ])

        # Calculate high-intent page views per user (if possible)
        # For now, just export what we have
        for user in users:
            email = user['email']
            sessions = user['sessions']
            page_views = user['page_views']
            events = user['events']
            engagement_rate = round(user['engagement_rate'] * 100, 1)

            # Try to get engagement score for this user
            try:
                engagement = ga4.get_engagement_score(email, days=90)
                high_intent_views = (
                    engagement.get('pricing_views', 0) +
                    engagement.get('contact_views', 0) +
                    engagement.get('demo_views', 0) +
                    engagement.get('quote_views', 0)
                )
                last_activity = engagement.get('last_visit_days_ago', 'N/A')
                if last_activity != 'N/A':
                    last_activity = f"{last_activity} dagen geleden"
            except:
                high_intent_views = 0
                last_activity = 'N/A'

            writer.writerow([
                email,
                sessions,
                page_views,
                events,
                engagement_rate,
                high_intent_views,
                last_activity
            ])

    print(f"        ✓ Exported {len(users)} users to CSV")
    print(f"\n[EXPORT] File saved:")
    print(f"         {filepath}")

    # Summary statistics
    print("\n" + "="*70)
    print("  SUMMARY")
    print("="*70)

    total_sessions = sum(u['sessions'] for u in users)
    total_pageviews = sum(u['page_views'] for u in users)
    avg_sessions = total_sessions / len(users) if users else 0
    avg_pageviews = total_pageviews / len(users) if users else 0

    print(f"\nTotal users tracked:     {len(users)}")
    print(f"Total sessions:          {total_sessions}")
    print(f"Total page views:        {total_pageviews}")
    print(f"Avg sessions per user:   {avg_sessions:.1f}")
    print(f"Avg pageviews per user:  {avg_pageviews:.1f}")

    print(f"\nHigh-intent pages:")
    intent_types = {}
    for page in pages:
        intent_type = page['intent_type']
        intent_types[intent_type] = intent_types.get(intent_type, 0) + page['page_views']

    for intent_type, count in sorted(intent_types.items(), key=lambda x: x[1], reverse=True):
        print(f"  {intent_type:10s}: {count} views")

    print("\n" + "="*70)
    print("  EXPORT COMPLEET!")
    print("="*70 + "\n")

    print("Next steps:")
    print("  1. Open CSV in Excel voor analyse")
    print("  2. Filter op high-intent users")
    print("  3. Cross-reference met Pipedrive/MailerLite data")
    print()

except FileNotFoundError as e:
    print(f"\n[ERROR] GA4 credentials not found!")
    print(f"        Expected location: {os.getenv('GA4_CREDENTIALS_PATH')}")
    print(f"\nSetup:")
    print("  1. Download service account JSON from Google Cloud")
    print("  2. Place at: C:\\projects\\tools_en_analyses\\funnel_automation\\ga4-service-account.json")
    print("  3. Or update GA4_CREDENTIALS_PATH in .env")
    print()

except Exception as e:
    print(f"\n[ERROR] {e}")
    print("\nPossible issues:")
    print("  - No User-ID data yet (wait for website deployment + 2-3 weeks)")
    print("  - Service account lacks permissions")
    print("  - Wrong GA4 Property ID in .env")
    print()
    import traceback
    traceback.print_exc()
