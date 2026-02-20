"""
OpenAI LLM provider implementation.
"""

import os
import time
from typing import Optional
import openai

from .base import LLMProvider, LLMRequest, LLMResponse, LLMUsageMetrics


class OpenAIProvider(LLMProvider):
    """OpenAI GPT API provider."""

    def __init__(
        self,
        model: str = "gpt-4-turbo-preview",
        api_key: Optional[str] = None,
        cost_per_input_token: float = 10.0,  # EUR per 1M tokens (GPT-4 Turbo)
        cost_per_output_token: float = 30.0,  # EUR per 1M tokens
        **kwargs
    ):
        """
        Initialize OpenAI provider.

        Args:
            model: OpenAI model identifier
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            cost_per_input_token: Cost per 1M input tokens
            cost_per_output_token: Cost per 1M output tokens
            **kwargs: Additional parameters
        """
        super().__init__(
            model=model,
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            cost_per_input_token=cost_per_input_token,
            cost_per_output_token=cost_per_output_token,
            **kwargs
        )

        if not self.api_key:
            raise ValueError("OpenAI API key is required (OPENAI_API_KEY env var or api_key parameter)")

        # Configure OpenAI client
        openai.api_key = self.api_key

    @property
    def provider_name(self) -> str:
        """Return provider name."""
        return "openai"

    def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate response using OpenAI API.

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
            response = openai.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": request.system_prompt
                    },
                    {
                        "role": "user",
                        "content": request.user_message
                    }
                ],
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Extract usage metrics
            usage = LLMUsageMetrics(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                latency_ms=latency_ms,
                cost_per_input_token=self.cost_per_input_token,
                cost_per_output_token=self.cost_per_output_token
            )

            # Extract content
            content = ""
            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content or ""

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
                    "finish_reason": response.choices[0].finish_reason if response.choices else None
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
                error_message=f"OpenAI API error: {str(e)}",
                request_id=request.request_id
            )

    def count_tokens(self, text: str) -> int:
        """
        Count tokens (approximate).

        For accurate counting, would need tiktoken library.

        Args:
            text: Text to count tokens for

        Returns:
            Approximate token count
        """
        try:
            # Try using tiktoken if available
            import tiktoken
            encoding = tiktoken.encoding_for_model(self.model)
            return len(encoding.encode(text))
        except ImportError:
            # Fallback to rough estimate (4 chars per token)
            return len(text) // 4
        except Exception:
            # Fallback to rough estimate
            return len(text) // 4
