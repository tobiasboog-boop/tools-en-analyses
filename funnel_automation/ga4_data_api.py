"""Google Analytics 4 Data API - Lead Scoring Integration.

Werkt met "Viewer" toegang - geen admin/BigQuery nodig!
"""
import os
import json
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    Dimension,
    Metric,
    DateRange,
    FilterExpression,
    Filter,
    FilterExpressionList
)
from google.oauth2 import service_account
from typing import Dict, List, Optional
from datetime import datetime, timedelta

# Try Streamlit secrets first (for Cloud), fallback to .env (for local)
try:
    import streamlit as st
    GA4_PROPERTY_ID = st.secrets["GA4_PROPERTY_ID"]
    GA4_SERVICE_ACCOUNT_JSON = st.secrets.get("GA4_SERVICE_ACCOUNT_JSON")
    GA4_CREDENTIALS_PATH = None
except (ImportError, KeyError, FileNotFoundError):
    from dotenv import load_dotenv
    load_dotenv()
    GA4_PROPERTY_ID = os.getenv('GA4_PROPERTY_ID', '273791186')
    GA4_CREDENTIALS_PATH = os.getenv('GA4_CREDENTIALS_PATH')
    GA4_SERVICE_ACCOUNT_JSON = None


class GA4DataAPI:
    """Google Analytics 4 Data API client for lead scoring."""

    def __init__(self):
        """Initialize GA4 Data API client."""
        # Option 1: Load from Streamlit secrets (JSON string)
        if GA4_SERVICE_ACCOUNT_JSON:
            credentials_info = json.loads(GA4_SERVICE_ACCOUNT_JSON)
            credentials = service_account.Credentials.from_service_account_info(
                credentials_info,
                scopes=['https://www.googleapis.com/auth/analytics.readonly']
            )
        # Option 2: Load from file (local development)
        else:
            if not GA4_CREDENTIALS_PATH or not os.path.exists(GA4_CREDENTIALS_PATH):
                # Try default location
                default_path = os.path.join(
                    os.path.dirname(__file__),
                    'ga4-service-account.json'
                )
                if os.path.exists(default_path):
                    credentials_path = default_path
                else:
                    raise ValueError(
                        f"GA4 credentials not found. Set GA4_CREDENTIALS_PATH in .env or place "
                        f"'ga4-service-account.json' in {os.path.dirname(__file__)}"
                    )
            else:
                credentials_path = GA4_CREDENTIALS_PATH

            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/analytics.readonly']
            )

        self.client = BetaAnalyticsDataClient(credentials=credentials)
        self.property_id = f"properties/{GA4_PROPERTY_ID}"

    def get_user_sessions(self, days: int = 30) -> List[Dict]:
        """Get user sessions with page views.

        Returns list of users with their session count, page views, and events.
        """
        request = RunReportRequest(
            property=self.property_id,
            date_ranges=[DateRange(
                start_date=f"{days}daysAgo",
                end_date="today"
            )],
            dimensions=[
                Dimension(name="customUser:email"),  # Requires User-ID setup
            ],
            metrics=[
                Metric(name="sessions"),
                Metric(name="screenPageViews"),
                Metric(name="eventCount"),
                Metric(name="engagementRate"),
            ],
        )

        try:
            response = self.client.run_report(request)
            users = []

            for row in response.rows:
                email = row.dimension_values[0].value
                if not email or email == "(not set)":
                    continue

                users.append({
                    'email': email,
                    'sessions': int(row.metric_values[0].value),
                    'page_views': int(row.metric_values[1].value),
                    'events': int(row.metric_values[2].value),
                    'engagement_rate': float(row.metric_values[3].value),
                })

            return users
        except Exception as e:
            print(f"Warning: Could not fetch user sessions: {e}")
            return []

    def get_high_intent_pages(self, days: int = 30) -> List[Dict]:
        """Get page views for high-intent pages (pricing, contact, demo).

        Returns list with page paths and view counts.
        """
        request = RunReportRequest(
            property=self.property_id,
            date_ranges=[DateRange(
                start_date=f"{days}daysAgo",
                end_date="today"
            )],
            dimensions=[
                Dimension(name="pagePath"),
            ],
            metrics=[
                Metric(name="screenPageViews"),
                Metric(name="activeUsers"),
            ],
            dimension_filter=FilterExpression(
                or_group=FilterExpressionList(
                    expressions=[
                        FilterExpression(
                            filter=Filter(
                                field_name="pagePath",
                                string_filter=Filter.StringFilter(
                                    match_type=Filter.StringFilter.MatchType.CONTAINS,
                                    value="prijzen"
                                )
                            )
                        ),
                        FilterExpression(
                            filter=Filter(
                                field_name="pagePath",
                                string_filter=Filter.StringFilter(
                                    match_type=Filter.StringFilter.MatchType.CONTAINS,
                                    value="contact"
                                )
                            )
                        ),
                        FilterExpression(
                            filter=Filter(
                                field_name="pagePath",
                                string_filter=Filter.StringFilter(
                                    match_type=Filter.StringFilter.MatchType.CONTAINS,
                                    value="demo"
                                )
                            )
                        ),
                        FilterExpression(
                            filter=Filter(
                                field_name="pagePath",
                                string_filter=Filter.StringFilter(
                                    match_type=Filter.StringFilter.MatchType.CONTAINS,
                                    value="offerte"
                                )
                            )
                        ),
                    ]
                )
            ),
            order_bys=[
                {"metric": {"metric_name": "screenPageViews"}, "desc": True}
            ],
            limit=50
        )

        try:
            response = self.client.run_report(request)
            pages = []

            for row in response.rows:
                page_path = row.dimension_values[0].value
                page_views = int(row.metric_values[0].value)
                users = int(row.metric_values[1].value)

                # Categorize intent
                intent_type = "other"
                if "prijzen" in page_path.lower():
                    intent_type = "pricing"
                elif "contact" in page_path.lower():
                    intent_type = "contact"
                elif "demo" in page_path.lower():
                    intent_type = "demo"
                elif "offerte" in page_path.lower():
                    intent_type = "quote"

                pages.append({
                    'page_path': page_path,
                    'page_views': page_views,
                    'users': users,
                    'intent_type': intent_type
                })

            return pages
        except Exception as e:
            print(f"Warning: Could not fetch high-intent pages: {e}")
            return []

    def get_engagement_score(self, email: str, days: int = 30) -> Dict:
        """Calculate website engagement score for email address.

        Scoring (0-40 points):
        - Sessions: 0-15 points (3 pts per session, max 15)
        - High-intent pages: 0-20 points (pricing, contact, demo, offerte)
        - Recent activity: 0-5 points (visited in last 7 days)

        Args:
            email: Email address to score
            days: Number of days to look back

        Returns:
            Dict with engagement_score and metrics
        """
        # Get user metrics
        request = RunReportRequest(
            property=self.property_id,
            date_ranges=[DateRange(
                start_date=f"{days}daysAgo",
                end_date="today"
            )],
            dimensions=[
                Dimension(name="customUser:email"),
                Dimension(name="date"),
            ],
            metrics=[
                Metric(name="sessions"),
                Metric(name="screenPageViews"),
            ],
            dimension_filter=FilterExpression(
                filter=Filter(
                    field_name="customUser:email",
                    string_filter=Filter.StringFilter(
                        match_type=Filter.StringFilter.MatchType.EXACT,
                        value=email
                    )
                )
            ),
        )

        try:
            response = self.client.run_report(request)

            if not response.rows:
                return {
                    'found': False,
                    'engagement_score': 0,
                    'sessions': 0,
                    'page_views': 0,
                    'last_visit_days_ago': None
                }

            # Aggregate metrics
            total_sessions = 0
            total_page_views = 0
            most_recent_date = None

            for row in response.rows:
                date_str = row.dimension_values[1].value
                sessions = int(row.metric_values[0].value)
                page_views = int(row.metric_values[1].value)

                total_sessions += sessions
                total_page_views += page_views

                # Track most recent visit
                visit_date = datetime.strptime(date_str, "%Y%m%d")
                if most_recent_date is None or visit_date > most_recent_date:
                    most_recent_date = visit_date

            # Calculate days since last visit
            days_ago = (datetime.now() - most_recent_date).days if most_recent_date else None

            # Calculate scores
            session_score = min(total_sessions * 3, 15)  # 3 pts per session, max 15

            # Recency score (0-5 points)
            recency_score = 0
            if days_ago is not None:
                if days_ago <= 7:
                    recency_score = 5
                elif days_ago <= 14:
                    recency_score = 3
                elif days_ago <= 30:
                    recency_score = 1

            # Get high-intent page views for this user
            intent_request = RunReportRequest(
                property=self.property_id,
                date_ranges=[DateRange(
                    start_date=f"{days}daysAgo",
                    end_date="today"
                )],
                dimensions=[
                    Dimension(name="customUser:email"),
                    Dimension(name="pagePath"),
                ],
                metrics=[
                    Metric(name="screenPageViews"),
                ],
                dimension_filter=FilterExpression(
                    and_group=FilterExpressionList(
                        expressions=[
                            FilterExpression(
                                filter=Filter(
                                    field_name="customUser:email",
                                    string_filter=Filter.StringFilter(
                                        match_type=Filter.StringFilter.MatchType.EXACT,
                                        value=email
                                    )
                                )
                            ),
                            FilterExpression(
                                or_group=FilterExpressionList(
                                    expressions=[
                                        FilterExpression(
                                            filter=Filter(
                                                field_name="pagePath",
                                                string_filter=Filter.StringFilter(
                                                    match_type=Filter.StringFilter.MatchType.CONTAINS,
                                                    value="prijzen"
                                                )
                                            )
                                        ),
                                        FilterExpression(
                                            filter=Filter(
                                                field_name="pagePath",
                                                string_filter=Filter.StringFilter(
                                                    match_type=Filter.StringFilter.MatchType.CONTAINS,
                                                    value="contact"
                                                )
                                            )
                                        ),
                                        FilterExpression(
                                            filter=Filter(
                                                field_name="pagePath",
                                                string_filter=Filter.StringFilter(
                                                    match_type=Filter.StringFilter.MatchType.CONTAINS,
                                                    value="demo"
                                                )
                                            )
                                        ),
                                        FilterExpression(
                                            filter=Filter(
                                                field_name="pagePath",
                                                string_filter=Filter.StringFilter(
                                                    match_type=Filter.StringFilter.MatchType.CONTAINS,
                                                    value="offerte"
                                                )
                                            )
                                        ),
                                    ]
                                )
                            )
                        ]
                    )
                ),
            )

            intent_response = self.client.run_report(intent_request)

            # Count intent pages
            pricing_views = 0
            contact_views = 0
            demo_views = 0
            quote_views = 0

            for row in intent_response.rows:
                page_path = row.dimension_values[1].value.lower()
                views = int(row.metric_values[0].value)

                if "prijzen" in page_path:
                    pricing_views += views
                elif "contact" in page_path:
                    contact_views += views
                elif "demo" in page_path:
                    demo_views += views
                elif "offerte" in page_path:
                    quote_views += views

            # Intent score (0-20 points)
            intent_score = 0
            intent_score += min(pricing_views * 3, 5)   # Max 5 pts
            intent_score += min(contact_views * 5, 8)   # Max 8 pts
            intent_score += min(demo_views * 8, 8)      # Max 8 pts
            intent_score += min(quote_views * 6, 6)     # Max 6 pts
            intent_score = min(intent_score, 20)

            # Total score
            total_score = session_score + recency_score + intent_score

            return {
                'found': True,
                'engagement_score': total_score,
                'sessions': total_sessions,
                'page_views': total_page_views,
                'last_visit_days_ago': days_ago,
                'session_score': session_score,
                'recency_score': recency_score,
                'intent_score': intent_score,
                'pricing_views': pricing_views,
                'contact_views': contact_views,
                'demo_views': demo_views,
                'quote_views': quote_views
            }

        except Exception as e:
            print(f"Warning: Could not calculate engagement for {email}: {e}")
            return {
                'found': False,
                'engagement_score': 0,
                'sessions': 0,
                'page_views': 0,
                'error': str(e)
            }


if __name__ == '__main__':
    """Test GA4 Data API connection."""
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    print("\n" + "="*70)
    print("  GA4 DATA API CONNECTION TEST")
    print("="*70 + "\n")

    try:
        ga4 = GA4DataAPI()
        print("[OK] Connected to GA4 Data API!")
        print(f"     Property ID: {GA4_PROPERTY_ID}")

        # Test 1: High-intent pages
        print("\n[1/3] Testing high-intent pages (30 days)...")
        pages = ga4.get_high_intent_pages(days=30)
        print(f"        Found {len(pages)} high-intent pages")

        if pages:
            print("\n        Top 5 high-intent pages:")
            for i, page in enumerate(pages[:5], 1):
                print(f"        {i}. {page['intent_type']:8s} {page['page_path'][:40]:40s} ({page['page_views']} views)")

        # Test 2: User sessions
        print("\n[2/3] Testing user sessions...")
        users = ga4.get_user_sessions(days=30)
        print(f"        Found {len(users)} users with email")

        if users:
            print("\n        Top 5 active users:")
            for i, user in enumerate(users[:5], 1):
                print(f"        {i}. {user['email'][:35]:35s} {user['sessions']} sessions, {user['page_views']} views")

        # Test 3: Engagement score for sample user
        if users:
            print("\n[3/3] Testing engagement score...")
            sample_email = users[0]['email']
            print(f"        Calculating score for: {sample_email}")

            score = ga4.get_engagement_score(sample_email, days=30)

            if score['found']:
                print(f"\n        Engagement Score: {score['engagement_score']}/40")
                print(f"        Sessions: {score['sessions']} ({score['session_score']} pts)")
                print(f"        Intent: {score['intent_score']} pts (pricing:{score['pricing_views']} contact:{score['contact_views']} demo:{score['demo_views']})")
                print(f"        Recency: {score['recency_score']} pts (last visit: {score['last_visit_days_ago']} days ago)")

        print("\n" + "="*70)
        print("  CONNECTION SUCCESSFUL!")
        print("="*70 + "\n")

        print("Ready to integrate into lead scoring!")
        print()

        print("NOTE: This requires User-ID tracking in GA4.")
        print("      If no users found, check GA4 User-ID implementation.")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        print("\nSetup checklist:")
        print("  1. Zorg dat je Viewer toegang hebt op GA4 property 273791186")
        print("  2. Download service account JSON (of gebruik bestaande)")
        print("  3. Update .env: GA4_CREDENTIALS_PATH=path/to/json")
        print("  4. Implementeer User-ID tracking op website (om emails te koppelen)")
        print()
