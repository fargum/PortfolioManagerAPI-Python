"""Service for managing AI agent prompts from configuration."""
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class AgentPromptService:
    """
    Service for managing AI agent prompts from JSON configuration.
    """
    
    def __init__(self, prompts_file: Optional[Path] = None):
        """
        Initialize the agent prompt service.
        
        Args:
            prompts_file: Path to AgentPrompts.json file. If None, uses default location.
        """
        if prompts_file is None:
            prompts_file = Path(__file__).parent / "prompts" / "agent_prompts.json"
        
        self.prompts_file = prompts_file
        self._config: Optional[Dict[str, Any]] = None
    
    def _load_configuration(self) -> Dict[str, Any]:
        """
        Load prompt configuration from JSON file.
        
        Returns:
            Dictionary containing prompt configuration
        """
        if self._config is not None:
            return self._config
        
        try:
            if not self.prompts_file.exists():
                logger.warning(f"Prompt configuration file not found: {self.prompts_file}")
                return self._create_fallback_configuration()
            
            with open(self.prompts_file, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
                logger.info(f"Successfully loaded agent prompt configuration from {self.prompts_file}")
                return self._config
                
        except Exception as e:
            logger.error(f"Error loading prompt configuration: {e}")
            return self._create_fallback_configuration()
    
    def get_portfolio_advisor_prompt(self, account_id: int) -> str:
        """
        Get the portfolio advisor prompt for a specific account.
        
        Args:
            account_id: Account ID to include in the prompt
            
        Returns:
            Complete prompt text for the portfolio advisor agent
        """
        try:
            config = self._load_configuration()
            advisor_config = config.get("PortfolioAdvisor", {})
            
            # Start building the prompt
            prompt_parts = []
            
            # Base instructions with account ID substitution
            base_instructions = advisor_config.get("BaseInstructions", "")
            base_instructions = base_instructions.replace("{accountId}", str(account_id))
            prompt_parts.append(base_instructions)
            prompt_parts.append("")
            
            # Tool usage guidance
            tool_guidance = advisor_config.get("ToolUsageGuidance", {})
            if tool_guidance:
                prompt_parts.append("WHEN TO USE YOUR TOOLS:")
                prompt_parts.append("You have some great tools at your disposal, but only use them when someone actually wants portfolio or market information:")
                prompt_parts.append("")
                
                prompt_parts.append("✅ Perfect times to use tools:")
                for example in tool_guidance.get("WhenToUseTools", []):
                    prompt_parts.append(f'- "{example}"')
                prompt_parts.append("")
                
                prompt_parts.append("❌ Just have a normal chat for:")
                for example in tool_guidance.get("WhenNotToUseTools", []):
                    prompt_parts.append(f'- "{example}"')
                prompt_parts.append("")
                
                # Tool combinations
                tool_combos = tool_guidance.get("ToolCombinations", [])
                if tool_combos:
                    prompt_parts.append("TOOL COMBINATIONS:")
                    for combo in tool_combos:
                        prompt_parts.append(combo)
                    prompt_parts.append("")
                
                # Available tools
                available_tools = tool_guidance.get("AvailableTools", [])
                if available_tools:
                    prompt_parts.append("YOUR AVAILABLE TOOLS:")
                    for tool in available_tools:
                        prompt_parts.append(f"- {tool}")
                    prompt_parts.append("")
                
                # News and sentiment guidance
                news_guidance = tool_guidance.get("NewsAndSentimentGuidance", [])
                if news_guidance:
                    prompt_parts.append("CRITICAL - NEWS AND SENTIMENT TOOLS:")
                    for guidance in news_guidance:
                        prompt_parts.append(guidance)
                    prompt_parts.append("")
            
            # Communication style
            comm_style = advisor_config.get("CommunicationStyle", {})
            if comm_style:
                prompt_parts.append("COMMUNICATION STYLE:")
                prompt_parts.append(comm_style.get("Approach", ""))
                prompt_parts.append("")
                
                # Bad example
                bad_example = comm_style.get("BadExample", {})
                prompt_parts.append("❌ Avoid this robotic style:")
                prompt_parts.append(f"## {bad_example.get('Title', 'Example')}")
                bad_content = bad_example.get("Content", "")
                if isinstance(bad_content, list):
                    for item in bad_content:
                        prompt_parts.append(f"- {item}")
                else:
                    prompt_parts.append(bad_content)
                prompt_parts.append("")
                
                # Good example
                good_example = comm_style.get("GoodExample", {})
                prompt_parts.append("✅ Go for this friendly approach:")
                prompt_parts.append(f"## {good_example.get('Title', 'Example')}")
                good_content = good_example.get("Content", "")
                if isinstance(good_content, list):
                    for item in good_content:
                        prompt_parts.append(item)
                else:
                    prompt_parts.append(good_content)
                prompt_parts.append("")
            
            # Formatting guidelines
            formatting = advisor_config.get("FormattingGuidelines", [])
            if formatting:
                prompt_parts.append("FORMATTING THAT FEELS NATURAL:")
                for guideline in formatting:
                    prompt_parts.append(f"- {guideline}")
                prompt_parts.append("")
            
            # Table example
            table_example = advisor_config.get("TableExample", {})
            if table_example:
                prompt_parts.append("TABLES WHEN NEEDED:")
                prompt_parts.append(table_example.get("Description", ""))
                prompt_parts.append("")
                prompt_parts.append(table_example.get("Format", ""))
                prompt_parts.append("")
            
            # Key reminders
            reminders = advisor_config.get("KeyReminders", [])
            if reminders:
                prompt_parts.append("REMEMBER:")
                for reminder in reminders:
                    prompt_parts.append(f"- {reminder}")
                prompt_parts.append("")
            
            # Personality
            personality = advisor_config.get("Personality", "")
            if personality:
                prompt_parts.append(personality)
            
            return "\n".join(prompt_parts)
            
        except Exception as e:
            logger.error(f"Error building portfolio advisor prompt for account {account_id}: {e}")
            return f"You are a helpful financial advisor for Account ID {account_id}. Provide clear, friendly assistance with portfolio questions."
    
    def get_prompt(self, prompt_name: str, parameters: Optional[Dict[str, Any]] = None) -> str:
        """
        Get a custom prompt by name with parameter substitution.
        
        Args:
            prompt_name: Name of the prompt configuration
            parameters: Optional parameters for substitution
            
        Returns:
            Complete prompt text
        """
        if prompt_name == "PortfolioAdvisor" and parameters and "accountId" in parameters:
            account_id = int(parameters["accountId"])
            return self.get_portfolio_advisor_prompt(account_id)
        
        # Add other prompt types here as needed (e.g., MemoryExtractionAgent)
        
        logger.warning(f"Unknown prompt name: {prompt_name}")
        return "You are a helpful AI assistant."
    
    @staticmethod
    def _create_fallback_configuration() -> Dict[str, Any]:
        """
        Create a fallback configuration if loading fails.
        
        Returns:
            Dictionary with minimal configuration
        """
        return {
            "PortfolioAdvisor": {
                "BaseInstructions": "You are a friendly financial advisor helping the owner of Account ID {accountId}.",
                "ToolUsageGuidance": {
                    "WhenToUseTools": [
                        "Show me my portfolio",
                        "How am I doing?",
                        "What's happening with my investments?"
                    ],
                    "WhenNotToUseTools": [
                        "General greetings",
                        "Casual conversation",
                        "Thank you messages"
                    ]
                },
                "CommunicationStyle": {
                    "Approach": "Be conversational and friendly.",
                    "BadExample": {
                        "Title": "Robotic Response",
                        "Content": ["Dry bullet points", "Technical jargon", "No personality"]
                    },
                    "GoodExample": {
                        "Title": "Natural Conversation",
                        "Content": "Friendly, conversational approach with clear explanations."
                    }
                },
                "FormattingGuidelines": [
                    "Use clear formatting",
                    "Format currency as £1,234.56 (GBP)",
                    "Use UK date formats (DD/MM/YYYY)"
                ],
                "TableExample": {
                    "Description": "Use tables when appropriate for data presentation",
                    "Format": "| Column 1 | Column 2 |"
                },
                "KeyReminders": [
                    "Be helpful and professional",
                    "Focus on actionable insights",
                    "Use conversational language"
                ],
                "Personality": "Be the advisor they'd want to grab coffee with!"
            }
        }
