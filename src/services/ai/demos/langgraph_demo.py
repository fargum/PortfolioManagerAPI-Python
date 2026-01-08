"""
Phase 3 Demo: LangGraph Agent with Portfolio Tools

Demonstrates:
1. LangGraph create_react_agent for stateful workflows
2. LangChain @tool decorator pattern
3. Automatic tool orchestration
4. Streaming responses with tool calls

Compared to manual implementation:
- No custom tool registry needed
- No manual tool_calls handling
- Built-in streaming support
- Cleaner code with @tool decorator
"""
import asyncio
import logging
import sys
from datetime import datetime

# Set UTF-8 encoding for stdout to handle Unicode characters
if sys.platform == "win32" and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')  # type: ignore[union-attr]

from src.core.ai_config import AIConfig
from src.core.config import settings
from src.db.session import get_db
from src.services.holding_service import HoldingService
from src.services.ai.agent_prompt_service import AgentPromptService
from src.services.ai.portfolio_analysis_service import PortfolioAnalysisService
from src.services.ai.langgraph_agent_service import LangGraphAgentService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_basic_tool_call():
    """Test basic tool calling: get portfolio holdings."""
    print("\n" + "=" * 80)
    print("TEST 1: Basic Tool Call - Get Portfolio Holdings")
    print("=" * 80 + "\n")
    
    # Setup singleton agent service
    ai_config = AIConfig()
    prompt_service = AgentPromptService()
    agent_service = LangGraphAgentService(
        ai_config=ai_config,
        agent_prompt_service=prompt_service
    )
    
    # Get database session
    db = await anext(get_db())
    try:
        # Test query
        account_id = 1
        query = "Show me my portfolio holdings for today"
        
        print(f"User Query: {query}")
        print(f"Account ID: {account_id}")
        print("\nAgent Response (streaming):\n")
        
        # Stream response
        response_tokens = []
        async for token in agent_service.stream_chat(
            user_message=query,
            account_id=account_id,
            db=db
        ):
            print(token, end='', flush=True)
            response_tokens.append(token)
        
        print("\n")
        
        return ''.join(response_tokens)
        
    finally:
        await db.close()


async def test_portfolio_analysis():
    """Test portfolio analysis tool."""
    print("\n" + "=" * 80)
    print("TEST 2: Portfolio Analysis - Performance Metrics")
    print("=" * 80 + "\n")
    
    # Setup singleton agent service
    ai_config = AIConfig()
    prompt_service = AgentPromptService()
    agent_service = LangGraphAgentService(
        ai_config=ai_config,
        agent_prompt_service=prompt_service
    )
    
    # Get database session
    db = await anext(get_db())
    try:
        # Test query
        account_id = 1
        query = "How is my portfolio performing today? Give me a detailed analysis."
        
        print(f"User Query: {query}")
        print(f"Account ID: {account_id}")
        print("\nAgent Response (streaming):\n")
        
        # Stream response
        response_tokens = []
        async for token in agent_service.stream_chat(
            user_message=query,
            account_id=account_id,
            db=db
        ):
            print(token, end='', flush=True)
            response_tokens.append(token)
        
        print("\n")
        
        return ''.join(response_tokens)
        
    finally:
        await db.close()


async def test_portfolio_comparison():
    """Test portfolio comparison tool."""
    print("\n" + "=" * 80)
    print("TEST 3: Portfolio Comparison - Historical Analysis")
    print("=" * 80 + "\n")
    
    # Setup singleton agent service
    ai_config = AIConfig()
    prompt_service = AgentPromptService()
    agent_service = LangGraphAgentService(
        ai_config=ai_config,
        agent_prompt_service=prompt_service
    )
    
    # Get database session
    db = await anext(get_db())
    try:
        # Test query
        account_id = 1
        query = "Compare my portfolio performance between yesterday and today"
        
        print(f"User Query: {query}")
        print(f"Account ID: {account_id}")
        print("\nAgent Response (streaming):\n")
        
        # Stream response
        response_tokens = []
        async for token in agent_service.stream_chat(
            user_message=query,
            account_id=account_id,
            db=db
        ):
            print(token, end='', flush=True)
            response_tokens.append(token)
        
        print("\n")
        
        return ''.join(response_tokens)
        
    finally:
        await db.close()


async def test_multi_turn_conversation():
    """Test multi-turn conversation with context."""
    print("\n" + "=" * 80)
    print("TEST 4: Multi-Turn Conversation with Context")
    print("=" * 80 + "\n")
    
    # Setup singleton agent service
    ai_config = AIConfig()
    prompt_service = AgentPromptService()
    agent_service = LangGraphAgentService(
        ai_config=ai_config,
        agent_prompt_service=prompt_service
    )
    
    # Get database session
    db = await anext(get_db())
    try:
        account_id = 1
        
        # First turn
        query1 = "Show me my portfolio holdings"
        print(f"User: {query1}")
        print("\nAgent Response:\n")
        
        response1_tokens = []
        async for token in agent_service.stream_chat(
            user_message=query1,
            account_id=account_id,
            db=db
        ):
            print(token, end='', flush=True)
            response1_tokens.append(token)
        
        response1 = ''.join(response1_tokens)
        print("\n")
        
        # Second turn with context
        query2 = "Which holdings are performing best?"
        print(f"\nUser: {query2}")
        print("\nAgent Response:\n")
        
        # Build conversation history
        conversation_history = [
            {"role": "user", "content": query1},
            {"role": "assistant", "content": response1}
        ]
        
        response2_tokens = []
        async for token in agent_service.stream_chat(
            user_message=query2,
            account_id=account_id,
            db=db,
            conversation_history=conversation_history
        ):
            print(token, end='', flush=True)
            response2_tokens.append(token)
        
        print("\n")
        
        return (''.join(response1_tokens), ''.join(response2_tokens))
        
    finally:
        await db.close()


async def main():
    """Run all Phase 3 LangGraph demos."""
    print("\n" + "=" * 80)
    print("PHASE 3 DEMO: LangGraph Agent with Portfolio Tools")
    print("=" * 80)
    print("\nDemonstrating LangChain/LangGraph patterns:")
    print("- @tool decorator for tool definitions")
    print("- create_react_agent for stateful workflows")
    print("- Automatic tool orchestration")
    print("- Streaming responses with tool calls")
    print("- Multi-turn conversations with context")
    print("\n" + "=" * 80)
    
    try:
        # Run tests
        await test_basic_tool_call()
        await asyncio.sleep(1)
        
        await test_portfolio_analysis()
        await asyncio.sleep(1)
        
        await test_portfolio_comparison()
        await asyncio.sleep(1)
        
        await test_multi_turn_conversation()
        
        print("\n" + "=" * 80)
        print("ALL TESTS COMPLETED SUCCESSFULLY")
        print("=" * 80 + "\n")
        
        print("Key Learnings:")
        print("1. LangChain @tool decorator is cleaner than class-based tools")
        print("2. create_react_agent handles tool orchestration automatically")
        print("3. No need for manual tool registry or tool_calls handling")
        print("4. Streaming works out of the box with astream_events")
        print("5. State management is built into LangGraph")
        
    except Exception as e:
        logger.error(f"Demo failed: {str(e)}", exc_info=True)
        print(f"\n❌ Error: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
