"""
LangGraph agent service for portfolio chat with tool calling.
Uses create_react_agent for stateful workflows with Azure OpenAI.
"""
import logging
from typing import AsyncIterator

from langchain_openai import AzureChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage

from src.core.ai_config import AIConfig
from src.services.ai.agent_prompt_service import AgentPromptService
from src.services.holding_service import HoldingService
from src.services.ai.portfolio_analysis_service import PortfolioAnalysisService

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
    get_market_sentiment
)

logger = logging.getLogger(__name__)


class LangGraphAgentService:
    """
    Portfolio chat agent using LangGraph's create_react_agent.
    Provides stateful agentic workflows with tool calling.
    Singleton service that accepts database session per request.
    """
    
    def __init__(
        self,
        ai_config: AIConfig,
        agent_prompt_service: AgentPromptService
    ):
        """
        Initialize the LangGraph agent service.
        
        Args:
            ai_config: AI configuration with Azure OpenAI settings
            agent_prompt_service: Service for system prompts
        """
        self.ai_config = ai_config
        self.agent_prompt_service = agent_prompt_service
        
        # Initialize Azure OpenAI model
        self.model = AzureChatOpenAI(
            azure_endpoint=ai_config.azure_openai_endpoint,
            api_key=ai_config.azure_openai_api_key,
            api_version=ai_config.azure_openai_api_version,
            azure_deployment=ai_config.azure_openai_deployment_name,
            streaming=True
        )
        
        logger.info(
            f"Initialized LangGraph agent with model: {ai_config.azure_openai_deployment_name}"
        )
    
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
        
        logger.info(f"Tools initialized for account {account_id}")
    
    def _create_agent(self, account_id: int):
        """
        Create a LangGraph agent with portfolio tools.
        
        Args:
            account_id: Account ID for prompt context
        
        Returns:
            LangGraph agent with tool calling capabilities
        """
        # Portfolio tools list
        tools = [
            get_portfolio_holdings,
            analyze_portfolio_performance,
            compare_portfolio_performance,
            get_market_context,
            get_market_sentiment
        ]
        
        # Get system prompt with account context
        system_prompt = self.agent_prompt_service.get_portfolio_advisor_prompt(account_id)
        
        # Create agent with tools and system prompt
        agent = create_react_agent(
            model=self.model,
            tools=tools,
            prompt=system_prompt
        )
        
        return agent
    
    async def stream_chat(
        self,
        user_message: str,
        account_id: int,
        db,
        conversation_history: list = None
    ) -> AsyncIterator[str]:
        """
        Stream chat response with tool calling.
        Uses LangGraph agent for stateful workflows.
        
        Args:
            user_message: User's message
            account_id: Authenticated user's account ID (injected from request)
            db: Database session for this request
            conversation_history: Optional conversation history
        
        Yields:
            Chunks of the AI response
        """
        try:
            # Create services with database session
            holding_service = HoldingService(db)
            portfolio_analysis_service = PortfolioAnalysisService(holding_service)
            
            # Initialize tools with account context
            self._initialize_tools_for_account(
                account_id,
                holding_service,
                portfolio_analysis_service
            )
            
            # Create agent
            agent = self._create_agent(account_id)
            
            # Build message history
            messages = []
            if conversation_history:
                for msg in conversation_history:
                    if msg.get("role") == "user":
                        messages.append(HumanMessage(content=msg["content"]))
                    elif msg.get("role") == "assistant":
                        messages.append(AIMessage(content=msg["content"]))
            
            # Add current user message
            messages.append(HumanMessage(content=user_message))
            
            logger.info(f"Streaming chat for account {account_id}: {user_message[:100]}")
            
            # Stream agent response
            async for event in agent.astream_events(
                {"messages": messages},
                version="v1"
            ):
                # Stream token events from the model
                if event["event"] == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, "content") and chunk.content:
                        yield chunk.content
                
                # Log tool calls
                elif event["event"] == "on_tool_start":
                    tool_name = event["name"]
                    logger.info(f"Tool called: {tool_name}")
                
                elif event["event"] == "on_tool_end":
                    tool_name = event["name"]
                    logger.info(f"Tool completed: {tool_name}")
        
        except Exception as e:
            logger.error(f"Error in stream_chat: {str(e)}", exc_info=True)
            error_message = f"I apologize, but I encountered an error: {str(e)}"
            yield error_message
    
    async def chat(
        self,
        user_message: str,
        account_id: int,
        db,
        conversation_history: list = None
    ) -> str:
        """
        Non-streaming chat response with tool calling.
        
        Args:
            user_message: User's message
            account_id: Authenticated user's account ID (injected from request)
            db: Database session for this request
            conversation_history: Optional conversation history
        
        Returns:
            Complete AI response
        """
        try:
            # Create services with database session
            holding_service = HoldingService(db)
            portfolio_analysis_service = PortfolioAnalysisService(holding_service)
            
            # Initialize tools with account context
            self._initialize_tools_for_account(
                account_id,
                holding_service,
                portfolio_analysis_service
            )
            
            # Create agent
            agent = self._create_agent(account_id)
            
            # Build message history
            messages = []
            if conversation_history:
                for msg in conversation_history:
                    if msg.get("role") == "user":
                        messages.append(HumanMessage(content=msg["content"]))
                    elif msg.get("role") == "assistant":
                        messages.append(AIMessage(content=msg["content"]))
            
            # Add current user message
            messages.append(HumanMessage(content=user_message))
            
            logger.info(f"Chat for account {account_id}: {user_message[:100]}")
            
            # Invoke agent
            response = await agent.ainvoke({"messages": messages})
            
            # Extract final message
            final_message = response["messages"][-1].content
            
            return final_message
        
        except Exception as e:
            logger.error(f"Error in chat: {str(e)}", exc_info=True)
            return f"I apologize, but I encountered an error: {str(e)}"
