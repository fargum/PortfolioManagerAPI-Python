"""
LangGraph agent service for portfolio chat with tool calling.
Uses LangGraph's StateGraph for explicit graph construction with memory persistence.
Leverages PostgresSaver checkpointer for conversation state management.
"""
import logging
from typing import Any, AsyncIterator, Optional

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.core.ai_config import AIConfig
from src.core.config import Settings
from src.core.telemetry import get_tracer
from src.services.ai.agent_prompt_service import AgentPromptService
from src.services.ai.langgraph_graph_builder import GraphBuilder
from src.services.ai.langgraph_stream_adapter import (
    collect_graph_response,
    stream_graph_events,
)
from src.services.ai.langgraph_tool_registry import build_request_tools
from src.services.ai.portfolio_analysis_service import PortfolioAnalysisService
from src.services.conversation_thread_service import ConversationThreadService
from src.services.currency_conversion_service import CurrencyConversionService
from src.services.eod_market_data_service import EodMarketDataTool
from src.services.holding_service import HoldingService
from src.services.pricing_calculation_service import PricingCalculationService
from src.services.tavily_service import TavilyService

logger = logging.getLogger(__name__)


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
        settings: Settings,
        tavily_service: Optional[TavilyService] = None,
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
        self.tavily_service = tavily_service
        self.graph_builder = GraphBuilder(ai_config)

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

    async def _prepare_chat_context(
        self,
        user_message: str,
        account_id: int,
        db,
        thread_id: Optional[int] = None,
        voice_mode: bool = False,
        model_id: Optional[str] = None,
    ) -> tuple[Any, dict, dict, int]:
        """
        Prepare common context for chat operations.

        Sets up services, creates per-request tools, creates/retrieves conversation thread,
        and builds the graph workflow.

        IMPORTANT: Tools are created per-request using factory functions to avoid
        global state race conditions that could cause cross-account data leakage.

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

        # Create tools per-request with bound account context (avoids race conditions)
        tools = build_request_tools(
            account_id,
            holding_service,
            portfolio_analysis_service,
            self.tavily_service,
        )

        # Get or create conversation thread
        thread = await conversation_thread_service.get_or_create_active_thread(
            account_id=account_id,
            thread_id=thread_id
        )

        logger.info(f"Using conversation thread {thread.id} for account {account_id}")

        # Build graph components - use voice mode prompt if requested
        if voice_mode:
            system_prompt = self.agent_prompt_service.get_voice_mode_prompt(account_id)
        else:
            system_prompt = self.agent_prompt_service.get_portfolio_advisor_prompt(account_id)
        workflow = self.graph_builder.build_graph(tools, system_prompt, model_id=model_id)

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

        return workflow, initial_state, config, int(thread.id)

    async def stream_chat(
        self,
        user_message: str,
        account_id: int,
        db,
        thread_id: Optional[int] = None,
        model_id: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        Stream chat response with tool calling and conversation memory.
        Uses LangGraph agent with AsyncPostgresSaver for persistent conversation history.

        Args:
            user_message: User's message
            account_id: Authenticated user's account ID (injected from request)
            db: Database session for this request
            thread_id: Optional conversation thread ID (None creates/uses active thread)
            model_id: Optional model deployment name; falls back to configured default

        Yields:
            Chunks of the AI response
        """
        tracer = get_tracer()
        effective_model = model_id or self.ai_config.azure_openai_deployment_name

        with tracer.start_as_current_span("AgentStreamChat") as span:
            span.set_attribute("agent.account_id", account_id)
            span.set_attribute("agent.mode", "stream")
            span.set_attribute("agent.model", effective_model)
            span.set_attribute("agent.user_message_length", len(user_message))
            span.set_attribute("agent.user_message_preview", user_message[:200] if len(user_message) > 200 else user_message)

            try:
                # Prepare common chat context
                workflow, initial_state, config, actual_thread_id = await self._prepare_chat_context(
                    user_message, account_id, db, thread_id, model_id=model_id
                )

                span.set_attribute("agent.thread_id", actual_thread_id)

                # Create and use async checkpointer
                async with AsyncPostgresSaver.from_conn_string(self.postgres_url) as checkpointer:
                    graph = workflow.compile(checkpointer=checkpointer)

                    logger.info(
                        f"Streaming chat for account {account_id} on thread {actual_thread_id}: {user_message[:100]}"
                    )

                    # Stream agent response with memory
                    async for chunk in stream_graph_events(graph, initial_state, config):
                        yield chunk

            except Exception as e:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                span.record_exception(e)
                logger.error(f"Error in stream_chat: {str(e)}", exc_info=True)
                yield f"I apologize, but I encountered an error: {str(e)}"

    async def run_chat(
        self,
        user_message: str,
        account_id: int,
        db,
        thread_id: Optional[int] = None,
        voice_mode: bool = False,
        model_id: Optional[str] = None,
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
            model_id: Optional model deployment name; falls back to configured default

        Returns:
            Tuple of (final_text, tool_events) where:
            - final_text: Complete AI response text
            - tool_events: List of {"name": str, "input": Any, "output": Any}
        """
        tracer = get_tracer()
        effective_model = model_id or self.ai_config.azure_openai_deployment_name

        with tracer.start_as_current_span("AgentRunChat") as span:
            span.set_attribute("agent.account_id", account_id)
            span.set_attribute("agent.mode", "voice" if voice_mode else "run")
            span.set_attribute("agent.model", effective_model)
            span.set_attribute("agent.user_message_length", len(user_message))
            span.set_attribute("agent.user_message_preview", user_message[:200] if len(user_message) > 200 else user_message)

            try:
                # Prepare common chat context
                workflow, initial_state, config, actual_thread_id = await self._prepare_chat_context(
                    user_message, account_id, db, thread_id, voice_mode=voice_mode, model_id=model_id
                )

                span.set_attribute("agent.thread_id", actual_thread_id)

                # Create and use async checkpointer
                async with AsyncPostgresSaver.from_conn_string(self.postgres_url) as checkpointer:
                    graph = workflow.compile(checkpointer=checkpointer)

                    logger.info(
                        f"Running chat for account {account_id} on thread {actual_thread_id}: {user_message[:100]}"
                    )

                    # Collect complete response with tool events
                    final_text, tool_events = await collect_graph_response(graph, initial_state, config)

                    span.set_attribute("agent.response_length", len(final_text))
                    span.set_attribute("agent.tool_count", len(tool_events))

                    return final_text, tool_events

            except Exception as e:
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                span.record_exception(e)
                logger.error(f"Error in run_chat: {str(e)}", exc_info=True)
                return f"I apologize, but I encountered an error: {str(e)}", []
