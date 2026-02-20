"""
LLM Provider Factory

Creates appropriate provider instances based on configuration.
"""

from typing import Dict, Any, Optional
import os

from .base import LLMProvider
from .anthropic_provider import AnthropicProvider
from .mistral_provider import MistralProvider
from .openai_provider import OpenAIProvider
from .local_provider import LocalProvider


class LLMProviderFactory:
    """
    Factory for creating LLM provider instances.

    Supports creating providers from:
    - Configuration dictionaries (from Supabase)
    - Direct instantiation with parameters
    """

    # Provider class mapping
    PROVIDERS = {
        "anthropic": AnthropicProvider,
        "mistral": MistralProvider,
        "openai": OpenAIProvider,
        "local": LocalProvider
    }

    @staticmethod
    def create_provider(
        provider: str,
        model: str,
        api_key: Optional[str] = None,
        api_endpoint: Optional[str] = None,
        cost_per_input_token: float = 0.0,
        cost_per_output_token: float = 0.0,
        **kwargs
    ) -> LLMProvider:
        """
        Create LLM provider instance.

        Args:
            provider: Provider name ('anthropic', 'mistral', 'openai', 'local')
            model: Model identifier
            api_key: API key (optional, can use env vars)
            api_endpoint: API endpoint (for custom/local endpoints)
            cost_per_input_token: Cost per 1M input tokens
            cost_per_output_token: Cost per 1M output tokens
            **kwargs: Additional provider-specific parameters

        Returns:
            Configured LLM provider instance

        Raises:
            ValueError: If provider is not supported
        """
        provider_lower = provider.lower()

        if provider_lower not in LLMProviderFactory.PROVIDERS:
            raise ValueError(
                f"Unsupported provider: {provider}. "
                f"Supported providers: {', '.join(LLMProviderFactory.PROVIDERS.keys())}"
            )

        provider_class = LLMProviderFactory.PROVIDERS[provider_lower]

        return provider_class(
            model=model,
            api_key=api_key,
            api_endpoint=api_endpoint,
            cost_per_input_token=cost_per_input_token,
            cost_per_output_token=cost_per_output_token,
            **kwargs
        )

    @staticmethod
    def from_config(config: Dict[str, Any]) -> LLMProvider:
        """
        Create provider from configuration dictionary.

        Expected config structure (matches Supabase schema):
        {
            "provider": "anthropic",
            "model_name": "claude-sonnet-4-20250514",
            "api_endpoint": "...",  # Optional
            "api_key_env_var": "ANTHROPIC_API_KEY",  # Optional
            "max_tokens": 1024,
            "temperature": 0.0,
            "cost_per_input_token": 3.0,
            "cost_per_output_token": 15.0,
            "additional_params": {...}  # Optional JSON
        }

        Args:
            config: Configuration dictionary

        Returns:
            Configured LLM provider instance

        Raises:
            ValueError: If required config fields are missing
        """
        # Required fields
        provider = config.get("provider")
        model = config.get("model_name")

        if not provider:
            raise ValueError("Provider is required in config")
        if not model:
            raise ValueError("Model name is required in config")

        # Optional fields
        api_endpoint = config.get("api_endpoint")
        api_key_env_var = config.get("api_key_env_var")

        # Get API key from env var if specified
        api_key = None
        if api_key_env_var:
            api_key = os.getenv(api_key_env_var)

        # Cost configuration
        cost_per_input_token = float(config.get("cost_per_input_token", 0.0))
        cost_per_output_token = float(config.get("cost_per_output_token", 0.0))

        # Additional parameters
        additional_params = config.get("additional_params", {}) or {}

        return LLMProviderFactory.create_provider(
            provider=provider,
            model=model,
            api_key=api_key,
            api_endpoint=api_endpoint,
            cost_per_input_token=cost_per_input_token,
            cost_per_output_token=cost_per_output_token,
            **additional_params
        )

    @staticmethod
    def create_default_anthropic() -> AnthropicProvider:
        """
        Create default Anthropic provider with standard settings.

        Returns:
            Configured Anthropic provider
        """
        return AnthropicProvider(
            model="claude-sonnet-4-20250514",
            cost_per_input_token=3.0,
            cost_per_output_token=15.0
        )

    @staticmethod
    def create_default_mistral() -> MistralProvider:
        """
        Create default Mistral provider with standard settings.

        Returns:
            Configured Mistral provider
        """
        return MistralProvider(
            model="mistral-large-latest",
            cost_per_input_token=0.80,
            cost_per_output_token=2.40
        )

    @staticmethod
    def create_local_mistral(
        endpoint: str = "http://localhost:11434/v1/chat/completions",
        model: str = "mistral-7b-instruct"
    ) -> LocalProvider:
        """
        Create local Mistral provider for self-hosted deployment.

        Args:
            endpoint: Local API endpoint
            model: Model identifier

        Returns:
            Configured local provider
        """
        return LocalProvider(
            model=model,
            api_endpoint=endpoint,
            cost_per_input_token=0.0,
            cost_per_output_token=0.0
        )
