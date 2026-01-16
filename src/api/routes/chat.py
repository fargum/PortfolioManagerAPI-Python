"""AI Chat routes for streaming conversations with LangGraph agents."""
import logging
import time
from functools import lru_cache
from typing import AsyncIterator, Literal, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from src.core.ai_config import AIConfig
from src.core.auth import get_current_account_id
from src.core.config import Settings
from src.core.config import settings as app_settings
from src.core.telemetry import get_tracer
from src.db.session import get_db
from src.schemas.voice import UIResponse, VoiceResponse
from src.services.ai.agent_prompt_service import AgentPromptService
from src.services.ai.langgraph_agent_service import LangGraphAgentService
from src.services.ai.voice_adapter import VoiceResponseAdapter
from src.services.metrics_service import MetricsService, get_metrics_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai/chat", tags=["ai-chat"])


# Request/Response Models
class ChatRequest(BaseModel):
    """Chat request from client."""

    query: str = Field(..., description="User's question or message")
    thread_id: Optional[int] = Field(
        None, description="Conversation thread ID for multi-turn chat"
    )
    mode: Literal["ui", "voice"] = Field(
        "ui", description="Response mode: 'ui' for markdown, 'voice' for TTS-optimized"
    )
    max_speak_words: int = Field(
        100,
        ge=10,
        le=100,
        alias="maxSpeakWords",
        description="Max words for speak_text in voice mode",
    )

    model_config = ConfigDict(populate_by_name=True)


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
    return app_settings


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
    account_id: int = Depends(get_current_account_id),
    agent_service: LangGraphAgentService = Depends(get_agent_service),
    db = Depends(get_db),
    metrics: MetricsService = Depends(get_metrics_service)
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
    tracer = get_tracer()

    with tracer.start_as_current_span("StreamChat") as span:
        span.set_attribute("account.id", account_id)
        span.set_attribute("mode", "stream")
        span.set_attribute("query.length", len(request.query))

        try:
            logger.info(
                f"Streaming LangGraph agent for account {account_id}, "
                f"query: {request.query[:50]}..."
            )

            metrics.increment_ai_chat_requests(account_id, "stream", "requested")
            start_time = time.perf_counter()

            # Stream response using LangGraph agent with conversation memory
            async def generate() -> AsyncIterator[str]:
                """Generate streaming response."""
                try:
                    async for token in agent_service.stream_chat(
                        user_message=request.query,
                        account_id=account_id,
                        db=db,  # Database session for this request
                        thread_id=request.thread_id  # Optional thread ID for conversation continuity
                    ):
                        # Send token as Server-Sent Event
                        yield f"data: {token}\n\n"

                    # Send completion signal
                    yield "data: [DONE]\n\n"

                    # Record success metrics
                    duration = time.perf_counter() - start_time
                    metrics.record_ai_chat_request_duration(
                        duration, account_id, "stream",
                        agent_service.ai_config.azure_openai_deployment_name, "success"
                    )

                except Exception as e:
                    logger.error(f"Error during streaming: {e}", exc_info=True)
                    duration = time.perf_counter() - start_time
                    metrics.record_ai_chat_request_duration(
                        duration, account_id, "stream",
                        agent_service.ai_config.azure_openai_deployment_name, "error"
                    )
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
            span.set_attribute("error", True)
            span.record_exception(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing chat request: {str(e)}"
            )


@router.post("/respond", response_model=Union[UIResponse, VoiceResponse])
async def respond_chat(
    request: ChatRequest,
    account_id: int = Depends(get_current_account_id),
    agent_service: LangGraphAgentService = Depends(get_agent_service),
    settings: Settings = Depends(get_settings),
    db=Depends(get_db),
    metrics: MetricsService = Depends(get_metrics_service),
):
    """
    Non-streaming chat response endpoint with mode support.

    Modes:
    - ui: Returns {"answer": "<markdown>"}
    - voice: Returns VoiceResponse with speak_text, sources, actions, telemetry

    Args:
        request: Chat request with query, account_id, mode, and optional max_speak_words

    Returns:
        UIResponse for ui mode, VoiceResponse for voice mode

    Example:
        POST /api/ai/chat/respond
        {
            "query": "How is my portfolio performing?",
            "account_id": 123,
            "mode": "voice",
            "maxSpeakWords": 100
        }
    """
    tracer = get_tracer()

    with tracer.start_as_current_span("RespondChat") as span:
        span.set_attribute("account.id", account_id)
        span.set_attribute("mode", request.mode)
        span.set_attribute("query.length", len(request.query))

        with metrics.track_ai_chat_request(
            account_id,
            request.mode,
            agent_service.ai_config.azure_openai_deployment_name
        ):
            try:
                start_time = time.perf_counter()

                logger.info(
                    f"Respond chat for account {account_id}, "
                    f"mode: {request.mode}, query: {request.query[:50]}..."
                )

                # Execute non-streaming chat with tool event capture
                # Use voice_mode=True for voice requests to get structured response
                final_text, tool_events = await agent_service.run_chat(
                    user_message=request.query,
                    account_id=account_id,
                    db=db,
                    thread_id=request.thread_id,
                    voice_mode=(request.mode == "voice"),
                )

                latency_ms = int((time.perf_counter() - start_time) * 1000)
                span.set_attribute("latency.ms", latency_ms)
                span.set_attribute("response.length", len(final_text))

                if request.mode == "ui":
                    return UIResponse(answer=final_text)

                # Voice mode: use adapter to build response
                adapter = VoiceResponseAdapter(
                    final_text=final_text,
                    tool_events=tool_events,
                    query=request.query,
                    max_speak_words=request.max_speak_words,
                    model_name=agent_service.ai_config.azure_openai_deployment_name,
                    latency_ms=latency_ms,
                    include_telemetry=settings.enable_voice_debug,
                )

                return adapter.build()

            except Exception as e:
                logger.error(f"Error in respond_chat: {e}", exc_info=True)
                span.set_attribute("error", True)
                span.record_exception(e)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error processing chat request: {str(e)}",
                )
