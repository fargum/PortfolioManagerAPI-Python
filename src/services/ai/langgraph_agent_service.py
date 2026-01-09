"""
LangGraph agent service for portfolio chat with tool calling.
Uses LangGraph's StateGraph for explicit graph construction with memory persistence.
Leverages PostgresSaver checkpointer for conversation state management.
"""
import logging
from typing import AsyncIterator, Optional, Literal
from typing_extensions import TypedDict

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, ToolMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.core.ai_config import AIConfig
from src.services.ai.agent_prompt_service import AgentPromptService
from src.services.holding_service import HoldingService
from src.services.ai.portfolio_analysis_service import PortfolioAnalysisService
from src.services.conversation_thread_service import ConversationThreadService
from src.services.eod_market_data_tool import EodMarketDataTool
from src.services.pricing_calculation_service import PricingCalculationService
from src.services.currency_conversion_service import CurrencyConversionService
from src.core.config import Settings

# Import LangChain tools
from src.services.ai.tools.portfolio_holdings_tool import (
    get_portfolio_holdings,
    initialize_holdings_tool
)
from src.services.ai.tools.portfolio_analysis_tool import (
    analyze_portfolio_performance,
    initialize_analysis_tool
)
from src.services.ai.tools.portfolio_comparison_tool import (
    compare_portfolio_performance,
    initialize_comparison_tool
)
from src.services.ai.tools.market_intelligence_tool import (
    get_market_context,
    get_market_sentiment,
    initialize_market_intelligence_tool
)
from src.services.ai.tools.real_time_prices_tool import (
    get_real_time_prices,
    initialize_real_time_prices_tool
)

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
        Create the agent node function.
        
        Args:
            model_with_tools: LLM with tools bound
            system_prompt: System prompt for the agent
            
        Returns:
            Function that processes agent state
        """
        def call_model(state: AgentState) -> AgentState:
            messages = state["messages"]
            # Inject system prompt on first message
            if not any(isinstance(m, (AIMessage, ToolMessage)) for m in messages):
                messages = [{"role": "system", "content": system_prompt}] + messages
            response = model_with_tools.invoke(messages)
            
            # Log what the AI decided to do
            if hasattr(response, "tool_calls") and response.tool_calls:
                logger.info(f"🤖 AI decided to call {len(response.tool_calls)} tool(s): {[tc['name'] for tc in response.tool_calls]}")
            else:
                logger.info(f"🤖 AI responded without calling tools (message length: {len(response.content) if hasattr(response, 'content') else 0})")
            
            return {"messages": [response]}
        
        return call_model
    
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
        Stream events from the compiled graph.
        
        Args:
            graph: Compiled LangGraph
            initial_state: Initial state with messages
            config: Configuration with thread_id
            
        Yields:
            Content chunks from the model and status updates for tool execution
        """
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
                        yield chunk.content
                
                case "on_tool_start":
                    # Stream status updates when tools are called
                    tool_name = event.get("name", "")
                    tool_input = event.get("data", {}).get("input", {})
                    logger.info(f"🔧 Tool called: {tool_name} with input: {tool_input}")
                    
                    # Send user-friendly status message
                    if tool_name in tool_status_messages:
                        yield tool_status_messages[tool_name]
                
                case "on_tool_end":
                    tool_name = event.get("name", "")
                    logger.info(f"Tool completed: {tool_name}")
                    
                    # Send completion message
                    if tool_name in tool_completion_messages:
                        yield tool_completion_messages[tool_name]
    
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
        try:
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
            
            # Build graph components
            tools = self._get_portfolio_tools()
            system_prompt = self.agent_prompt_service.get_portfolio_advisor_prompt(account_id)
            workflow = self._build_graph(tools, system_prompt)
            
            # Create and use async checkpointer
            async with AsyncPostgresSaver.from_conn_string(self.postgres_url) as checkpointer:
                graph = workflow.compile(checkpointer=checkpointer)
                
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
                
                logger.info(
                    f"Streaming chat for account {account_id} on thread {thread.id}: {user_message[:100]}"
                )
                
                # Stream agent response with memory
                async for chunk in self._stream_graph_events(graph, initial_state, config):
                    yield chunk
        
        except Exception as e:
            logger.error(f"Error in stream_chat: {str(e)}", exc_info=True)
            yield f"I apologize, but I encountered an error: {str(e)}"
