"""
LLM Usage Logger

Logs all LLM API calls to Supabase for cost tracking and analytics.
"""

import os
from typing import Optional, Dict, Any
from datetime import datetime
from supabase import create_client, Client

from .llm_provider import LLMResponse


class LLMUsageLogger:
    """
    Service for logging LLM usage to Supabase.

    Tracks:
    - Token usage (input/output)
    - Costs
    - Performance metrics (latency)
    - Success/failure
    - Contextual data (client, action, werkbon/contract IDs)
    """

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        application_id: str = "contract-checker"
    ):
        """
        Initialize usage logger.

        Args:
            supabase_url: Supabase project URL (defaults to SUPABASE_URL env var)
            supabase_key: Supabase API key (defaults to SUPABASE_KEY env var)
            application_id: Application identifier for multi-app support
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

    def log_usage(
        self,
        response: LLMResponse,
        action_type: str,
        client_id: Optional[str] = None,
        user_id: Optional[str] = None,
        werkbon_id: Optional[str] = None,
        contract_id: Optional[str] = None,
        config_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Log LLM usage to Supabase.

        Args:
            response: LLM response with usage metrics
            action_type: Action type (e.g., 'werkbon_classification')
            client_id: Client identifier
            user_id: User who triggered the request
            werkbon_id: Werkbon ID (if applicable)
            contract_id: Contract ID (if applicable)
            config_id: Configuration ID used
            metadata: Additional metadata

        Returns:
            Usage log ID (UUID) or None on error
        """
        try:
            log_entry = {
                # Configuration reference
                "config_id": config_id,

                # Application & Request context
                "application_id": self.application_id,
                "client_id": client_id,
                "action_type": action_type,
                "request_id": response.request_id,

                # Model used
                "provider": response.provider,
                "model_name": response.model,

                # Token usage
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,

                # Costs
                "input_cost": response.usage.input_cost,
                "output_cost": response.usage.output_cost,
                "currency": response.usage.currency,

                # Performance
                "latency_ms": response.usage.latency_ms,
                "success": response.success,
                "error_message": response.error_message,

                # Additional context
                "user_id": user_id,
                "werkbon_id": werkbon_id,
                "contract_id": contract_id,
                "metadata": metadata or {},

                # Timestamp
                "created_at": response.timestamp.isoformat()
            }

            result = self.client.table("llm_usage_logs").insert(log_entry).execute()

            if result.data and len(result.data) > 0:
                return result.data[0].get("id")

            return None

        except Exception as e:
            # Log to console but don't fail the main operation
            print(f"Warning: Failed to log LLM usage to Supabase: {e}")
            return None

    def get_usage_stats(
        self,
        client_id: Optional[str] = None,
        action_type: Optional[str] = None,
        provider: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated usage statistics.

        Args:
            client_id: Filter by client
            action_type: Filter by action type
            provider: Filter by provider
            start_date: Start date for filtering
            end_date: End date for filtering

        Returns:
            Dictionary with aggregated statistics
        """
        try:
            query = self.client.table("llm_usage_logs").select("*")

            # Filter by application_id
            query = query.eq("application_id", self.application_id)

            # Apply filters
            if client_id:
                query = query.eq("client_id", client_id)
            if action_type:
                query = query.eq("action_type", action_type)
            if provider:
                query = query.eq("provider", provider)
            if start_date:
                query = query.gte("created_at", start_date.isoformat())
            if end_date:
                query = query.lte("created_at", end_date.isoformat())

            result = query.execute()
            logs = result.data or []

            # Calculate aggregated statistics
            total_requests = len(logs)
            successful_requests = sum(1 for log in logs if log.get("success", False))
            failed_requests = total_requests - successful_requests

            total_input_tokens = sum(log.get("input_tokens", 0) for log in logs)
            total_output_tokens = sum(log.get("output_tokens", 0) for log in logs)
            total_tokens = total_input_tokens + total_output_tokens

            total_cost = sum(
                (log.get("input_cost", 0) or 0) + (log.get("output_cost", 0) or 0)
                for log in logs
            )

            avg_latency = (
                sum(log.get("latency_ms", 0) for log in logs) / total_requests
                if total_requests > 0 else 0
            )

            # Get currency from first log (assume consistent)
            currency = logs[0].get("currency", "EUR") if logs else "EUR"

            return {
                "total_requests": total_requests,
                "successful_requests": successful_requests,
                "failed_requests": failed_requests,
                "success_rate": successful_requests / total_requests if total_requests > 0 else 0,
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "total_tokens": total_tokens,
                "total_cost": round(total_cost, 4),
                "avg_cost_per_request": round(total_cost / total_requests, 6) if total_requests > 0 else 0,
                "avg_latency_ms": round(avg_latency, 0),
                "currency": currency,
                "period": {
                    "start": start_date.isoformat() if start_date else None,
                    "end": end_date.isoformat() if end_date else None
                }
            }

        except Exception as e:
            print(f"Error getting usage stats from Supabase: {e}")
            return {}

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
            start_date: Start date for filtering
            end_date: End date for filtering

        Returns:
            Dictionary mapping action types to their statistics
        """
        try:
            query = self.client.table("llm_usage_logs").select("*")

            # Filter by application_id
            query = query.eq("application_id", self.application_id)

            if client_id:
                query = query.eq("client_id", client_id)
            if start_date:
                query = query.gte("created_at", start_date.isoformat())
            if end_date:
                query = query.lte("created_at", end_date.isoformat())

            result = query.execute()
            logs = result.data or []

            # Group by action type
            action_stats = {}
            for log in logs:
                action = log.get("action_type", "unknown")
                if action not in action_stats:
                    action_stats[action] = []
                action_stats[action].append(log)

            # Calculate stats for each action
            breakdown = {}
            for action, action_logs in action_stats.items():
                total_cost = sum(
                    (log.get("input_cost", 0) or 0) + (log.get("output_cost", 0) or 0)
                    for log in action_logs
                )
                breakdown[action] = {
                    "request_count": len(action_logs),
                    "total_tokens": sum(
                        log.get("input_tokens", 0) + log.get("output_tokens", 0)
                        for log in action_logs
                    ),
                    "total_cost": round(total_cost, 4),
                    "avg_latency_ms": round(
                        sum(log.get("latency_ms", 0) for log in action_logs) / len(action_logs),
                        0
                    )
                }

            return breakdown

        except Exception as e:
            print(f"Error getting usage breakdown from Supabase: {e}")
            return {}

    def get_recent_errors(
        self,
        limit: int = 50,
        client_id: Optional[str] = None,
        action_type: Optional[str] = None
    ) -> list:
        """
        Get recent failed LLM requests.

        Args:
            limit: Maximum number of errors to return
            client_id: Filter by client
            action_type: Filter by action type

        Returns:
            List of error log entries
        """
        try:
            query = (
                self.client
                .table("llm_usage_logs")
                .select("*")
                .eq("application_id", self.application_id)
                .eq("success", False)
                .order("created_at", desc=True)
                .limit(limit)
            )

            if client_id:
                query = query.eq("client_id", client_id)
            if action_type:
                query = query.eq("action_type", action_type)

            result = query.execute()
            return result.data or []

        except Exception as e:
            print(f"Error getting recent errors from Supabase: {e}")
            return []


# Global instance (singleton pattern)
_llm_usage_logger: Optional[LLMUsageLogger] = None


def get_llm_usage_logger() -> LLMUsageLogger:
    """
    Get global LLM usage logger instance.

    Returns:
        LLM usage logger
    """
    global _llm_usage_logger

    if _llm_usage_logger is None:
        _llm_usage_logger = LLMUsageLogger()

    return _llm_usage_logger
