"""Google Analytics 4 API wrapper voor website gedrag tracking."""
import sys
import io
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from google.oauth2 import service_account
from pathlib import Path
from utils.config import GA4_PROPERTY_ID, GA4_SERVICE_ACCOUNT_JSON

# Fix voor Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


class GA4API:
    """Wrapper voor Google Analytics 4 Data API calls."""

    def __init__(self):
        self.property_id = f"properties/{GA4_PROPERTY_ID}"

        # Service account credentials laden
        credentials_path = Path(__file__).parent / GA4_SERVICE_ACCOUNT_JSON
        self.credentials = service_account.Credentials.from_service_account_file(
            str(credentials_path),
            scopes=['https://www.googleapis.com/auth/analytics.readonly']
        )

        self.client = BetaAnalyticsDataClient(credentials=self.credentials)

    def run_report(
        self,
        dimensions: List[str],
        metrics: List[str],
        start_date: str = "30daysAgo",
        end_date: str = "today",
        dimension_filter: Optional[Dict] = None,
        limit: int = 10000
    ) -> List[Dict]:
        """Generieke functie om GA4 report op te halen.

        Args:
            dimensions: Lijst van dimensies (bijv. ['pagePath', 'date'])
            metrics: Lijst van metrics (bijv. ['activeUsers', 'sessions'])
            start_date: Start datum (bijv. '30daysAgo', '2024-01-01')
            end_date: End datum (bijv. 'today', '2024-01-31')
            dimension_filter: Optionele filter
            limit: Max aantal rijen
        """
        request = RunReportRequest(
            property=self.property_id,
            dimensions=[Dimension(name=dim) for dim in dimensions],
            metrics=[Metric(name=metric) for metric in metrics],
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            limit=limit
        )

        response = self.client.run_report(request)

        # Parse response naar list of dicts
        results = []
        for row in response.rows:
            result = {}

            # Dimensies
            for i, dimension in enumerate(dimensions):
                result[dimension] = row.dimension_values[i].value

            # Metrics
            for i, metric in enumerate(metrics):
                result[metric] = row.metric_values[i].value

            results.append(result)

        return results

    # === USER BEHAVIOR QUERIES ===

    def get_page_views_by_page(self, days: int = 30) -> List[Dict]:
        """Haal page views per pagina op."""
        start_date = f"{days}daysAgo"

        return self.run_report(
            dimensions=['pagePath', 'pageTitle'],
            metrics=['screenPageViews', 'averageSessionDuration'],
            start_date=start_date
        )

    def get_user_engagement(self, days: int = 30) -> List[Dict]:
        """Haal user engagement metrics op."""
        start_date = f"{days}daysAgo"

        return self.run_report(
            dimensions=['date'],
            metrics=[
                'activeUsers',
                'sessions',
                'averageSessionDuration',
                'bounceRate',
                'engagementRate'
            ],
            start_date=start_date
        )

    def get_traffic_sources(self, days: int = 30) -> List[Dict]:
        """Haal traffic sources op (hoe komen bezoekers?)."""
        start_date = f"{days}daysAgo"

        return self.run_report(
            dimensions=['sessionSource', 'sessionMedium', 'sessionCampaignName'],
            metrics=['sessions', 'activeUsers'],
            start_date=start_date
        )

    def get_conversions(self, days: int = 30) -> List[Dict]:
        """Haal conversie events op."""
        start_date = f"{days}daysAgo"

        return self.run_report(
            dimensions=['eventName'],
            metrics=['eventCount', 'conversions'],
            start_date=start_date
        )

    def get_top_pages(self, days: int = 7, limit: int = 20) -> List[Dict]:
        """Haal meest bekeken pagina's op."""
        start_date = f"{days}daysAgo"

        results = self.run_report(
            dimensions=['pagePath', 'pageTitle'],
            metrics=['screenPageViews', 'activeUsers'],
            start_date=start_date,
            limit=limit
        )

        # Sorteer op page views (descending)
        results.sort(key=lambda x: int(x['screenPageViews']), reverse=True)
        return results

    # === LEAD SCORING HELPERS ===

    def get_user_sessions_summary(self, days: int = 30) -> Dict:
        """Haal totaal overzicht van sessies op voor lead scoring.

        Returns summary met:
        - Totaal aantal sessies
        - Gemiddelde sessie duur
        - Bounce rate
        - Engagement rate
        """
        data = self.run_report(
            dimensions=['date'],
            metrics=[
                'sessions',
                'activeUsers',
                'averageSessionDuration',
                'bounceRate',
                'engagementRate'
            ],
            start_date=f"{days}daysAgo"
        )

        # Aggregeer totalen
        total_sessions = sum(int(row['sessions']) for row in data)
        total_users = sum(int(row['activeUsers']) for row in data)
        avg_duration = sum(float(row['averageSessionDuration']) for row in data) / len(data) if data else 0
        avg_bounce = sum(float(row['bounceRate']) for row in data) / len(data) if data else 0
        avg_engagement = sum(float(row['engagementRate']) for row in data) / len(data) if data else 0

        return {
            'total_sessions': total_sessions,
            'total_users': total_users,
            'avg_session_duration': avg_duration,
            'avg_bounce_rate': avg_bounce,
            'avg_engagement_rate': avg_engagement,
            'period_days': days
        }

    def get_high_intent_pages_views(self, days: int = 7) -> List[Dict]:
        """Haal views van high-intent pagina's op (pricing, contact, demo, etc).

        Deze pagina's wijzen op koopintentie.
        """
        # Pagina's die wijzen op koopintentie
        high_intent_keywords = [
            'pricing', 'prijs', 'tarif', 'contact', 'demo', 'aanmeld',
            'offerte', 'afspraak', 'trial', 'kopen', 'bestellen'
        ]

        all_pages = self.get_page_views_by_page(days=days)

        # Filter op high-intent pages
        high_intent_pages = [
            page for page in all_pages
            if any(keyword in page['pagePath'].lower() or keyword in page['pageTitle'].lower()
                   for keyword in high_intent_keywords)
        ]

        return high_intent_pages


def test_connection():
    """Test GA4 API connectie."""
    try:
        api = GA4API()

        print("✅ GA4 API connectie succesvol!")
        print(f"📊 Property ID: {GA4_PROPERTY_ID}")

        # Test 1: Haal laatste 7 dagen sessies op
        print("\n📈 Test 1: Laatste 7 dagen user engagement...")
        summary = api.get_user_sessions_summary(days=7)
        print(f"  - Totaal sessies: {summary['total_sessions']}")
        print(f"  - Totaal users: {summary['total_users']}")
        print(f"  - Gem. sessie duur: {summary['avg_session_duration']:.1f} seconden")
        print(f"  - Engagement rate: {summary['avg_engagement_rate']:.1%}")

        # Test 2: Top 5 pagina's
        print("\n🔥 Test 2: Top 5 meest bekeken pagina's...")
        top_pages = api.get_top_pages(days=7, limit=5)
        for i, page in enumerate(top_pages[:5], 1):
            print(f"  {i}. {page['pageTitle'][:50]} - {page['screenPageViews']} views")

        # Test 3: High-intent pagina's
        print("\n🎯 Test 3: High-intent pagina views (laatste 7 dagen)...")
        high_intent = api.get_high_intent_pages_views(days=7)
        if high_intent:
            print(f"  - {len(high_intent)} high-intent pagina's bezocht")
            for page in high_intent[:3]:
                print(f"    • {page['pageTitle'][:40]} - {page['screenPageViews']} views")
        else:
            print("  ℹ️  Geen high-intent pagina's gevonden")

        # Test 4: Traffic sources
        print("\n🌐 Test 4: Traffic sources...")
        sources = api.get_traffic_sources(days=7)
        source_summary = {}
        for row in sources:
            source = row['sessionSource']
            count = int(row['sessions'])
            source_summary[source] = source_summary.get(source, 0) + count

        for source, count in sorted(source_summary.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  - {source}: {count} sessies")

        return True

    except FileNotFoundError:
        print("❌ Service account JSON bestand niet gevonden!")
        print(f"   Verwacht locatie: {Path(__file__).parent / GA4_SERVICE_ACCOUNT_JSON}")
        print("\n📝 Voltooi eerst deze stappen:")
        print("   1. Download service account JSON van Google Cloud Console")
        print("   2. Zet het bestand in: c:/projects/tools_en_analyses/funnel_automation/service-account.json")
        print("   3. Geef de service account 'Viewer' toegang in Google Analytics")
        return False
    except Exception as e:
        print(f"❌ Fout bij verbinden met GA4: {e}")
        print("\n🔍 Mogelijke oorzaken:")
        print("   - Service account heeft geen toegang tot GA4 property")
        print("   - Verkeerd property ID")
        print("   - API nog niet geactiveerd in Google Cloud Console")
        return False


if __name__ == "__main__":
    print("🔌 Test Google Analytics 4 API connectie...\n")
    test_connection()
