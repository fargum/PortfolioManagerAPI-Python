"""Test the AI chat streaming API endpoint."""
import asyncio
import aiohttp


async def test_streaming_endpoint():
    """Test the streaming chat endpoint."""
    url = "http://localhost:8000/api/ai/chat/stream"
    
    payload = {
        "query": "Hello! Can you introduce yourself?",
        "account_id": 123
    }
    
    print("Testing AI Chat Streaming Endpoint")
    print("=" * 80)
    print(f"URL: {url}")
    print(f"Query: {payload['query']}")
    print(f"Account ID: {payload['account_id']}")
    print()
    print("Streaming Response:")
    print("-" * 80)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"❌ Error: {response.status}")
                    print(error_text)
                    return
                
                # Stream the response
                async for line in response.content:
                    decoded_line = line.decode('utf-8').strip()
                    
                    if decoded_line.startswith("data: "):
                        data = decoded_line[6:]  # Remove "data: " prefix
                        
                        if data == "[DONE]":
                            print()
                            print("-" * 80)
                            print("✅ Streaming completed!")
                            break
                        elif data.startswith("[ERROR"):
                            print()
                            print("-" * 80)
                            print(f"❌ {data}")
                            break
                        else:
                            # Print token without newline
                            print(data, end="", flush=True)
    
    except Exception as e:
        print()
        print("-" * 80)
        print(f"❌ Error: {e}")


async def test_health_endpoint():
    """Test the health check endpoint."""
    url = "http://localhost:8000/api/ai/chat/health"
    
    print()
    print("Testing Health Endpoint")
    print("=" * 80)
    print(f"URL: {url}")
    print()
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Status: {data['status']}")
                    print(f"✅ Azure Configured: {data['azure_configured']}")
                    print(f"✅ Model: {data['model_name']}")
                else:
                    error_text = await response.text()
                    print(f"❌ Error: {response.status}")
                    print(error_text)
    
    except Exception as e:
        print(f"❌ Error: {e}")


async def main():
    """Run all tests."""
    await test_health_endpoint()
    print()
    await test_streaming_endpoint()


if __name__ == "__main__":
    asyncio.run(main())
