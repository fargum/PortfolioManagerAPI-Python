"""
Stream/event adapters for the LangGraph portfolio agent.

Translates raw `astream_events` output from a compiled LangGraph graph into
the two shapes the agent service needs:
- `stream_graph_events`: an async generator of text chunks for SSE/streaming responses
- `collect_graph_response`: a single (final_text, tool_events) tuple for non-streaming responses

Both share the same tool tracing/metrics bookkeeping via `ToolTelemetryTracker`
so the tracing/metrics lifecycle can't drift between the two call paths.
"""
import json
import logging
import time
from typing import Any, AsyncIterator

from src.core.telemetry import get_tracer
from src.services.ai.langgraph_messages import (
    TOOL_COMPLETION_MESSAGES,
    TOOL_STATUS_MESSAGES,
)
from src.services.metrics_service import get_metrics_service

logger = logging.getLogger(__name__)


class ToolTelemetryTracker:
    """
    Shared tool-span/metric bookkeeping for on_tool_start/on_tool_end/on_tool_error
    events from astream_events. Used by both stream_graph_events and
    collect_graph_response so the tracing/metrics lifecycle can't drift between
    the two call paths.

    Spans are keyed by run_id (unique per invocation) rather than tool name, since
    the model can issue multiple parallel calls to the same tool.
    """

    def __init__(self, tracer: Any, metrics: Any):
        self._tracer = tracer
        self._metrics = metrics
        self._active_spans: dict[str, Any] = {}
        self._start_times: dict[str, float] = {}

    def start(self, event: dict) -> tuple[str, str, Any]:
        """Handle on_tool_start. Returns (tool_name, run_id, tool_input)."""
        tool_name = event.get("name", "")
        run_id = event.get("run_id", "")
        tool_input = event.get("data", {}).get("input", {})

        tool_span = self._tracer.start_span(f"ToolExecution:{tool_name}")
        tool_span.set_attribute("tool.name", tool_name)
        tool_span.set_attribute("tool.input", json.dumps(tool_input) if tool_input else "{}")
        self._active_spans[run_id] = tool_span
        self._start_times[run_id] = time.perf_counter()

        return tool_name, run_id, tool_input

    def end(self, event: dict) -> tuple[str, str, Any]:
        """Handle on_tool_end. Returns (tool_name, run_id, tool_output)."""
        tool_name = event.get("name", "")
        run_id = event.get("run_id", "")
        tool_output = event.get("data", {}).get("output", {})

        if run_id in self._active_spans:
            tool_span = self._active_spans.pop(run_id)
            duration = time.perf_counter() - self._start_times.pop(run_id, time.perf_counter())

            output_str = str(tool_output)
            output_preview = output_str[:1000] + "..." if len(output_str) > 1000 else output_str
            tool_span.set_attribute("tool.output_preview", output_preview)
            tool_span.set_attribute("tool.output_length", len(output_str))
            tool_span.set_attribute("tool.duration_ms", int(duration * 1000))
            tool_span.end()

            self._metrics.increment_tool_executions(tool_name, "success")
            self._metrics.record_tool_execution_duration(duration, tool_name, "success")

        return tool_name, run_id, tool_output

    def error(self, event: dict) -> tuple[str, str, Any]:
        """Handle on_tool_error. Returns (tool_name, run_id, error)."""
        tool_name = event.get("name", "")
        run_id = event.get("run_id", "")
        error = event.get("data", {}).get("error")

        if run_id in self._active_spans:
            tool_span = self._active_spans.pop(run_id)
            duration = time.perf_counter() - self._start_times.pop(run_id, time.perf_counter())

            tool_span.set_attribute("error", True)
            tool_span.set_attribute("error.message", str(error))
            tool_span.set_attribute("tool.duration_ms", int(duration * 1000))
            if isinstance(error, BaseException):
                tool_span.record_exception(error)
            tool_span.end()

            self._metrics.increment_tool_executions(tool_name, "error")
            self._metrics.record_tool_execution_duration(duration, tool_name, "error")

        return tool_name, run_id, error

    def close(self) -> None:
        """
        Safety net: force-end any spans left open because the stream ended
        (client disconnect, cancellation, upstream error) without a matching
        on_tool_end/on_tool_error for that invocation.
        """
        for span in self._active_spans.values():
            span.set_attribute("error", True)
            span.set_attribute("error.message", "Stream ended before tool completion")
            span.end()
        self._active_spans.clear()
        self._start_times.clear()


async def stream_graph_events(
    graph,
    initial_state: dict,
    config: dict
) -> AsyncIterator[str]:
    """
    Stream events from the compiled graph with comprehensive tracing.

    Args:
        graph: Compiled LangGraph
        initial_state: Initial state with messages
        config: Configuration with thread_id

    Yields:
        Content chunks from the model and status updates for tool execution
    """
    tracer = get_tracer()
    metrics = get_metrics_service()

    tool_telemetry = ToolTelemetryTracker(tracer, metrics)
    total_tokens_streamed = 0

    with tracer.start_as_current_span("AgentGraphExecution") as graph_span:
        graph_span.set_attribute("agent.thread_id", config.get("configurable", {}).get("thread_id", ""))
        graph_span.set_attribute("agent.account_id", initial_state.get("account_id", 0))

        try:
            async for event in graph.astream_events(
                initial_state,
                config=config,
                version="v2"
            ):
                # Handle events using pattern matching
                match event["event"]:
                    case "on_chat_model_stream":
                        # Stream token events from the model
                        chunk = event["data"]["chunk"]
                        if hasattr(chunk, "content") and chunk.content:
                            total_tokens_streamed += 1
                            yield chunk.content

                    case "on_tool_start":
                        tool_name, _, tool_input = tool_telemetry.start(event)
                        logger.info(f"🔧 Tool called: {tool_name} with input: {tool_input}")

                        # Send user-friendly status message
                        if tool_name in TOOL_STATUS_MESSAGES:
                            yield TOOL_STATUS_MESSAGES[tool_name]

                    case "on_tool_end":
                        tool_name, _, _ = tool_telemetry.end(event)
                        logger.info(f"Tool completed: {tool_name}")

                        # Send completion message
                        if tool_name in TOOL_COMPLETION_MESSAGES:
                            yield TOOL_COMPLETION_MESSAGES[tool_name]

                    case "on_tool_error":
                        tool_name, _, error = tool_telemetry.error(event)
                        logger.error(f"Tool failed: {tool_name}: {error}")
        finally:
            tool_telemetry.close()

        graph_span.set_attribute("agent.total_stream_chunks", total_tokens_streamed)


async def collect_graph_response(
    graph,
    initial_state: dict,
    config: dict
) -> tuple[str, list[dict[str, Any]]]:
    """
    Collect complete response from graph execution with tool events and tracing.

    Args:
        graph: Compiled LangGraph
        initial_state: Initial state with messages
        config: Configuration with thread_id

    Returns:
        Tuple of (final_text, tool_events) where:
        - final_text: Complete AI response text
        - tool_events: List of tool event dicts with name, input, output
    """
    tracer = get_tracer()
    metrics = get_metrics_service()

    final_text_chunks: list[str] = []
    tool_events: list[dict[str, Any]] = []

    tool_telemetry = ToolTelemetryTracker(tracer, metrics)

    with tracer.start_as_current_span("AgentGraphExecution") as graph_span:
        graph_span.set_attribute("agent.mode", "collect")
        graph_span.set_attribute("agent.thread_id", config.get("configurable", {}).get("thread_id", ""))
        graph_span.set_attribute("agent.account_id", initial_state.get("account_id", 0))

        try:
            async for event in graph.astream_events(
                initial_state,
                config=config,
                version="v2"
            ):
                match event["event"]:
                    case "on_chat_model_stream":
                        chunk = event["data"]["chunk"]
                        if hasattr(chunk, "content") and chunk.content:
                            final_text_chunks.append(chunk.content)

                    case "on_tool_start":
                        tool_name, run_id, tool_input = tool_telemetry.start(event)
                        logger.info(f"Tool started: {tool_name}")
                        # Start tracking this tool call
                        tool_events.append({
                            "run_id": run_id,
                            "name": tool_name,
                            "input": tool_input,
                            "output": None  # Will be filled on_tool_end/on_tool_error
                        })

                    case "on_tool_end":
                        tool_name, run_id, tool_output = tool_telemetry.end(event)
                        logger.info(f"Tool completed: {tool_name}")
                        # Find and update the matching tool event by run_id — unambiguous
                        # even when multiple parallel calls share the same tool name.
                        for te in tool_events:
                            if te["run_id"] == run_id:
                                te["output"] = tool_output
                                break

                    case "on_tool_error":
                        tool_name, run_id, error = tool_telemetry.error(event)
                        logger.error(f"Tool failed: {tool_name}: {error}")
                        # Record the failure on the matching tool event
                        for te in tool_events:
                            if te["run_id"] == run_id:
                                te["output"] = {"Error": str(error)}
                                break
        finally:
            tool_telemetry.close()

        # Record final response stats
        final_text = "".join(final_text_chunks)
        graph_span.set_attribute("agent.response_length", len(final_text))
        graph_span.set_attribute("agent.tool_count", len(tool_events))

    return final_text, tool_events
