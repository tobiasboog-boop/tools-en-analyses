"""Test GA4 API Access met nieuwe property"""
import json
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Dimension, Metric
from google.oauth2 import service_account

# Laad secrets
import tomli
with open('.streamlit/secrets.toml', 'rb') as f:
    secrets = tomli.load(f)

CREDENTIALS_JSON = secrets['GA4_SERVICE_ACCOUNT_JSON']
PROPERTY_ID = secrets['GA4_PROPERTY_ID']

print(f"Testing GA4 API access...")
print(f"Property ID: {PROPERTY_ID}")

# Parse credentials
credentials_info = json.loads(CREDENTIALS_JSON)
credentials = service_account.Credentials.from_service_account_info(
    credentials_info,
    scopes=['https://www.googleapis.com/auth/analytics.readonly']
)
print(f"Service account: {credentials_info['client_email']}")

# Test API call
client = BetaAnalyticsDataClient(credentials=credentials)

try:
    request = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        dimensions=[Dimension(name="date")],
        metrics=[Metric(name="activeUsers")],
        date_ranges=[DateRange(start_date="7daysAgo", end_date="today")],
    )

    print("\nTesting API call...")
    response = client.run_report(request)

    print(f"\nSUCCESS! API toegang werkt!")
    print(f"Data ontvangen: {len(response.rows)} rijen")

    if response.rows:
        print("\nVoorbeeld data:")
        for i, row in enumerate(response.rows[:3]):
            date = row.dimension_values[0].value
            users = row.metric_values[0].value
            print(f"  {date}: {users} gebruikers")
    else:
        print("\nGeen data gevonden (property is nieuw, dit is normaal)")

except Exception as e:
    print(f"\nERROR: {str(e)}")
    print("\nDit betekent waarschijnlijk dat de service account nog geen toegang heeft.")
    print("We moeten de service account handmatig toevoegen aan de property.")
