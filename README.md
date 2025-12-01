# Portfolio Manager Python API

Python FastAPI implementation of the Portfolio Manager API. This project recreates the C# Portfolio Manager API using Python, FastAPI, SQLAlchemy, and LangChain/LangGraph for AI functionality.

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

### 5. Run the API

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
