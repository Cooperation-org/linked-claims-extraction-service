# Local Development Setup

Quick setup for testing claim extraction locally without Redis/Celery.

## Prerequisites

```bash
export ANTHROPIC_API_KEY=your-api-key
```

## Quick Test

```bash
# Install dependencies
pip install -e .

# Run manual test
python manual_test.py
```

This will:
1. Test extraction on sample text
2. Test extraction on example PDF (if present)
3. Show extracted claims in JSON format

## Full Local Development

```bash
# Install all dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Initialize database (optional)
python migrations_init.py

# Run Flask app
python run.py
```

## Files Added for Local Dev

- `manual_test.py` - Manual test runner without database/Celery  
- `src/sync_processor.py` - Synchronous processor for local testing
- `tests/test_sync_processor.py` - Unit tests for sync processor
- `README-local.md` - This file

## Run Unit Tests

```bash
python -m pytest tests/test_sync_processor.py -v
```

## Testing Without Database

The `SyncClaimProcessor` can run without database connection for testing:

```python
from src.sync_processor import SyncClaimProcessor

processor = SyncClaimProcessor()  # No db connection
result = processor.extract_claims_from_document("path/to/file.pdf")
```