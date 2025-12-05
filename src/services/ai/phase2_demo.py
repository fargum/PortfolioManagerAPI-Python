"""
Demo script to test Phase 2: Streaming Chat Service

This script verifies:
1. Chat service can stream responses from Azure Foundry
2. Integration with Phase 1 agent prompt service
3. Real-time token streaming (typewriter effect)

Run with: python -m src.services.ai.phase2_demo
"""
import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.core.ai_config import get_azure_foundry_client, azure_foundry_config
from src.services.ai.agent_prompt_service import AgentPromptService
from src.services.ai.azure_foundry_chat_service import AzureFoundryChatService


async def test_simple_streaming():
    """Test basic streaming chat completion."""
    print("=" * 80)
    print("TEST 1: Simple Streaming Chat")
    print("=" * 80)
    print()
    
    # Get configured client from Phase 1
    client = get_azure_foundry_client()
    if not client:
        print("❌ Azure Foundry is not configured!")
        print("   Please set AZURE_FOUNDRY_ENDPOINT and AZURE_FOUNDRY_API_KEY in .env")
        return False
    
    # Create chat service
    chat_service = AzureFoundryChatService(
        client=client,
        model_name=azure_foundry_config.model_name
    )
    
    # Simple test messages
    messages = [
        {"role": "system", "content": "You are a helpful AI assistant. Keep responses brief (2-3 sentences)."},
        {"role": "user", "content": "What is Python?"}
    ]
    
    print("Question: What is Python?")
    print()
    print("Streaming Response:")
    print("-" * 80)
    
    full_response = ""
    try:
        async for token in chat_service.complete_chat_streaming_async(messages):
            print(token, end="", flush=True)
            full_response += token
        
        print()
        print("-" * 80)
        print()
        print(f"✅ Streaming completed successfully!")
        print(f"   Total characters: {len(full_response)}")
        print()
        return True
        
    except Exception as e:
        print()
        print("-" * 80)
        print(f"❌ Streaming failed: {e}")
        print()
        return False


async def test_portfolio_advisor_streaming():
    """Test streaming with portfolio advisor prompt from Phase 1."""
    print("=" * 80)
    print("TEST 2: Portfolio Advisor Streaming Chat")
    print("=" * 80)
    print()
    
    # Get configured client from Phase 1
    client = get_azure_foundry_client()
    if not client:
        print("❌ Azure Foundry is not configured!")
        return False
    
    # Create chat service
    chat_service = AzureFoundryChatService(
        client=client,
        model_name=azure_foundry_config.model_name
    )
    
    # Get portfolio advisor prompt from Phase 1
    prompt_service = AgentPromptService()
    system_prompt = prompt_service.get_portfolio_advisor_prompt(account_id=123)
    
    print("Using Portfolio Advisor prompt for Account ID 123")
    print()
    
    # Test with portfolio-related question
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Hello! Can you introduce yourself?"}
    ]
    
    print("User: Hello! Can you introduce yourself?")
    print()
    print("Assistant:")
    print("-" * 80)
    
    full_response = ""
    try:
        async for token in chat_service.complete_chat_streaming_async(messages):
            print(token, end="", flush=True)
            full_response += token
        
        print()
        print("-" * 80)
        print()
        
        # Validate response contains expected elements
        checks = [
            ("Mentions Account ID 123", "123" in full_response or "account" in full_response.lower()),
            ("Friendly tone", any(word in full_response.lower() for word in ["help", "assist", "portfolio", "advisor"])),
            ("Reasonable length", 50 < len(full_response) < 1000)
        ]
        
        print("Validation Checks:")
        for check_name, result in checks:
            status = "✅" if result else "⚠️"
            print(f"  {status} {check_name}")
        print()
        
        print(f"✅ Portfolio advisor streaming completed successfully!")
        print(f"   Response length: {len(full_response)} characters")
        print()
        return True
        
    except Exception as e:
        print()
        print("-" * 80)
        print(f"❌ Streaming failed: {e}")
        print()
        return False


async def test_multi_turn_conversation():
    """Test streaming with multi-turn conversation."""
    print("=" * 80)
    print("TEST 3: Multi-Turn Conversation Streaming")
    print("=" * 80)
    print()
    
    # Get configured client from Phase 1
    client = get_azure_foundry_client()
    if not client:
        print("❌ Azure Foundry is not configured!")
        return False
    
    # Create chat service
    chat_service = AzureFoundryChatService(
        client=client,
        model_name=azure_foundry_config.model_name
    )
    
    # Get portfolio advisor prompt
    prompt_service = AgentPromptService()
    system_prompt = prompt_service.get_portfolio_advisor_prompt(account_id=456)
    
    # Multi-turn conversation
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "What types of questions can you help me with?"},
        {"role": "assistant", "content": "I can help you with questions about your portfolio holdings, performance analysis, market trends, and investment insights. I have access to your portfolio data and can provide detailed analysis."},
        {"role": "user", "content": "Great! What format do you use for currency?"}
    ]
    
    print("User: What types of questions can you help me with?")
    print("Assistant: [previous response about capabilities]")
    print()
    print("User: Great! What format do you use for currency?")
    print()
    print("Assistant:")
    print("-" * 80)
    
    full_response = ""
    try:
        async for token in chat_service.complete_chat_streaming_async(messages):
            print(token, end="", flush=True)
            full_response += token
        
        print()
        print("-" * 80)
        print()
        
        # Should mention GBP/£ format
        mentions_gbp = "gbp" in full_response.lower() or "£" in full_response
        
        print(f"✅ Multi-turn conversation streaming completed!")
        print(f"   Mentions GBP currency: {'✅ Yes' if mentions_gbp else '⚠️ No'}")
        print()
        return True
        
    except Exception as e:
        print()
        print("-" * 80)
        print(f"❌ Streaming failed: {e}")
        print()
        return False


async def main():
    """Run all Phase 2 tests."""
    print()
    print("=" * 80)
    print("PHASE 2 DEMO: Streaming Chat Service")
    print("=" * 80)
    print()
    
    # Check configuration first
    if not azure_foundry_config.is_configured():
        print("❌ Azure Foundry is NOT configured!")
        print("   Please set AZURE_FOUNDRY_ENDPOINT and AZURE_FOUNDRY_API_KEY in .env")
        print()
        return
    
    print(f"✅ Azure Foundry configured: {azure_foundry_config.endpoint}")
    print(f"✅ Model: {azure_foundry_config.model_name}")
    print()
    
    # Run tests
    test1_passed = await test_simple_streaming()
    test2_passed = await test_portfolio_advisor_streaming()
    test3_passed = await test_multi_turn_conversation()
    
    # Summary
    print("=" * 80)
    print("PHASE 2 DEMO COMPLETE")
    print("=" * 80)
    print()
    
    tests = [
        ("Simple Streaming", test1_passed),
        ("Portfolio Advisor", test2_passed),
        ("Multi-Turn Conversation", test3_passed)
    ]
    
    print("Test Results:")
    for test_name, passed in tests:
        status = "✅" if passed else "❌"
        print(f"  {status} {test_name}")
    print()
    
    all_passed = all(result for _, result in tests)
    
    if all_passed:
        print("✅ Phase 2 streaming foundation is ready!")
        print()
        print("Next Steps:")
        print("1. Phase 3: Add MCP tool integration")
        print("2. Phase 4: Add AI orchestration with agent framework")
        print("3. Phase 5: Add conversation memory and guardrails")
    else:
        print("⚠️ Some tests failed. Please check the errors above.")
    print()


if __name__ == "__main__":
    asyncio.run(main())
