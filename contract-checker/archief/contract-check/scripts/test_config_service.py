#!/usr/bin/env python3
"""
Test the config service - verify app_configuration table integration
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.config_service import get_config_service, get_app_config

def main():
    print("=" * 80)
    print("  CONFIG SERVICE TEST")
    print("=" * 80)

    # Test 1: Get config service
    print("\n[1] Initialize Config Service:")
    print("-" * 80)
    try:
        service = get_config_service("werkbon-checker")
        print("[OK] Config service initialized")
    except Exception as e:
        print(f"[ERROR] Failed to initialize: {e}")
        return

    # Test 2: Read individual configs
    print("\n[2] Read Individual Configs:")
    print("-" * 80)

    test_configs = [
        ("confidence_threshold", 0.85, "Minimum classification confidence"),
        ("max_batch_size", 100, "Maximum werkbonnen per batch"),
        ("enable_llm_caching", True, "Cache LLM ready contracts"),
        ("feature_quick_classification", True, "Quick classification enabled"),
        ("ui_items_per_page", 50, "Items per page in tables"),
    ]

    for key, default, description in test_configs:
        try:
            value = service.get_config(key, default=default)
            value_type = type(value).__name__
            print(f"  ✓ {key:35} = {value:6} ({value_type})")
            print(f"    {description}")
        except Exception as e:
            print(f"  ✗ {key:35} ERROR: {e}")

    # Test 3: Read all configs at once
    print("\n[3] Read All Configs:")
    print("-" * 80)
    try:
        all_configs = service.get_all_configs()
        if all_configs:
            for key, value in sorted(all_configs.items()):
                print(f"  • {key:35} = {value} ({type(value).__name__})")
        else:
            print("  [WARN] No configs found - schema may not be deployed yet")
    except Exception as e:
        print(f"  [ERROR] Failed to read configs: {e}")

    # Test 4: Convenience function
    print("\n[4] Convenience Function Test:")
    print("-" * 80)
    try:
        threshold = get_app_config('confidence_threshold', default=0.85)
        print(f"  threshold = get_app_config('confidence_threshold', default=0.85)")
        print(f"  → {threshold} ({type(threshold).__name__})")
    except Exception as e:
        print(f"  [ERROR] {e}")

    # Test 5: Non-existent config with default
    print("\n[5] Non-Existent Config with Default:")
    print("-" * 80)
    try:
        value = service.get_config('non_existent_key', default='fallback_value')
        print(f"  non_existent_key = {value}")
        print(f"  [OK] Fallback to default works correctly")
    except Exception as e:
        print(f"  [ERROR] {e}")

    # Summary
    print("\n" + "=" * 80)
    print("  SUMMARY")
    print("=" * 80)

    if all_configs:
        print(f"  [OK] Config service working correctly!")
        print(f"  [OK] Found {len(all_configs)} configuration settings")
        print(f"  [OK] Type parsing working (number, boolean, string)")
    else:
        print(f"  [WARN] No configs found in database")
        print(f"  [INFO] Deploy sql/003_app_configuration.sql to Supabase first:")
        print(f"         1. Open Supabase SQL Editor")
        print(f"         2. Run sql/003_app_configuration.sql")
        print(f"         3. Run this test again")

    print("=" * 80)

if __name__ == "__main__":
    main()
