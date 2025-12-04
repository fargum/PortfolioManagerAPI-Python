# AI Services Implementation

This directory contains the AI agent implementation for the Portfolio Manager Python API.

## Phase 1: Foundation & Configuration ✅

### Completed Components

#### 1. Azure OpenAI Configuration (`ai_config.py`)
- `AzureOpenAIConfig` class for managing Azure AI Foundry settings
- Client creation using `azure-ai-inference` SDK
- Configuration validation and error handling
- Dependency injection support via `get_azure_openai_client()`

**Key Features:**
- Loads configuration from environment variables
- Creates `ChatCompletionsClient` for Azure AI Foundry
- Provides model configuration defaults (temperature, max_tokens, etc.)
- Validates configuration before client creation

#### 2. Agent Prompt Service (`agent_prompt_service.py`)
- `AgentPromptService` class for managing AI agent prompts
- Loads prompts from JSON configuration file
- Supports parameter substitution (e.g., {accountId})
- Fallback configuration for graceful degradation

**Key Features:**
- `get_portfolio_advisor_prompt(account_id)` - Get formatted prompt for portfolio advisor agent
- `get_prompt(prompt_name, parameters)` - Generic method for any prompt type
- Automatic prompt building from JSON structure
- Includes tool usage guidance, communication style, formatting rules

#### 3. Prompt Configuration (`prompts/agent_prompts.json`)
- JSON-based prompt configuration matching C# implementation
- Structured sections:
  - BaseInstructions
  - ToolUsageGuidance (when to use tools vs. chat)
  - CommunicationStyle (good/bad examples)
  - FormattingGuidelines (currency, dates, percentages)
  - KeyReminders
  - Personality

#### 4. Environment Configuration (`.env`)
New environment variables added:
```env
AZURE_OPENAI_ENDPOINT=https://your-foundry-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_MODEL_NAME=gpt-4o-mini
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_TIMEOUT_SECONDS=120
```

#### 5. Dependencies (`requirements.txt`)
New packages:
- `azure-ai-inference==1.0.0b7` - Azure AI Inference SDK
- `azure-identity==1.19.0` - Azure authentication
- `openai==1.59.5` - OpenAI Python SDK

### Testing Phase 1

Run the demo script to verify Phase 1 setup:

```bash
# Install dependencies
pip install -r requirements.txt

# Run Phase 1 demo
python -m src.services.ai.phase1_demo
```

**Demo Script Tests:**
1. ✅ Azure OpenAI configuration loading
2. ✅ Azure OpenAI client creation
3. ✅ Agent prompt service initialization
4. ✅ Prompt loading and formatting
5. ✅ Parameter substitution (accountId)
6. ✅ Validation of key sections

### Configuration Setup

1. **Get Azure AI Foundry Credentials:**
   - Go to Azure Portal → Azure AI Foundry resource
   - Copy the endpoint URL
   - Copy the API key

2. **Update `.env` file:**
   ```env
   AZURE_OPENAI_ENDPOINT=https://your-actual-endpoint.openai.azure.com/
   AZURE_OPENAI_API_KEY=your-actual-api-key
   AZURE_OPENAI_MODEL_NAME=gpt-4o-mini  # or your deployed model name
   ```

3. **Verify Configuration:**
   ```bash
   python -m src.services.ai.phase1_demo
   ```

### Project Structure

```
src/
├── core/
│   ├── ai_config.py          # Azure OpenAI client configuration
│   └── config.py             # Settings with Azure OpenAI support
└── services/
    └── ai/
        ├── __init__.py
        ├── agent_prompt_service.py   # Prompt management service
        ├── phase1_demo.py            # Phase 1 test/demo script
        └── prompts/
            └── agent_prompts.json    # Agent prompt configuration
```

## Next Phases

### Phase 2: Basic Chat Service (Coming Next)
- `IAiChatService` interface
- `AzureOpenAiChatService` implementation
- Simple prompt → response (no agents, no tools)
- Streaming response support
- Error handling and retries

### Phase 3: MCP Tool Integration
- MCP tool interface design
- Portfolio holdings tool
- Market intelligence tool
- Tool registration system

### Phase 4: AI Orchestration Service
- `AiOrchestrationService` implementation
- Agent framework pattern
- Tool calling logic (agentic loop)
- Streaming with tool status updates

### Phase 5: Memory & Advanced Features
- Conversation thread management
- Message persistence
- Memory summarization agent
- Guardrails (input/output validation)

## Architecture Notes

### Matching C# Implementation

This Python implementation mirrors the C# codebase structure:

**C# → Python Mapping:**
- `AzureFoundryOptions` → `AzureOpenAIConfig`
- `AgentPromptService` → `AgentPromptService`
- `AgentPrompts.json` → `agent_prompts.json`
- `IOptions<T>` pattern → Property-based config
- Embedded resources → File-based JSON

**Key Differences:**
- Python uses `azure-ai-inference` SDK (simpler than C# Azure.AI.OpenAI)
- Settings loaded via `pydantic-settings` instead of IOptions
- JSON files instead of embedded resources
- Snake_case naming convention

### Design Decisions

1. **Separate AI Config Module:**
   - Keeps Azure-specific configuration isolated
   - Easy to swap implementations
   - Clean dependency injection

2. **JSON-Based Prompts:**
   - Easy to modify without code changes
   - Version control friendly
   - Supports multiple agents/personas

3. **Fallback Configuration:**
   - Graceful degradation if JSON missing
   - Development-friendly
   - Production-safe

4. **Environment-Based Secrets:**
   - Credentials never in code
   - .env file (gitignored)
   - Azure Key Vault ready (future)

## References

- C# Implementation: `fargum/portfoliomanager`
- Azure AI Inference SDK: https://learn.microsoft.com/en-us/python/api/azure-ai-inference/
- Agent Framework Documentation: https://learn.microsoft.com/en-us/azure/ai-foundry/
