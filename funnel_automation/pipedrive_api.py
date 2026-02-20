"""Pipedrive API wrapper voor lead management."""
import requests
from typing import List, Dict, Optional
from utils.config import PIPEDRIVE_API_TOKEN, PIPEDRIVE_COMPANY_DOMAIN

class PipedriveAPI:
    """Wrapper voor Pipedrive API calls."""

    def __init__(self):
        self.api_token = PIPEDRIVE_API_TOKEN
        self.base_url = f"https://{PIPEDRIVE_COMPANY_DOMAIN}.pipedrive.com/api/v1"
        self.headers = {
            "Content-Type": "application/json"
        }

    def _get(self, endpoint: str, params: Dict = None) -> Dict:
        """Generieke GET request naar Pipedrive API."""
        if params is None:
            params = {}
        params['api_token'] = self.api_token

        response = requests.get(
            f"{self.base_url}/{endpoint}",
            params=params,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint: str, data: Dict) -> Dict:
        """Generieke POST request naar Pipedrive API."""
        params = {'api_token': self.api_token}

        response = requests.post(
            f"{self.base_url}/{endpoint}",
            params=params,
            json=data,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    def _put(self, endpoint: str, data: Dict) -> Dict:
        """Generieke PUT request naar Pipedrive API."""
        params = {'api_token': self.api_token}

        response = requests.put(
            f"{self.base_url}/{endpoint}",
            params=params,
            json=data,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    # === PERSONS (Contacten) ===

    def get_persons(self, limit: int = 100, start: int = 0) -> List[Dict]:
        """Haal alle personen op uit Pipedrive."""
        result = self._get("persons", {"limit": limit, "start": start})
        return result.get('data', [])

    def get_person(self, person_id: int) -> Dict:
        """Haal specifiek persoon op."""
        result = self._get(f"persons/{person_id}")
        return result.get('data', {})

    def update_person(self, person_id: int, data: Dict) -> Dict:
        """Update persoon gegevens (bijv. custom fields)."""
        result = self._put(f"persons/{person_id}", data)
        return result.get('data', {})

    def search_person_by_email(self, email: str) -> Optional[Dict]:
        """Zoek persoon op email adres."""
        result = self._get("persons/search", {
            "term": email,
            "fields": "email",
            "exact_match": True
        })

        items = result.get('data', {}).get('items', [])
        if items:
            return items[0].get('item', {})
        return None

    # === DEALS (Opportunities) ===

    def get_deals(self, limit: int = 100, start: int = 0) -> List[Dict]:
        """Haal alle deals op."""
        result = self._get("deals", {"limit": limit, "start": start})
        return result.get('data', [])

    def get_person_deals(self, person_id: int) -> List[Dict]:
        """Haal alle deals voor specifiek persoon op."""
        result = self._get(f"persons/{person_id}/deals")
        return result.get('data', [])

    # === ACTIVITIES (Activiteiten) ===

    def get_person_activities(self, person_id: int) -> List[Dict]:
        """Haal alle activiteiten voor persoon op."""
        result = self._get(f"persons/{person_id}/activities")
        return result.get('data', [])

    def create_activity(self, data: Dict) -> Dict:
        """Maak nieuwe activiteit aan (bijv. taak om te bellen)."""
        result = self._post("activities", data)
        return result.get('data', {})

    # === VISITORS (Website Tracking) ===

    def get_visitors(self, person_id: Optional[int] = None, start_date: Optional[str] = None) -> List[Dict]:
        """Haal website visitor data op.

        Args:
            person_id: Specifiek persoon ID (optioneel)
            start_date: Start datum in YYYY-MM-DD format (optioneel)
        """
        params = {}
        if person_id:
            params['person_id'] = person_id
        if start_date:
            params['start_date'] = start_date

        result = self._get("visitors", params)
        return result.get('data', [])

    def get_person_visits(self, person_id: int) -> List[Dict]:
        """Haal alle website visits voor specifiek persoon op."""
        return self.get_visitors(person_id=person_id)

    # === CUSTOM FIELDS ===

    def get_person_fields(self) -> List[Dict]:
        """Haal alle custom fields voor personen op."""
        result = self._get("personFields")
        return result.get('data', [])

    def create_person_field(self, name: str, field_type: str = "varchar") -> Dict:
        """Maak nieuw custom field aan voor personen.

        field_type kan zijn: varchar, text, double, monetary, date, set, enum, user, org, people, phone, time, timerange, daterange
        """
        data = {
            "name": name,
            "field_type": field_type
        }
        result = self._post("personFields", data)
        return result.get('data', {})

    # === LEAD SCORING HELPERS ===

    def get_all_persons_with_details(self) -> List[Dict]:
        """Haal alle personen op met deals, activiteiten en website visits.

        Dit is handig voor lead scoring.
        """
        persons = self.get_persons(limit=500)

        for person in persons:
            person_id = person['id']
            person['deals'] = self.get_person_deals(person_id)
            person['activities'] = self.get_person_activities(person_id)
            person['website_visits'] = self.get_person_visits(person_id)

        return persons


def test_connection():
    """Test Pipedrive API connectie."""
    try:
        api = PipedriveAPI()
        persons = api.get_persons(limit=5)

        print("✅ Pipedrive API connectie succesvol!")
        print(f"📊 Aantal personen (eerste batch): {len(persons)}")

        if persons:
            print("\n🔍 Voorbeeld persoon:")
            person = persons[0]
            print(f"  - Naam: {person.get('name')}")
            print(f"  - Email: {person.get('email', [{}])[0].get('value', 'Geen email')}")
            print(f"  - ID: {person.get('id')}")

        # Check custom fields
        fields = api.get_person_fields()
        print(f"\n📝 Aantal custom fields: {len(fields)}")

        lead_score_field = [f for f in fields if 'lead' in f.get('name', '').lower() and 'score' in f.get('name', '').lower()]
        if lead_score_field:
            print(f"✅ Lead Score field bestaat al: {lead_score_field[0].get('name')}")
        else:
            print("⚠️  Geen 'Lead Score' field gevonden - we kunnen die aanmaken")

        # Test website visitor tracking
        print("\n🌐 Test website visitor tracking...")
        try:
            visitors = api.get_visitors()
            print(f"📊 Aantal website visitors gevonden: {len(visitors) if visitors else 0}")

            if visitors and len(visitors) > 0:
                visitor = visitors[0]
                print(f"\n🔍 Voorbeeld website visit:")
                print(f"  - Persoon ID: {visitor.get('person_id')}")
                print(f"  - Visit datum: {visitor.get('visit_time')}")
                print(f"  - Pagina URL: {visitor.get('page_url', 'Onbekend')}")
                print(f"  - Duration: {visitor.get('duration', 0)} seconden")
            else:
                print("ℹ️  Nog geen website visitors getracked (mogelijk is tracking nog niet geactiveerd)")
                print("   Je kunt Pipedrive Website Visitor tracking activeren in Settings → Features → Website Visitors")
        except Exception as e:
            print(f"⚠️  Website visitor tracking niet beschikbaar: {e}")
            print("   Dit is mogelijk niet inbegrepen in je Pipedrive plan, of nog niet geactiveerd")

        return True

    except requests.exceptions.RequestException as e:
        print(f"❌ Fout bij verbinden met Pipedrive: {e}")
        return False
    except Exception as e:
        print(f"❌ Onverwachte fout: {e}")
        return False


if __name__ == "__main__":
    print("🔌 Test Pipedrive API connectie...\n")
    test_connection()
