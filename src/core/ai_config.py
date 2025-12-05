"""Azure OpenAI configuration for LangChain/LangGraph."""
import logging
from .config import settings

logger = logging.getLogger(__name__)


class AIConfig:
    """Configuration for Azure OpenAI using existing Azure Foundry settings."""
    
    def __init__(self):
        """Initialize Azure OpenAI configuration from existing settings."""
        self.azure_openai_endpoint = settings.azure_foundry_endpoint
        self.azure_openai_api_key = settings.azure_foundry_api_key
        self.azure_openai_api_version = settings.azure_foundry_api_version
        self.azure_openai_deployment_name = settings.azure_foundry_model_name
        
    def is_configured(self) -> bool:
        """Check if Azure OpenAI is properly configured."""
        return settings.is_azure_foundry_configured
