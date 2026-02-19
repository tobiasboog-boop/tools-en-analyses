"""Export historische GA4 data voordat we overstappen naar nieuwe property"""
import json
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, Dimension, Metric, DateRange
from google.oauth2 import service_account
import csv
from datetime import datetime

# Load credentials
with open('c:/projects/tools_en_analyses/funnel_automation/ga4-service-account.json', 'r') as f:
    credentials_info = json.load(f)

credentials = service_account.Credentials.from_service_account_info(
    credentials_info,
    scopes=['https://www.googleapis.com/auth/analytics.readonly']
)

client = BetaAnalyticsDataClient(credentials=credentials)
property_id = "273791186"

print("Exporteren van historische GA4 data (laatste 90 dagen)...")

# Export verschillende reports
reports = {
    'page_views': {
        'dimensions': ['date', 'pagePath', 'pageTitle'],
        'metrics': ['screenPageViews', 'activeUsers']
    },
    'traffic_sources': {
        'dimensions': ['date', 'sessionSource', 'sessionMedium'],
        'metrics': ['sessions', 'activeUsers']
    },
    'user_demographics': {
        'dimensions': ['date', 'city', 'country'],
        'metrics': ['activeUsers', 'newUsers']
    }
}

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

for report_name, config in reports.items():
    print(f"\nExporteren: {report_name}...")
    
    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[Dimension(name=d) for d in config['dimensions']],
        metrics=[Metric(name=m) for m in config['metrics']],
        date_ranges=[DateRange(start_date="90daysAgo", end_date="today")],
    )
    
    try:
        response = client.run_report(request)
        
        # Write to CSV
        filename = f"c:/projects/tools_en_analyses/lead-dashboard/ga4_export_{report_name}_{timestamp}.csv"
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Header
            headers = config['dimensions'] + config['metrics']
            writer.writerow(headers)
            
            # Data
            for row in response.rows:
                data = []
                for dim in row.dimension_values:
                    data.append(dim.value)
                for metric in row.metric_values:
                    data.append(metric.value)
                writer.writerow(data)
        
        print(f"   OK - {len(response.rows)} rijen -> {filename}")
        
    except Exception as e:
        print(f"   ERROR: {e}")

print("\nExport compleet!")
print(f"Bestanden opgeslagen in: c:/projects/tools_en_analyses/lead-dashboard/")
