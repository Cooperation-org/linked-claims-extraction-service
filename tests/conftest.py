"""
Pytest configuration and fixtures for testing
"""
import os
import sys
import pytest
from unittest.mock import Mock, patch
import tempfile

# Add src to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

# Configure Celery for testing
os.environ['CELERY_ALWAYS_EAGER'] = 'True'
os.environ['CELERY_EAGER_PROPAGATES_EXCEPTIONS'] = 'True'
os.environ['CELERY_RESULT_BACKEND'] = 'cache+memory://'
os.environ['CELERY_BROKER_URL'] = 'memory://'

@pytest.fixture(scope='session')
def celery_config():
    """Celery configuration for tests"""
    return {
        'broker_url': 'memory://',
        'result_backend': 'cache+memory://',
        'task_always_eager': True,
        'task_eager_propagates': True,
        'task_serializer': 'json',
        'accept_content': ['json'],
        'result_serializer': 'json',
        'timezone': 'UTC',
        'enable_utc': True,
    }

@pytest.fixture
def mock_flask_app():
    """Mock Flask app for testing"""
    with patch('tasks.flask_app') as mock_app:
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=None)
        mock_context.__exit__ = Mock(return_value=None)
        mock_app.app_context.return_value = mock_context
        yield mock_app

@pytest.fixture
def temp_pdf_file():
    """Create a temporary PDF file for testing"""
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
        # Write minimal PDF content (PDF header)
        f.write(b'%PDF-1.4')
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    try:
        os.unlink(temp_path)
    except:
        pass

@pytest.fixture
def sample_claim_data():
    """Sample claim data for testing"""
    return {
        'subject': 'https://example.com/person/123',
        'claim': 'has degree',
        'statement': 'has degree',
        'object': 'https://example.com/degree/456',
        'howKnown': 'DOCUMENT',
        'confidence': 0.95,
        'aspect': 'education',
        'score': 90,
        'stars': 4.5,
        'amt': 50000,
        'unit': 'USD',
        'howMeasured': 'university transcript'
    }

@pytest.fixture
def sample_document_data():
    """Sample document data for testing"""
    from datetime import datetime
    return {
        'id': 'doc-123-456',
        'filename': 'test_document.pdf',
        'file_path': '/path/to/test_document.pdf',
        'public_url': 'https://example.com/docs/test_document',
        'status': 'pending',
        'effective_date': datetime(2024, 1, 1),
        'created_at': datetime.utcnow(),
    }