#!/usr/bin/env python3
"""
App Configuration Service - Read app-wide settings from Supabase
"""

import os
from typing import Optional, Any, Dict
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # Use service key for backend

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env file")


class ConfigService:
    """Service for reading app configuration from Supabase"""

    def __init__(self, app_code: str = "werkbon-checker"):
        """
        Initialize config service

        Args:
            app_code: Application code (e.g., 'werkbon-checker')
        """
        self.app_code = app_code
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        self._cache: Dict[tuple, Any] = {}

    def get_config(
        self,
        config_key: str,
        organization_id: Optional[str] = None,
        default: Any = None,
        parse_type: bool = True
    ) -> Any:
        """
        Get app configuration value

        Args:
            config_key: Configuration key (e.g., 'confidence_threshold')
            organization_id: Optional organization ID for org-specific override
            default: Default value if config not found
            parse_type: Automatically parse value based on value_type field

        Returns:
            Configuration value, parsed to correct type if parse_type=True
        """
        # Check cache
        cache_key = (config_key, organization_id)
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            # Use Supabase function for proper fallback logic
            result = self.client.rpc(
                "get_app_config",
                {
                    "p_app_code": self.app_code,
                    "p_config_key": config_key,
                    "p_organization_id": organization_id
                }
            ).execute()

            if result.data is None:
                self._cache[cache_key] = default
                return default

            value_str = result.data

            # If we want just the raw string, return it
            if not parse_type:
                self._cache[cache_key] = value_str
                return value_str

            # Get value_type to parse correctly
            query = (
                self.client.table("app_configuration")
                .select("value_type")
                .eq("config_key", config_key)
                .limit(1)
            )

            # Get app_id first
            app_result = self.client.table("apps").select("id").eq("code", self.app_code).single().execute()
            if not app_result.data:
                self._cache[cache_key] = default
                return default

            app_id = app_result.data["id"]
            query = query.eq("app_id", app_id)

            if organization_id:
                query = query.eq("organization_id", organization_id)
            else:
                query = query.is_("organization_id", "null")

            type_result = query.execute()

            if not type_result.data:
                self._cache[cache_key] = value_str
                return value_str

            value_type = type_result.data[0]["value_type"]

            # Parse based on type
            parsed_value = self._parse_value(value_str, value_type, default)
            self._cache[cache_key] = parsed_value
            return parsed_value

        except Exception as e:
            print(f"Error reading config {config_key}: {e}")
            self._cache[cache_key] = default
            return default

    def _parse_value(self, value_str: str, value_type: str, default: Any) -> Any:
        """Parse string value to correct type"""
        if value_str is None:
            return default

        try:
            if value_type == "number":
                # Try int first, then float
                if "." in value_str:
                    return float(value_str)
                return int(value_str)
            elif value_type == "boolean":
                return value_str.lower() in ("true", "1", "yes", "on")
            elif value_type == "json":
                import json
                return json.loads(value_str)
            else:  # string or unknown
                return value_str
        except Exception as e:
            print(f"Error parsing value '{value_str}' as {value_type}: {e}")
            return default

    def clear_cache(self):
        """Clear configuration cache"""
        self._cache.clear()

    def get_all_configs(self, organization_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get all configurations for this app

        Args:
            organization_id: Optional organization ID

        Returns:
            Dictionary of config_key -> value
        """
        try:
            # Get app_id
            app_result = self.client.table("apps").select("id").eq("code", self.app_code).single().execute()
            if not app_result.data:
                return {}

            app_id = app_result.data["id"]

            # Query configs
            query = (
                self.client.table("app_configuration")
                .select("config_key, config_value, value_type")
                .eq("app_id", app_id)
                .eq("is_active", True)
            )

            if organization_id:
                query = query.eq("organization_id", organization_id)
            else:
                query = query.is_("organization_id", "null")

            result = query.execute()

            # Parse all values
            configs = {}
            for row in result.data:
                key = row["config_key"]
                value_str = row["config_value"]
                value_type = row["value_type"]
                configs[key] = self._parse_value(value_str, value_type, None)

            return configs

        except Exception as e:
            print(f"Error reading all configs: {e}")
            return {}


# Singleton instance for easy import
_config_service: Optional[ConfigService] = None

def get_config_service(app_code: str = "werkbon-checker") -> ConfigService:
    """Get or create config service singleton"""
    global _config_service
    if _config_service is None or _config_service.app_code != app_code:
        _config_service = ConfigService(app_code)
    return _config_service


# Convenience function
def get_app_config(
    config_key: str,
    app_code: str = "werkbon-checker",
    organization_id: Optional[str] = None,
    default: Any = None
) -> Any:
    """
    Convenience function to get a single config value

    Args:
        config_key: Configuration key
        app_code: Application code (default: 'werkbon-checker')
        organization_id: Optional organization ID
        default: Default value if not found

    Returns:
        Configuration value

    Example:
        >>> threshold = get_app_config('confidence_threshold', default=0.85)
        >>> # Returns: 0.85 (float)

        >>> batch_size = get_app_config('max_batch_size', default=100)
        >>> # Returns: 100 (int)

        >>> enabled = get_app_config('feature_quick_classification', default=True)
        >>> # Returns: True (bool)
    """
    service = get_config_service(app_code)
    return service.get_config(config_key, organization_id, default)


if __name__ == "__main__":
    # Test the config service
    print("Testing Config Service...")
    print("=" * 80)

    service = ConfigService("werkbon-checker")

    # Test individual configs
    print("\n[1] Individual Configs:")
    print(f"  confidence_threshold: {service.get_config('confidence_threshold', default=0.85)}")
    print(f"  max_batch_size: {service.get_config('max_batch_size', default=100)}")
    print(f"  feature_quick_classification: {service.get_config('feature_quick_classification', default=True)}")
    print(f"  ui_items_per_page: {service.get_config('ui_items_per_page', default=50)}")

    # Test all configs
    print("\n[2] All Configs:")
    all_configs = service.get_all_configs()
    for key, value in sorted(all_configs.items()):
        print(f"  {key}: {value} ({type(value).__name__})")

    # Test convenience function
    print("\n[3] Convenience Function:")
    threshold = get_app_config('confidence_threshold', default=0.85)
    print(f"  threshold = {threshold} (type: {type(threshold).__name__})")

    print("\n" + "=" * 80)
    print("[OK] Config service test complete!")
