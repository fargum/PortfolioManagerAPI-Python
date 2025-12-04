"""Azure AI Foundry client configuration and initialization."""
import logging
from typing import Optional
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from .config import settings

logger = logging.getLogger(__name__)


class AzureFoundryConfig:
    """Configuration for Azure AI Foundry client (matches C# AzureFoundryOptions)."""
    
    def __init__(self):
        """Initialize Azure Foundry configuration from settings."""
        self.endpoint = settings.azure_foundry_endpoint
        self.api_key = settings.azure_foundry_api_key
        self.model_name = settings.azure_foundry_model_name
        
    def is_configured(self) -> bool:
        """Check if Azure Foundry is properly configured."""
        return bool(self.endpoint and self.api_key)
    
    def create_client(self) -> Optional[ChatCompletionsClient]:
        """
        Create and return an Azure AI Inference client.
        
        Returns:
            ChatCompletionsClient if configured, None otherwise
            
        Raises:
            ValueError: If configuration is incomplete
        """
        if not self.is_configured():
            logger.warning("Azure Foundry configuration is incomplete. Set AZURE_FOUNDRY_ENDPOINT and AZURE_FOUNDRY_API_KEY in .env")
            return None
        
        try:
            client = ChatCompletionsClient(
                endpoint=self.endpoint,
                credential=AzureKeyCredential(self.api_key)
            )
            logger.info(f"Azure Foundry client initialized with endpoint: {self.endpoint}")
            return client
            
        except Exception as e:
            logger.error(f"Failed to create Azure Foundry client: {e}")
            raise ValueError(f"Azure Foundry client initialization failed: {e}")
    
    def get_model_config(self) -> dict:
        """Get model configuration dictionary for API calls."""
        return {
            "model": self.model_name,
            "temperature": 0.7,
            "max_tokens": 4096,
            "top_p": 0.95,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0
        }


# Global Azure Foundry config instance
azure_foundry_config = AzureFoundryConfig()


def get_azure_foundry_client() -> Optional[ChatCompletionsClient]:
    """
    Get or create Azure Foundry client instance.
    
    This is a convenience function for dependency injection.
    
    Returns:
        ChatCompletionsClient if configured, None otherwise
    """
    return azure_foundry_config.create_client()
