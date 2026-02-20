"""
Local LLM provider implementation (Ollama, vLLM, LocalAI, etc.).

Supports any OpenAI-compatible local API endpoint.
"""

import time
import requests
from typing import Optional

from .base import LLMProvider, LLMRequest, LLMResponse, LLMUsageMetrics


class LocalProvider(LLMProvider):
    """
    Local LLM provider for self-hosted models.

    Supports OpenAI-compatible APIs like:
    - Ollama (http://localhost:11434/v1/chat/completions)
    - vLLM (http://localhost:8000/v1/chat/completions)
    - LocalAI (http://localhost:8080/v1/chat/completions)
    - LM Studio (http://localhost:1234/v1/chat/completions)
    """

    def __init__(
        self,
        model: str = "mistral-7b-instruct",
        api_endpoint: str = "http://localhost:11434/v1/chat/completions",
        api_key: Optional[str] = None,  # Optional, some local APIs don't need keys
        cost_per_input_token: float = 0.0,  # Zero cost for local models
        cost_per_output_token: float = 0.0,  # Zero cost for local models
        **kwargs
    ):
        """
        Initialize Local provider.

        Args:
            model: Model identifier (e.g., 'mistral-7b-instruct', 'llama2')
            api_endpoint: Local API endpoint
            api_key: Optional API key (if local server requires authentication)
            cost_per_input_token: Cost per 1M input tokens (default 0)
            cost_per_output_token: Cost per 1M output tokens (default 0)
            **kwargs: Additional parameters
        """
        super().__init__(
            model=model,
            api_key=api_key,
            api_endpoint=api_endpoint,
            cost_per_input_token=cost_per_input_token,
            cost_per_output_token=cost_per_output_token,
            **kwargs
        )

        if not self.api_endpoint:
            raise ValueError("Local API endpoint is required")

    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "local"

    def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate response using local LLM API.

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
                "Content-Type": "application/json"
            }

            # Add authorization if API key provided
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

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
                "temperature": request.temperature,
                "stream": False  # Disable streaming for simplicity
            }

            # Make API call
            response = requests.post(
                self.api_endpoint,
                headers=headers,
                json=payload,
                timeout=300  # Longer timeout for local models
            )
            response.raise_for_status()

            # Parse response
            data = response.json()

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Extract usage metrics
            # Note: Not all local APIs return usage stats
            usage_data = data.get("usage", {})
            usage = LLMUsageMetrics(
                input_tokens=usage_data.get("prompt_tokens", 0),
                output_tokens=usage_data.get("completion_tokens", 0),
                latency_ms=latency_ms,
                cost_per_input_token=self.cost_per_input_token,
                cost_per_output_token=self.cost_per_output_token
            )

            # If usage not provided, estimate tokens
            if usage.input_tokens == 0:
                usage.input_tokens = self.count_tokens(request.system_prompt + request.user_message)

            # Extract content
            content = ""
            if data.get("choices") and len(data["choices"]) > 0:
                message = data["choices"][0].get("message", {})
                content = message.get("content", "")

            # Estimate output tokens if not provided
            if usage.output_tokens == 0 and content:
                usage.output_tokens = self.count_tokens(content)

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
                error_message=f"Local API error: {str(e)}",
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
        Count tokens (approximate).

        Local models don't always expose tokenizers,
        so we use a rough estimate.

        Args:
            text: Text to count tokens for

        Returns:
            Approximate token count
        """
        # Rough estimate: average 4 characters per token
        return len(text) // 4

    def health_check(self) -> bool:
        """
        Check if local API endpoint is accessible.

        Returns:
            True if endpoint responds, False otherwise
        """
        try:
            # Try to reach the endpoint
            response = requests.get(
                self.api_endpoint.replace("/chat/completions", "/models"),
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False
