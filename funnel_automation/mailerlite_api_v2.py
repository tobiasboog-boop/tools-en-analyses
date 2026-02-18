"""MailerLite API v2 - Werkende versie met subscribers en campaigns."""
import os
import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta

# Try Streamlit secrets first (for Cloud deployment), fallback to .env (for local)
try:
    import streamlit as st
    MAILERLITE_API_TOKEN = st.secrets["MAILERLITE_API_TOKEN"]
except (ImportError, KeyError, FileNotFoundError):
    from dotenv import load_dotenv
    load_dotenv()
    MAILERLITE_API_TOKEN = os.getenv('MAILERLITE_API_TOKEN')

MAIN_GROUP_ID = 177296943307818341  # Actieve inschrijvingen

class MailerLiteAPI:
    """MailerLite API v2 client - werkende versie."""

    def __init__(self):
        self.api_token = MAILERLITE_API_TOKEN
        self.base_url = "https://api.mailerlite.com/api/v2"
        self.headers = {
            'X-MailerLite-ApiKey': self.api_token,
            'Content-Type': 'application/json'
        }
        self._subscribers_cache = {}
        self._campaigns_cache = None

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make GET request to MailerLite API."""
        url = f"{self.base_url}/{endpoint}"
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def get_all_subscribers(self, limit: int = 1000) -> List[Dict]:
        """Get all subscribers from main group (paginated)."""
        all_subscribers = []
        offset = 0
        batch_size = 100

        while len(all_subscribers) < limit:
            subscribers = self._get(
                f"groups/{MAIN_GROUP_ID}/subscribers",
                {"limit": batch_size, "offset": offset}
            )

            if not subscribers:
                break

            all_subscribers.extend(subscribers)
            offset += batch_size

            if len(subscribers) < batch_size:
                break  # Last page

        return all_subscribers

    def get_subscriber_by_email(self, email: str) -> Optional[Dict]:
        """Get subscriber data by email (with caching)."""
        if email in self._subscribers_cache:
            return self._subscribers_cache[email]

        # If not in cache, try API lookup
        try:
            subscriber = self._get(f"subscribers/{email}")
            self._subscribers_cache[email] = subscriber
            return subscriber
        except requests.exceptions.HTTPError:
            self._subscribers_cache[email] = None
            return None

    def build_subscriber_lookup(self, subscribers: List[Dict]) -> Dict[str, Dict]:
        """Build email -> subscriber lookup dict from subscribers list."""
        lookup = {}
        for sub in subscribers:
            email = sub.get('email', '').lower()
            if email:
                lookup[email] = sub
        return lookup

    def get_campaigns(self) -> List[Dict]:
        """Get all campaigns with stats (cached)."""
        if self._campaigns_cache is not None:
            return self._campaigns_cache

        campaigns = self._get("campaigns", {"type": "regular", "limit": 100})
        self._campaigns_cache = campaigns
        return campaigns

    def get_campaign_stats_summary(self) -> Dict:
        """Get summary of campaign performance."""
        campaigns = self.get_campaigns()

        sent_campaigns = [c for c in campaigns if c.get('status') == 'sent']

        if not sent_campaigns:
            return {
                'total_campaigns': 0,
                'avg_open_rate': 0,
                'avg_click_rate': 0,
                'best_campaign': None
            }

        avg_open_rate = sum(c.get('opened', {}).get('rate', 0) for c in sent_campaigns) / len(sent_campaigns)
        avg_click_rate = sum(c.get('clicked', {}).get('rate', 0) for c in sent_campaigns) / len(sent_campaigns)

        best_campaign = max(sent_campaigns, key=lambda c: c.get('opened', {}).get('rate', 0))

        return {
            'total_campaigns': len(sent_campaigns),
            'avg_open_rate': avg_open_rate * 100,
            'avg_click_rate': avg_click_rate * 100,
            'best_campaign': {
                'name': best_campaign.get('name'),
                'open_rate': best_campaign.get('opened', {}).get('rate', 0) * 100,
                'click_rate': best_campaign.get('clicked', {}).get('rate', 0) * 100
            }
        }

    def get_subscriber_activity(self, subscriber_id: int) -> List[Dict]:
        """Get activity timeline for subscriber."""
        try:
            activity = self._get(f"subscribers/{subscriber_id}/activity")
            return activity if activity else []
        except:
            return []

    def get_engagement_score(self, email: str, subscriber_data: Optional[Dict] = None) -> Dict:
        """Calculate engagement score for email address.

        Args:
            email: Email address to score
            subscriber_data: Optional pre-fetched subscriber data (to avoid extra API calls)
        """
        if subscriber_data is None:
            subscriber_data = self.get_subscriber_by_email(email)

        if not subscriber_data:
            return {
                'found': False,
                'engagement_score': 0,
                'opens': 0,
                'clicks': 0,
                'sent': 0,
                'open_rate': 0,
                'click_rate': 0
            }

        # Get stats
        opens = subscriber_data.get('opened', 0)
        clicks = subscriber_data.get('clicked', 0)
        sent = subscriber_data.get('sent', 0)

        # Calculate rates
        open_rate = (opens / sent * 100) if sent > 0 else 0
        click_rate = (clicks / sent * 100) if sent > 0 else 0

        # Calculate engagement score (0-30 points)
        score = 0

        # Open rate scoring (0-15 points)
        if open_rate >= 80:
            score += 15
        elif open_rate >= 50:
            score += 10
        elif open_rate >= 25:
            score += 5

        # Click scoring (0-15 points)
        if clicks >= 3:
            score += 15
        elif clicks >= 1:
            score += 10
        elif clicks >= 1:
            score += 5

        return {
            'found': True,
            'engagement_score': min(score, 30),
            'opens': opens,
            'clicks': clicks,
            'sent': sent,
            'open_rate': round(open_rate, 1),
            'click_rate': round(click_rate, 1)
        }

    def get_account_stats(self) -> Dict:
        """Get overall account statistics."""
        return self._get("stats")


if __name__ == '__main__':
    """Test MailerLite API."""
    print("\n" + "="*70)
    print("  MAILERLITE API - WERKENDE VERSIE TEST")
    print("="*70 + "\n")

    api = MailerLiteAPI()

    # Test 1: Account stats
    print("[1/4] Account statistieken...")
    stats = api.get_account_stats()
    print(f"        Campaigns: {stats['campaigns']}")
    print(f"        Verzonden emails: {stats['sent_emails']}")
    print(f"        Opens: {stats['opens_count']} ({stats['open_rate']*100:.1f}%)")
    print(f"        Clicks: {stats['clicks_count']} ({stats['click_rate']*100:.1f}%)")

    # Test 2: Campaign stats
    print("\n[2/4] Campaign statistieken...")
    campaign_summary = api.get_campaign_stats_summary()
    print(f"        Totaal campaigns: {campaign_summary['total_campaigns']}")
    print(f"        Gem. open rate: {campaign_summary['avg_open_rate']:.1f}%")
    print(f"        Gem. click rate: {campaign_summary['avg_click_rate']:.1f}%")

    if campaign_summary['best_campaign']:
        best = campaign_summary['best_campaign']
        print(f"\n        Beste campaign: {best['name']}")
        print(f"          Open rate: {best['open_rate']:.1f}%")
        print(f"          Click rate: {best['click_rate']:.1f}%")

    # Test 3: Subscribers ophalen (sample)
    print("\n[3/4] Subscribers ophalen (eerste 100)...")
    subscribers = api.get_all_subscribers(limit=100)
    print(f"        Gevonden: {len(subscribers)} subscribers")

    if subscribers:
        # Build lookup
        lookup = api.build_subscriber_lookup(subscribers)
        print(f"        Lookup dict size: {len(lookup)}")

        # Test engagement score
        sample_email = subscribers[0].get('email')
        print(f"\n        Test engagement voor: {sample_email}")

        engagement = api.get_engagement_score(sample_email, subscriber_data=subscribers[0])
        print(f"          Score: {engagement['engagement_score']}/30")
        print(f"          Opens: {engagement['opens']} ({engagement['open_rate']}%)")
        print(f"          Clicks: {engagement['clicks']} ({engagement['click_rate']}%)")

    # Test 4: Batch processing simulation
    print("\n[4/4] Batch processing test (10 subscribers)...")
    for i, sub in enumerate(subscribers[:10], 1):
        email = sub.get('email')
        engagement = api.get_engagement_score(email, subscriber_data=sub)
        print(f"        {i}. {email[:30]:30s} Score: {engagement['engagement_score']:2d}/30")

    print("\n" + "="*70)
    print("  TEST COMPLEET")
    print("="*70 + "\n")

    print("API werkt! Klaar voor integratie in lead scoring.")
    print()
