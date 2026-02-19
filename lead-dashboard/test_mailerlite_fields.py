"""Test welke velden MailerLite subscribers hebben"""
import requests
import json

try:
    import tomli
    with open('.streamlit/secrets.toml', 'rb') as f:
        secrets = tomli.load(f)
    token = secrets['MAILERLITE_API_TOKEN']
except:
    print("Secrets file niet gevonden - gebruik hardcoded token")
    token = input("Plak MAILERLITE_API_TOKEN: ")

MAIN_GROUP_ID = 177296943307818341

headers = {'X-MailerLite-ApiKey': token}
url = f"https://api.mailerlite.com/api/v2/groups/{MAIN_GROUP_ID}/subscribers"
params = {'limit': 1}  # Just get 1 subscriber to see fields

print(f"Fetching subscriber from group {MAIN_GROUP_ID}...\n")

response = requests.get(url, headers=headers, params=params, timeout=10)

if response.status_code == 200:
    subscribers = response.json()
    if subscribers:
        print("✅ SUCCESS! Eerste subscriber ontvangen:\n")
        print(json.dumps(subscribers[0], indent=2))

        print("\n" + "="*60)
        print("BESCHIKBARE VELDEN:")
        print("="*60)
        for key in sorted(subscribers[0].keys()):
            value = subscribers[0][key]
            print(f"  {key:20} = {value}")
    else:
        print("Geen subscribers gevonden")
else:
    print(f"❌ ERROR: {response.status_code}")
    print(response.text)
