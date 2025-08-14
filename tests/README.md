# Test Suite for Linked Claims Extraction Service

## Overview
This directory contains comprehensive unit tests for the Celery background tasks in the Linked Claims Extraction Service.

## Test Files

### `test_tasks_final.py`
The main test file with comprehensive unit tests for:
- **Task Bindings**: Verifies Celery tasks are properly configured
- **Extract Claims Task**: Tests PDF processing and claim extraction
- **Publish Claims Task**: Tests LinkedTrust API publishing
- **Callback Task**: Tests success/failure callbacks
- **Error Handling**: Tests graceful error recovery

### `test_celery_tasks.py`
Alternative test implementations with different mocking approaches.

### `conftest.py`
Pytest configuration and shared fixtures:
- Celery test configuration (memory broker/backend)
- Mock Flask app fixture
- Sample data fixtures
- Path configuration for imports

## Running Tests

### Run All Tests
```bash
source .venv/bin/activate
python -m pytest tests/test_tasks_final.py -v
```

### Run Specific Test Class
```bash
python -m pytest tests/test_tasks_final.py::TestCallbackTaskUnit -v
```

### Run with Coverage
```bash
python -m pytest tests/test_tasks_final.py --cov=tasks --cov-report=html
```

## Test Coverage

The test suite covers:

### ✅ Successfully Tested (10 passing tests)
- Task bindings and Celery configuration
- Publishing claims to LinkedTrust API
- Handling partial API failures
- Callback task success/failure handlers
- No claims to publish scenario
- API error handling

### 🔧 Areas Needing Fixes
- PDF page extraction mocking
- Document validation error handling
- Claim extraction with PyMuPDF integration

## Key Testing Patterns

### 1. Mocking Flask App Context
All database operations require Flask app context:
```python
@patch('tasks.flask_app.app_context')
def test_something(mock_context):
    mock_context.return_value.__enter__ = Mock()
    mock_context.return_value.__exit__ = Mock()
```

### 2. Mocking Database Models
Models are imported within context, so patch at module level:
```python
with patch('models.db') as mock_db, \
     patch('models.Document') as mock_doc_class:
    # Test code
```

### 3. Testing Celery Tasks
Use `__wrapped__` to bypass Celery execution:
```python
result = extract_claims_from_document.__wrapped__(mock_self, 'doc-id')
```

## Dependencies

The tests require these packages:
- pytest
- celery
- redis
- pymupdf (fitz)
- psycopg2-binary
- linked-claims-extractor (or claim_extractor)

Install with:
```bash
pip install pytest celery redis pymupdf psycopg2-binary
```

## Known Issues

1. **Import Path**: Tests add `src/` to Python path to resolve imports
2. **Deprecation Warnings**: `datetime.utcnow()` should be updated to `datetime.now(UTC)`
3. **Mock Complexity**: Due to dynamic imports in tasks, mocking requires careful patching

## Future Improvements

1. Add integration tests with real Celery worker
2. Add performance tests for large PDF processing
3. Mock Redis/PostgreSQL with test containers
4. Add tests for batch processing limits
5. Test memory management for large documents