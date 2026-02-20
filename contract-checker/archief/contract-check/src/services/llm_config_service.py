"""
LLM Configuration Service

Manages LLM configurations from Supabase database.
Handles configuration loading, caching, and fallback strategies.
"""

import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from supabase import create_client, Client

from .llm_provider import LLMProvider, LLMProviderFactory


class LLMConfigService:
    """
    Service for loading and managing LLM configurations from Supabase.

    Features:
    - Configuration lookup by client and action type
    - In-memory caching with TTL
    - Fallback to defaults
    - Priority-based selection
    """

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        application_id: str = "contract-checker",
        cache_ttl_seconds: int = 300  # 5 minutes
    ):
        """
        Initialize LLM configuration service.

        Args:
            supabase_url: Supabase project URL (defaults to SUPABASE_URL env var)
            supabase_key: Supabase API key (defaults to SUPABASE_KEY env var)
            application_id: Application identifier for multi-app support
            cache_ttl_seconds: Cache TTL in seconds
        """
        self.supabase_url = supabase_url or os.getenv("SUPABASE_URL")
        self.supabase_key = supabase_key or os.getenv("SUPABASE_KEY")
        self.application_id = application_id

        if not self.supabase_url or not self.supabase_key:
            raise ValueError(
                "Supabase URL and Key are required. "
                "Set SUPABASE_URL and SUPABASE_KEY environment variables."
            )

        self.client: Client = create_client(self.supabase_url, self.supabase_key)
        self.cache_ttl_seconds = cache_ttl_seconds

        # In-memory cache: {(application_id, client_id, action_type): (config, timestamp)}
        self._cache: Dict[tuple, tuple] = {}

    def get_provider(
        self,
        action_type: str,
        client_id: Optional[str] = None,
        use_cache: bool = True
    ) -> LLMProvider:
        """
        Get configured LLM provider for action type and client.

        Lookup strategy:
        1. Check cache if enabled
        2. Try client-specific config (application_id + client_id + action_type)
        3. Fallback to default config (application_id + NULL client_id + action_type)
        4. Fallback to hardcoded default (Anthropic)

        Args:
            action_type: Action type (e.g., 'contract_generation', 'werkbon_classification')
            client_id: Client identifier (optional)
            use_cache: Whether to use cached configuration

        Returns:
            Configured LLM provider instance
        """
        cache_key = (self.application_id, client_id, action_type)

        # Check cache
        if use_cache and cache_key in self._cache:
            config, timestamp = self._cache[cache_key]
            if datetime.now() - timestamp < timedelta(seconds=self.cache_ttl_seconds):
                return LLMProviderFactory.from_config(config)

        # Load from Supabase
        config = self._load_config(action_type, client_id)

        if config:
            # Cache the configuration
            self._cache[cache_key] = (config, datetime.now())
            return LLMProviderFactory.from_config(config)

        # Fallback to default provider
        return self._get_fallback_provider(action_type)

    def _load_config(
        self,
        action_type: str,
        client_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Load configuration from Supabase.

        Args:
            action_type: Action type
            client_id: Client identifier (optional)

        Returns:
            Configuration dictionary or None if not found
        """
        try:
            # Build query with application_id
            query = (
                self.client
                .table("llm_configurations")
                .select("*")
                .eq("application_id", self.application_id)
                .eq("action_type", action_type)
                .eq("is_active", True)
            )

            # Try client-specific config first
            if client_id:
                result = query.eq("client_id", client_id).order("priority", desc=True).limit(1).execute()
                if result.data and len(result.data) > 0:
                    return result.data[0]

            # Fallback to default config (client_id = NULL)
            result = query.is_("client_id", "null").order("priority", desc=True).limit(1).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]

            return None

        except Exception as e:
            print(f"Error loading LLM config from Supabase: {e}")
            return None

    def _get_fallback_provider(self, action_type: str) -> LLMProvider:
        """
        Get hardcoded fallback provider.

        Args:
            action_type: Action type

        Returns:
            Default LLM provider
        """
        # Default to Anthropic for all actions if no config found
        return LLMProviderFactory.create_default_anthropic()

    def clear_cache(self, client_id: Optional[str] = None, action_type: Optional[str] = None):
        """
        Clear configuration cache.

        Args:
            client_id: Clear specific client (optional, None = all)
            action_type: Clear specific action (optional, None = all)
        """
        if client_id is None and action_type is None:
            # Clear entire cache
            self._cache.clear()
        else:
            # Clear specific entries
            keys_to_remove = [
                key for key in self._cache.keys()
                if (client_id is None or key[0] == client_id) and
                   (action_type is None or key[1] == action_type)
            ]
            for key in keys_to_remove:
                del self._cache[key]

    def refresh_config(self, action_type: str, client_id: Optional[str] = None) -> LLMProvider:
        """
        Force refresh configuration from Supabase.

        Args:
            action_type: Action type
            client_id: Client identifier (optional)

        Returns:
            Refreshed LLM provider instance
        """
        # Clear cache for this specific config
        self.clear_cache(client_id=client_id, action_type=action_type)

        # Reload from Supabase
        return self.get_provider(action_type, client_id, use_cache=False)

    def list_configurations(
        self,
        action_type: Optional[str] = None,
        client_id: Optional[str] = None,
        active_only: bool = True,
        application_id: Optional[str] = None
    ) -> list:
        """
        List all configurations from Supabase.

        Args:
            action_type: Filter by action type (optional)
            client_id: Filter by client (optional)
            active_only: Only return active configs
            application_id: Filter by application (defaults to instance application_id)

        Returns:
            List of configuration dictionaries
        """
        try:
            query = self.client.table("llm_configurations").select("*")

            # Use provided application_id or default to instance application_id
            app_id = application_id or self.application_id
            query = query.eq("application_id", app_id)

            if action_type:
                query = query.eq("action_type", action_type)
            if client_id:
                query = query.eq("client_id", client_id)
            if active_only:
                query = query.eq("is_active", True)

            result = query.order("priority", desc=True).execute()
            return result.data or []

        except Exception as e:
            print(f"Error listing LLM configs from Supabase: {e}")
            return []

    def create_configuration(self, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create new LLM configuration in Supabase.

        Args:
            config: Configuration dictionary

        Returns:
            Created configuration or None on error
        """
        try:
            result = self.client.table("llm_configurations").insert(config).execute()
            if result.data and len(result.data) > 0:
                # Clear cache for affected client/action
                self.clear_cache(
                    client_id=config.get("client_id"),
                    action_type=config.get("action_type")
                )
                return result.data[0]
            return None

        except Exception as e:
            print(f"Error creating LLM config in Supabase: {e}")
            return None

    def update_configuration(
        self,
        config_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update existing LLM configuration in Supabase.

        Args:
            config_id: Configuration ID (UUID)
            updates: Fields to update

        Returns:
            Updated configuration or None on error
        """
        try:
            # Add updated_at timestamp
            updates["updated_at"] = datetime.now().isoformat()

            result = (
                self.client
                .table("llm_configurations")
                .update(updates)
                .eq("id", config_id)
                .execute()
            )

            if result.data and len(result.data) > 0:
                updated_config = result.data[0]
                # Clear cache for affected client/action
                self.clear_cache(
                    client_id=updated_config.get("client_id"),
                    action_type=updated_config.get("action_type")
                )
                return updated_config
            return None

        except Exception as e:
            print(f"Error updating LLM config in Supabase: {e}")
            return None

    def delete_configuration(self, config_id: str) -> bool:
        """
        Delete LLM configuration from Supabase.

        Args:
            config_id: Configuration ID (UUID)

        Returns:
            True if deleted successfully
        """
        try:
            # First get the config to know which cache to clear
            config_result = (
                self.client
                .table("llm_configurations")
                .select("client_id, action_type")
                .eq("id", config_id)
                .execute()
            )

            if config_result.data and len(config_result.data) > 0:
                config = config_result.data[0]

                # Delete the config
                self.client.table("llm_configurations").delete().eq("id", config_id).execute()

                # Clear cache
                self.clear_cache(
                    client_id=config.get("client_id"),
                    action_type=config.get("action_type")
                )
                return True

            return False

        except Exception as e:
            print(f"Error deleting LLM config from Supabase: {e}")
            return False


# Global instance (singleton pattern)
_llm_config_service: Optional[LLMConfigService] = None


def get_llm_config_service() -> LLMConfigService:
    """
    Get global LLM configuration service instance.

    Returns:
        LLM configuration service
    """
    global _llm_config_service

    if _llm_config_service is None:
        _llm_config_service = LLMConfigService()

    return _llm_config_service
