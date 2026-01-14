"""OpenTelemetry configuration for comprehensive observability.

This module configures OpenTelemetry for tracing, metrics, and logging with:
- OTLP exporter for development (Aspire Dashboard)
- Azure Monitor integration for production
- Auto-instrumentation for FastAPI and HTTP clients
"""
import logging
import socket
from typing import Any, Optional

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from src.core.config import settings

logger = logging.getLogger(__name__)

# Global tracer for custom spans
_tracer: Optional[trace.Tracer] = None


def get_tracer() -> trace.Tracer:
    """Get the configured tracer for creating custom spans."""
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer(
            settings.otel_service_name,
            settings.otel_service_version
        )
    return _tracer


def _create_resource() -> Resource:
    """Create OpenTelemetry resource with service attributes."""
    environment = "Development" if settings.debug else "Production"

    return Resource.create({
        SERVICE_NAME: settings.otel_service_name,
        SERVICE_VERSION: settings.otel_service_version,
        "deployment.environment": environment,
        "service.instance.id": socket.gethostname(),
    })


def configure_telemetry() -> None:
    """
    Configure OpenTelemetry with tracing, metrics, and logging.

    Endpoint resolution follows the same hierarchy as the C# API:
    1. OTEL_EXPORTER_OTLP_ENDPOINT (Azure Container Apps standard)
    2. OTLP_ENDPOINT (backward compatibility)
    3. http://host.docker.internal:18889 (development default)
    """
    otlp_endpoint = settings.resolved_otlp_endpoint
    resource = _create_resource()

    logger.info(f"Configuring OpenTelemetry with endpoint: {otlp_endpoint}")
    logger.info(f"Service: {settings.otel_service_name} v{settings.otel_service_version}")

    # Configure Tracing
    _configure_tracing(resource, otlp_endpoint)

    # Configure Metrics
    _configure_metrics(resource, otlp_endpoint)

    # Configure Logging
    _configure_logging(resource, otlp_endpoint)

    # Configure Azure Monitor if available (production)
    if settings.is_azure_monitor_configured:
        _configure_azure_monitor()

    logger.info("OpenTelemetry configuration complete")


def _configure_tracing(resource: Resource, otlp_endpoint: str) -> None:
    """Configure distributed tracing with OTLP exporter."""
    tracer_provider = TracerProvider(resource=resource)

    # OTLP exporter for traces
    otlp_exporter = OTLPSpanExporter(
        endpoint=otlp_endpoint,
        insecure=True  # For local development; use TLS in production
    )

    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    trace.set_tracer_provider(tracer_provider)

    logger.info("Tracing configured with OTLP exporter")


def _configure_metrics(resource: Resource, otlp_endpoint: str) -> None:
    """Configure metrics collection with OTLP exporter."""
    otlp_metric_exporter = OTLPMetricExporter(
        endpoint=otlp_endpoint,
        insecure=True
    )

    metric_reader = PeriodicExportingMetricReader(
        otlp_metric_exporter,
        export_interval_millis=60000  # Export every 60 seconds
    )

    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[metric_reader]
    )

    metrics.set_meter_provider(meter_provider)

    logger.info("Metrics configured with OTLP exporter")


def _configure_logging(resource: Resource, otlp_endpoint: str) -> None:
    """Configure structured logging with OTLP exporter."""
    logger_provider = LoggerProvider(resource=resource)

    otlp_log_exporter = OTLPLogExporter(
        endpoint=otlp_endpoint,
        insecure=True
    )

    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(otlp_log_exporter)
    )

    set_logger_provider(logger_provider)

    # Add OpenTelemetry handler to root logger
    handler = LoggingHandler(
        level=logging.NOTSET,
        logger_provider=logger_provider
    )
    logging.getLogger().addHandler(handler)

    logger.info("Logging configured with OTLP exporter")


def _configure_azure_monitor() -> None:
    """Configure Azure Application Insights integration for production."""
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(
            connection_string=settings.applicationinsights_connection_string
        )
        logger.info("Azure Monitor configured for production telemetry")
    except ImportError:
        logger.warning(
            "azure-monitor-opentelemetry not installed, "
            "skipping Azure Monitor configuration"
        )
    except Exception as e:
        logger.error(f"Failed to configure Azure Monitor: {e}")


def instrument_app(app: Any) -> None:
    """
    Apply auto-instrumentation to the FastAPI application.

    Instruments:
    - FastAPI requests and responses
    - HTTPX client calls
    - Python logging
    """
    # FastAPI instrumentation
    FastAPIInstrumentor.instrument_app(app)
    logger.info("FastAPI instrumentation enabled")

    # HTTPX client instrumentation (for external API calls)
    HTTPXClientInstrumentor().instrument()
    logger.info("HTTPX client instrumentation enabled")

    # Logging instrumentation (adds trace context to logs)
    LoggingInstrumentor().instrument(set_logging_format=True)
    logger.info("Logging instrumentation enabled")
