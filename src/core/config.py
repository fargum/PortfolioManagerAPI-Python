"""Application configuration using Pydantic settings."""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/portfoliomanager"
    database_pool_size: int = 5
    database_max_overflow: int = 10
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True
    debug: bool = True
    
    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:4200"]
    
    # Logging
    log_level: str = "INFO"
    
    # EOD Historical Data API
    eod_api_token: str = ""
    eod_api_base_url: str = "https://eodhd.com/api"
    eod_api_timeout_seconds: int = 30
    
    @property
    def async_database_url(self) -> str:
        """Convert postgresql:// to postgresql+asyncpg:// for async operations."""
        return self.database_url.replace("postgresql://", "postgresql+asyncpg://")


# Global settings instance
settings = Settings()
