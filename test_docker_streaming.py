import httpx
import json

def test_streaming_chat():
    url = "http://localhost:8000/api/ai/chat/stream"
    
    payload = {
        "account_id": 1,
        "query": "Show me my portfolio holdings and get the current prices for them",
        "conversation_id": None
    }
    
    print("🚀 Testing streaming chat with new features...")
    print(f"Query: {payload['query']}\n")
    print("=" * 80)
    
    with httpx.Client(timeout=60.0) as client:
        with client.stream("POST", url, json=payload) as response:
            print(f"Status Code: {response.status_code}\n")
            
            if response.status_code == 200:
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        data = line[6:]  # Remove "data: " prefix
                        if data.strip() == "[DONE]":
                            print("\n" + "=" * 80)
                            print("✅ Stream complete!")
                            break
                        try:
                            chunk = json.loads(data)
                            if isinstance(chunk, dict):
                                content = chunk.get("content", "")
                                if content:
                                    # Print content, checking for status emojis
                                    if any(emoji in content for emoji in ["📊", "💰", "✓"]):
                                        print(f"\n🔔 {content.strip()}", end="", flush=True)
                                    else:
                                        print(content, end="", flush=True)
                        except json.JSONDecodeError:
                            pass
            else:
                print(f"❌ Error: {response.status_code}")
                print(response.text)

if __name__ == "__main__":
    test_streaming_chat()
