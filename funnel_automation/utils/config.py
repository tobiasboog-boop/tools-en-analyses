"""Configuratie en environment variabelen laden."""
import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Pipedrive
PIPEDRIVE_API_TOKEN = os.getenv('PIPEDRIVE_API_TOKEN')
PIPEDRIVE_COMPANY_DOMAIN = os.getenv('PIPEDRIVE_COMPANY_DOMAIN')

# Google Analytics 4
GA4_PROPERTY_ID = os.getenv('GA4_PROPERTY_ID')
GA4_SERVICE_ACCOUNT_JSON = os.getenv('GA4_SERVICE_ACCOUNT_JSON')

# Google Search Console
GSC_SITE_URL = os.getenv('GSC_SITE_URL')

# Lead Scoring Thresholds
WARM_LEAD_THRESHOLD = int(os.getenv('WARM_LEAD_THRESHOLD', 80))
LUKEWARM_LEAD_THRESHOLD = int(os.getenv('LUKEWARM_LEAD_THRESHOLD', 40))

def validate_config():
    """Valideer of alle benodigde configuratie aanwezig is."""
    errors = []

    if not PIPEDRIVE_API_TOKEN:
        errors.append("PIPEDRIVE_API_TOKEN ontbreekt in .env")
    if not PIPEDRIVE_COMPANY_DOMAIN:
        errors.append("PIPEDRIVE_COMPANY_DOMAIN ontbreekt in .env")

    if errors:
        raise ValueError(f"Configuratie fouten:\n" + "\n".join(f"  - {e}" for e in errors))

    return True
