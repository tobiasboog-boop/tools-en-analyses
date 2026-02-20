"""MailerLite data integration voor email engagement scoring."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import csv
from typing import Dict, List


class MailerLiteData:
    """Load en parse MailerLite export data."""

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.data = {}
        self._load_data()

    def _load_data(self):
        """Load MailerLite CSV export."""
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                email = row['Subscriber'].lower().strip()

                self.data[email] = {
                    'sent': int(row['Sent']) if row['Sent'] else 0,
                    'opens': int(row['Opens']) if row['Opens'] else 0,
                    'clicks': int(row['Clicks']) if row['Clicks'] else 0,
                    'subscribed': row['Subscribed'],
                    'location': row['Location']
                }

    def get_engagement(self, email: str) -> Dict:
        """Haal email engagement data op voor een email adres.

        Returns:
            Dict met sent, opens, clicks en engagement metrics
        """
        email = email.lower().strip()

        if email not in self.data:
            return {
                'sent': 0,
                'opens': 0,
                'clicks': 0,
                'open_rate': 0.0,
                'click_rate': 0.0,
                'engagement_score': 0
            }

        data = self.data[email]
        sent = data['sent']
        opens = data['opens']
        clicks = data['clicks']

        # Calculate rates
        open_rate = (opens / sent * 100) if sent > 0 else 0
        click_rate = (clicks / sent * 100) if sent > 0 else 0

        # Engagement score (0-30 punten voor lead scoring)
        engagement_score = 0

        # Opens
        if open_rate >= 80:
            engagement_score += 15  # Zeer hoog engagement
        elif open_rate >= 50:
            engagement_score += 10  # Hoog engagement
        elif open_rate >= 25:
            engagement_score += 5   # Matig engagement

        # Clicks
        if clicks >= 3:
            engagement_score += 15  # Zeer actief
        elif clicks >= 1:
            engagement_score += 10  # Actief
        elif click_rate >= 10:
            engagement_score += 5   # Enige interesse

        return {
            'sent': sent,
            'opens': opens,
            'clicks': clicks,
            'open_rate': round(open_rate, 1),
            'click_rate': round(click_rate, 1),
            'engagement_score': min(engagement_score, 30)  # Cap op 30
        }

    def get_statistics(self) -> Dict:
        """Get overall statistics."""
        total_subscribers = len(self.data)
        total_sent = sum(d['sent'] for d in self.data.values())
        total_opens = sum(d['opens'] for d in self.data.values())
        total_clicks = sum(d['clicks'] for d in self.data.values())

        engaged = sum(1 for d in self.data.values() if d['opens'] > 0)
        clicked = sum(1 for d in self.data.values() if d['clicks'] > 0)

        return {
            'total_subscribers': total_subscribers,
            'total_sent': total_sent,
            'total_opens': total_opens,
            'total_clicks': total_clicks,
            'engaged_subscribers': engaged,
            'clicked_subscribers': clicked,
            'avg_open_rate': round((total_opens / total_sent * 100) if total_sent > 0 else 0, 1),
            'avg_click_rate': round((total_clicks / total_sent * 100) if total_sent > 0 else 0, 1)
        }


def test_mailerlite_data():
    """Test MailerLite data loading."""
    csv_path = r"C:\Users\tobia\OneDrive - Notifica B.V\Documenten - Sharepoint Notifica intern\105. Marketing\export mailer lite.csv"

    print("\n===== MAILERLITE DATA TEST =====\n")

    ml = MailerLiteData(csv_path)

    # Statistics
    stats = ml.get_statistics()
    print("[STATISTICS]")
    print(f"  Total subscribers: {stats['total_subscribers']}")
    print(f"  Total emails sent: {stats['total_sent']}")
    print(f"  Total opens: {stats['total_opens']}")
    print(f"  Total clicks: {stats['total_clicks']}")
    print(f"  Engaged (opened): {stats['engaged_subscribers']}")
    print(f"  Clicked: {stats['clicked_subscribers']}")
    print(f"  Avg open rate: {stats['avg_open_rate']}%")
    print(f"  Avg click rate: {stats['avg_click_rate']}%")

    # Test specific emails
    print("\n[TOP ENGAGED SUBSCRIBERS]")
    test_emails = [
        'chloe.haring@gmail.com',
        'info@klimaatcomfort.nl',
        'zvdweerd@aalbertsinstallaties.nl'
    ]

    for email in test_emails:
        engagement = ml.get_engagement(email)
        print(f"\n  {email}")
        print(f"    Sent: {engagement['sent']}, Opens: {engagement['opens']}, Clicks: {engagement['clicks']}")
        print(f"    Open rate: {engagement['open_rate']}%")
        print(f"    Click rate: {engagement['click_rate']}%")
        print(f"    Engagement score: {engagement['engagement_score']}/30")

    print("\n===== TEST COMPLETE =====\n")


if __name__ == "__main__":
    test_mailerlite_data()
