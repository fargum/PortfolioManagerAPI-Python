"""AI Chat routes for streaming conversations with LangGraph agents."""
import logging
from typing import AsyncIterator, Optional
from functools import lru_cache
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.core.ai_config import AIConfig
from src.core.config import Settings
from src.db.session import get_db
from src.services.holding_service import HoldingService
from src.services.ai.agent_prompt_service import AgentPromptService
from src.services.ai.langgraph_agent_service import LangGraphAgentService
from src.services.ai.portfolio_analysis_service import PortfolioAnalysisService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai/chat", tags=["ai-chat"])


# Request/Response Models
class ChatRequest(BaseModel):
    """Chat request from client."""
    query: str = Field(..., description="User's question or message")
    account_id: int = Field(..., description="Account ID for personalized responses")
    thread_id: Optional[int] = Field(None, description="Conversation thread ID for multi-turn chat")


class ChatHealthResponse(BaseModel):
    """Health check response."""
    status: str
    azure_configured: bool
    model_name: str


# Dependencies
@lru_cache()
def get_ai_config() -> AIConfig:
    """Get AI configuration (singleton)."""
    return AIConfig()


@lru_cache()
def get_prompt_service() -> AgentPromptService:
    """Get agent prompt service (singleton)."""
    return AgentPromptService()


@lru_cache()
def get_settings() -> Settings:
    """Get application settings (singleton)."""
    return Settings()


@lru_cache()
def get_agent_service() -> LangGraphAgentService:
    """
    Get configured LangGraph agent service with conversation memory (singleton).
    
    Database session is passed per request when calling stream_chat methods.
    """
    try:
        ai_config = get_ai_config()
        prompt_service = get_prompt_service()
        settings = get_settings()
        
        logger.info("Initializing LangGraph agent service...")
        agent_service = LangGraphAgentService(
            ai_config=ai_config,
            agent_prompt_service=prompt_service,
            settings=settings
        )
        logger.info("LangGraph agent service initialized successfully")
        return agent_service
    except Exception as e:
        logger.error(f"Failed to initialize agent service: {e}", exc_info=True)
        raise


# Routes
@router.get("/health", response_model=ChatHealthResponse)
async def health_check(ai_config: AIConfig = Depends(get_ai_config)):
    """
    Health check for AI chat service.
    
    Returns configuration status and model information.
    """
    is_configured = bool(
        ai_config.azure_openai_endpoint and 
        ai_config.azure_openai_api_key and 
        ai_config.azure_openai_deployment_name
    )
    
    return ChatHealthResponse(
        status="healthy" if is_configured else "not_configured",
        azure_configured=is_configured,
        model_name=ai_config.azure_openai_deployment_name or "not_configured"
    )


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    agent_service: LangGraphAgentService = Depends(get_agent_service),
    db = Depends(get_db)
):
    """
    Stream AI chat response for user query with LangGraph agent and tool calling.
    
    Uses LangGraph's create_react_agent for stateful workflows with portfolio tools.
    Automatically handles tool orchestration and streaming.
    
    Tools available:
    - get_portfolio_holdings: Retrieve portfolio holdings
    - analyze_portfolio_performance: Analyze portfolio performance
    - compare_portfolio_performance: Compare performance between dates
    - get_market_context: Get market context (stub)
    - get_market_sentiment: Get market sentiment (stub)
    
    Args:
        request: Chat request with query and account_id
        
    Returns:
        StreamingResponse with text/event-stream content
        
    Example:
        POST /api/ai/chat/stream
        {
            "query": "How is my portfolio performing today?",
            "account_id": 123
        }
    """
    try:
        logger.info(
            f"Streaming LangGraph agent for account {request.account_id}, "
            f"query: {request.query[:50]}..."
        )
        
        # Stream response using LangGraph agent with conversation memory
        async def generate() -> AsyncIterator[str]:
            """Generate streaming response."""
            try:
                async for token in agent_service.stream_chat(
                    user_message=request.query,
                    account_id=request.account_id,  # Injected from auth context, not from AI
                    db=db,  # Database session for this request
                    thread_id=request.thread_id  # Optional thread ID for conversation continuity
                ):
                    # Send token as Server-Sent Event
                    yield f"data: {token}\n\n"
                
                # Send completion signal
                yield "data: [DONE]\n\n"
                
            except Exception as e:
                logger.error(f"Error during streaming: {e}", exc_info=True)
                yield f"data: [ERROR: {str(e)}]\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )
        
    except Exception as e:
        logger.error(f"Error in stream_chat: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing chat request: {str(e)}"
        )
