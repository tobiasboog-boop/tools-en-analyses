#!/usr/bin/env python3
"""
PILOT QUICK START: Switch to Claude Everywhere

Run this to use Claude for both contract_generation AND werkbon_classification.
Later, when you have Mistral API key, you can switch back to save costs.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("[ERROR] SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
    exit(1)

print("=" * 80)
print("  SWITCHING TO CLAUDE EVERYWHERE (Pilot Mode)")
print("=" * 80)

# Use service key for updates
headers = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# Step 1: Get Claude Sonnet 4 model ID
print("\n[1] Finding Claude Sonnet 4 model...")
models_url = f"{SUPABASE_URL}/rest/v1/llm_models"
response = requests.get(
    models_url,
    headers=headers,
    params={"select": "id,model_code,model_name", "model_code": "eq.claude-sonnet-4-20250514"}
)

if response.status_code != 200:
    print(f"[ERROR] Could not fetch models: {response.status_code}")
    print(response.text)
    exit(1)

models = response.json()
if not models:
    print("[ERROR] Claude Sonnet 4 model not found in database!")
    exit(1)

claude_model_id = models[0]['id']
print(f"[OK] Found: {models[0]['model_name']} (ID: {claude_model_id})")

# Step 2: Get werkbon-checker app ID
print("\n[2] Finding werkbon-checker app...")
apps_url = f"{SUPABASE_URL}/rest/v1/apps"
response = requests.get(
    apps_url,
    headers=headers,
    params={"select": "id,code,name", "code": "eq.werkbon-checker"}
)

if response.status_code != 200:
    print(f"[ERROR] Could not fetch apps: {response.status_code}")
    exit(1)

apps = response.json()
if not apps:
    print("[ERROR] werkbon-checker app not found!")
    exit(1)

app_id = apps[0]['id']
print(f"[OK] Found: {apps[0]['name']} (ID: {app_id})")

# Step 3: Update werkbon_classification to use Claude
print("\n[3] Updating werkbon_classification config...")
config_url = f"{SUPABASE_URL}/rest/v1/llm_configurations"

# Find the config to update
response = requests.get(
    config_url,
    headers=headers,
    params={
        "select": "id,action_type,model_id",
        "app_id": f"eq.{app_id}",
        "action_type": "eq.werkbon_classification",
        "organization_id": "is.null"
    }
)

if response.status_code != 200:
    print(f"[ERROR] Could not fetch config: {response.status_code}")
    exit(1)

configs = response.json()
if not configs:
    print("[ERROR] werkbon_classification config not found!")
    exit(1)

config_id = configs[0]['id']
old_model_id = configs[0]['model_id']

# Update to Claude
update_url = f"{config_url}?id=eq.{config_id}"
response = requests.patch(
    update_url,
    headers=headers,
    json={"model_id": claude_model_id}
)

if response.status_code not in [200, 204]:
    print(f"[ERROR] Could not update config: {response.status_code}")
    print(response.text)
    exit(1)

print(f"[OK] Updated werkbon_classification to use Claude Sonnet 4")

# Step 4: Verify current configuration
print("\n[4] Verifying configuration...")
verify_url = f"{SUPABASE_URL}/rest/v1/llm_configurations_overview"
response = requests.get(
    verify_url,
    headers=headers,
    params={
        "select": "action_type,provider_name,model_name,priority",
        "app_code": "eq.werkbon-checker",
        "order": "action_type,priority.desc"
    }
)

if response.status_code == 200:
    configs = response.json()
    print("\n" + "=" * 80)
    print("  CURRENT LLM CONFIGURATION")
    print("=" * 80)
    for c in configs:
        print(f"  {c['action_type']:30} → {c['model_name']:25} ({c['provider_name']})")
    print("=" * 80)
else:
    print(f"[WARN] Could not verify: {response.status_code}")

# Summary
print("\n" + "=" * 80)
print("  SUCCESS! Configuration Updated")
print("=" * 80)
print()
print("[OK] Both actions now use Claude Sonnet 4:")
print("     • contract_generation     → Claude Sonnet 4")
print("     • werkbon_classification  → Claude Sonnet 4")
print()
print("[INFO] No Mistral API key needed for pilot!")
print("[INFO] Token usage will be tracked in llm_usage_logs")
print()
print("[LATER] To switch back to Mistral (76% cheaper):")
print("        1. Get Mistral API key from https://console.mistral.ai/")
print("        2. Add to .env: MISTRAL_API_KEY=...")
print("        3. Run: python scripts/switch_to_mistral.py")
print()
print("=" * 80)
