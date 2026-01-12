"""
Unit tests for AgentPromptService.

Tests cover:
- Loading prompts from JSON configuration
- Fallback configuration when file is missing
- Portfolio advisor prompt generation
- Account ID substitution in prompts
"""
import pytest
import json
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

from src.services.ai.agent_prompt_service import AgentPromptService


@pytest.fixture
def sample_prompts_config():
    """Sample agent prompts configuration for testing."""
    return {
        "PortfolioAdvisor": {
            "BaseInstructions": "You are a portfolio advisor for account {accountId}.",
            "ToolUsageGuidance": {
                "WhenToUseTools": [
                    "Show me my portfolio",
                    "What's my best performer?"
                ],
                "WhenNotToUseTools": [
                    "Hello",
                    "How are you?"
                ],
                "ToolCombinations": [
                    "Use holdings + analysis for comprehensive view"
                ],
                "AvailableTools": [
                    "get_portfolio_holdings - Get current holdings",
                    "analyze_portfolio_performance - Analyze performance"
                ],
                "NewsAndSentimentGuidance": [
                    "Use market tools for news queries"
                ]
            },
            "CommunicationStyle": {
                "Approach": "Be friendly and helpful.",
                "BadExample": {
                    "Title": "Bad Response",
                    "Content": "Here is data."
                },
                "GoodExample": {
                    "Title": "Good Response",
                    "Content": "Great question! Let me help you."
                }
            }
        }
    }


@pytest.fixture
def prompt_service_with_mock_file(sample_prompts_config, tmp_path):
    """Create AgentPromptService with a temporary prompts file."""
    prompts_file = tmp_path / "agent_prompts.json"
    prompts_file.write_text(json.dumps(sample_prompts_config))
    return AgentPromptService(prompts_file=prompts_file)


class TestAgentPromptServiceInitialization:
    """Test AgentPromptService initialization."""
    
    @pytest.mark.unit
    def test_init_with_default_path(self):
        """Test initialization with default prompts file path."""
        service = AgentPromptService()
        expected_path = Path(__file__).parent.parent.parent.parent.parent / "src" / "services" / "ai" / "prompts" / "agent_prompts.json"
        # Just verify it initializes without error
        assert service.prompts_file is not None
    
    @pytest.mark.unit
    def test_init_with_custom_path(self, tmp_path):
        """Test initialization with custom prompts file path."""
        custom_path = tmp_path / "custom_prompts.json"
        service = AgentPromptService(prompts_file=custom_path)
        assert service.prompts_file == custom_path


class TestLoadConfiguration:
    """Test prompt configuration loading."""
    
    @pytest.mark.unit
    def test_load_valid_configuration(self, prompt_service_with_mock_file, sample_prompts_config):
        """Test loading valid JSON configuration."""
        config = prompt_service_with_mock_file._load_configuration()
        assert "PortfolioAdvisor" in config
        assert config["PortfolioAdvisor"]["BaseInstructions"] == sample_prompts_config["PortfolioAdvisor"]["BaseInstructions"]
    
    @pytest.mark.unit
    def test_configuration_is_cached(self, prompt_service_with_mock_file):
        """Test that configuration is cached after first load."""
        # Load twice
        config1 = prompt_service_with_mock_file._load_configuration()
        config2 = prompt_service_with_mock_file._load_configuration()
        
        # Should return same cached instance
        assert config1 is config2
    
    @pytest.mark.unit
    def test_fallback_when_file_missing(self, tmp_path):
        """Test fallback configuration when prompts file doesn't exist."""
        missing_file = tmp_path / "nonexistent.json"
        service = AgentPromptService(prompts_file=missing_file)
        
        config = service._load_configuration()
        
        # Should return fallback configuration
        assert config is not None
        assert "PortfolioAdvisor" in config
    
    @pytest.mark.unit
    def test_fallback_on_invalid_json(self, tmp_path):
        """Test fallback configuration when JSON is invalid."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("{ invalid json }")
        
        service = AgentPromptService(prompts_file=invalid_file)
        config = service._load_configuration()
        
        # Should return fallback configuration
        assert config is not None
        assert "PortfolioAdvisor" in config


class TestGetPortfolioAdvisorPrompt:
    """Test portfolio advisor prompt generation."""
    
    @pytest.mark.unit
    def test_account_id_substitution(self, prompt_service_with_mock_file):
        """Test that account ID is substituted in the prompt."""
        account_id = 12345
        prompt = prompt_service_with_mock_file.get_portfolio_advisor_prompt(account_id)
        
        # Account ID should be substituted
        assert str(account_id) in prompt
        assert "{accountId}" not in prompt
    
    @pytest.mark.unit
    def test_prompt_contains_tool_guidance(self, prompt_service_with_mock_file):
        """Test that prompt contains tool usage guidance."""
        prompt = prompt_service_with_mock_file.get_portfolio_advisor_prompt(100)
        
        assert "WHEN TO USE YOUR TOOLS" in prompt
        assert "Show me my portfolio" in prompt
    
    @pytest.mark.unit
    def test_prompt_contains_communication_style(self, prompt_service_with_mock_file):
        """Test that prompt contains communication style guidance."""
        prompt = prompt_service_with_mock_file.get_portfolio_advisor_prompt(100)
        
        assert "COMMUNICATION STYLE" in prompt
        assert "Be friendly and helpful" in prompt
    
    @pytest.mark.unit
    def test_prompt_with_different_account_ids(self, prompt_service_with_mock_file):
        """Test prompt generation with different account IDs."""
        prompt1 = prompt_service_with_mock_file.get_portfolio_advisor_prompt(100)
        prompt2 = prompt_service_with_mock_file.get_portfolio_advisor_prompt(200)
        
        assert "100" in prompt1
        assert "200" in prompt2
        assert "100" not in prompt2
        assert "200" not in prompt1
