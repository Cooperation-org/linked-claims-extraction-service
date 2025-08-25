# Local Development Setup

## Quick Start

### 1. Install Dependencies

```bash
# Install in virtual environment
pip install -r requirements.txt
```

### 2. Set API Key

```bash
export ANTHROPIC_API_KEY=your-api-key-here
```

### 3. Run Tests

```bash
# Unit tests (no API key needed)
python -m pytest tests/test_sync_processor.py -v

# Manual test (requires API key)
python manual_test.py
```

## What Gets Tested

### Unit Tests
- Mock all external dependencies
- Test error handling
- Test PDF processing logic
- No API calls made

### Manual Test
- Real claim extraction using ClaimExtractor 1.6+
- Tests sample text and PDF files
- Shows actual extracted claims in JSON format
- Requires valid ANTHROPIC_API_KEY

## Files Overview

- `manual_test.py` - Manual test runner with real API calls
- `src/sync_processor.py` - Synchronous processor (no Celery)  
- `tests/test_sync_processor.py` - Unit tests with mocks
- `requirements.txt` - Updated to use claim_extractor 1.6+

## Next Steps

Once local extraction works:
1. Test full Flask service with `python run.py`
2. Add database setup for full functionality
3. Test end-to-end PDF upload and processing