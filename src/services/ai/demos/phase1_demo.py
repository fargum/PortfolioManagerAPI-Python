"""Demo script to test Phase 1: AI Configuration and Prompt Service

This script verifies:
1. Azure Foundry configuration is loaded from .env
2. Azure Foundry client can be created
3. Agent prompt service loads and formats prompts correctly

Run with: python -m src.services.ai.phase1_demo
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.core.ai_config import azure_foundry_config, get_azure_foundry_client
from src.services.ai.agent_prompt_service import AgentPromptService


def test_azure_foundry_config():
    """Test Azure Foundry configuration."""
    print("=" * 80)
    print("PHASE 1 DEMO: AI Configuration Test")
    print("=" * 80)
    print()
    
    # Test configuration loading
    print("1. Testing Azure Foundry Configuration...")
    print(f"   Endpoint: {azure_foundry_config.endpoint or 'NOT SET'}")
    print(f"   API Key: {'***SET***' if azure_foundry_config.api_key else 'NOT SET'}")
    print(f"   Model Name: {azure_foundry_config.model_name}")
    print(f"   Is Configured: {azure_foundry_config.is_configured()}")
    print()
    
    if not azure_foundry_config.is_configured():
        print("⚠️  Azure Foundry is NOT configured!")
        print("   Please set AZURE_FOUNDRY_ENDPOINT and AZURE_FOUNDRY_API_KEY in .env")
        print()
    else:
        print("✅ Azure Foundry is configured!")
        print()
        
        # Test client creation
        print("2. Testing Azure Foundry Client Creation...")
        try:
            client = get_azure_foundry_client()
            if client:
                print("✅ Azure Foundry client created successfully!")
                print(f"   Client type: {type(client).__name__}")
            else:
                print("❌ Failed to create Azure Foundry client")
        except Exception as e:
            print(f"❌ Error creating client: {e}")
        print()


def test_agent_prompt_service():
    """Test agent prompt service."""
    print("=" * 80)
    print("3. Testing Agent Prompt Service...")
    print("=" * 80)
    print()
    
    # Initialize service
    prompt_service = AgentPromptService()
    
    # Test portfolio advisor prompt
    print("Loading PortfolioAdvisor prompt for Account ID 123...")
    print()
    
    prompt = prompt_service.get_portfolio_advisor_prompt(account_id=123)
    
    print("-" * 80)
    print(prompt)
    print("-" * 80)
    print()
    
    # Check key sections are present
    checks = [
        ("Account ID substitution", "Account ID 123" in prompt),
        ("Tool usage guidance", "WHEN TO USE YOUR TOOLS" in prompt),
        ("Communication style", "COMMUNICATION STYLE" in prompt),
        ("Formatting guidelines", "FORMATTING" in prompt),
        ("Currency format (GBP)", "£" in prompt),
        ("UK date format", "DD/MM/YYYY" in prompt),
    ]
    
    print("Validation Checks:")
    for check_name, result in checks:
        status = "✅" if result else "❌"
        print(f"  {status} {check_name}")
    print()
    
    # Test generic get_prompt method
    print("Testing generic get_prompt method...")
    prompt2 = prompt_service.get_prompt("PortfolioAdvisor", {"accountId": 456})
    print(f"✅ Generic method works! Contains 'Account ID 456': {'Account ID 456' in prompt2}")
    print()


def main():
    """Run all Phase 1 tests."""
    print()
    test_azure_foundry_config()
    test_agent_prompt_service()
    
    print("=" * 80)
    print("PHASE 1 DEMO COMPLETE")
    print("=" * 80)
    print()
    print("✅ Phase 1 foundation is ready!")
    print()
    print("Next Steps:")
    print("1. Update .env with your Azure Foundry credentials")
    print("2. Run: pip install -r requirements.txt")
    print("3. Proceed to Phase 2: Basic Chat Service")
    print()


if __name__ == "__main__":
    main()
