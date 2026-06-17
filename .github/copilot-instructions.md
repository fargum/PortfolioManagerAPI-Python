# GitHub Copilot Instructions — Portfolio Manager Python API

This is a FastAPI portfolio management API with AI-powered chat using LangGraph. These rules apply to every Copilot interaction in this repo.

## Non-negotiable security rule
`account_id` must ALWAYS come from `Depends(get_current_account_id)` in route handlers and be closed over inside AI tool factory functions. It must NEVER appear as a request body field, query parameter, or LLM-controlled tool parameter.

## Layer structure
```
src/
├── api/routes/         # FastAPI route handlers — thin, HTTP mapping only
├── core/               # Config (settings.py, ai_config.py)
├── db/models/          # SQLAlchemy models — all use app schema prefix
├── schemas/            # Pydantic DTOs with camelCase aliases
└── services/           # Business logic
    └── ai/tools/       # LangGraph tool factories (per-request, not globals)
```

## Critical patterns

### Service result handling
```python
result = await service.do_something(account_id, ...)
if not result.success:
    if result.error_code == ErrorCode.NOT_FOUND:
        raise HTTPException(status_code=404)
    elif result.error_code == ErrorCode.NOT_ACCESSIBLE:
        raise HTTPException(status_code=403)
```

### AI tool factory (security-critical)
```python
def create_my_tool(service: MyService, account_id: int) -> StructuredTool:
    async def my_tool(param: Annotated[str, "description"]) -> dict:
        # account_id closed over — NOT a parameter the LLM can set
        result = await service.method(account_id, param)
        if not result:
            return {"Error": "not found", "AccountId": account_id}
        return {"Key": "value"}
    return StructuredTool.from_function(coroutine=my_tool, name="...", description="...")
```

### Singleton services — stateless only
```python
@lru_cache()
def get_my_service() -> MyService:
    return MyService()
```
Services that accept `AsyncSession` are NOT singletons.

### Database — app schema
All models use `__table_args__ = {'schema': 'app'}` and FK refs like `ForeignKey("app.table.id")`.
Async SQLAlchemy requires eager loading — never access relationships without `selectinload()`.

### Pydantic schemas
```python
model_config = ConfigDict(populate_by_name=True)
field: int = Field(alias="fieldAlias")
```
Use `model_dump(by_alias=True)` in JSONResponse.

## Code style
- No comments explaining WHAT — only WHY when non-obvious
- Surgical changes only — don't reformat or refactor adjacent code
- Remove imports/variables made unused by your changes
- Async throughout — all services, routes, and tools use `async/await`

## Dependency management
- Dependencies are declared in `pyproject.toml` and pinned in `uv.lock`. There are no `requirements*.txt` files.
- Install production deps: `uv sync`
- Install with dev tools: `uv sync --extra dev`
- After adding or changing a dependency in `pyproject.toml`, run `uv lock` to update the lockfile.
- Run all tools via uv: `uv run pytest`, `uv run black src/`, `uv run ruff check src/`, `uv run mypy src/`

## Specialist agents available
Use `@` to invoke: `@portfolio-coder`, `@portfolio-planner`, `@portfolio-qa`, `@portfolio-reviewer`, `@portfolio-debugger`, `@portfolio-db`, `@portfolio-prompt-engineer`, `@langgraph-agent-specialist`
