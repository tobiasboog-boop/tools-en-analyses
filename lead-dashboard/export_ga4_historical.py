"""GA4 Historical Data Export - Haalt data op uit oude property"""
import json
import os
from datetime import datetime, timedelta
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, Dimension, Metric, DateRange
from google.oauth2 import service_account
import pandas as pd

# Probeer secrets te laden
def load_secrets():
    """Laad secrets uit .streamlit/secrets.toml of gebruik hardcoded."""
    try:
        import tomli
        secrets_path = os.path.join(os.path.dirname(__file__), '.streamlit', 'secrets.toml')
        with open(secrets_path, 'rb') as f:
            secrets = tomli.load(f)
            return secrets.get('GA4_SERVICE_ACCOUNT_JSON'), secrets.get('GA4_PROPERTY_ID', '273791186')
    except:
        # Fallback: hardcoded credentials
        return """PASTE_GA4_SERVICE_ACCOUNT_JSON_HERE""", "273791186"

CREDENTIALS_JSON, GA4_PROPERTY_ID = load_secrets()

def export_ga4_report(client, property_id, report_name, dimensions, metrics, start_date="90daysAgo"):
    """Export een specifiek GA4 rapport."""
    print(f"\nExporteren: {report_name}...")

    try:
        request = RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[Dimension(name=dim) for dim in dimensions],
            metrics=[Metric(name=met) for met in metrics],
            date_ranges=[DateRange(start_date=start_date, end_date="today")],
        )

        response = client.run_report(request)

        # Convert naar DataFrame
        data = []
        for row in response.rows:
            row_data = {}
            for i, dim in enumerate(dimensions):
                row_data[dim] = row.dimension_values[i].value
            for i, met in enumerate(metrics):
                row_data[met] = row.metric_values[i].value
            data.append(row_data)

        df = pd.DataFrame(data)

        # Export naar CSV
        filename = f"ga4_export_{report_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(filename, index=False, encoding='utf-8-sig')

        print(f"SUCCESS: {len(data)} rijen geexporteerd naar {filename}")
        return df

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return None

def main():
    """Hoofdfunctie - exporteert alle rapporten."""

    print("=" * 60)
    print("GA4 HISTORICAL DATA EXPORT")
    print("=" * 60)

    # Parse credentials
    try:
        credentials_info = json.loads(CREDENTIALS_JSON)
        credentials = service_account.Credentials.from_service_account_info(
            credentials_info,
            scopes=['https://www.googleapis.com/auth/analytics.readonly']
        )
        print(f"Service account: {credentials_info.get('client_email', 'unknown')}")
    except json.JSONDecodeError:
        print("ERROR: Plak eerst de GA4_SERVICE_ACCOUNT_JSON in dit script (regel 9)")
        return

    # Maak client
    client = BetaAnalyticsDataClient(credentials=credentials)
    print(f"Property ID: {GA4_PROPERTY_ID}")
    print(f"Periode: Laatste 90 dagen")

    # Rapporten om te exporteren
    reports = {
        'page_views': {
            'dimensions': ['date', 'pagePath', 'pageTitle'],
            'metrics': ['screenPageViews', 'activeUsers', 'averageSessionDuration']
        },
        'traffic_sources': {
            'dimensions': ['date', 'sessionSource', 'sessionMedium', 'sessionCampaignName'],
            'metrics': ['sessions', 'activeUsers', 'newUsers']
        },
        'user_demographics': {
            'dimensions': ['date', 'city', 'country', 'deviceCategory'],
            'metrics': ['activeUsers', 'sessions']
        },
        'high_intent_pages': {
            'dimensions': ['date', 'pagePath'],
            'metrics': ['screenPageViews', 'activeUsers']
        }
    }

    # Exporteer elk rapport
    results = {}
    for report_name, config in reports.items():
        df = export_ga4_report(
            client,
            GA4_PROPERTY_ID,
            report_name,
            config['dimensions'],
            config['metrics']
        )
        if df is not None:
            results[report_name] = df

    # Summary
    print("\n" + "=" * 60)
    print("EXPORT SUMMARY")
    print("=" * 60)
    if results:
        for name, df in results.items():
            print(f"{name}: {len(df)} rijen")
        print(f"\nTotaal: {len(results)} rapporten geexporteerd")
    else:
        print("Geen data geexporteerd - check permissies!")
        print("\nOplossing:")
        print("1. Ga naar GA4 property settings")
        print("2. Voeg service account toe met 'Viewer' role:")
        print(f"   {credentials_info.get('client_email', 'unknown')}")

if __name__ == "__main__":
    main()
