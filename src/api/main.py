"""Main FastAPI application."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from src.core.config import settings
from src.core.ai_config import AIConfig
from src.api.routes import holdings, chat
from src.db.session import AsyncSessionLocal

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and shutdown events."""
    # Startup
    logger.info("Starting Portfolio Manager API...")
    logger.info(f"Environment: {'Development' if settings.debug else 'Production'}")
    yield
    # Shutdown
    logger.info("Shutting down Portfolio Manager API...")


# Create FastAPI app
app = FastAPI(
    title="Portfolio Manager API",
    description="Python FastAPI implementation of Portfolio Manager",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    from fastapi.responses import JSONResponse
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )

# Include routers
app.include_router(holdings.router)
app.include_router(chat.router)


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - basic service info."""
    return {
        "status": "healthy",
        "service": "Portfolio Manager API",
        "version": "0.1.0"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Comprehensive health check endpoint.
    
    Verifies:
    - Database connectivity (executes SELECT 1)
    - AI configuration status (Azure AI Foundry)
    
    Returns 200 if all systems operational, 503 if critical services unavailable.
    """
    health_status = {
        "status": "healthy",
        "service": "Portfolio Manager API",
        "version": "0.1.0",
        "checks": {}
    }
    
    # Check database connectivity
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            result.scalar()
            health_status["checks"]["database"] = {
                "status": "healthy",
                "message": "Connected"
            }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_status["status"] = "unhealthy"
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "message": f"Connection failed: {str(e)}"
        }
    
    # Check AI configuration
    try:
        ai_config = AIConfig()
        is_configured = ai_config.azure_openai_endpoint and ai_config.azure_openai_api_key
        health_status["checks"]["ai"] = {
            "status": "configured" if is_configured else "not_configured",
            "message": f"Azure AI Foundry: {'Ready' if is_configured else 'Not configured'}",
            "model": ai_config.azure_openai_deployment_name if is_configured else None
        }
    except Exception as e:
        logger.warning(f"AI configuration check failed: {e}")
        health_status["checks"]["ai"] = {
            "status": "error",
            "message": f"Configuration error: {str(e)}"
        }
    
    # Return 503 if critical services (database) are down
    from fastapi import status
    from fastapi.responses import JSONResponse
    
    status_code = status.HTTP_200_OK if health_status["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
    
    return JSONResponse(content=health_status, status_code=status_code)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower()
    )
