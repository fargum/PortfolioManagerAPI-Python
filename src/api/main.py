"""Main FastAPI application."""
import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from src.api.routes import chat, holdings
from src.core.ai_config import AIConfig
from src.core.auth import get_azure_scheme
from src.core.config import settings
from src.core.telemetry import configure_telemetry, instrument_app
from src.db.session import AsyncSessionLocal


class UTCJsonFormatter(logging.Formatter):
    """Structured JSON formatter with UTC timestamps matching C# API format."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        log_entry = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def configure_logging() -> None:
    """Configure structured logging with JSON format."""
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler with JSON formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(settings.log_level)

    if settings.debug:
        # Human-readable format for development
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    else:
        # JSON format for production
        formatter = UTCJsonFormatter()

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


# Configure logging first
configure_logging()

# Configure OpenTelemetry
configure_telemetry()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and shutdown events."""
    # Startup
    logger.info("Starting Portfolio Manager Python API...")
    logger.info(f"Environment: {'Development' if settings.debug else 'Production'}")
    logger.info(f"Service: {settings.otel_service_name} v{settings.otel_service_version}")
    logger.info(f"OTLP Endpoint: {settings.resolved_otlp_endpoint}")
    if settings.is_azure_monitor_configured:
        logger.info("Azure Application Insights: Configured")

    # Initialize Azure AD authentication
    azure_scheme = get_azure_scheme()
    if azure_scheme:
        await azure_scheme.openid_config.load_config()
        logger.info("Azure AD authentication: Initialized")
    else:
        logger.warning("Azure AD authentication: Not configured (API running without auth)")

    yield
    # Shutdown
    logger.info("Shutting down Portfolio Manager Python API...")


# Create FastAPI app
app = FastAPI(
    title="Portfolio Manager API",
    description="Python FastAPI implementation of Portfolio Manager",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Instrument FastAPI with OpenTelemetry
instrument_app(app)

# Configure CORS
logger.info(f"Configuring CORS with origins: {settings.cors_origins}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info("CORS middleware configured")

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests with CORS headers."""
    origin = request.headers.get("origin", "No origin header")
    logger.info(f"Request: {request.method} {request.url.path} from origin: {origin}")
    response = await call_next(request)
    logger.info(f"Response headers: {dict(response.headers)}")
    return response

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    from fastapi.responses import JSONResponse
    # Log the full exception details for debugging (server-side only)
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    # Return a generic error message to the client - never expose internal details
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."}
    )

# Include routers
app.include_router(holdings.router)
app.include_router(chat.router)


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - basic service info."""
    return {
        "status": "healthy",
        "service": settings.otel_service_name,
        "version": settings.otel_service_version
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
        "service": settings.otel_service_name,
        "version": settings.otel_service_version,
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

    # Check telemetry configuration
    health_status["checks"]["telemetry"] = {
        "status": "configured",
        "otlp_endpoint": settings.resolved_otlp_endpoint,
        "azure_monitor": "configured" if settings.is_azure_monitor_configured else "not_configured"
    }

    # Check Azure AD authentication configuration
    health_status["checks"]["authentication"] = {
        "status": "configured" if settings.is_azure_ad_configured else "not_configured",
        "message": "Azure AD" if settings.is_azure_ad_configured else "Authentication disabled"
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
