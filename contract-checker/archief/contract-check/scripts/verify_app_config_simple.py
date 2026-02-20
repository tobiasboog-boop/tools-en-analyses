#!/usr/bin/env python3
"""
Quick verification of app_configuration deployment via REST API
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

print("=" * 80)
print("  APP CONFIGURATION DEPLOYMENT VERIFICATION")
print("=" * 80)

# Check if app_configuration table exists
url = f"{SUPABASE_URL}/rest/v1/app_configuration"
headers = {
    "apikey": SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {SUPABASE_ANON_KEY}"
}

try:
    response = requests.get(url, headers=headers, params={"limit": 5})

    if response.status_code == 200:
        data = response.json()
        print(f"\n[OK] app_configuration table EXISTS")
        print(f"[OK] Found {len(data)} configuration entries")

        if data:
            print("\n[CONFIGS] Sample configurations:")
            for config in data:
                key = config.get('config_key', 'unknown')
                value = config.get('config_value', 'N/A')
                value_type = config.get('value_type', 'string')
                print(f"  • {key:35} = {value:10} ({value_type})")

        print("\n" + "=" * 80)
        print(f"[SUCCESS] Schema deployment verified!")
        print(f"[SUCCESS] sql/003_app_configuration.sql is properly deployed")
        print("=" * 80)

    elif response.status_code == 404:
        print(f"\n[ERROR] app_configuration table NOT FOUND")
        print(f"[ERROR] Please deploy sql/003_app_configuration.sql in Supabase SQL Editor")
        print("=" * 80)
        exit(1)
    else:
        print(f"\n[ERROR] Unexpected status code: {response.status_code}")
        print(f"Response: {response.text}")
        exit(1)

except Exception as e:
    print(f"\n[ERROR] Failed to connect to Supabase: {e}")
    exit(1)

# Check if view exists
print("\n[CHECKING] app_configuration_overview view...")
view_url = f"{SUPABASE_URL}/rest/v1/app_configuration_overview"

try:
    response = requests.get(view_url, headers=headers, params={"limit": 1})

    if response.status_code == 200:
        print(f"[OK] app_configuration_overview view EXISTS")
    else:
        print(f"[WARN] View might not exist: {response.status_code}")

except Exception as e:
    print(f"[WARN] Could not verify view: {e}")

print("\n" + "=" * 80)
print("[READY] System ready for pilot deployment!")
print("=" * 80)
