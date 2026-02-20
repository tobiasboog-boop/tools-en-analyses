#!/usr/bin/env python3
"""
Inspect current Supabase database structure using REST API
"""

import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Supabase credentials from .env
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_ANON_KEY must be set in .env file")
    exit(1)

def check_table(table_name):
    """Check if table exists and get sample data"""
    url = f"{SUPABASE_URL}/rest/v1/{table_name}"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}"
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            params={"limit": 5}
        )

        if response.status_code == 200:
            data = response.json()
            print(f"[YES] {table_name:30} EXISTS - {len(data)} rows (showing max 5)")
            if data:
                # Show first row structure
                print(f"   Columns: {', '.join(data[0].keys())}")
            return True
        else:
            print(f"[NO]  {table_name:30} NOT FOUND")
            return False

    except Exception as e:
        print(f"[ERR] {table_name:30} ERROR: {e}")
        return False

def main():
    print("="*80)
    print("  SUPABASE DATABASE INSPECTION")
    print(f"  URL: {SUPABASE_URL}")
    print("="*80)

    # Expected Notifica App tables
    print("\n[*] Notifica App Tables (from 001_extend_schema.sql):")
    print("-"*80)
    notifica_tables = [
        "organizations",
        "user_profiles",
        "connections",
        "connection_health_log",
        "connection_notes",
        "source_systems",
        "vpn_profiles",
        "vps_servers",
        "dwh_connections",
        "apps",
        "app_permissions",
        "audit_log"
    ]

    notifica_exists = {}
    for table in notifica_tables:
        notifica_exists[table] = check_table(table)

    # Check for LLM tables
    print("\n[AI] LLM Configuration Tables (to be added):")
    print("-"*80)
    llm_tables = [
        "llm_providers",
        "llm_models",
        "llm_configurations",
        "llm_usage_logs"
    ]

    llm_exists = {}
    for table in llm_tables:
        llm_exists[table] = check_table(table)

    # Get specific data if tables exist
    if notifica_exists.get("apps"):
        print("\n[APP] Apps Registry:")
        print("-"*80)
        url = f"{SUPABASE_URL}/rest/v1/apps"
        headers = {
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}"
        }
        response = requests.get(url, headers=headers, params={"select": "code,name,is_active"})
        if response.status_code == 200:
            apps = response.json()
            for app in apps:
                print(f"   - {app.get('code'):20} {app.get('name'):30} Active: {app.get('is_active')}")

    if notifica_exists.get("organizations"):
        print("\n[ORG] Organizations:")
        print("-"*80)
        url = f"{SUPABASE_URL}/rest/v1/organizations"
        headers = {
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}"
        }
        response = requests.get(url, headers=headers, params={"select": "name,organization_type,is_active", "limit": 10})
        if response.status_code == 200:
            orgs = response.json()
            for org in orgs:
                print(f"   - {org.get('name'):30} Type: {org.get('organization_type'):15} Active: {org.get('is_active')}")

    # Summary
    print("\n" + "="*80)
    print("  SUMMARY")
    print("="*80)

    notifica_count = sum(1 for v in notifica_exists.values() if v)
    llm_count = sum(1 for v in llm_exists.values() if v)

    print(f"[OK] Notifica App Tables: {notifica_count}/{len(notifica_tables)}")
    print(f"[AI] LLM Tables: {llm_count}/{len(llm_tables)}")

    if notifica_count == len(notifica_tables) and llm_count == 0:
        print("\n[OK] READY FOR LLM SCHEMA DEPLOYMENT!")
        print("   Run: sql/002_llm_configuration_integrated.sql in Supabase SQL Editor")
    elif llm_count > 0:
        print("\n[WARN] LLM tables already exist. Check if schema matches or needs update.")
    else:
        print("\n[WARN] Some Notifica App tables missing. Run 001_extend_schema.sql first.")

    print("="*80)

if __name__ == "__main__":
    main()
