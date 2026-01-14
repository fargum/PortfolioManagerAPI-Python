"""Business metrics service for OpenTelemetry instrumentation.

This module provides custom business metrics matching the C# PortfolioManager patterns:
- Counters for tracking operation counts
- Histograms for measuring operation durations
- Consistent tagging with account_id, status, etc.
"""
import time
from contextlib import contextmanager
from functools import lru_cache
from typing import Generator, Optional

from opentelemetry import metrics

# Meter for business metrics
_meter = metrics.get_meter("PortfolioManager.PythonAPI.Business", "1.0.0")

# Counters
_holdings_requests_total = _meter.create_counter(
    name="holdings_requests_total",
    description="Total number of holdings API requests",
    unit="1"
)

_holdings_mutations_total = _meter.create_counter(
    name="holdings_mutations_total",
    description="Total number of holdings mutation operations (add/update/delete)",
    unit="1"
)

_ai_chat_requests_total = _meter.create_counter(
    name="ai_chat_requests_total",
    description="Total number of AI chat requests",
    unit="1"
)

_price_requests_total = _meter.create_counter(
    name="price_requests_total",
    description="Total number of price quote requests",
    unit="1"
)

# Histograms for duration tracking
_holdings_request_duration = _meter.create_histogram(
    name="holdings_request_duration_seconds",
    description="Duration of holdings retrieval operations in seconds",
    unit="s"
)

_holdings_mutation_duration = _meter.create_histogram(
    name="holdings_mutation_duration_seconds",
    description="Duration of holdings mutation operations in seconds",
    unit="s"
)

_ai_chat_request_duration = _meter.create_histogram(
    name="ai_chat_request_duration_seconds",
    description="Duration of AI chat request processing in seconds",
    unit="s"
)

_price_request_duration = _meter.create_histogram(
    name="price_request_duration_seconds",
    description="Duration of price fetch operations in seconds",
    unit="s"
)

# LLM-specific metrics
_llm_requests_total = _meter.create_counter(
    name="llm_requests_total",
    description="Total number of LLM API requests",
    unit="1"
)

_llm_request_duration = _meter.create_histogram(
    name="llm_request_duration_seconds",
    description="Duration of LLM API calls in seconds",
    unit="s"
)

_llm_tokens_total = _meter.create_counter(
    name="llm_tokens_total",
    description="Total tokens used in LLM requests",
    unit="1"
)

_llm_prompt_tokens = _meter.create_histogram(
    name="llm_prompt_tokens",
    description="Number of prompt tokens per request",
    unit="1"
)

_llm_completion_tokens = _meter.create_histogram(
    name="llm_completion_tokens",
    description="Number of completion tokens per request",
    unit="1"
)

_tool_executions_total = _meter.create_counter(
    name="tool_executions_total",
    description="Total number of tool executions by the agent",
    unit="1"
)

_tool_execution_duration = _meter.create_histogram(
    name="tool_execution_duration_seconds",
    description="Duration of tool executions in seconds",
    unit="s"
)


class MetricsService:
    """Service for recording business metrics."""

    def increment_holdings_requests(
        self,
        account_id: Optional[int] = None,
        status: str = "requested"
    ) -> None:
        """Increment holdings request counter."""
        attributes = {"status": status}
        if account_id is not None:
            attributes["account_id"] = str(account_id)
        _holdings_requests_total.add(1, attributes)

    def record_holdings_request_duration(
        self,
        duration_seconds: float,
        account_id: Optional[int] = None,
        status: str = "success"
    ) -> None:
        """Record holdings request duration."""
        attributes = {"status": status}
        if account_id is not None:
            attributes["account_id"] = str(account_id)
        _holdings_request_duration.record(duration_seconds, attributes)

    def increment_holdings_mutations(
        self,
        operation: str,
        account_id: Optional[int] = None,
        status: str = "success"
    ) -> None:
        """Increment holdings mutation counter (add/update/delete)."""
        attributes = {"operation": operation, "status": status}
        if account_id is not None:
            attributes["account_id"] = str(account_id)
        _holdings_mutations_total.add(1, attributes)

    def record_holdings_mutation_duration(
        self,
        duration_seconds: float,
        operation: str,
        account_id: Optional[int] = None,
        status: str = "success"
    ) -> None:
        """Record holdings mutation duration."""
        attributes = {"operation": operation, "status": status}
        if account_id is not None:
            attributes["account_id"] = str(account_id)
        _holdings_mutation_duration.record(duration_seconds, attributes)

    def increment_ai_chat_requests(
        self,
        account_id: Optional[int] = None,
        mode: str = "ui",
        status: str = "requested"
    ) -> None:
        """Increment AI chat request counter."""
        attributes = {"mode": mode, "status": status}
        if account_id is not None:
            attributes["account_id"] = str(account_id)
        _ai_chat_requests_total.add(1, attributes)

    def record_ai_chat_request_duration(
        self,
        duration_seconds: float,
        account_id: Optional[int] = None,
        mode: str = "ui",
        model: Optional[str] = None,
        status: str = "success"
    ) -> None:
        """Record AI chat request duration."""
        attributes = {"mode": mode, "status": status}
        if account_id is not None:
            attributes["account_id"] = str(account_id)
        if model:
            attributes["model"] = model
        _ai_chat_request_duration.record(duration_seconds, attributes)

    def increment_price_requests(
        self,
        symbol: Optional[str] = None,
        status: str = "requested"
    ) -> None:
        """Increment price request counter."""
        attributes = {"status": status}
        if symbol:
            attributes["symbol"] = symbol
        _price_requests_total.add(1, attributes)

    def record_price_request_duration(
        self,
        duration_seconds: float,
        symbol: Optional[str] = None,
        status: str = "success"
    ) -> None:
        """Record price request duration."""
        attributes = {"status": status}
        if symbol:
            attributes["symbol"] = symbol
        _price_request_duration.record(duration_seconds, attributes)

    @contextmanager
    def track_holdings_request(
        self, account_id: Optional[int] = None
    ) -> Generator[None, None, None]:
        """Context manager for tracking holdings request metrics."""
        self.increment_holdings_requests(account_id, "requested")
        start_time = time.perf_counter()
        status = "success"
        try:
            yield
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.perf_counter() - start_time
            self.record_holdings_request_duration(duration, account_id, status)

    @contextmanager
    def track_holdings_mutation(
        self,
        operation: str,
        account_id: Optional[int] = None
    ) -> Generator[None, None, None]:
        """Context manager for tracking holdings mutation metrics."""
        start_time = time.perf_counter()
        status = "success"
        try:
            yield
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.perf_counter() - start_time
            self.increment_holdings_mutations(operation, account_id, status)
            self.record_holdings_mutation_duration(
                duration, operation, account_id, status
            )

    @contextmanager
    def track_ai_chat_request(
        self,
        account_id: Optional[int] = None,
        mode: str = "ui",
        model: Optional[str] = None
    ) -> Generator[None, None, None]:
        """Context manager for tracking AI chat request metrics."""
        self.increment_ai_chat_requests(account_id, mode, "requested")
        start_time = time.perf_counter()
        status = "success"
        try:
            yield
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.perf_counter() - start_time
            self.record_ai_chat_request_duration(
                duration, account_id, mode, model, status
            )

    # LLM-specific metrics methods
    def increment_llm_requests(
        self,
        model: Optional[str] = None,
        status: str = "success"
    ) -> None:
        """Increment LLM request counter."""
        attributes = {"status": status}
        if model:
            attributes["model"] = model
        _llm_requests_total.add(1, attributes)

    def record_llm_request_duration(
        self,
        duration_seconds: float,
        model: Optional[str] = None,
        status: str = "success"
    ) -> None:
        """Record LLM request duration."""
        attributes = {"status": status}
        if model:
            attributes["model"] = model
        _llm_request_duration.record(duration_seconds, attributes)

    def record_llm_tokens(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: Optional[str] = None
    ) -> None:
        """Record LLM token usage."""
        attributes = {}
        if model:
            attributes["model"] = model

        # Record total tokens
        total_tokens = prompt_tokens + completion_tokens
        _llm_tokens_total.add(total_tokens, {**attributes, "type": "total"})
        _llm_tokens_total.add(prompt_tokens, {**attributes, "type": "prompt"})
        _llm_tokens_total.add(completion_tokens, {**attributes, "type": "completion"})

        # Record histogram distributions
        _llm_prompt_tokens.record(prompt_tokens, attributes)
        _llm_completion_tokens.record(completion_tokens, attributes)

    def increment_tool_executions(
        self,
        tool_name: str,
        status: str = "success"
    ) -> None:
        """Increment tool execution counter."""
        _tool_executions_total.add(1, {"tool": tool_name, "status": status})

    def record_tool_execution_duration(
        self,
        duration_seconds: float,
        tool_name: str,
        status: str = "success"
    ) -> None:
        """Record tool execution duration."""
        _tool_execution_duration.record(
            duration_seconds,
            {"tool": tool_name, "status": status}
        )


@lru_cache()
def get_metrics_service() -> MetricsService:
    """Get singleton metrics service instance."""
    return MetricsService()
