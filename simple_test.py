"""Simple test to check the chat endpoint."""
import requests
import json

print("Testing chat endpoint...")
print("=" * 80)

try:
    response = requests.post(
        "http://127.0.0.1:8001/api/ai/chat/stream",
        json={
            "query": "What holdings do I have?",
            "account_id": 1
        },
        timeout=30
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    print(f"\nResponse Text:")
    print(response.text[:500])
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
