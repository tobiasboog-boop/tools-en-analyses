"""Lead scoring engine - berekent automatisch lead scores op basis van Pipedrive data."""
import sys
import io
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

# Fix voor Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


class LeadScorer:
    """Berekent lead scores op basis van CRM activiteit."""

    def __init__(self, warm_threshold: int = 80, lukewarm_threshold: int = 40):
        self.warm_threshold = warm_threshold
        self.lukewarm_threshold = lukewarm_threshold

    def calculate_score(self, person: Dict) -> Tuple[int, str]:
        """Bereken lead score voor een persoon.

        Returns:
            Tuple[int, str]: (score, segment) waarbij segment 'Warm', 'Lauw' of 'Koud' is
        """
        score = 0
        now = datetime.now()

        # === 1. RECENT CONTACT (max 30 punten) ===
        activities = person.get('activities', [])
        if activities:
            recent_score = self._score_recent_activities(activities, now)
            score += recent_score

        # === 2. DEAL STATUS (max 35 punten) ===
        deals = person.get('deals', [])
        if deals:
            deal_score = self._score_deals(deals)
            score += deal_score

        # === 3. ACTIVITEIT FREQUENTIE (max 20 punten) ===
        frequency_score = self._score_activity_frequency(activities, now)
        score += frequency_score

        # === 4. EMAIL ENGAGEMENT (max 15 punten) ===
        email_score = self._score_email_engagement(activities)
        score += email_score

        # Bepaal segment
        if score >= self.warm_threshold:
            segment = "Warm"
        elif score >= self.lukewarm_threshold:
            segment = "Lauw"
        else:
            segment = "Koud"

        return min(score, 100), segment  # Cap op 100

    def _score_recent_activities(self, activities: List[Dict], now: datetime) -> int:
        """Score op basis van recente activiteiten.

        - Activiteit in laatste 7 dagen: 30 punten
        - Activiteit in laatste 14 dagen: 20 punten
        - Activiteit in laatste 30 dagen: 10 punten
        - Ouder: 0 punten
        """
        if not activities:
            return 0

        # Zoek meest recente activiteit
        most_recent = None
        for activity in activities:
            done_date = activity.get('due_date') or activity.get('add_time')
            if not done_date:
                continue

            try:
                # Parse datum (kan verschillende formaten zijn)
                if isinstance(done_date, str):
                    # Probeer verschillende formaten
                    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                        try:
                            activity_date = datetime.strptime(done_date, fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        continue
                else:
                    activity_date = done_date

                if most_recent is None or activity_date > most_recent:
                    most_recent = activity_date
            except Exception:
                continue

        if most_recent is None:
            return 0

        days_ago = (now - most_recent).days

        if days_ago <= 7:
            return 30
        elif days_ago <= 14:
            return 20
        elif days_ago <= 30:
            return 10
        else:
            return 0

    def _score_deals(self, deals: List[Dict]) -> int:
        """Score op basis van deal status en waarde.

        - Actieve deal in late stage: 35 punten
        - Actieve deal in mid stage: 25 punten
        - Actieve deal in early stage: 15 punten
        - Geen actieve deals: 0 punten
        - Gesloten deals (won): +5 punten (bewezen interesse)
        """
        if not deals:
            return 0

        score = 0
        has_active_deal = False

        for deal in deals:
            status = deal.get('status', '')

            # Actieve deals
            if status == 'open':
                has_active_deal = True
                stage_order = deal.get('stage_order_nr', 0)

                # Hoe later in de funnel, hoe hoger de score
                if stage_order >= 3:  # Late stage
                    score = max(score, 35)
                elif stage_order >= 2:  # Mid stage
                    score = max(score, 25)
                else:  # Early stage
                    score = max(score, 15)

            # Gewonnen deals = bewijs van interesse
            elif status == 'won':
                score += 5  # Bonus voor historie

        return min(score, 35)  # Cap op 35

    def _score_activity_frequency(self, activities: List[Dict], now: datetime) -> int:
        """Score op basis van activiteit frequentie (laatste 30 dagen).

        - 5+ activiteiten: 20 punten
        - 3-4 activiteiten: 15 punten
        - 1-2 activiteiten: 10 punten
        - 0 activiteiten: 0 punten
        """
        if not activities:
            return 0

        # Tel activiteiten in laatste 30 dagen
        recent_count = 0
        thirty_days_ago = now - timedelta(days=30)

        for activity in activities:
            done_date = activity.get('due_date') or activity.get('add_time')
            if not done_date:
                continue

            try:
                if isinstance(done_date, str):
                    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                        try:
                            activity_date = datetime.strptime(done_date, fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        continue
                else:
                    activity_date = done_date

                if activity_date >= thirty_days_ago:
                    recent_count += 1
            except Exception:
                continue

        if recent_count >= 5:
            return 20
        elif recent_count >= 3:
            return 15
        elif recent_count >= 1:
            return 10
        else:
            return 0

    def _score_email_engagement(self, activities: List[Dict]) -> int:
        """Score op basis van email engagement.

        - Recent email gesprek (laatste 14 dagen): 15 punten
        - Oudere email engagement: 5 punten
        - Geen email activiteit: 0 punten
        """
        if not activities:
            return 0

        now = datetime.now()
        fourteen_days_ago = now - timedelta(days=14)
        has_recent_email = False
        has_old_email = False

        for activity in activities:
            # Check of het een email activiteit is
            activity_type = activity.get('type', '').lower()
            if 'email' not in activity_type and activity_type != 'mail':
                continue

            done_date = activity.get('due_date') or activity.get('add_time')
            if not done_date:
                continue

            try:
                if isinstance(done_date, str):
                    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                        try:
                            activity_date = datetime.strptime(done_date, fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        continue
                else:
                    activity_date = done_date

                if activity_date >= fourteen_days_ago:
                    has_recent_email = True
                else:
                    has_old_email = True
            except Exception:
                continue

        if has_recent_email:
            return 15
        elif has_old_email:
            return 5
        else:
            return 0

    def score_all_persons(self, persons: List[Dict]) -> List[Dict]:
        """Bereken scores voor alle personen.

        Returns:
            List van persons met toegevoegde 'lead_score' en 'lead_segment' velden
        """
        results = []

        for person in persons:
            score, segment = self.calculate_score(person)

            # Voeg score toe aan person dict
            person_result = person.copy()
            person_result['lead_score'] = score
            person_result['lead_segment'] = segment

            results.append(person_result)

        # Sorteer op score (hoogste eerst)
        results.sort(key=lambda x: x['lead_score'], reverse=True)

        return results


def test_scoring():
    """Test lead scoring met dummy data."""
    from datetime import datetime

    print("🧪 Test Lead Scoring Algoritme\n")

    scorer = LeadScorer()

    # Test case 1: Warme lead
    warm_lead = {
        'name': 'Test Warme Lead',
        'activities': [
            {'due_date': datetime.now().strftime('%Y-%m-%d'), 'type': 'call'},
            {'due_date': (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d'), 'type': 'email'},
            {'due_date': (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d'), 'type': 'meeting'},
        ],
        'deals': [
            {'status': 'open', 'stage_order_nr': 3, 'value': 50000}
        ]
    }

    # Test case 2: Lauwe lead
    lukewarm_lead = {
        'name': 'Test Lauwe Lead',
        'activities': [
            {'due_date': (datetime.now() - timedelta(days=20)).strftime('%Y-%m-%d'), 'type': 'call'},
        ],
        'deals': [
            {'status': 'open', 'stage_order_nr': 1, 'value': 10000}
        ]
    }

    # Test case 3: Koude lead
    cold_lead = {
        'name': 'Test Koude Lead',
        'activities': [
            {'due_date': (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'), 'type': 'email'},
        ],
        'deals': []
    }

    for lead in [warm_lead, lukewarm_lead, cold_lead]:
        score, segment = scorer.calculate_score(lead)
        print(f"📊 {lead['name']}")
        print(f"   Score: {score}/100")
        print(f"   Segment: {segment}")
        print()


if __name__ == "__main__":
    test_scoring()
