"""Debug Web Visitors matching met Pipedrive CRM."""
import pandas as pd
import requests
import tomli

# Load secrets
try:
    with open('.streamlit/secrets.toml', 'rb') as f:
        secrets = tomli.load(f)
    mailerlite_token = secrets['MAILERLITE_API_TOKEN']
    pipedrive_token = secrets['PIPEDRIVE_API_TOKEN']
except Exception as e:
    print(f"Error loading secrets: {e}")
    exit(1)

# Load Web Visitors mapping
web_visitors_df = pd.read_csv('web_visitors_mapping.csv', encoding='utf-8-sig')
web_visitors_mapping = {
    str(row['company_name']).strip().lower(): int(row['website_visits_score'])
    for _, row in web_visitors_df.iterrows()
}

print(f"Web Visitors: {len(web_visitors_mapping)} bedrijven\n")

# Get Pipedrive organizations
url = f"https://notifica.pipedrive.com/v1/organizations"
params = {'api_token': pipedrive_token, 'limit': 500}

try:
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    orgs = response.json().get('data', [])

    print(f"Pipedrive Orgs: {len(orgs)} bedrijven\n")

    # Check matches
    matches = []
    pipedrive_org_names = {}

    for org in orgs:
        org_name = org.get('name', '').strip()
        org_key = org_name.lower()
        pipedrive_org_names[org_key] = org_name

        if org_key in web_visitors_mapping:
            matches.append({
                'pipedrive_name': org_name,
                'web_visitors_score': web_visitors_mapping[org_key]
            })

    print("=" * 80)
    print(f"MATCHES GEVONDEN: {len(matches)}")
    print("=" * 80)

    if matches:
        for m in matches[:20]:
            print(f"  {m['pipedrive_name']:50} → {m['web_visitors_score']} punten")
    else:
        print("\n⚠️ GEEN MATCHES! Bedrijfsnamen komen niet overeen.\n")
        print("Eerste 10 Pipedrive org namen:")
        for org_name in list(pipedrive_org_names.values())[:10]:
            print(f"  - {org_name}")

        print("\nEerste 10 Web Visitors namen:")
        for visitor_name in list(web_visitors_df['company_name'].head(10)):
            print(f"  - {visitor_name}")

except Exception as e:
    print(f"Error: {e}")
