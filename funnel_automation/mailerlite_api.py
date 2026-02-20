"""MailerLite API v2 wrapper for campaign stats and subscriber activity."""
import os
import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

MAILERLITE_API_TOKEN = os.getenv('MAILERLITE_API_TOKEN')

class MailerLiteAPI:
    """MailerLite API v2 client."""

    def __init__(self):
        self.api_token = MAILERLITE_API_TOKEN
        self.base_url = "https://api.mailerlite.com/api/v2"
        self.headers = {
            'X-MailerLite-ApiKey': self.api_token,
            'Content-Type': 'application/json'
        }

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make GET request to MailerLite API."""
        url = f"{self.base_url}/{endpoint}"
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def get_subscriber(self, email: str) -> Optional[Dict]:
        """Get subscriber by email."""
        try:
            return self._get(f"subscribers/{email}")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def get_subscriber_activity(self, subscriber_id: int) -> List[Dict]:
        """Get activity timeline for subscriber."""
        return self._get(f"subscribers/{subscriber_id}/activity")

    def get_campaigns(self, status: str = 'sent', limit: int = 100) -> List[Dict]:
        """Get campaigns. Status: sent, draft, outbox."""
        return self._get("campaigns", {"status": status, "limit": limit})

    def get_campaign_stats(self, campaign_id: int) -> Dict:
        """Get detailed stats for a campaign."""
        campaign = self._get(f"campaigns/{campaign_id}")
        return {
            'id': campaign['id'],
            'name': campaign.get('name', 'Unnamed'),
            'subject': campaign.get('subject', ''),
            'sent_at': campaign.get('date_send'),
            'total_recipients': campaign.get('total_recipients', 0),
            'opens': campaign.get('opened', {}).get('count', 0),
            'open_rate': campaign.get('opened', {}).get('rate', 0),
            'clicks': campaign.get('clicked', {}).get('count', 0),
            'click_rate': campaign.get('clicked', {}).get('rate', 0),
            'unsubscribes': campaign.get('unsubscribed', {}).get('count', 0)
        }

    def get_all_campaign_stats(self, limit: int = 50) -> List[Dict]:
        """Get stats for all sent campaigns."""
        campaigns = self.get_campaigns(status='sent', limit=limit)
        stats = []
        for campaign in campaigns:
            try:
                stats.append(self.get_campaign_stats(campaign['id']))
            except Exception as e:
                print(f"Error getting stats for campaign {campaign['id']}: {e}")
        return stats

    def get_recent_engagement(self, email: str, days: int = 30) -> Dict:
        """Get subscriber engagement in last N days."""
        subscriber = self.get_subscriber(email)
        if not subscriber:
            return {
                'found': False,
                'recent_opens': 0,
                'recent_clicks': 0,
                'recent_campaigns': [],
                'engagement_score': 0
            }

        # Get activity timeline
        subscriber_id = subscriber['id']
        activity = self.get_subscriber_activity(subscriber_id)

        # Filter to recent activity
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_opens = 0
        recent_clicks = 0
        recent_campaigns = set()

        for event in activity:
            event_date_str = event.get('date')
            if not event_date_str:
                continue

            # Parse date (format: "2024-01-15 10:30:00")
            try:
                event_date = datetime.strptime(event_date_str, "%Y-%m-%d %H:%M:%S")
            except:
                continue

            if event_date < cutoff_date:
                continue

            event_type = event.get('type', '')
            if event_type == 'open':
                recent_opens += 1
                recent_campaigns.add(event.get('campaign_id'))
            elif event_type == 'click':
                recent_clicks += 1
                recent_campaigns.add(event.get('campaign_id'))

        # Calculate engagement score (0-30 points, higher weight for recent activity)
        score = 0

        # Recent opens (0-15 points)
        if recent_opens >= 5:
            score += 15
        elif recent_opens >= 3:
            score += 10
        elif recent_opens >= 1:
            score += 5

        # Recent clicks (0-15 points)
        if recent_clicks >= 3:
            score += 15
        elif recent_clicks >= 2:
            score += 10
        elif recent_clicks >= 1:
            score += 5

        return {
            'found': True,
            'recent_opens': recent_opens,
            'recent_clicks': recent_clicks,
            'recent_campaigns': list(recent_campaigns),
            'engagement_score': min(score, 30),
            'total_opens': subscriber.get('opened', 0),
            'total_clicks': subscriber.get('clicked', 0)
        }

    def get_campaign_engagement_by_subscriber(self, email: str) -> Dict:
        """Get which campaigns this subscriber engaged with."""
        subscriber = self.get_subscriber(email)
        if not subscriber:
            return {'found': False, 'campaigns': []}

        subscriber_id = subscriber['id']
        activity = self.get_subscriber_activity(subscriber_id)

        # Group by campaign
        campaign_engagement = {}
        for event in activity:
            campaign_id = event.get('campaign_id')
            if not campaign_id:
                continue

            if campaign_id not in campaign_engagement:
                campaign_engagement[campaign_id] = {
                    'campaign_id': campaign_id,
                    'opens': 0,
                    'clicks': 0,
                    'last_activity': event.get('date')
                }

            event_type = event.get('type', '')
            if event_type == 'open':
                campaign_engagement[campaign_id]['opens'] += 1
            elif event_type == 'click':
                campaign_engagement[campaign_id]['clicks'] += 1

        return {
            'found': True,
            'email': email,
            'campaigns': list(campaign_engagement.values())
        }


if __name__ == '__main__':
    """Test MailerLite API connection and show campaign stats."""
    print("\n" + "="*70)
    print("  MAILERLITE API TEST - Campaign Statistics")
    print("="*70 + "\n")

    api = MailerLiteAPI()

    # Test 1: Get all campaign stats
    print("[1/3] Fetching campaign statistics...")
    campaigns = api.get_all_campaign_stats(limit=10)

    print(f"\n        Found {len(campaigns)} recent campaigns\n")
    print("-"*70)
    print(f"{'Campaign Name':<30} {'Sent':<12} {'Open%':>7} {'Click%':>7}")
    print("-"*70)

    for campaign in campaigns[:10]:
        name = campaign['name'][:28]
        sent_date = campaign.get('sent_at', 'N/A')
        if sent_date and sent_date != 'N/A':
            sent_date = sent_date[:10]  # Just date part
        open_rate = campaign['open_rate']
        click_rate = campaign['click_rate']

        print(f"{name:<30} {sent_date:<12} {open_rate:>6.1f}% {click_rate:>6.1f}%")

    # Test 2: Get recent engagement for a test email
    print("\n[2/3] Testing recent engagement tracking (30 days)...")
    test_email = "t.boog@notifica.nl"  # Your own email

    engagement = api.get_recent_engagement(test_email, days=30)

    if engagement['found']:
        print(f"\n        Email: {test_email}")
        print(f"        Recent opens (30d): {engagement['recent_opens']}")
        print(f"        Recent clicks (30d): {engagement['recent_clicks']}")
        print(f"        Recent campaigns: {len(engagement['recent_campaigns'])}")
        print(f"        Engagement score: {engagement['engagement_score']}/30")
        print(f"        Total opens (all-time): {engagement['total_opens']}")
        print(f"        Total clicks (all-time): {engagement['total_clicks']}")
    else:
        print(f"        Email {test_email} not found in MailerLite")

    # Test 3: Campaign-level engagement for subscriber
    print("\n[3/3] Testing campaign-level engagement...")

    campaign_data = api.get_campaign_engagement_by_subscriber(test_email)

    if campaign_data['found'] and campaign_data['campaigns']:
        print(f"\n        Found engagement with {len(campaign_data['campaigns'])} campaigns")
        print("\n        Top 5 campaigns by engagement:")

        # Sort by total activity (opens + clicks)
        sorted_campaigns = sorted(
            campaign_data['campaigns'],
            key=lambda x: x['opens'] + x['clicks'],
            reverse=True
        )[:5]

        for camp in sorted_campaigns:
            print(f"          Campaign {camp['campaign_id']}: {camp['opens']} opens, {camp['clicks']} clicks")
    else:
        print(f"        No campaign engagement found for {test_email}")

    print("\n" + "="*70)
    print("  TEST COMPLETE")
    print("="*70 + "\n")

    print("Next steps:")
    print("  1. Review campaign statistics above")
    print("  2. Run with different test emails to verify data")
    print("  3. Integrate into score_leads_complete.py for enhanced scoring")
    print()
