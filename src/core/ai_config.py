"""Azure AI Foundry configuration for LangChain/LangGraph."""
import json
import logging
from dataclasses import dataclass

from .config import settings

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for a single available AI model."""
    id: str
    display_name: str
    supports_tools: bool = True


class AIConfig:
    """Configuration for Azure AI Foundry using the project endpoint."""

    def __init__(self):
        """Initialize AI configuration from settings."""
        self.azure_openai_api_key = settings.azure_foundry_api_key
        self.azure_openai_deployment_name = settings.azure_foundry_model_name
        self.project_endpoint = settings.azure_foundry_project_endpoint
        self.available_models: list[ModelConfig] = self._parse_available_models()

    def _parse_available_models(self) -> list[ModelConfig]:
        """Parse available models from JSON config."""
        try:
            raw = json.loads(settings.azure_foundry_available_models)
            return [
                ModelConfig(
                    id=m["id"],
                    display_name=m.get("display_name", m["id"]),
                    supports_tools=m.get("supports_tools", True),
                )
                for m in raw
            ]
        except Exception as e:
            logger.warning(f"Failed to parse AZURE_FOUNDRY_AVAILABLE_MODELS: {e}")
            return []

    def get_model_config(self, model_id: str | None) -> ModelConfig | None:
        """Look up a model by ID. Returns None if not found (tools assumed supported)."""
        if not model_id:
            return None
        return next((m for m in self.available_models if m.id == model_id), None)

    def is_configured(self) -> bool:
        """Check if Azure AI Foundry is properly configured."""
        return settings.is_azure_foundry_configured
