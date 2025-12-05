"""Azure Foundry implementation of streaming AI chat service."""
import logging
from typing import AsyncIterator, List, Dict, Any
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage, AssistantMessage

from .ai_chat_service import IAiChatService

logger = logging.getLogger(__name__)


class AzureFoundryChatService:
    """
    Azure Foundry implementation of streaming AI chat service.
    Uses the ChatCompletionsClient from azure-ai-inference SDK.
    """
    
    def __init__(self, client: ChatCompletionsClient, model_name: str):
        """
        Initialize the Azure Foundry chat service.
        
        Args:
            client: Configured ChatCompletionsClient from Phase 1
            model_name: Model deployment name (e.g., "gpt-5-mini")
        """
        self.client = client
        self.model_name = model_name
        
    async def complete_chat_streaming_async(
        self,
        messages: List[Dict[str, str]]
    ) -> AsyncIterator[str]:
        """
        Complete a chat conversation with streaming response.
        
        Args:
            messages: List of chat messages in format:
                [
                    {"role": "system", "content": "You are a helpful assistant"},
                    {"role": "user", "content": "Hello!"}
                ]
                
        Yields:
            str: Tokens/chunks of the response as they arrive
            
        Raises:
            ValueError: If message format is invalid
            Exception: If Azure API call fails
        """
        try:
            # Convert dict messages to Azure AI message types
            azure_messages = self._convert_messages(messages)
            
            logger.info(f"Starting streaming chat completion with {len(messages)} messages using model {self.model_name}")
            
            # Stream the response from Azure
            # Note: Model is NOT passed here because it's already in the endpoint URL
            # Azure OpenAI endpoint format: https://{resource}.openai.azure.com/openai/deployments/{model-name}
            # GPT-5 mini has limited parameter support - using defaults
            response = self.client.complete(
                messages=azure_messages,
                stream=True
            )
            
            # Yield tokens as they arrive
            for chunk in response:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content
                        
            logger.info("Streaming chat completion finished successfully")
            
        except Exception as e:
            logger.error(f"Error during streaming chat completion: {e}")
            raise
    
    def _convert_messages(self, messages: List[Dict[str, str]]) -> List[Any]:
        """
        Convert dictionary messages to Azure AI message types.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            
        Returns:
            List of Azure AI message objects (SystemMessage, UserMessage, AssistantMessage)
            
        Raises:
            ValueError: If message format is invalid or role is unknown
        """
        azure_messages = []
        
        for msg in messages:
            role = msg.get("role", "").lower()
            content = msg.get("content", "")
            
            if not content:
                raise ValueError(f"Message content cannot be empty for role: {role}")
            
            if role == "system":
                azure_messages.append(SystemMessage(content=content))
            elif role == "user":
                azure_messages.append(UserMessage(content=content))
            elif role == "assistant":
                azure_messages.append(AssistantMessage(content=content))
            else:
                raise ValueError(f"Unknown message role: {role}. Must be 'system', 'user', or 'assistant'")
        
        return azure_messages
