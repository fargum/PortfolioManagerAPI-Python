"""
LangGraph agent service for portfolio chat with tool calling.
Uses LangGraph's StateGraph for explicit graph construction with memory persistence.
Leverages PostgresSaver checkpointer for conversation state management.
"""
import json
import logging
import time
from typing import Any, AsyncIterator, Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai import AzureChatOpenAI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from src.core.ai_config import AIConfig
from src.core.config import Settings
from src.core.telemetry import get_tracer
from src.services.ai.agent_prompt_service import AgentPromptService
from src.services.ai.portfolio_analysis_service import PortfolioAnalysisService
from src.services.ai.tools.market_intelligence_tool import (
    get_market_context,
    get_market_sentiment,
    initialize_market_intelligence_tool,
)
from src.services.ai.tools.portfolio_analysis_tool import (
    analyze_portfolio_performance,
    initialize_analysis_tool,
)
from src.services.ai.tools.portfolio_comparison_tool import (
    compare_portfolio_performance,
    initialize_comparison_tool,
)

# Import LangChain tools
from src.services.ai.tools.portfolio_holdings_tool import (
    get_portfolio_holdings,
    initialize_holdings_tool,
)
from src.services.ai.tools.real_time_prices_tool import (
    get_real_time_prices,
    initialize_real_time_prices_tool,
)
from src.services.conversation_thread_service import ConversationThreadService
from src.services.currency_conversion_service import CurrencyConversionService
from src.services.eod_market_data_tool import EodMarketDataTool
from src.services.holding_service import HoldingService
from src.services.metrics_service import get_metrics_service
from src.services.pricing_calculation_service import PricingCalculationService

logger = logging.getLogger(__name__)


class AgentState(MessagesState):
    """
    Custom state for the portfolio agent.
    Extends MessagesState with additional portfolio context.
    """
    account_id: int  # Account context for security
    thread_id: int   # Conversation thread ID


class LangGraphAgentService:
    """
    Portfolio chat agent using LangGraph's create_react_agent.
    Provides stateful agentic workflows with tool calling and conversation memory.
    Uses PostgresSaver checkpointer for persistent conversation history.
    Singleton service that accepts database session per request.
    """

    def __init__(
        self,
        ai_config: AIConfig,
        agent_prompt_service: AgentPromptService,
        settings: Settings
    ):
        """
        Initialize the LangGraph agent service.

        Args:
            ai_config: AI configuration with Azure OpenAI settings
            agent_prompt_service: Service for system prompts
            settings: Application settings with database connection string
        """
        self.ai_config = ai_config
        self.agent_prompt_service = agent_prompt_service
        self.settings = settings

        # Initialize Azure OpenAI model
        self.model = AzureChatOpenAI(
            azure_endpoint=ai_config.azure_openai_endpoint,
            api_key=ai_config.azure_openai_api_key,
            api_version=ai_config.azure_openai_api_version,
            azure_deployment=ai_config.azure_openai_deployment_name,
            streaming=True
        )

        # Initialize AsyncPostgresSaver checkpointer for conversation memory
        # AsyncPostgresSaver expects standard psycopg connection string
        # Tables must already exist in public schema (checkpoints, checkpoint_writes, checkpoint_blobs)
        try:
            # Convert SQLAlchemy async URL back to standard postgres URL for psycopg
            # AsyncPostgresSaver uses psycopg3 which handles async natively
            postgres_url = settings.database_url  # Use standard postgresql:// format

            # Store connection string for creating checkpointer instances
            self.postgres_url = postgres_url
            self.checkpointer = None  # Will be created per request

            logger.info(
                f"Initialized LangGraph agent with model: {ai_config.azure_openai_deployment_name} and PostgreSQL async memory"
            )
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL checkpointer: {e}", exc_info=True)
            raise RuntimeError(
                f"Cannot initialize conversation memory: {e}. "
                f"Check database connection and permissions."
            ) from e

    def _initialize_tools_for_account(
        self,
        account_id: int,
        holding_service: HoldingService,
        portfolio_analysis_service: PortfolioAnalysisService
    ):
        """
        Initialize tools with account context and database-backed services.
        Security: account_id is injected from authenticated request, not from AI.

        Args:
            account_id: Authenticated user's account ID
            holding_service: Service for accessing holding data (with DB session)
            portfolio_analysis_service: Service for portfolio analysis (with DB session)
        """
        initialize_holdings_tool(holding_service, account_id)
        initialize_analysis_tool(portfolio_analysis_service, account_id)
        initialize_comparison_tool(portfolio_analysis_service, account_id)

        # Initialize real-time prices and market intelligence tools with EOD market data tool
        if holding_service.eod_tool:
            initialize_real_time_prices_tool(holding_service.eod_tool)
            initialize_market_intelligence_tool(holding_service.eod_tool)
            logger.info(f"Real-time prices and market intelligence tools initialized for account {account_id}")
        else:
            logger.warning(f"EOD tool not available for account {account_id}, real-time prices and market intelligence tools not initialized")

        logger.info(f"Tools initialized for account {account_id}")

    def _get_portfolio_tools(self):
        """Get list of portfolio tools for the agent."""
        return [
            get_portfolio_holdings,
            analyze_portfolio_performance,
            compare_portfolio_performance,
            get_market_context,
            get_market_sentiment,
            get_real_time_prices
        ]

    def _create_agent_node(self, model_with_tools, system_prompt: str):
        """
        Create the agent node function with comprehensive LLM tracing.

        Args:
            model_with_tools: LLM with tools bound
            system_prompt: System prompt for the agent

        Returns:
            Function that processes agent state
        """
        model_name = self.ai_config.azure_openai_deployment_name
        metrics = get_metrics_service()

        def call_model(state: AgentState) -> AgentState:
            tracer = get_tracer()

            with tracer.start_as_current_span("LLMInvocation") as span:
                span.set_attribute("llm.model", model_name)
                span.set_attribute("llm.provider", "azure_openai")

                messages = state["messages"]
                # Inject system prompt on first message
                is_first_message = not any(isinstance(m, (AIMessage, ToolMessage)) for m in messages)
                if is_first_message:
                    messages = [{"role": "system", "content": system_prompt}] + messages

                # Trace the context being sent to LLM
                span.set_attribute("llm.is_first_message", is_first_message)
                span.set_attribute("llm.message_count", len(messages))

                # Log detailed context for tracing
                context_summary = self._summarize_messages_for_trace(messages, system_prompt if is_first_message else None)
                span.set_attribute("llm.context_summary", context_summary)

                # Track prompt size (approximate token count based on chars/4)
                total_chars = sum(
                    len(m.content) if hasattr(m, 'content') else len(str(m.get('content', '')))
                    for m in messages
                )
                span.set_attribute("llm.prompt_chars", total_chars)
                span.set_attribute("llm.prompt_tokens_estimate", total_chars // 4)

                start_time = time.perf_counter()

                try:
                    response = model_with_tools.invoke(messages)
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

    def _summarize_messages_for_trace(
        self,
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

    def _create_routing_function(self):
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

    def _build_graph(self, tools: list, system_prompt: str):
        """
        Build the LangGraph StateGraph with nodes and edges.

        Args:
            tools: List of portfolio tools
            system_prompt: System prompt for the agent

        Returns:
            Compiled StateGraph workflow
        """
        workflow = StateGraph(AgentState)

        # Log available tools
        tool_names = [tool.name if hasattr(tool, 'name') else str(tool) for tool in tools]
        logger.info(f"🔧 Binding {len(tools)} tools to model: {tool_names}")

        # Bind tools to model
        model_with_tools = self.model.bind_tools(tools)

        # Create node functions
        call_model = self._create_agent_node(model_with_tools, system_prompt)
        should_continue = self._create_routing_function()

        # Build graph structure
        workflow.add_node("agent", call_model)
        workflow.add_node("tools", ToolNode(tools))
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges(
            "agent",
            should_continue,
            {"tools": "tools", "__end__": END}
        )
        workflow.add_edge("tools", "agent")

        return workflow

    async def _stream_graph_events(
        self,
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

        # Map tool names to user-friendly status messages
        tool_status_messages = {
            "get_portfolio_holdings": "📊 Fetching your portfolio holdings...\n\n",
            "analyze_portfolio_performance": "📈 Analyzing portfolio performance...\n\n",
            "compare_portfolio_performance": "📊 Comparing portfolio performance...\n\n",
            "get_market_context": "🌍 Getting market context...\n\n",
            "get_market_sentiment": "💭 Analyzing market sentiment...\n\n",
            "get_real_time_prices": "💰 Fetching real-time stock prices...\n\n"
        }

        tool_completion_messages = {
            "get_portfolio_holdings": "✓ Portfolio data retrieved\n\n",
            "analyze_portfolio_performance": "✓ Analysis complete\n\n",
            "compare_portfolio_performance": "✓ Comparison complete\n\n",
            "get_market_context": "✓ Market context retrieved\n\n",
            "get_market_sentiment": "✓ Sentiment analysis complete\n\n",
            "get_real_time_prices": "✓ Prices retrieved\n\n"
        }

        # Track active tool spans and their start times
        active_tool_spans = {}
        tool_start_times = {}
        total_tokens_streamed = 0

        with tracer.start_as_current_span("AgentGraphExecution") as graph_span:
            graph_span.set_attribute("agent.thread_id", config.get("configurable", {}).get("thread_id", ""))
            graph_span.set_attribute("agent.account_id", initial_state.get("account_id", 0))

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
                        # Stream status updates when tools are called
                        tool_name = event.get("name", "")
                        tool_input = event.get("data", {}).get("input", {})

                        # Start a span for this tool execution
                        tool_span = tracer.start_span(f"ToolExecution:{tool_name}")
                        tool_span.set_attribute("tool.name", tool_name)
                        tool_span.set_attribute("tool.input", json.dumps(tool_input) if tool_input else "{}")
                        active_tool_spans[tool_name] = tool_span
                        tool_start_times[tool_name] = time.perf_counter()

                        logger.info(f"🔧 Tool called: {tool_name} with input: {tool_input}")

                        # Send user-friendly status message
                        if tool_name in tool_status_messages:
                            yield tool_status_messages[tool_name]

                    case "on_tool_end":
                        tool_name = event.get("name", "")
                        tool_output = event.get("data", {}).get("output", {})

                        # End the tool span
                        if tool_name in active_tool_spans:
                            tool_span = active_tool_spans.pop(tool_name)
                            duration = time.perf_counter() - tool_start_times.pop(tool_name, time.perf_counter())

                            # Summarize output for tracing (avoid huge payloads)
                            output_str = str(tool_output)
                            output_preview = output_str[:1000] + "..." if len(output_str) > 1000 else output_str
                            tool_span.set_attribute("tool.output_preview", output_preview)
                            tool_span.set_attribute("tool.output_length", len(output_str))
                            tool_span.set_attribute("tool.duration_ms", int(duration * 1000))
                            tool_span.end()

                            # Record tool metrics
                            metrics.increment_tool_executions(tool_name, "success")
                            metrics.record_tool_execution_duration(duration, tool_name, "success")

                        logger.info(f"Tool completed: {tool_name}")

                        # Send completion message
                        if tool_name in tool_completion_messages:
                            yield tool_completion_messages[tool_name]

            graph_span.set_attribute("agent.total_stream_chunks", total_tokens_streamed)

    async def _prepare_chat_context(
        self,
        user_message: str,
        account_id: int,
        db,
        thread_id: Optional[int] = None,
        voice_mode: bool = False
    ) -> tuple[Any, dict, dict, int]:
        """
        Prepare common context for chat operations.

        Sets up services, initializes tools, creates/retrieves conversation thread,
        and builds the graph workflow.

        Args:
            user_message: User's message
            account_id: Authenticated user's account ID
            db: Database session for this request
            thread_id: Optional conversation thread ID
            voice_mode: If True, use voice-optimized prompt with summary instructions

        Returns:
            Tuple of (workflow, initial_state, config, thread_id) where:
            - workflow: Uncompiled LangGraph StateGraph
            - initial_state: Initial state dict with messages
            - config: Configuration dict with thread_id
            - thread_id: The actual thread ID being used
        """
        # Create EOD tool if configured
        eod_tool = None
        if self.settings.eod_api_token:
            eod_tool = EodMarketDataTool(
                api_token=self.settings.eod_api_token,
                base_url=self.settings.eod_api_base_url,
                timeout_seconds=self.settings.eod_api_timeout_seconds
            )

        # Create pricing services
        currency_service = CurrencyConversionService(db)
        pricing_service = PricingCalculationService(currency_service)

        # Create services with database session
        holding_service = HoldingService(db, eod_tool, pricing_service)
        portfolio_analysis_service = PortfolioAnalysisService(holding_service)
        conversation_thread_service = ConversationThreadService(db)

        # Initialize tools with account context
        self._initialize_tools_for_account(
            account_id,
            holding_service,
            portfolio_analysis_service
        )

        # Get or create conversation thread
        thread = await conversation_thread_service.get_or_create_active_thread(
            account_id=account_id,
            thread_id=thread_id
        )

        logger.info(f"Using conversation thread {thread.id} for account {account_id}")

        # Build graph components - use voice mode prompt if requested
        tools = self._get_portfolio_tools()
        if voice_mode:
            system_prompt = self.agent_prompt_service.get_voice_mode_prompt(account_id)
        else:
            system_prompt = self.agent_prompt_service.get_portfolio_advisor_prompt(account_id)
        workflow = self._build_graph(tools, system_prompt)

        # Prepare state and config
        initial_state = {
            "messages": [HumanMessage(content=user_message)],
            "account_id": account_id,
            "thread_id": thread.id
        }

        config = {
            "configurable": {
                "thread_id": f"account_{account_id}_thread_{thread.id}"
            }
        }

        return workflow, initial_state, config, thread.id

    async def stream_chat(
        self,
        user_message: str,
        account_id: int,
        db,
        thread_id: Optional[int] = None
    ) -> AsyncIterator[str]:
        """
        Stream chat response with tool calling and conversation memory.
        Uses LangGraph agent with AsyncPostgresSaver for persistent conversation history.

        Args:
            user_message: User's message
            account_id: Authenticated user's account ID (injected from request)
            db: Database session for this request
            thread_id: Optional conversation thread ID (None creates/uses active thread)

        Yields:
            Chunks of the AI response
        """
        tracer = get_tracer()

        with tracer.start_as_current_span("AgentStreamChat") as span:
            span.set_attribute("agent.account_id", account_id)
            span.set_attribute("agent.mode", "stream")
            span.set_attribute("agent.model", self.ai_config.azure_openai_deployment_name)
            span.set_attribute("agent.user_message_length", len(user_message))
            span.set_attribute("agent.user_message_preview", user_message[:200] if len(user_message) > 200 else user_message)

            try:
                # Prepare common chat context
                workflow, initial_state, config, actual_thread_id = await self._prepare_chat_context(
                    user_message, account_id, db, thread_id
                )

                span.set_attribute("agent.thread_id", actual_thread_id)

                # Create and use async checkpointer
                async with AsyncPostgresSaver.from_conn_string(self.postgres_url) as checkpointer:
                    graph = workflow.compile(checkpointer=checkpointer)

                    logger.info(
                        f"Streaming chat for account {account_id} on thread {actual_thread_id}: {user_message[:100]}"
                    )

                    # Stream agent response with memory
                    async for chunk in self._stream_graph_events(graph, initial_state, config):
                        yield chunk

            except Exception as e:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                span.record_exception(e)
                logger.error(f"Error in stream_chat: {str(e)}", exc_info=True)
                yield f"I apologize, but I encountered an error: {str(e)}"

    async def _collect_graph_response(
        self,
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

        # Track active tool spans and their start times
        active_tool_spans = {}
        tool_start_times = {}

        with tracer.start_as_current_span("AgentGraphExecution") as graph_span:
            graph_span.set_attribute("agent.mode", "collect")
            graph_span.set_attribute("agent.thread_id", config.get("configurable", {}).get("thread_id", ""))
            graph_span.set_attribute("agent.account_id", initial_state.get("account_id", 0))

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
                        tool_name = event.get("name", "")
                        tool_input = event.get("data", {}).get("input", {})

                        # Start a span for this tool execution
                        tool_span = tracer.start_span(f"ToolExecution:{tool_name}")
                        tool_span.set_attribute("tool.name", tool_name)
                        tool_span.set_attribute("tool.input", json.dumps(tool_input) if tool_input else "{}")
                        active_tool_spans[tool_name] = tool_span
                        tool_start_times[tool_name] = time.perf_counter()

                        logger.info(f"Tool started: {tool_name}")
                        # Start tracking this tool call
                        tool_events.append({
                            "name": tool_name,
                            "input": tool_input,
                            "output": None  # Will be filled on_tool_end
                        })

                    case "on_tool_end":
                        tool_name = event.get("name", "")
                        tool_output = event.get("data", {}).get("output", {})

                        # End the tool span
                        if tool_name in active_tool_spans:
                            tool_span = active_tool_spans.pop(tool_name)
                            duration = time.perf_counter() - tool_start_times.pop(tool_name, time.perf_counter())

                            # Summarize output for tracing
                            output_str = str(tool_output)
                            output_preview = output_str[:1000] + "..." if len(output_str) > 1000 else output_str
                            tool_span.set_attribute("tool.output_preview", output_preview)
                            tool_span.set_attribute("tool.output_length", len(output_str))
                            tool_span.set_attribute("tool.duration_ms", int(duration * 1000))
                            tool_span.end()

                            # Record tool metrics
                            metrics.increment_tool_executions(tool_name, "success")
                            metrics.record_tool_execution_duration(duration, tool_name, "success")

                        logger.info(f"Tool completed: {tool_name}")
                        # Find and update the matching tool event (reversed to get most recent)
                        for te in reversed(tool_events):
                            if te["name"] == tool_name and te["output"] is None:
                                te["output"] = tool_output
                                break

            # Record final response stats
            final_text = "".join(final_text_chunks)
            graph_span.set_attribute("agent.response_length", len(final_text))
            graph_span.set_attribute("agent.tool_count", len(tool_events))

        return final_text, tool_events

    async def run_chat(
        self,
        user_message: str,
        account_id: int,
        db,
        thread_id: Optional[int] = None,
        voice_mode: bool = False
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Execute chat and return complete response with tool events.
        Non-streaming alternative to stream_chat for voice mode.

        Args:
            user_message: User's message
            account_id: Authenticated user's account ID
            db: Database session
            thread_id: Optional conversation thread ID
            voice_mode: If True, use voice-optimized prompt with summary instructions

        Returns:
            Tuple of (final_text, tool_events) where:
            - final_text: Complete AI response text
            - tool_events: List of {"name": str, "input": Any, "output": Any}
        """
        tracer = get_tracer()

        with tracer.start_as_current_span("AgentRunChat") as span:
            span.set_attribute("agent.account_id", account_id)
            span.set_attribute("agent.mode", "voice" if voice_mode else "run")
            span.set_attribute("agent.model", self.ai_config.azure_openai_deployment_name)
            span.set_attribute("agent.user_message_length", len(user_message))
            span.set_attribute("agent.user_message_preview", user_message[:200] if len(user_message) > 200 else user_message)

            try:
                # Prepare common chat context
                workflow, initial_state, config, actual_thread_id = await self._prepare_chat_context(
                    user_message, account_id, db, thread_id, voice_mode=voice_mode
                )

                span.set_attribute("agent.thread_id", actual_thread_id)

                # Create and use async checkpointer
                async with AsyncPostgresSaver.from_conn_string(self.postgres_url) as checkpointer:
                    graph = workflow.compile(checkpointer=checkpointer)

                    logger.info(
                        f"Running chat for account {account_id} on thread {actual_thread_id}: {user_message[:100]}"
                    )

                    # Collect complete response with tool events
                    final_text, tool_events = await self._collect_graph_response(graph, initial_state, config)

                    span.set_attribute("agent.response_length", len(final_text))
                    span.set_attribute("agent.tool_count", len(tool_events))

                    return final_text, tool_events

            except Exception as e:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                span.record_exception(e)
                logger.error(f"Error in run_chat: {str(e)}", exc_info=True)
                return f"I apologize, but I encountered an error: {str(e)}", []
