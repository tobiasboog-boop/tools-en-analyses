"""Google Analytics 4 BigQuery Integration."""
import os
from google.cloud import bigquery
from google.oauth2 import service_account
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# BigQuery settings
PROJECT_ID = os.getenv('GA4_BIGQUERY_PROJECT_ID')
DATASET_ID = os.getenv('GA4_BIGQUERY_DATASET', 'analytics_273791186')
CREDENTIALS_PATH = os.getenv('GA4_BIGQUERY_CREDENTIALS')


class GA4BigQuery:
    """Google Analytics 4 BigQuery client."""

    def __init__(self):
        """Initialize BigQuery client with service account credentials."""
        if not CREDENTIALS_PATH or not os.path.exists(CREDENTIALS_PATH):
            raise ValueError(f"GA4 BigQuery credentials not found at: {CREDENTIALS_PATH}")

        credentials = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH,
            scopes=["https://www.googleapis.com/auth/bigquery.readonly"],
        )

        self.client = bigquery.Client(
            credentials=credentials,
            project=PROJECT_ID
        )
        self.dataset_id = DATASET_ID

    def _query(self, sql: str) -> List[Dict]:
        """Execute BigQuery SQL and return results as list of dicts."""
        query_job = self.client.query(sql)
        results = query_job.result()

        rows = []
        for row in results:
            rows.append(dict(row))

        return rows

    def get_user_sessions(self, days: int = 30, min_sessions: int = 1) -> List[Dict]:
        """Get users with their session counts and last activity.

        Args:
            days: Number of days to look back
            min_sessions: Minimum sessions required

        Returns:
            List of dicts with user_id, email, sessions, events, last_activity
        """
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
        end_date = datetime.now().strftime('%Y%m%d')

        sql = f"""
        SELECT
          user_pseudo_id,
          (SELECT value.string_value FROM UNNEST(user_properties) WHERE key = 'email') AS email,
          COUNT(DISTINCT CONCAT(
            user_pseudo_id,
            CAST((SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS STRING)
          )) as sessions,
          COUNT(*) as events,
          MAX(TIMESTAMP_MICROS(event_timestamp)) as last_activity
        FROM
          `{PROJECT_ID}.{self.dataset_id}.events_*`
        WHERE
          _TABLE_SUFFIX BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY
          user_pseudo_id, email
        HAVING
          sessions >= {min_sessions}
        ORDER BY
          sessions DESC
        """

        return self._query(sql)

    def get_high_intent_users(self, days: int = 30) -> List[Dict]:
        """Get users who visited high-intent pages (pricing, contact, demo).

        Args:
            days: Number of days to look back

        Returns:
            List of dicts with email, intent scores, total events
        """
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
        end_date = datetime.now().strftime('%Y%m%d')

        sql = f"""
        SELECT
          (SELECT value.string_value FROM UNNEST(user_properties) WHERE key = 'email') AS email,
          COUNTIF(event_name = 'page_view' AND
            LOWER((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'))
            LIKE '%prijzen%') as pricing_views,
          COUNTIF(event_name = 'page_view' AND
            LOWER((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'))
            LIKE '%contact%') as contact_views,
          COUNTIF(event_name = 'page_view' AND
            LOWER((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'))
            LIKE '%demo%') as demo_views,
          COUNTIF(event_name = 'page_view' AND
            LOWER((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'))
            LIKE '%offerte%') as quote_views,
          COUNT(*) as total_events,
          MAX(TIMESTAMP_MICROS(event_timestamp)) as last_activity
        FROM
          `{PROJECT_ID}.{self.dataset_id}.events_*`
        WHERE
          _TABLE_SUFFIX BETWEEN '{start_date}' AND '{end_date}'
        GROUP BY
          email
        HAVING
          email IS NOT NULL
          AND (pricing_views > 0 OR contact_views > 0 OR demo_views > 0 OR quote_views > 0)
        ORDER BY
          (pricing_views * 3 + contact_views * 5 + demo_views * 10 + quote_views * 8) DESC
        """

        return self._query(sql)

    def get_top_pages(self, days: int = 30, limit: int = 20) -> List[Dict]:
        """Get most viewed pages.

        Args:
            days: Number of days to look back
            limit: Maximum number of results

        Returns:
            List of dicts with page_url, page_views, unique_users
        """
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
        end_date = datetime.now().strftime('%Y%m%d')

        sql = f"""
        SELECT
          (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') AS page_url,
          COUNT(*) as page_views,
          COUNT(DISTINCT user_pseudo_id) as unique_users
        FROM
          `{PROJECT_ID}.{self.dataset_id}.events_*`
        WHERE
          _TABLE_SUFFIX BETWEEN '{start_date}' AND '{end_date}'
          AND event_name = 'page_view'
        GROUP BY
          page_url
        ORDER BY
          page_views DESC
        LIMIT {limit}
        """

        return self._query(sql)

    def get_engagement_score(self, email: str, days: int = 30) -> Dict:
        """Calculate website engagement score for email address.

        Scoring:
        - High-intent pages (pricing, contact, demo): 0-30 points
        - Session count: 0-15 points
        - Recent activity (< 7 days): 0-10 points
        - Total: 0-55 points (scaled to 0-40 for lead scoring)

        Args:
            email: Email address to score
            days: Number of days to look back

        Returns:
            Dict with engagement_score, sessions, events, last_activity
        """
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
        end_date = datetime.now().strftime('%Y%m%d')

        sql = f"""
        SELECT
          COUNT(DISTINCT CONCAT(
            user_pseudo_id,
            CAST((SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS STRING)
          )) as sessions,
          COUNT(*) as events,
          MAX(TIMESTAMP_MICROS(event_timestamp)) as last_activity,
          COUNTIF(event_name = 'page_view' AND
            LOWER((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'))
            LIKE '%prijzen%') as pricing_views,
          COUNTIF(event_name = 'page_view' AND
            LOWER((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'))
            LIKE '%contact%') as contact_views,
          COUNTIF(event_name = 'page_view' AND
            LOWER((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'))
            LIKE '%demo%') as demo_views,
          COUNTIF(event_name = 'page_view' AND
            LOWER((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location'))
            LIKE '%offerte%') as quote_views
        FROM
          `{PROJECT_ID}.{self.dataset_id}.events_*`
        WHERE
          _TABLE_SUFFIX BETWEEN '{start_date}' AND '{end_date}'
          AND (SELECT value.string_value FROM UNNEST(user_properties) WHERE key = 'email') = '{email}'
        """

        results = self._query(sql)

        if not results or results[0]['sessions'] == 0:
            return {
                'found': False,
                'engagement_score': 0,
                'sessions': 0,
                'events': 0,
                'last_activity': None,
                'intent_score': 0
            }

        data = results[0]

        # Calculate intent score (0-30 points)
        intent_score = 0
        intent_score += min(data['pricing_views'] * 3, 10)  # Max 10 pts
        intent_score += min(data['contact_views'] * 5, 10)  # Max 10 pts
        intent_score += min(data['demo_views'] * 10, 10)    # Max 10 pts
        intent_score += min(data['quote_views'] * 8, 10)    # Max 10 pts
        intent_score = min(intent_score, 30)

        # Session score (0-15 points)
        session_score = min(data['sessions'] * 3, 15)

        # Recency score (0-10 points)
        recency_score = 0
        if data['last_activity']:
            days_ago = (datetime.now(data['last_activity'].tzinfo) - data['last_activity']).days
            if days_ago <= 7:
                recency_score = 10
            elif days_ago <= 14:
                recency_score = 5
            elif days_ago <= 30:
                recency_score = 3

        # Total score (0-55), scaled to 0-40
        raw_score = intent_score + session_score + recency_score
        scaled_score = int(raw_score * 40 / 55)

        return {
            'found': True,
            'engagement_score': scaled_score,
            'sessions': data['sessions'],
            'events': data['events'],
            'last_activity': data['last_activity'],
            'intent_score': intent_score,
            'session_score': session_score,
            'recency_score': recency_score,
            'pricing_views': data['pricing_views'],
            'contact_views': data['contact_views'],
            'demo_views': data['demo_views'],
            'quote_views': data['quote_views']
        }


if __name__ == '__main__':
    """Test GA4 BigQuery connection."""
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    print("\n" + "="*70)
    print("  GA4 BIGQUERY CONNECTION TEST")
    print("="*70 + "\n")

    try:
        ga4 = GA4BigQuery()
        print("[OK] Connected to BigQuery!")
        print(f"     Project: {PROJECT_ID}")
        print(f"     Dataset: {ga4.dataset_id}")

        # Test 1: Top pages
        print("\n[1/3] Testing top pages query...")
        pages = ga4.get_top_pages(days=30, limit=5)
        print(f"        Found {len(pages)} pages")

        if pages:
            print("\n        Top 5 pages:")
            for i, page in enumerate(pages[:5], 1):
                url = page['page_url'][:50] if page['page_url'] else 'N/A'
                print(f"        {i}. {url} ({page['page_views']} views)")

        # Test 2: High-intent users
        print("\n[2/3] Testing high-intent users query...")
        users = ga4.get_high_intent_users(days=30)
        print(f"        Found {len(users)} high-intent users")

        if users:
            print("\n        Top 5 high-intent users:")
            for i, user in enumerate(users[:5], 1):
                email = user['email'][:30] if user['email'] else 'N/A'
                print(f"        {i}. {email} (pricing:{user['pricing_views']} contact:{user['contact_views']} demo:{user['demo_views']})")

        # Test 3: User sessions
        print("\n[3/3] Testing user sessions query...")
        sessions = ga4.get_user_sessions(days=30, min_sessions=2)
        print(f"        Found {len(sessions)} users with 2+ sessions")

        print("\n" + "="*70)
        print("  CONNECTION SUCCESSFUL!")
        print("="*70 + "\n")

        print("Ready to integrate into lead scoring!")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        print("\nSetup checklist:")
        print("  1. Activeer BigQuery export in GA4 (wacht 24u)")
        print("  2. Maak service account in Google Cloud")
        print("  3. Download JSON key")
        print("  4. Update .env met credentials")
        print()
