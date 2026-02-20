"""Debug MailerLite API to understand data structure."""
import os
import requests
from dotenv import load_dotenv
import json

load_dotenv()

MAILERLITE_API_TOKEN = os.getenv('MAILERLITE_API_TOKEN')

headers = {
    'X-MailerLite-ApiKey': MAILERLITE_API_TOKEN,
    'Content-Type': 'application/json'
}

base_url = "https://api.mailerlite.com/api/v2"

print("\n=== Testing MailerLite API Endpoints ===\n")

# Test 1: Get campaigns
print("[1] Testing campaigns endpoint...")
try:
    response = requests.get(f"{base_url}/campaigns", headers=headers, params={"status": "sent", "limit": 3})
    print(f"Status: {response.status_code}")
    campaigns = response.json()
    print(f"Found {len(campaigns)} campaigns\n")

    if campaigns:
        print("First campaign structure:")
        print(json.dumps(campaigns[0], indent=2))
        print()
except Exception as e:
    print(f"Error: {e}\n")

# Test 2: Try to get subscriber by email
print("\n[2] Testing subscriber lookup...")
test_emails = [
    "t.boog@notifica.nl",
    "info@notifica.nl"
]

for email in test_emails:
    try:
        response = requests.get(f"{base_url}/subscribers/{email}", headers=headers)
        print(f"Email: {email} - Status: {response.status_code}")
        if response.status_code == 200:
            subscriber = response.json()
            print(f"  Subscriber ID: {subscriber.get('id')}")
            print(f"  Total opens: {subscriber.get('opened', 0)}")
            print(f"  Total clicks: {subscriber.get('clicked', 0)}")
            break
    except Exception as e:
        print(f"  Error: {e}")

# Test 3: Get all subscribers (first 5)
print("\n[3] Testing subscribers list...")
try:
    response = requests.get(f"{base_url}/subscribers", headers=headers, params={"limit": 5})
    print(f"Status: {response.status_code}")
    subscribers = response.json()

    if isinstance(subscribers, list) and subscribers:
        print(f"Found subscribers. First one:")
        print(f"  Email: {subscribers[0].get('email')}")
        print(f"  ID: {subscribers[0].get('id')}")
        print(f"  Opens: {subscribers[0].get('opened', 0)}")
        print(f"  Clicks: {subscribers[0].get('clicked', 0)}")
except Exception as e:
    print(f"Error: {e}")

# Test 4: Groups/Lists
print("\n[4] Testing groups/lists...")
try:
    response = requests.get(f"{base_url}/groups", headers=headers)
    print(f"Status: {response.status_code}")
    groups = response.json()

    if groups:
        print(f"Found {len(groups)} groups:")
        for group in groups[:3]:
            print(f"  - {group.get('name')} (ID: {group.get('id')}, {group.get('total', 0)} subscribers)")
except Exception as e:
    print(f"Error: {e}")

print("\n=== Debug Complete ===\n")
