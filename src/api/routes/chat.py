"""AI Chat routes for streaming conversations."""
import logging
from typing import AsyncIterator, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.core.ai_config import get_azure_foundry_client, azure_foundry_config
from src.services.ai.agent_prompt_service import AgentPromptService
from src.services.ai.azure_foundry_chat_service import AzureFoundryChatService


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
def get_chat_service() -> AzureFoundryChatService:
    """Get configured Azure Foundry chat service."""
    client = get_azure_foundry_client()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Azure Foundry is not configured. Please set AZURE_FOUNDRY_ENDPOINT and AZURE_FOUNDRY_API_KEY."
        )
    
    return AzureFoundryChatService(
        client=client,
        model_name=azure_foundry_config.model_name
    )


def get_prompt_service() -> AgentPromptService:
    """Get agent prompt service."""
    return AgentPromptService()


# Routes
@router.get("/health", response_model=ChatHealthResponse)
async def health_check():
    """
    Health check for AI chat service.
    
    Returns configuration status and model information.
    """
    return ChatHealthResponse(
        status="healthy" if azure_foundry_config.is_configured() else "not_configured",
        azure_configured=azure_foundry_config.is_configured(),
        model_name=azure_foundry_config.model_name
    )


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    chat_service: AzureFoundryChatService = Depends(get_chat_service),
    prompt_service: AgentPromptService = Depends(get_prompt_service)
):
    """
    Stream AI chat response for user query.
    
    Uses portfolio advisor prompt from Phase 1 and streams tokens in real-time.
    
    Args:
        request: Chat request with query and account_id
        
    Returns:
        StreamingResponse with text/event-stream content
        
    Example:
        POST /api/ai/chat/stream
        {
            "query": "What is my portfolio value?",
            "account_id": 123
        }
    """
    try:
        # Get portfolio advisor prompt from Phase 1
        system_prompt = prompt_service.get_portfolio_advisor_prompt(
            account_id=request.account_id
        )
        
        # Build messages for chat
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.query}
        ]
        
        logger.info(f"Streaming chat for account {request.account_id}, query: {request.query[:50]}...")
        
        # Stream response
        async def generate() -> AsyncIterator[str]:
            """Generate streaming response."""
            try:
                async for token in chat_service.complete_chat_streaming_async(messages):
                    # Send token as Server-Sent Event
                    yield f"data: {token}\n\n"
                
                # Send completion signal
                yield "data: [DONE]\n\n"
                
            except Exception as e:
                logger.error(f"Error during streaming: {e}")
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
        logger.error(f"Error in stream_chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing chat request: {str(e)}"
        )
