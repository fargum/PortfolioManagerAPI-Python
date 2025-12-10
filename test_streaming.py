"""Test chat streaming with status updates."""
import asyncio
import httpx

async def test_chat_stream():
    """Test the chat streaming endpoint."""
    url = "http://127.0.0.1:8000/api/ai/chat/stream"
    payload = {
        "query": "Show me my portfolio holdings",
        "account_id": 1
    }
    
    print("Testing chat streaming with status updates...")
    print(f"Query: {payload['query']}")
    print("-" * 60)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", url, json=payload) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    content = line[6:]  # Remove "data: " prefix
                    if content == "[DONE]":
                        print("\n" + "-" * 60)
                        print("Stream complete!")
                        break
                    elif content.startswith("[ERROR"):
                        print(f"\nError: {content}")
                        break
                    else:
                        print(content, end="", flush=True)

if __name__ == "__main__":
    asyncio.run(test_chat_stream())
