Create a new service for the Portfolio Manager following the established patterns.

Service name / purpose provided by user: $ARGUMENTS

## Steps to follow

### Step 1 — Read reference implementations
Before writing any code:
- Read `src/services/holding_service.py` for a full DB-backed service example
- Read `src/services/result_objects.py` to understand the Result/ErrorCode pattern
- Read `tests/unit/test_services/test_holding_service.py` for the test pattern to follow

### Step 2 — Decide: singleton or per-request?

**Needs database access?**
- YES → Per-request service. Accept `db: AsyncSession` as the first constructor arg. Do NOT use `@lru_cache`.
- NO (stateless, e.g. only calls external APIs or does pure calculation) → Singleton. Use `@lru_cache()` on the factory.

### Step 3 — Create the service file
Create `src/services/<name>_service.py`:

```python
class <Name>Service:
    def __init__(self, db: AsyncSession, other_dep: OtherService):
        self.db = db
        self.other_dep = other_dep

    async def do_something(self, account_id: int, ...) -> <Name>Result:
        try:
            # Always validate ownership — confirm entity belongs to account_id
            # Use self.db.execute(select(...).where(...)) for queries
            # Use await self.db.commit() after mutations
            ...
            return <Name>Result(success=True, data=...)
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error in do_something: {e}", exc_info=True)
            return <Name>Result(success=False, error_code=ErrorCode.INTERNAL_ERROR)
```

Key rules:
- All methods touching DB or external APIs must be `async`
- Always check that queried entities belong to `account_id` before returning data
- Use `await self.db.rollback()` in exception handlers for mutation methods
- Return typed Result objects for mutations; return domain objects or `None` for reads

### Step 4 — Add Result types (if needed)
Edit `src/services/result_objects.py`:

```python
@dataclass
class <Name>Result(ServiceResult):
    data: Optional[<DomainType>] = None
```

Available `ErrorCode` values: `NOT_FOUND`, `NOT_ACCESSIBLE`, `DUPLICATE`, `VALIDATION_ERROR`, `INTERNAL_ERROR`

### Step 5 — Register the dependency
Edit the relevant route file in `src/api/routes/`:

**Per-request service (needs DB):**
```python
def get_<name>_service(db: AsyncSession = Depends(get_db)) -> <Name>Service:
    return <Name>Service(db=db)
```

**Singleton service (stateless):**
```python
@lru_cache()
def get_<name>_service() -> <Name>Service:
    return <Name>Service(other_dep=get_other_dep())
```

Then inject in route handlers: `service: <Name>Service = Depends(get_<name>_service)`

Map `ErrorCode` to HTTP status in route handlers:
- `NOT_FOUND` → 404, `NOT_ACCESSIBLE` → 403, `DUPLICATE` → 409, `VALIDATION_ERROR` → 422

### Step 6 — Write unit tests
Create `tests/unit/test_services/test_<name>_service.py`:

```python
@pytest.fixture
def <name>_service(mock_db_session, mock_other_dep):
    return <Name>Service(db=mock_db_session, other_dep=mock_other_dep)

class Test<Name>:
    @pytest.mark.asyncio
    async def test_happy_path(self, <name>_service, mock_db_session):
        # arrange: configure mock_db_session.execute.return_value
        # act
        result = await <name>_service.do_something(account_id=1, ...)
        # assert
        assert result.success is True

    @pytest.mark.asyncio
    async def test_not_found(self, <name>_service, mock_db_session):
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None
        result = await <name>_service.do_something(account_id=1, ...)
        assert result.success is False
        assert result.error_code == ErrorCode.NOT_FOUND

    @pytest.mark.asyncio
    async def test_db_exception_rolls_back(self, <name>_service, mock_db_session):
        mock_db_session.execute.side_effect = Exception("DB error")
        result = await <name>_service.do_something(account_id=1, ...)
        assert result.success is False
        mock_db_session.rollback.assert_called_once()
```

Use `mock_db_session` from `tests/conftest.py`. Mark all tests `@pytest.mark.unit`.

### Step 7 — Verify
Run: `.venv/Scripts/python.exe -m pytest tests/unit/ -v`

All tests should pass. Fix any import errors or logic issues before finishing.
