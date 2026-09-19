"""
LangGraph StateGraph construction for the portfolio agent.

Builds the agent/tools graph: the model invocation node (with LLM tracing and
token/metric recording), the tool-routing function, and the overall
StateGraph wiring. Extracted from `LangGraphAgentService` so graph assembly
can be tested and reasoned about independently of chat orchestration.
"""
import json
import logging
import time
from typing import Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from src.core.ai_config import AIConfig
from src.core.telemetry import get_tracer
from src.services.metrics_service import get_metrics_service

logger = logging.getLogger(__name__)


class AgentState(MessagesState):
    """
    Custom state for the portfolio agent.
    Extends MessagesState with additional portfolio context.
    """
    account_id: int  # Account context for security
    thread_id: int   # Conversation thread ID


def _summarize_messages_for_trace(
    messages: list,
    system_prompt: Optional[str] = None
) -> str:
    """
    Create a summary of messages for tracing without exposing full content.

    Args:
        messages: List of messages being sent to LLM
        system_prompt: System prompt if this is the first message

    Returns:
        JSON string summarizing the conversation context
    """
    summary = {
        "total_messages": len(messages),
        "message_types": [],
        "has_system_prompt": system_prompt is not None,
        "system_prompt_length": len(system_prompt) if system_prompt else 0,
    }

    for msg in messages:
        if isinstance(msg, dict):
            msg_type = msg.get("role", "unknown")
            content_len = len(msg.get("content", ""))
        elif isinstance(msg, HumanMessage):
            msg_type = "human"
            content_len = len(msg.content)
        elif isinstance(msg, AIMessage):
            msg_type = "ai"
            content_len = len(msg.content) if msg.content else 0
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                msg_type = f"ai_with_{len(msg.tool_calls)}_tool_calls"
        elif isinstance(msg, ToolMessage):
            msg_type = "tool_result"
            content_len = len(msg.content) if msg.content else 0
        else:
            msg_type = type(msg).__name__
            content_len = len(str(msg))

        summary["message_types"].append({
            "type": msg_type,
            "content_length": content_len
        })

    return json.dumps(summary)


def _create_routing_function():
    """
    Create routing function to determine next step (tools or end).

    Returns:
        Function that determines routing based on state
    """
    def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
        messages = state["messages"]
        last_message = messages[-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return "__end__"

    return should_continue


class GraphBuilder:
    """
    Builds the LangGraph StateGraph for the portfolio agent, given an
    AIConfig for model selection/configuration.
    """

    def __init__(self, ai_config: AIConfig):
        self.ai_config = ai_config

    def _create_model(self, model_id: Optional[str] = None):
        """
        Create a ChatOpenAI model instance for the given model ID.
        Called per-request so different callers can use different deployed models.

        Args:
            model_id: Deployment name to use. Falls back to configured default if None.

        Returns:
            Configured ChatOpenAI instance pointing at Azure AI Foundry project endpoint.
        """
        effective_id = model_id or self.ai_config.azure_openai_deployment_name
        return ChatOpenAI(
            base_url=self.ai_config.project_endpoint,
            api_key=self.ai_config.azure_openai_api_key,
            model=effective_id,
            streaming=True,
        )

    def _create_agent_node(self, model_with_tools, system_prompt: str, model_name: Optional[str] = None):
        """
        Create the agent node function with comprehensive LLM tracing.

        Args:
            model_with_tools: LLM with tools bound
            system_prompt: System prompt for the agent
            model_name: Effective model name for telemetry (defaults to configured default)

        Returns:
            Function that processes agent state
        """
        model_name = model_name or self.ai_config.azure_openai_deployment_name
        metrics = get_metrics_service()

        async def call_model(state: AgentState) -> AgentState:
            tracer = get_tracer()

            with tracer.start_as_current_span("LLMInvocation") as span:
                span.set_attribute("llm.model", model_name)
                span.set_attribute("llm.provider", "azure_openai")

                messages = state["messages"]
                # System prompt is an instruction boundary, not conversational memory —
                # prepend it on every invocation rather than only the first turn, since
                # the checkpointer persists only what this node returns (the AI response),
                # never the system message itself.
                is_first_message = not any(isinstance(m, (AIMessage, ToolMessage)) for m in messages)
                messages = [{"role": "system", "content": system_prompt}] + messages

                # Trace the context being sent to LLM
                span.set_attribute("llm.is_first_message", is_first_message)
                span.set_attribute("llm.message_count", len(messages))

                # Log detailed context for tracing
                context_summary = _summarize_messages_for_trace(messages, system_prompt)
                span.set_attribute("llm.context_summary", context_summary)

                # Track prompt size (approximate token count based on chars/4)
                total_chars = sum(
                    len(str(m.get('content', ''))) if isinstance(m, dict) else len(m.content)
                    for m in messages
                )
                span.set_attribute("llm.prompt_chars", total_chars)
                span.set_attribute("llm.prompt_tokens_estimate", total_chars // 4)

                start_time = time.perf_counter()

                try:
                    response = await model_with_tools.ainvoke(messages)
                    duration = time.perf_counter() - start_time

                    # Extract token usage from response metadata
                    prompt_tokens = 0
                    completion_tokens = 0
                    if hasattr(response, 'response_metadata'):
                        token_usage = response.response_metadata.get('token_usage', {})
                        prompt_tokens = token_usage.get('prompt_tokens', 0)
                        completion_tokens = token_usage.get('completion_tokens', 0)

                        span.set_attribute("llm.prompt_tokens", prompt_tokens)
                        span.set_attribute("llm.completion_tokens", completion_tokens)
                        span.set_attribute("llm.total_tokens", prompt_tokens + completion_tokens)

                        # Record token metrics
                        if prompt_tokens or completion_tokens:
                            metrics.record_llm_tokens(prompt_tokens, completion_tokens, model_name)

                    # Trace the response
                    response_content = response.content if hasattr(response, 'content') else ""
                    span.set_attribute("llm.response_length", len(response_content))

                    # Check for tool calls
                    has_tool_calls = bool(hasattr(response, "tool_calls") and response.tool_calls)
                    span.set_attribute("llm.has_tool_calls", has_tool_calls)

                    if has_tool_calls:
                        tool_names = [tc['name'] for tc in response.tool_calls]
                        span.set_attribute("llm.tool_calls", json.dumps(tool_names))
                        span.set_attribute("llm.tool_call_count", len(response.tool_calls))
                        logger.info(f"🤖 AI decided to call {len(response.tool_calls)} tool(s): {tool_names}")
                    else:
                        # Log truncated response for non-tool responses
                        response_preview = response_content[:500] + "..." if len(response_content) > 500 else response_content
                        span.set_attribute("llm.response_preview", response_preview)
                        logger.info(f"🤖 AI responded without calling tools (message length: {len(response_content)})")

                    # Record success metrics
                    span.set_attribute("llm.duration_ms", int(duration * 1000))
                    metrics.increment_llm_requests(model_name, "success")
                    metrics.record_llm_request_duration(duration, model_name, "success")

                    return {"messages": [response]}

                except Exception as e:
                    duration = time.perf_counter() - start_time
                    span.set_attribute("error", True)
                    span.set_attribute("error.message", str(e))
                    span.record_exception(e)
                    metrics.increment_llm_requests(model_name, "error")
                    metrics.record_llm_request_duration(duration, model_name, "error")
                    raise

        return call_model

    def build_graph(self, tools: list, system_prompt: str, model_id: Optional[str] = None):
        """
        Build the LangGraph StateGraph with nodes and edges.

        Args:
            tools: List of portfolio tools
            system_prompt: System prompt for the agent
            model_id: Optional model deployment name; falls back to configured default

        Returns:
            Compiled StateGraph workflow
        """
        workflow = StateGraph(AgentState)

        # Create model for this request
        model = self._create_model(model_id)

        # Check if model supports tool calling
        model_config = self.ai_config.get_model_config(model_id)
        supports_tools = model_config.supports_tools if model_config else True
        effective_tools = tools if supports_tools else []
        if not supports_tools:
            logger.info(f"Model '{model_id}' does not support tool calling — running without tools")

        # Log available tools
        tool_names = [tool.name if hasattr(tool, 'name') else str(tool) for tool in effective_tools]
        logger.info(f"Binding {len(effective_tools)} tools to model '{model_id or self.ai_config.azure_openai_deployment_name}': {tool_names}")

        # Bind tools to model
        model_with_tools = model.bind_tools(effective_tools) if supports_tools else model

        # Create node functions
        effective_model_name = model_id or self.ai_config.azure_openai_deployment_name
        call_model = self._create_agent_node(model_with_tools, system_prompt, model_name=effective_model_name)
        should_continue = _create_routing_function()

        # Build graph structure
        workflow.add_node("agent", call_model)
        workflow.add_node("tools", ToolNode(effective_tools))
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges(
            "agent",
            should_continue,
            {"tools": "tools", "__end__": END}
        )
        workflow.add_edge("tools", "agent")

        return workflow
