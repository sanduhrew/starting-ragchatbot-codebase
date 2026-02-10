# Testing Framework Documentation

## Overview

This directory contains a comprehensive test suite for the RAG chatbot system, covering unit tests, API endpoint tests, and integration tests.

## Test Structure

```
backend/tests/
├── __init__.py
├── conftest.py              # Shared fixtures and test app configuration
├── test_ai_generator.py     # Unit tests for AI generator with tool calling
├── test_api.py             # API endpoint tests for FastAPI
├── test_diagnostic.py      # Integration tests for system components
└── README.md               # This file
```

## Running Tests

### Run all tests
```bash
uv run pytest
```

### Run specific test file
```bash
uv run pytest tests/test_api.py
```

### Run tests by marker
```bash
uv run pytest -m api          # Run only API tests
uv run pytest -m integration  # Run only integration tests
uv run pytest -m unit         # Run only unit tests
```

### Run with verbose output
```bash
uv run pytest -v
```

### Run with coverage (if pytest-cov installed)
```bash
uv run pytest --cov=backend --cov-report=html
```

## Test Categories

### API Tests (`test_api.py`)
Tests for FastAPI endpoints using `TestClient`. Includes:

- **Query Endpoint Tests** (`POST /api/query`)
  - Query with/without session ID
  - Empty queries and missing fields
  - Multiple sources handling
  - Error handling (ValueError, unexpected errors)
  - Edge cases (long text, special characters)

- **Courses Endpoint Tests** (`GET /api/courses`)
  - Course statistics retrieval
  - Empty course list
  - Error handling

- **Root Endpoint Tests** (`GET /`)
  - Basic API info

- **CORS Tests**
  - Cross-origin request handling
  - Header validation

- **Response Model Tests**
  - Schema validation for QueryResponse
  - Schema validation for CourseStats

- **Content Negotiation Tests**
  - JSON content type requirements
  - Response format validation

- **End-to-End Flow Tests**
  - Complete query workflows
  - Multiple concurrent sessions
  - Cross-endpoint interactions

**Total: 26 API tests**

### AI Generator Tests (`test_ai_generator.py`)
Unit tests for the Anthropic Claude wrapper with sequential tool calling:

- General questions (no tools)
- Single round tool usage
- Two sequential rounds (outline → search)
- Max rounds enforcement
- Tool execution error handling
- Natural termination
- API error handling
- Conversation history preservation

**Total: 10 unit tests**

### Diagnostic Tests (`test_diagnostic.py`)
Integration tests requiring real external dependencies:

- Anthropic API key validation
- ChromaDB collections existence
- Vector store query execution
- Tool registration
- Embedding model loading

**Total: 7 integration tests**

## Pytest Configuration

Configuration is defined in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["backend/tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = ["-v", "--strict-markers", "--tb=short", "--disable-warnings"]
markers = [
    "unit: Unit tests for individual components",
    "integration: Integration tests requiring external dependencies",
    "api: API endpoint tests",
    "slow: Tests that take significant time to run",
]
```

## Shared Fixtures (conftest.py)

### Core Fixtures

- **`mock_config`** - Mock configuration with test settings
- **`test_vector_store`** - Temporary VectorStore for testing
- **`sample_course`** - Sample Course model instance
- **`sample_chunks`** - Sample CourseChunk instances
- **`mock_anthropic_client`** - Mock Anthropic API client
- **`mock_search_results`** - Mock vector search results

### API Testing Fixtures

- **`mock_rag_system`** - Mock RAGSystem with pre-configured responses
- **`test_app`** - FastAPI test app without static file mounting
- **`client`** - TestClient instance for making HTTP requests
- **`sample_query_request`** - Sample query request with session ID
- **`sample_query_request_no_session`** - Sample query without session

### Key Design Decision: Test App

The `test_app` fixture creates a separate FastAPI application instance that **does not mount static files**. This solves the problem of `../frontend` not existing in the test environment.

```python
@pytest.fixture
def test_app(mock_rag_system):
    """Create a test FastAPI app without static file mounting"""
    app = FastAPI(title="Test RAG System")
    # Define endpoints inline using mock_rag_system
    # No static file mounting
    return app
```

## Test Coverage

### ✅ Covered

- All FastAPI endpoints (`/api/query`, `/api/courses`, `/`)
- Request validation and error handling
- CORS configuration
- Response model validation
- Session management
- Multiple source handling
- AI generator tool calling flow
- Error propagation

### ⚠️ Partial Coverage

- Integration tests require external setup (ChromaDB, API keys)
- Frontend serving is not tested (static files excluded from test app)

### 📝 Future Enhancements

- Add test coverage measurement
- Add performance/load tests
- Add security tests (SQL injection, XSS)
- Add WebSocket tests if real-time features are added

## CI/CD Integration

Example GitHub Actions workflow:

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      - run: pip install uv
      - run: uv sync
      - run: uv run pytest -v -m "not integration"
```

## Troubleshooting

### Import Errors

Ensure you're running tests from the project root and the backend directory is in the Python path:

```bash
cd /path/to/project
uv run pytest
```

### Static File Mounting Errors

If you see errors about `../frontend` not existing, ensure you're using the `test_app` fixture from `conftest.py`, which creates an app without static file mounting.

### Integration Test Failures

Integration tests (`test_diagnostic.py`) require:
- Valid `ANTHROPIC_API_KEY` in `.env`
- ChromaDB populated with data (run the app once: `./run.sh`)

To skip integration tests:
```bash
uv run pytest -m "not integration"
```

## Best Practices

1. **Use appropriate fixtures** - Import fixtures from conftest.py
2. **Mark tests appropriately** - Use `@pytest.mark.api`, `@pytest.mark.integration`, etc.
3. **Mock external dependencies** - Don't call real APIs in unit tests
4. **Test error paths** - Include tests for failure scenarios
5. **Keep tests fast** - Unit tests should complete in milliseconds
6. **Use descriptive names** - Test names should explain what they verify

## Statistics

- **Total Tests**: 43
  - Unit Tests: 10
  - API Tests: 26
  - Integration Tests: 7
- **Test Execution Time**: ~8-10 seconds (including integration tests)
- **Fast Test Execution Time**: ~0.2 seconds (unit + API only)
