"""Test script for chat endpoint with streaming."""
import requests
import json

# Test 1: First message
print("=" * 80)
print("TEST 1: First message to establish context")
print("=" * 80)

response = requests.post(
    "http://127.0.0.1:8001/api/ai/chat/stream",
    json={
        "query": "What holdings do I have?",
        "account_id": 1
    },
    stream=True
)

print(f"Status Code: {response.status_code}")
print(f"Headers: {dict(response.headers)}")
print("\nResponse:")

for line in response.iter_lines():
    if line:
        decoded = line.decode('utf-8')
        print(decoded)
        if decoded == "data: [DONE]":
            break

print("\n" + "=" * 80)
print("TEST 2: Second message to test memory")
print("=" * 80)

# Test 2: Second message (should remember context)
response2 = requests.post(
    "http://127.0.0.1:8001/api/ai/chat/stream",
    json={
        "query": "What was my first question?",
        "account_id": 1
    },
    stream=True
)

print(f"Status Code: {response2.status_code}")
print("\nResponse:")

for line in response2.iter_lines():
    if line:
        decoded = line.decode('utf-8')
        print(decoded)
        if decoded == "data: [DONE]":
            break
