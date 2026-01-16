"""Application configuration using Pydantic settings."""
import json
from typing import List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    # Database
    database_url: str  # Required - no default (must be set in .env)
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True
    debug: bool = True

    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:4200", "http://localhost:8081"]

    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse CORS origins from JSON string or list."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [v]
        return v

    # Logging
    log_level: str = "INFO"

    # EOD Historical Data API
    eod_api_token: str = ""
    eod_api_base_url: str = "https://eodhd.com/api"
    eod_api_timeout_seconds: int = 30

    # Azure AI Foundry Configuration (optional - AI features disabled if not set)
    azure_foundry_endpoint: str = ""  # Optional - AI features disabled if not set
    azure_foundry_api_key: str = ""  # Optional - AI features disabled if not set
    azure_foundry_model_name: str = "gpt-4o-mini"
    azure_foundry_api_version: str = "2024-08-01-preview"

    # Voice mode settings
    enable_voice_debug: bool = False

    # Azure AD Authentication Configuration
    # All values loaded from .env file - use same values as C# API
    azure_ad_tenant_id: str = ""
    azure_ad_client_id: str = ""
    azure_ad_audience: str = ""

    # OpenTelemetry Configuration
    # Endpoint resolution priority:
    # 1. OTEL_EXPORTER_OTLP_ENDPOINT - Azure Container Apps standard (production)
    # 2. OTLP_ENDPOINT - Custom configuration (backward compatibility)
    # 3. Default: http://host.docker.internal:18889 (development)
    otel_exporter_otlp_endpoint: str = ""
    otlp_endpoint: str = ""
    otel_service_name: str = "PortfolioManager.PythonAPI"
    otel_service_version: str = "1.0.0"

    # Azure Application Insights (production)
    applicationinsights_connection_string: str = ""

    @property
    def resolved_otlp_endpoint(self) -> str:
        """Resolve OTLP endpoint with fallback hierarchy."""
        if self.otel_exporter_otlp_endpoint:
            return self.otel_exporter_otlp_endpoint
        if self.otlp_endpoint:
            return self.otlp_endpoint
        return "http://host.docker.internal:18889"

    @property
    def is_azure_monitor_configured(self) -> bool:
        """Check if Azure Application Insights is configured."""
        return bool(self.applicationinsights_connection_string)

    @property
    def async_database_url(self) -> str:
        """Convert postgresql:// to postgresql+asyncpg:// for async operations."""
        return self.database_url.replace("postgresql://", "postgresql+asyncpg://")

    @property
    def is_azure_foundry_configured(self) -> bool:
        """Check if Azure Foundry is properly configured."""
        return bool(self.azure_foundry_endpoint and self.azure_foundry_api_key)

    @property
    def is_azure_ad_configured(self) -> bool:
        """Check if Azure AD authentication is configured."""
        return bool(self.azure_ad_tenant_id and self.azure_ad_client_id)


# Global settings instance
settings = Settings()
