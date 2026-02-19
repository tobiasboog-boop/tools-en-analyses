"""Test Pipedrive API - minimale calls"""
import requests

PIPEDRIVE_API_TOKEN = "55e6c216918898cafd9687971a9945813b4dcd2f"
PIPEDRIVE_DOMAIN = "notifica"

# Test 1: Get one person to check structure
url = f"https://{PIPEDRIVE_DOMAIN}.pipedrive.com/v1/persons"
params = {
    'api_token': PIPEDRIVE_API_TOKEN,
    'limit': 1
}

response = requests.get(url, params=params, timeout=10)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    if data.get('data'):
        person = data['data'][0]
        print(f"\nPerson structure:")
        print(f"- ID: {person.get('id')}")
        print(f"- Name: {person.get('name')}")
        print(f"- Email: {person.get('email')}")
        print(f"- Phone: {person.get('phone')}")
        print(f"- Last activity: {person.get('last_activity_date')}")
        print(f"- Update time: {person.get('update_time')}")
        print(f"\nAvailable fields:")
        print(list(person.keys())[:10])
else:
    print(f"Error: {response.text}")
