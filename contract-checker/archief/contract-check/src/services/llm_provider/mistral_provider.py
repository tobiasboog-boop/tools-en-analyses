"""
Mistral AI LLM provider implementation.
"""

import os
import time
import requests
from typing import Optional, Dict, Any

from .base import LLMProvider, LLMRequest, LLMResponse, LLMUsageMetrics


class MistralProvider(LLMProvider):
    """Mistral AI API provider."""

    def __init__(
        self,
        model: str = "mistral-large-latest",
        api_key: Optional[str] = None,
        api_endpoint: str = "https://api.mistral.ai/v1/chat/completions",
        cost_per_input_token: float = 0.80,  # EUR per 1M tokens
        cost_per_output_token: float = 2.40,  # EUR per 1M tokens
        **kwargs
    ):
        """
        Initialize Mistral provider.

        Args:
            model: Mistral model identifier
            api_key: Mistral API key (defaults to MISTRAL_API_KEY env var)
            api_endpoint: Mistral API endpoint
            cost_per_input_token: Cost per 1M input tokens
            cost_per_output_token: Cost per 1M output tokens
            **kwargs: Additional parameters
        """
        super().__init__(
            model=model,
            api_key=api_key or os.getenv("MISTRAL_API_KEY"),
            api_endpoint=api_endpoint,
            cost_per_input_token=cost_per_input_token,
            cost_per_output_token=cost_per_output_token,
            **kwargs
        )

        if not self.api_key:
            raise ValueError("Mistral API key is required (MISTRAL_API_KEY env var or api_key parameter)")

    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "mistral"

    def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate response using Mistral API.

        Args:
            request: LLM request

        Returns:
            LLM response with content and usage metrics
        """
        start_time = time.time()

        try:
            # Use model from request if specified, otherwise use configured default
            model = request.model or self.model

            # Prepare API request
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": request.system_prompt
                    },
                    {
                        "role": "user",
                        "content": request.user_message
                    }
                ],
                "max_tokens": request.max_tokens,
                "temperature": request.temperature
            }

            # Make API call
            response = requests.post(
                self.api_endpoint,
                headers=headers,
                json=payload,
                timeout=120
            )
            response.raise_for_status()

            # Parse response
            data = response.json()

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Extract usage metrics
            usage_data = data.get("usage", {})
            usage = LLMUsageMetrics(
                input_tokens=usage_data.get("prompt_tokens", 0),
                output_tokens=usage_data.get("completion_tokens", 0),
                latency_ms=latency_ms,
                cost_per_input_token=self.cost_per_input_token,
                cost_per_output_token=self.cost_per_output_token
            )

            # Extract content
            content = ""
            if data.get("choices") and len(data["choices"]) > 0:
                message = data["choices"][0].get("message", {})
                content = message.get("content", "")

            return LLMResponse(
                content=content,
                usage=usage,
                provider=self.provider_name,
                model=model,
                success=True,
                request_id=request.request_id,
                raw_response={
                    "id": data.get("id"),
                    "model": data.get("model"),
                    "finish_reason": data["choices"][0].get("finish_reason") if data.get("choices") else None
                }
            )

        except requests.exceptions.RequestException as e:
            # Calculate latency even on error
            latency_ms = int((time.time() - start_time) * 1000)

            # Return error response
            return LLMResponse(
                content="",
                usage=LLMUsageMetrics(latency_ms=latency_ms),
                provider=self.provider_name,
                model=request.model or self.model,
                success=False,
                error_message=f"Mistral API error: {str(e)}",
                request_id=request.request_id
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
        Count tokens (approximate - Mistral doesn't provide public tokenizer).

        Uses rough estimate of ~4 characters per token.

        Args:
            text: Text to count tokens for

        Returns:
            Approximate token count
        """
        # Rough estimate: average 4 characters per token
        # More accurate would require Mistral's tokenizer library
        return len(text) // 4
