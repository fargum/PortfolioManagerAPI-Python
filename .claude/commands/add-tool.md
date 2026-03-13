Create a new LangGraph AI tool for the Portfolio Manager following the established factory pattern.

Tool name / description provided by user: $ARGUMENTS

## Steps to follow

### Step 1 — Read the canonical example
Read `src/services/ai/tools/portfolio_holdings_tool.py` to refresh your understanding of the exact
factory function structure before writing anything.

### Step 2 — Create the tool file
Create `src/services/ai/tools/<name>_tool.py`:

- Factory function named `create_<name>_tool(service: ServiceClass, account_id: int) -> StructuredTool`
- Inner `async def <tool_name>(param: Annotated[type, "description"]) -> dict:` contains the logic
- `account_id` is **closed over** from the factory — it must NOT be a parameter the LLM can set
- Return a dict with PascalCase keys on success
- On error, return `{"Error": "...", "AccountId": account_id}` — never raise from the tool function
- Handle the `'today'`/`'current'`/`'now'` keyword if the tool accepts dates
- End with `return StructuredTool.from_function(coroutine=<inner_fn>, name="...", description="...")`

### Step 3 — Register in LangGraphAgentService
Edit `src/services/ai/langgraph_agent_service.py`:

1. Add import at top: `from src.services.ai.tools.<name>_tool import create_<name>_tool`
2. In `_create_tools_for_request()`, append: `tools.append(create_<name>_tool(service, account_id))`
   - If the tool needs a service not yet in the method signature, add it as a parameter and update
     all callers (`stream_chat` and `run_chat`)
3. In `_stream_graph_events()`, add to `tool_status_messages`:
   `"<tool_name>": "🔍 Fetching <description>..."`
4. In `_stream_graph_events()`, add to `tool_completion_messages`:
   `"<tool_name>": "✅ <Description> retrieved"`
5. Do the same in `_collect_graph_response()` if that method also has status/completion dicts

### Step 4 — Export from the tools package
Edit `src/services/ai/tools/__init__.py`:
Add `from .<name>_tool import create_<name>_tool`

### Step 5 — Write unit tests
Create or extend `tests/unit/test_services/test_ai/test_ai_tools.py`:

Follow the existing class-based pattern:
```python
class Test<Name>ToolFactory:
    def test_creates_structured_tool(self, mock_<service>):
        tool = create_<name>_tool(mock_<service>, account_id=1)
        assert tool.name == "<tool_name>"
        assert isinstance(tool, StructuredTool)

    def test_two_instances_are_independent(self, mock_<service>):
        tool1 = create_<name>_tool(mock_<service>, account_id=1)
        tool2 = create_<name>_tool(mock_<service>, account_id=2)
        assert tool1 is not tool2

class Test<Name>ToolExecution:
    @pytest.mark.asyncio
    async def test_successful_execution(self, mock_<service>):
        # arrange: configure mock return value
        # act: await tool.coroutine(...)
        # assert: check returned dict keys

    @pytest.mark.asyncio
    async def test_returns_error_on_none_result(self, mock_<service>):
        mock_<service>.method.return_value = None
        result = await tool.coroutine(...)
        assert "Error" in result
```

Mark tests `@pytest.mark.unit`. Use `Mock(spec=ServiceClass)` and `AsyncMock` for async methods.

### Step 6 — Verify
Run: `.venv/Scripts/python.exe -m pytest tests/unit/test_services/test_ai/ -v`

All tests should pass. Fix any import errors or logic issues before finishing.
