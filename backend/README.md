# Drishtik Backend

This is the Python backend foundation for the Drishtik Forensic Analysis Platform.

## Current Implemented Scope
- FastAPI application foundation
- Environment-based configuration
- SQLite/SQLAlchemy database connection setup
- Alembic migration foundation
- Application logging
- Health check API endpoint

## Development Setup

### 1. Create a Virtual Environment
It is recommended to use a local virtual environment for this project.

```bash
cd backend
python -m venv .venv
```

Activate the environment:
- Windows: `.venv\Scripts\activate`
- macOS/Linux: `source .venv/bin/activate`

### 2. Install Dependencies
Install runtime and development dependencies using pip:

```bash
pip install -e .[dev]
```

### 3. Environment Variables
Copy `.env.example` to `.env` if not already present.

```bash
cp .env.example .env
```

### 4. Run the Development Server
Start the FastAPI server using Uvicorn:

```bash
uvicorn app.main:app --reload
```
By default, the server will be available at `http://localhost:8000`.

### 5. API Documentation
Once the server is running, interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 6. Run Tests
Execute the pytest suite:

```bash
pytest
```
