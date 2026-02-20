"""Diepgaand onderzoek MailerLite API - alle mogelijkheden."""
import os
import requests
from dotenv import load_dotenv
import json
from time import sleep

load_dotenv()

MAILERLITE_API_TOKEN = os.getenv('MAILERLITE_API_TOKEN')

headers = {
    'X-MailerLite-ApiKey': MAILERLITE_API_TOKEN,
    'Content-Type': 'application/json'
}

base_url = "https://api.mailerlite.com/api/v2"

print("\n" + "="*70)
print("  MAILERLITE API - DIEPGAAND ONDERZOEK")
print("="*70 + "\n")

# Test 1: Haal alle subscribers op uit hoofdgroep
print("[1] Subscribers ophalen uit 'Actieve inschrijvingen' groep...")
group_id = 177296943307818341  # Actieve inschrijvingen

try:
    # Get first 100 subscribers
    response = requests.get(
        f"{base_url}/groups/{group_id}/subscribers",
        headers=headers,
        params={"limit": 100, "offset": 0}
    )
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        subscribers = response.json()
        print(f"Gevonden: {len(subscribers)} subscribers (eerste 100)")

        if subscribers:
            # Show first subscriber details
            sub = subscribers[0]
            print(f"\nVoorbeeld subscriber:")
            print(f"  Email: {sub.get('email')}")
            print(f"  ID: {sub.get('id')}")
            print(f"  Name: {sub.get('name', 'N/A')}")
            print(f"  Total opens: {sub.get('opened', 0)}")
            print(f"  Total clicks: {sub.get('clicked', 0)}")
            print(f"  Total sent: {sub.get('sent', 0)}")
            print(f"  Subscribed: {sub.get('date_subscribe', 'N/A')}")

            # Check for custom fields
            if 'fields' in sub:
                print(f"  Custom fields: {len(sub['fields'])}")
                for field in sub['fields'][:3]:
                    print(f"    - {field.get('key')}: {field.get('value')}")

            # Save for later use
            sample_subscriber_id = sub.get('id')
            sample_email = sub.get('email')
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        sample_subscriber_id = None
        sample_email = None

except Exception as e:
    print(f"Error: {e}")
    sample_subscriber_id = None
    sample_email = None

# Test 2: Get activity voor een subscriber
if sample_subscriber_id:
    print(f"\n[2] Activity ophalen voor subscriber {sample_subscriber_id}...")

    try:
        response = requests.get(
            f"{base_url}/subscribers/{sample_subscriber_id}/activity",
            headers=headers
        )
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            activity = response.json()
            print(f"Activity events: {len(activity)}")

            if activity:
                print("\nLaatste 5 events:")
                for event in activity[:5]:
                    event_type = event.get('type', 'unknown')
                    date = event.get('date', 'N/A')
                    campaign_id = event.get('campaign_id', 'N/A')
                    subject = event.get('subject', 'N/A')

                    print(f"  {date} | {event_type:8s} | Campaign: {campaign_id} | {subject[:40]}")

                # Analyze activity
                opens = sum(1 for e in activity if e.get('type') == 'open')
                clicks = sum(1 for e in activity if e.get('type') == 'click')
                sent = sum(1 for e in activity if e.get('type') == 'sent')

                print(f"\nTotalen: {sent} sent, {opens} opens, {clicks} clicks")

                # Get unique campaigns
                campaign_ids = set(e.get('campaign_id') for e in activity if e.get('campaign_id'))
                print(f"Unieke campaigns: {len(campaign_ids)}")

        else:
            print(f"Error: {response.status_code}")
            print(response.text)

    except Exception as e:
        print(f"Error: {e}")

# Test 3: Probeer campaigns op verschillende manieren
print("\n[3] Campaigns endpoint testen (verschillende varianten)...")

# Variant A: GET /campaigns (all)
print("\n  A) GET /campaigns (geen filter)...")
try:
    response = requests.get(f"{base_url}/campaigns", headers=headers, params={"limit": 10})
    print(f"     Status: {response.status_code}")
    if response.status_code == 200:
        campaigns = response.json()
        print(f"     Result type: {type(campaigns)}")
        print(f"     Campaigns: {len(campaigns) if isinstance(campaigns, list) else 'not a list'}")
except Exception as e:
    print(f"     Error: {e}")

# Variant B: GET /campaigns met type=regular
print("\n  B) GET /campaigns?type=regular...")
try:
    response = requests.get(f"{base_url}/campaigns", headers=headers, params={"type": "regular", "limit": 10})
    print(f"     Status: {response.status_code}")
    if response.status_code == 200:
        campaigns = response.json()
        print(f"     Result: {campaigns}")
except Exception as e:
    print(f"     Error: {e}")

# Variant C: Direct campaign ID ophalen (from activity)
if sample_subscriber_id:
    print("\n  C) Direct campaign opvragen via ID uit activity...")

    # Get a campaign ID from activity
    try:
        response = requests.get(f"{base_url}/subscribers/{sample_subscriber_id}/activity", headers=headers)
        if response.status_code == 200:
            activity = response.json()
            if activity:
                campaign_id = activity[0].get('campaign_id')

                if campaign_id:
                    print(f"     Probeer campaign {campaign_id} op te halen...")

                    response2 = requests.get(f"{base_url}/campaigns/{campaign_id}", headers=headers)
                    print(f"     Status: {response2.status_code}")

                    if response2.status_code == 200:
                        campaign = response2.json()
                        print(f"\n     SUCCESS! Campaign data:")
                        print(f"     Name: {campaign.get('name', 'N/A')}")
                        print(f"     Subject: {campaign.get('subject', 'N/A')}")
                        print(f"     Type: {campaign.get('type', 'N/A')}")

                        # Stats
                        if 'opened' in campaign:
                            print(f"     Opens: {campaign['opened'].get('count', 0)} ({campaign['opened'].get('rate', 0)}%)")
                        if 'clicked' in campaign:
                            print(f"     Clicks: {campaign['clicked'].get('count', 0)} ({campaign['clicked'].get('rate', 0)}%)")
                        if 'total_recipients' in campaign:
                            print(f"     Recipients: {campaign['total_recipients']}")
                    else:
                        print(f"     Error: {response2.text}")

    except Exception as e:
        print(f"     Error: {e}")

# Test 4: Segments endpoint
print("\n[4] Segments endpoint testen...")
try:
    response = requests.get(f"{base_url}/segments", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        segments = response.json()
        print(f"Segments gevonden: {len(segments)}")
        if segments:
            for seg in segments[:3]:
                print(f"  - {seg.get('name')} (ID: {seg.get('id')})")
except Exception as e:
    print(f"Error: {e}")

# Test 5: Fields endpoint (custom fields)
print("\n[5] Fields endpoint testen...")
try:
    response = requests.get(f"{base_url}/fields", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        fields = response.json()
        print(f"Custom fields gevonden: {len(fields)}")
        if fields:
            for field in fields[:5]:
                print(f"  - {field.get('title')} (key: {field.get('key')}, type: {field.get('type')})")
except Exception as e:
    print(f"Error: {e}")

# Test 6: Webhooks endpoint
print("\n[6] Webhooks endpoint testen...")
try:
    response = requests.get(f"{base_url}/webhooks", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        webhooks = response.json()
        print(f"Webhooks: {len(webhooks)}")
        if webhooks:
            for hook in webhooks:
                print(f"  - {hook.get('event')} -> {hook.get('url')}")
        else:
            print("  Geen webhooks geconfigureerd")
except Exception as e:
    print(f"Error: {e}")

# Test 7: Stats endpoint
print("\n[7] Stats endpoint testen...")
try:
    response = requests.get(f"{base_url}/stats", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        stats = response.json()
        print(f"Account stats:")
        print(json.dumps(stats, indent=2))
except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*70)
print("  ONDERZOEK COMPLEET")
print("="*70 + "\n")
