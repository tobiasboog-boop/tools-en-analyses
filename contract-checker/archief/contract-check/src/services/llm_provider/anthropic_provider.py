"""
Anthropic (Claude) LLM provider implementation.
"""

import os
import time
from typing import Optional
from anthropic import Anthropic

from .base import LLMProvider, LLMRequest, LLMResponse, LLMUsageMetrics


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: Optional[str] = None,
        cost_per_input_token: float = 3.0,  # EUR per 1M tokens
        cost_per_output_token: float = 15.0,  # EUR per 1M tokens
        **kwargs
    ):
        """
        Initialize Anthropic provider.

        Args:
            model: Claude model identifier
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            cost_per_input_token: Cost per 1M input tokens
            cost_per_output_token: Cost per 1M output tokens
            **kwargs: Additional parameters
        """
        super().__init__(
            model=model,
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY"),
            cost_per_input_token=cost_per_input_token,
            cost_per_output_token=cost_per_output_token,
            **kwargs
        )

        if not self.api_key:
            raise ValueError("Anthropic API key is required (ANTHROPIC_API_KEY env var or api_key parameter)")

        self.client = Anthropic(api_key=self.api_key)

    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "anthropic"

    def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate response using Anthropic Claude API.

        Args:
            request: LLM request

        Returns:
            LLM response with content and usage metrics
        """
        start_time = time.time()

        try:
            # Use model from request if specified, otherwise use configured default
            model = request.model or self.model

            # Make API call
            response = self.client.messages.create(
                model=model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                system=request.system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": request.user_message
                    }
                ]
            )

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Extract usage metrics
            usage = LLMUsageMetrics(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                latency_ms=latency_ms,
                cost_per_input_token=self.cost_per_input_token,
                cost_per_output_token=self.cost_per_output_token
            )

            # Extract content (Claude returns list of content blocks)
            content = ""
            if response.content:
                # Get first text block
                for block in response.content:
                    if hasattr(block, 'text'):
                        content = block.text
                        break

            return LLMResponse(
                content=content,
                usage=usage,
                provider=self.provider_name,
                model=model,
                success=True,
                request_id=request.request_id,
                raw_response={
                    "id": response.id,
                    "model": response.model,
                    "role": response.role,
                    "stop_reason": response.stop_reason
                }
            )

        except Exception as e:
            # Calculate latency even on error
            latency_ms = int((time.time() - start_time) * 1000)

            # Return error response
            return LLMResponse(
                content="",
                usage=LLMUsageMetrics(latency_ms=latency_ms),
                provider=self.provider_name,
                model=request.model or self.model,
                success=False,
                error_message=str(e),
                request_id=request.request_id
            )

    def count_tokens(self, text: str) -> int:
        """
        Count tokens using Anthropic's token counter.

        Args:
            text: Text to count tokens for

        Returns:
            Exact token count from Anthropic
        """
        try:
            count = self.client.count_tokens(text)
            return count
        except Exception:
            # Fallback to rough estimate (4 chars per token)
            return len(text) // 4
