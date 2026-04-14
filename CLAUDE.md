# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Behavioral Guidelines

### Before Implementing
- State assumptions explicitly before writing code. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so and push back.

### Surgical Changes
- Don't improve, reformat, or refactor code adjacent to your changes.
- Remove imports/variables/functions that **your** changes made unused.
- Don't remove pre-existing dead code unless asked — mention it instead.

### Multi-Step Tasks
State a brief plan with verifiable checkpoints before starting:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
```
For bug fixes: write a test reproducing it, then make it pass.

## Build and Development Commands

```bash
# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # for development

# Run the API server
python -m src.api.main
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000  # with hot reload

# Code quality
black src/                    # format code
ruff check src/               # lint
mypy src/                     # type check

# Testing
pytest                        # run all tests
pytest -m unit                # unit tests only
pytest -m integration         # integration tests only
pytest -m api                 # API tests only
pytest tests/unit/test_services/test_holding_service.py  # single file
pytest --cov=src tests/       # with coverage
```

## Architecture Overview

This is a FastAPI portfolio management API with AI-powered chat using LangGraph.

### Layer Structure

```
src/
├── api/                    # FastAPI routes and app setup
│   ├── main.py            # Entry point, middleware, exception handlers
│   └── routes/            # Feature-based route modules
├── core/                   # Configuration (settings, AI config)
├── db/                     # Database layer
│   ├── models/            # SQLAlchemy models (app schema)
│   └── session.py         # Async session management
├── schemas/               # Pydantic DTOs for API requests/responses
└── services/              # Business logic layer
    └── ai/                # AI-specific services
```

### Key Services

- **HoldingService** (`services/holding_service.py`): Core CRUD for holdings with real-time pricing integration
- **LangGraphAgentService** (`services/ai/langgraph_agent_service.py`): Stateful AI agent with tool-calling, uses PostgreSQL checkpointer for conversation memory
- **PortfolioAnalysisService** (`services/ai/portfolio_analysis_service.py`): Portfolio performance analytics
- **ConversationThreadService** (`services/conversation_thread_service.py`): Manages AI conversation threads per account

### AI/LangGraph Pattern

The AI uses a LangGraph StateGraph with these tools:
- `get_portfolio_holdings`, `analyze_portfolio_performance`, `compare_portfolio_performance`
- `get_market_context`, `get_market_sentiment`, `get_real_time_prices`

Conversation memory persists to PostgreSQL via `AsyncPostgresSaver`. Streaming responses use `astream_events()`.

### Database

- Uses PostgreSQL with `app` schema (models in `src/db/models/`)
- Async SQLAlchemy with `AsyncSession`
- Core entities: Account, Portfolio, Holding, Instrument, Platform, ConversationThread, ChatMessage

### Important Patterns

- **Account ID injection**: Always from `Depends(get_current_account_id)` in routes. Never from
  request body or AI tool input — this is the security boundary.
- **Result objects**: Services return typed results (`AddHoldingResult`, etc.) extending `ServiceResult`.
  Check `result.success` and `result.error_code` (ErrorCode enum).
  Routes map ErrorCode → HTTP status: `NOT_FOUND`→404, `NOT_ACCESSIBLE`→403, `DUPLICATE`→409.
- **Singleton services**: `@lru_cache()` on stateless `get_X_service()` factory functions used as `Depends()`.
  Services that take `AsyncSession` are NOT singletons — create per-request.
- **Async throughout**: `AsyncSession`, all services, all tools use `async/await`.
- **Pydantic aliases**: Schemas use `model_config = ConfigDict(populate_by_name=True)` with camelCase
  aliases (e.g., `portfolioId`). Use `model_dump(by_alias=True)` in JSONResponse.
- **Tool factory pattern**: Never create AI tools as module-level globals. Call
  `create_X_tool(service, account_id)` per-request. `account_id` is closed over in the inner
  async function — the LLM cannot set it. See `services/ai/tools/portfolio_holdings_tool.py`.
- **Test mocking**: `AsyncMock` for `AsyncSession`, `Mock(spec=ClassName)` for services.
  Shared fixtures in `tests/conftest.py`: `mock_db_session`, `mock_eod_tool`,
  `mock_currency_service`, `mock_pricing_service`, `sample_portfolio`, `sample_holding`.

### Environment Configuration

Required in `.env`:
- `DATABASE_URL`: PostgreSQL connection string
- Azure AI Foundry settings for AI features: `AZURE_FOUNDRY_ENDPOINT`, `AZURE_FOUNDRY_API_KEY`, `AZURE_FOUNDRY_MODEL_NAME`

### Test Structure

Tests use pytest markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.api`.
Async tests use `@pytest.mark.asyncio` (auto mode — configured in `pyproject.toml`).
Database tests require real PostgreSQL (SQLite lacks `app.` schema support).

## Adding New Features

### New API endpoint
1. Add route to `src/api/routes/` (register new files in `main.py`)
2. Add Pydantic schemas to `src/schemas/`
3. Add service method returning a typed Result object
4. Map `ErrorCode` → HTTP status in the route handler
5. Test: `AsyncMock` for DB, `Mock(spec=ClassName)` for services

### New AI tool
1. Create `src/services/ai/tools/<name>_tool.py` with `create_<name>_tool(service, account_id)`
2. Inner async function closes over `account_id` — do NOT make it a tool parameter
3. Return `StructuredTool.from_function(coroutine=..., name=..., description=...)`
4. On error, return `{"Error": "...", ...}` dict — never raise from the tool function
5. Register in `LangGraphAgentService._create_tools_for_request()`
6. Add entries to `tool_status_messages` and `tool_completion_messages` dicts
7. Export from `src/services/ai/tools/__init__.py`
8. Reference: `src/services/ai/tools/portfolio_holdings_tool.py`

### New service
1. If DB access needed: accept `db: AsyncSession` as first arg, do NOT `@lru_cache`
2. If stateless: use `@lru_cache()` factory registered as a `Depends()`
3. Return `ServiceResult` subclasses for mutations; add new types to `src/services/result_objects.py`
4. Reference: `src/services/holding_service.py`
