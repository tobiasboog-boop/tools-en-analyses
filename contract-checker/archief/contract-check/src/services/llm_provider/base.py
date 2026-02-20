"""
Base classes and interfaces for LLM provider abstraction.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid


@dataclass
class LLMUsageMetrics:
    """Token usage and cost metrics for an LLM API call."""

    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0

    cost_per_input_token: float = 0.0  # Per 1M tokens
    cost_per_output_token: float = 0.0  # Per 1M tokens
    currency: str = "EUR"

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens

    @property
    def input_cost(self) -> float:
        """Cost for input tokens."""
        return (self.input_tokens / 1_000_000) * self.cost_per_input_token

    @property
    def output_cost(self) -> float:
        """Cost for output tokens."""
        return (self.output_tokens / 1_000_000) * self.cost_per_output_token

    @property
    def total_cost(self) -> float:
        """Total cost for the API call."""
        return self.input_cost + self.output_cost


@dataclass
class LLMRequest:
    """Request to an LLM provider."""

    # Required fields
    system_prompt: str
    user_message: str

    # Optional fields
    model: Optional[str] = None
    max_tokens: int = 1024
    temperature: float = 0.0

    # Context for tracking
    action_type: str = "unknown"
    client_id: Optional[str] = None
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert request to dictionary."""
        return {
            "system_prompt": self.system_prompt,
            "user_message": self.user_message,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "action_type": self.action_type,
            "client_id": self.client_id,
            "request_id": self.request_id,
            "metadata": self.metadata
        }


@dataclass
class LLMResponse:
    """Response from an LLM provider."""

    # Response content
    content: str

    # Usage metrics
    usage: LLMUsageMetrics

    # Provider info
    provider: str
    model: str

    # Status
    success: bool = True
    error_message: Optional[str] = None

    # Tracking
    request_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    # Raw response for debugging
    raw_response: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary."""
        return {
            "content": self.content,
            "provider": self.provider,
            "model": self.model,
            "success": self.success,
            "error_message": self.error_message,
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
            "usage": {
                "input_tokens": self.usage.input_tokens,
                "output_tokens": self.usage.output_tokens,
                "total_tokens": self.usage.total_tokens,
                "latency_ms": self.usage.latency_ms,
                "input_cost": self.usage.input_cost,
                "output_cost": self.usage.output_cost,
                "total_cost": self.usage.total_cost,
                "currency": self.usage.currency
            }
        }


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All providers must implement this interface to support
    configuration-driven LLM selection and usage tracking.
    """

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        api_endpoint: Optional[str] = None,
        cost_per_input_token: float = 0.0,
        cost_per_output_token: float = 0.0,
        **kwargs
    ):
        """
        Initialize LLM provider.

        Args:
            model: Model identifier (e.g., 'claude-sonnet-4-20250514')
            api_key: API key for authentication
            api_endpoint: Custom API endpoint (for local/alternative endpoints)
            cost_per_input_token: Cost per 1M input tokens
            cost_per_output_token: Cost per 1M output tokens
            **kwargs: Additional provider-specific parameters
        """
        self.model = model
        self.api_key = api_key
        self.api_endpoint = api_endpoint
        self.cost_per_input_token = cost_per_input_token
        self.cost_per_output_token = cost_per_output_token
        self.additional_params = kwargs

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate a response from the LLM.

        Args:
            request: LLM request with prompts and parameters

        Returns:
            LLM response with content and usage metrics

        Raises:
            Exception: If the API call fails
        """
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text (approximate if provider doesn't have tokenizer).

        Args:
            text: Text to count tokens for

        Returns:
            Approximate token count
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'anthropic', 'mistral')."""
        pass

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost for token usage.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in configured currency
        """
        input_cost = (input_tokens / 1_000_000) * self.cost_per_input_token
        output_cost = (output_tokens / 1_000_000) * self.cost_per_output_token
        return input_cost + output_cost

    def __repr__(self) -> str:
        """String representation."""
        return f"{self.__class__.__name__}(model={self.model})"
