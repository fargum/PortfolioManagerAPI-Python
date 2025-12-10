# Portfolio Manager Python API

Python FastAPI implementation of the Portfolio Manager API. This project recreates the C# Portfolio Manager API using Python, FastAPI, SQLAlchemy, and LangChain/LangGraph for AI functionality.

I decided to build this because I wanted to see how a python based agentic application (powered with langchain, langgraph) would compare with my earlier .net/c# solution which uses Microsoft Agent Framework (built on Semantic Kernel and Autogen).

This solution does not implement the full feature set of the earlier one, nor does it adopt the full DDD approach. The aim here was simplicity. I was keen to understand how langgraph handles memory and tool use.

## Features

- **FastAPI** - Modern, fast web framework with automatic OpenAPI documentation
- **SQLAlchemy** - Async ORM for PostgreSQL database access
- **Pydantic** - Data validation and settings management
- **Repository Pattern** - Clean separation of data access logic
- **Service Layer** - Business logic and domain operations
- **LangChain/LangGraph** - AI agent functionality (coming soon)

## Project Structure

```
PortfolioManagerPythonAPI/
├── src/
│   ├── api/                # FastAPI application and routes
│   │   ├── main.py        # Application entry point
│   │   └── routes/        # API endpoints
│   ├── core/              # Core configuration
│   ├── db/                # Database models and session
│   ├── repositories/      # Data access layer
│   ├── schemas/           # Pydantic schemas (DTOs)
│   └── services/          # Business logic
├── tests/                 # Unit and integration tests
├── requirements.txt       # Production dependencies
├── requirements-dev.txt   # Development dependencies
├── .env.example          # Environment variables template
└── pyproject.toml        # Project configuration
```

## Prerequisites

- Python 3.11 or higher
- PostgreSQL database (existing Portfolio Manager database)
- pip or uv for package management

## Setup

### 1. Clone and Navigate

```powershell
cd c:\Users\neilb\projects\PorfolioManagerPythonAPI
```

### 2. Create Virtual Environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```powershell
pip install -r requirements.txt
```

For development:
```powershell
pip install -r requirements-dev.txt
```

### 4. Configure Environment

Copy `.env.example` to `.env` and update with your database credentials:

```powershell
copy .env.example .env
```

Edit `.env`:
```env
DATABASE_URL=postgresql://your_user:your_password@localhost:5432/portfoliomanager
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=true
```

### 5. Configure AI Features (Optional)

The Portfolio Manager API includes AI-powered portfolio analysis using Azure AI Foundry (Azure OpenAI). AI features are **optional** and the API will run without them, but they enable:

- Natural language portfolio queries
- LangGraph-based agent with tool calling
- Conversation memory with multi-turn interactions
- Intelligent portfolio analysis and insights

#### Azure AI Foundry Setup

1. **Create Azure AI Resource**:
   - Go to [Azure AI Foundry](https://ai.azure.com)
   - Create a new project or use existing one
   - Deploy a chat model (e.g., `gpt-4o-mini`, `gpt-4o`, `gpt-4`)

2. **Get Configuration Values**:
   - **Endpoint**: Your Azure OpenAI endpoint (e.g., `https://your-resource.openai.azure.com/`)
   - **API Key**: From Azure portal under Keys and Endpoint
   - **Deployment Name**: The name you gave your model deployment
   - **API Version**: Use `2024-08-01-preview` (or latest)

3. **Update `.env`**:
   ```env
   AZURE_FOUNDRY_ENDPOINT=https://your-resource.openai.azure.com/
   AZURE_FOUNDRY_API_KEY=your-api-key-here
   AZURE_FOUNDRY_MODEL_NAME=gpt-4o-mini
   AZURE_FOUNDRY_API_VERSION=2024-08-01-preview
   ```

4. **Database Setup for Memory**:
   The AI agent uses PostgreSQL to store conversation state. Run the migration scripts:
   ```sql
   -- Run migrations in order from migrations/ folder
   \i migrations/001_langgraph_checkpointer_tables.sql
   \i migrations/002_checkpoint_blobs_table.sql
   \i migrations/003_add_blob_to_checkpoint_writes.sql
   \i migrations/004_add_task_path_to_checkpoint_writes.sql
   ```

#### Verify AI Setup

```bash
curl http://localhost:8000/api/ai/chat/health
```

Expected response:
```json
{
  "status": "healthy",
  "azure_configured": true,
  "model_name": "gpt-4o-mini"
}
```

If `azure_configured` is `false`, AI features are disabled and the API will return configuration errors when accessing AI endpoints.

### 6. Run the API

#### Option A: Local Development

```powershell
python -m src.api.main
```

Or using uvicorn directly:
```powershell
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API**: http://localhost:8000
- **Interactive Docs (Swagger)**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

#### Option B: Docker Deployment

**Note**: Docker deployment is recommended for testing on Windows as it avoids the `psycopg3` ProactorEventLoop limitation that affects the conversation memory feature.

1. **Configure Environment**:
   ```powershell
   copy .env.docker .env
   # Edit .env with your Azure AI Foundry and EOD API credentials
   ```

2. **Build and Run**:
   ```powershell
   docker-compose up -d
   ```

3. **Run Database Migrations**:
   ```powershell
   docker-compose exec api python -c "
   import asyncio
   from sqlalchemy import text
   from src.db.session import AsyncSessionLocal
   
   async def run_migrations():
       async with AsyncSessionLocal() as session:
           # Add migration SQL here if needed
           pass
   
   asyncio.run(run_migrations())
   "
   ```

   Or connect to PostgreSQL directly:
   ```powershell
   docker-compose exec postgres psql -U portfoliouser -d portfoliomanager
   ```

4. **View Logs**:
   ```powershell
   docker-compose logs -f api
   ```

5. **Stop Services**:
   ```powershell
   docker-compose down
   ```

**Development Mode** (with hot reload):
```powershell
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

The API will be available at:
- **API**: http://localhost:8000
- **Interactive Docs (Swagger)**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **PostgreSQL**: localhost:5432

## API Endpoints

### Health Check
- `GET /` - Root endpoint
- `GET /health` - Health check

### Holdings
- `GET /api/holdings/{holding_id}` - Get holding by ID
- `GET /api/holdings/portfolio/{portfolio_id}` - Get all holdings for a portfolio
- `GET /api/holdings/portfolio/{portfolio_id}/summary` - Get portfolio summary
- `GET /api/holdings/symbol/{symbol}` - Get holdings by symbol
- `POST /api/holdings/` - Create new holding
- `PUT /api/holdings/{holding_id}` - Update holding
- `DELETE /api/holdings/{holding_id}` - Delete holding
- `PATCH /api/holdings/portfolio/{portfolio_id}/prices` - Batch update prices

## Example Usage

### Get Holdings for a Portfolio

```bash
curl http://localhost:8000/api/holdings/portfolio/1?skip=0&limit=10
```

### Create a New Holding

```bash
curl -X POST http://localhost:8000/api/holdings/ \
  -H "Content-Type: application/json" \
  -d '{
    "portfolio_id": 1,
    "symbol": "AAPL",
    "company_name": "Apple Inc.",
    "quantity": 100,
    "average_cost": 150.00,
    "current_price": 175.50,
    "asset_type": "Stock",
    "sector": "Technology"
  }'
```

### Update Current Prices

```bash
curl -X PATCH http://localhost:8000/api/holdings/portfolio/1/prices \
  -H "Content-Type: application/json" \
  -d '{
    "AAPL": 175.50,
    "GOOGL": 2850.00,
    "MSFT": 380.25
  }'
```

## Database Schema

The API expects a `holdings` table with the following structure (adjust to match your existing schema):

```sql
-- This is a reference - your existing table may have different structure
-- The SQLAlchemy model in src/db/models/holding.py should match your actual schema
```

## Development

### Code Quality

Format code with Black:
```powershell
black src/
```

Lint with Ruff:
```powershell
ruff check src/
```

Type checking with mypy:
```powershell
mypy src/
```

### Testing

Run tests (when implemented):
```powershell
pytest
```

With coverage:
```powershell
pytest --cov=src tests/
```

## Next Steps

1. **Adjust Database Models** - Update `src/db/models/holding.py` to match your actual PostgreSQL schema
2. **Add Authentication** - Implement JWT or OAuth2 authentication
3. **Add More Entities** - Create models/routes for Portfolios, Transactions, etc.
4. **AI Integration** - Implement LangChain/LangGraph agents for portfolio analysis
5. **Testing** - Add unit and integration tests
6. **Docker** - Add Dockerfile and docker-compose for containerization

## Differences from C# Implementation

| C# | Python |
|----|--------|
| Entity Framework Core | SQLAlchemy |
| Data Annotations | Pydantic |
| Built-in DI | FastAPI Depends |
| IRepository<T> | BaseRepository[T] |
| DbContext | AsyncSession |
| async/await | async/await (asyncio) |

## License

Same as the original Portfolio Manager project.
