"""
Unified LLM Service

High-level service that combines configuration loading, provider selection,
and usage tracking. This is the main interface for making LLM API calls.
"""

from typing import Optional, Dict, Any
from datetime import datetime

from .llm_provider import LLMRequest, LLMResponse, LLMProvider
from .llm_config_service import get_llm_config_service
from .llm_usage_logger import get_llm_usage_logger


class LLMService:
    """
    Unified LLM service for making AI API calls.

    Features:
    - Automatic provider selection based on Supabase configuration
    - Usage tracking and cost logging
    - Fallback to defaults if Supabase unavailable
    """

    def __init__(
        self,
        enable_supabase: bool = True,
        enable_usage_logging: bool = True
    ):
        """
        Initialize LLM service.

        Args:
            enable_supabase: Use Supabase for configuration (False = use defaults)
            enable_usage_logging: Log usage to Supabase
        """
        self.enable_supabase = enable_supabase
        self.enable_usage_logging = enable_usage_logging

        # Initialize services
        self.config_service = None
        self.usage_logger = None

        if enable_supabase:
            try:
                self.config_service = get_llm_config_service()
            except Exception as e:
                print(f"Warning: Supabase config service unavailable: {e}")
                self.enable_supabase = False

        if enable_usage_logging:
            try:
                self.usage_logger = get_llm_usage_logger()
            except Exception as e:
                print(f"Warning: Supabase usage logger unavailable: {e}")
                self.enable_usage_logging = False

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        action_type: str,
        client_id: Optional[str] = None,
        user_id: Optional[str] = None,
        werkbon_id: Optional[str] = None,
        contract_id: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> LLMResponse:
        """
        Generate LLM response with automatic provider selection and usage tracking.

        Args:
            system_prompt: System prompt
            user_message: User message
            action_type: Action type (e.g., 'werkbon_classification', 'contract_generation')
            client_id: Client identifier
            user_id: User who triggered the request
            werkbon_id: Werkbon ID (if applicable)
            contract_id: Contract ID (if applicable)
            model: Override model (optional)
            max_tokens: Maximum tokens in response
            temperature: Temperature for generation
            metadata: Additional metadata

        Returns:
            LLM response with content and usage metrics
        """
        # Get configured provider
        provider = self._get_provider(action_type, client_id)

        # Create request
        request = LLMRequest(
            system_prompt=system_prompt,
            user_message=user_message,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            action_type=action_type,
            client_id=client_id,
            metadata=metadata or {}
        )

        # Generate response
        response = provider.generate(request)

        # Log usage
        if self.enable_usage_logging and self.usage_logger:
            try:
                self.usage_logger.log_usage(
                    response=response,
                    action_type=action_type,
                    client_id=client_id,
                    user_id=user_id,
                    werkbon_id=werkbon_id,
                    contract_id=contract_id,
                    metadata=metadata
                )
            except Exception as e:
                # Don't fail the main operation if logging fails
                print(f"Warning: Failed to log LLM usage: {e}")

        return response

    def _get_provider(self, action_type: str, client_id: Optional[str] = None) -> LLMProvider:
        """
        Get LLM provider for action type and client.

        Args:
            action_type: Action type
            client_id: Client identifier

        Returns:
            Configured LLM provider
        """
        if self.enable_supabase and self.config_service:
            try:
                return self.config_service.get_provider(action_type, client_id)
            except Exception as e:
                print(f"Warning: Failed to get provider from config service: {e}")

        # Fallback to default provider
        from .llm_provider import LLMProviderFactory
        return LLMProviderFactory.create_default_anthropic()

    def get_provider_info(
        self,
        action_type: str,
        client_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get information about which provider will be used.

        Args:
            action_type: Action type
            client_id: Client identifier

        Returns:
            Dictionary with provider info
        """
        provider = self._get_provider(action_type, client_id)

        return {
            "provider": provider.provider_name,
            "model": provider.model,
            "cost_per_input_token": provider.cost_per_input_token,
            "cost_per_output_token": provider.cost_per_output_token
        }

    def estimate_cost(
        self,
        action_type: str,
        input_text: str,
        estimated_output_tokens: int = 150,
        client_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Estimate cost for an LLM request.

        Args:
            action_type: Action type
            input_text: Input text (system + user message)
            estimated_output_tokens: Expected output tokens
            client_id: Client identifier

        Returns:
            Dictionary with cost estimate
        """
        provider = self._get_provider(action_type, client_id)

        # Count input tokens
        input_tokens = provider.count_tokens(input_text)

        # Calculate cost
        cost = provider.estimate_cost(input_tokens, estimated_output_tokens)

        return {
            "provider": provider.provider_name,
            "model": provider.model,
            "input_tokens": input_tokens,
            "estimated_output_tokens": estimated_output_tokens,
            "total_tokens": input_tokens + estimated_output_tokens,
            "estimated_cost": round(cost, 6)
        }

    def get_usage_stats(
        self,
        client_id: Optional[str] = None,
        action_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get usage statistics from Supabase.

        Args:
            client_id: Filter by client
            action_type: Filter by action type
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary with usage statistics
        """
        if not self.enable_usage_logging or not self.usage_logger:
            return {"error": "Usage logging not enabled"}

        try:
            return self.usage_logger.get_usage_stats(
                client_id=client_id,
                action_type=action_type,
                start_date=start_date,
                end_date=end_date
            )
        except Exception as e:
            return {"error": str(e)}

    def get_usage_by_action(
        self,
        client_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get usage breakdown by action type.

        Args:
            client_id: Filter by client
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary mapping action types to statistics
        """
        if not self.enable_usage_logging or not self.usage_logger:
            return {"error": "Usage logging not enabled"}

        try:
            return self.usage_logger.get_usage_by_action(
                client_id=client_id,
                start_date=start_date,
                end_date=end_date
            )
        except Exception as e:
            return {"error": str(e)}


# Global instance (singleton pattern)
_llm_service: Optional[LLMService] = None


def get_llm_service(
    enable_supabase: bool = True,
    enable_usage_logging: bool = True
) -> LLMService:
    """
    Get global LLM service instance.

    Args:
        enable_supabase: Use Supabase for configuration
        enable_usage_logging: Log usage to Supabase

    Returns:
        LLM service
    """
    global _llm_service

    if _llm_service is None:
        _llm_service = LLMService(
            enable_supabase=enable_supabase,
            enable_usage_logging=enable_usage_logging
        )

    return _llm_service
