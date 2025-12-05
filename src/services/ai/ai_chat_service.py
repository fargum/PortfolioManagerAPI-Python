"""Protocol (interface) for AI chat services with streaming support."""
from typing import Protocol, AsyncIterator, List, Dict, Any
from typing_extensions import runtime_checkable


@runtime_checkable
class IAiChatService(Protocol):
    """
    Protocol for AI chat completion services with streaming support.
    
    This defines the interface that all AI chat service implementations must follow.
    Similar to C# IAiChatService interface.
    """
    
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
            
        Example:
            async for token in chat_service.complete_chat_streaming_async(messages):
                print(token, end="", flush=True)
        """
        ...
