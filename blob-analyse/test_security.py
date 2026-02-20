"""
Security test: Probeer andere klant data op te halen
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).parent / '.env'
if not env_path.exists():
    env_path = Path('c:/projects/notifica_app/apps/tools-analyses/blob-analyse/.env')
load_dotenv(env_path)

# SDK import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '_sdk'))
from notifica_sdk import NotificaClient, NotificaError

# Test connectie
api_url = os.getenv('NOTIFICA_API_URL')
api_key = os.getenv('NOTIFICA_APP_KEY')

print(f"API URL: {api_url}")
print(f"API Key: {api_key[:20]}...")

client = NotificaClient(api_url, api_key)

# Simple test query
test_query = "SELECT COUNT(*) as aantal FROM stg_werkbonnen LIMIT 1"

# TEST 1: Klant 1229 (Zenith - MOET WERKEN)
print("\n=== TEST 1: Klant 1229 (Zenith Security) ===")
try:
    result = client.query(1229, test_query)
    print(f"[OK] SUCCESS: {result[0]['aantal']} werkbonnen gevonden")
except NotificaError as e:
    print(f"[FAIL] BLOCKED: {e}")

# TEST 2: Klant 1234 (Andere klant - MOET FALEN)
print("\n=== TEST 2: Klant 1234 (Andere klant) ===")
try:
    result = client.query(1234, test_query)
    print(f"[WARNING] SECURITY ISSUE: Toegang tot andere klant! {result[0]['aantal']} records")
except NotificaError as e:
    print(f"[OK] BLOCKED (verwacht): {e}")

# TEST 3: Klant 1 (Notifica zelf - MOET FALEN)
print("\n=== TEST 3: Klant 1 (Notifica zelf) ===")
try:
    result = client.query(1, test_query)
    print(f"[WARNING] SECURITY ISSUE: Toegang tot Notifica data! {result[0]['aantal']} records")
except NotificaError as e:
    print(f"[OK] BLOCKED (verwacht): {e}")

print("\n=== CONCLUSIE ===")
print("Als alleen TEST 1 succesvol is -> API key is veilig beperkt tot klant 1229")
print("Als TEST 2 of 3 ook werkt -> API key heeft te brede toegang (SECURITY RISK)")
