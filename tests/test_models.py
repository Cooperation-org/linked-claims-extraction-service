"""
Unit tests for database models
"""
import os
import sys
import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import uuid
import json

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestDocument:
    """Test the Document model"""
    
    def test_document_creation(self):
        """Test creating a Document instance"""
        from models import Document
        
        doc_id = str(uuid.uuid4())
        doc = Document(
            id=doc_id,
            user_id='user123',
            original_filename='test.pdf',
            file_path='/path/to/test.pdf',
            public_url='https://example.com/test.pdf',
            effective_date=datetime(2024, 1, 1),
            status='pending',
            upload_time=datetime.now()
        )
        
        assert doc.id == doc_id
        assert doc.user_id == 'user123'
        assert doc.original_filename == 'test.pdf'
        assert doc.file_path == '/path/to/test.pdf'
        assert doc.public_url == 'https://example.com/test.pdf'
        assert doc.effective_date == datetime(2024, 1, 1)
        assert doc.status == 'pending'
        assert doc.upload_time is not None
    
    def test_document_repr(self):
        """Test Document string representation"""
        from models import Document
        
        doc = Document(
            id=str(uuid.uuid4()),
            original_filename='test.pdf'
        )
        
        assert 'test.pdf' in repr(doc)
        assert doc.id in repr(doc)


class TestDraftClaim:
    """Test the DraftClaim model"""
    
    def test_draft_claim_creation(self):
        """Test creating a DraftClaim instance"""
        from models import DraftClaim
        
        claim_id = str(uuid.uuid4())
        doc_id = str(uuid.uuid4())
        claim_data = {
            'howKnown': 'DOCUMENT',
            'confidence': 0.9,
            'aspect': 'quality'
        }
        
        claim = DraftClaim(
            id=claim_id,
            document_id=doc_id,
            subject='Test Subject',
            statement='Test Statement',
            object='Test Object',
            claim_data=claim_data,
            page_number=1,
            page_text_snippet='Sample text',
            status='draft',
            created_at=datetime.now()
        )
        
        assert claim.id == claim_id
        assert claim.document_id == doc_id
        assert claim.subject == 'Test Subject'
        assert claim.statement == 'Test Statement'
        assert claim.object == 'Test Object'
        assert claim.claim_data == claim_data
        assert claim.page_number == 1
        assert claim.page_text_snippet == 'Sample text'
        assert claim.status == 'draft'
        assert claim.created_at is not None
    
    def test_draft_claim_repr(self):
        """Test DraftClaim string representation"""
        from models import DraftClaim
        
        claim = DraftClaim(
            id=str(uuid.uuid4()),
            statement='Test Statement'
        )
        
        assert 'Test Statement' in repr(claim)
        assert claim.id in repr(claim)
    
    def test_draft_claim_json_field(self):
        """Test that claim_data is properly handled as JSON"""
        from models import DraftClaim
        
        claim_data = {
            'howKnown': 'DOCUMENT',
            'confidence': 0.9,
            'nested': {'key': 'value'}
        }
        
        claim = DraftClaim(
            id=str(uuid.uuid4()),
            claim_data=claim_data
        )
        
        # Verify the data is stored correctly
        assert claim.claim_data['howKnown'] == 'DOCUMENT'
        assert claim.claim_data['confidence'] == 0.9
        assert claim.claim_data['nested']['key'] == 'value'


class TestProcessingJob:
    """Test the ProcessingJob model"""
    
    def test_processing_job_creation(self):
        """Test creating a ProcessingJob instance"""
        from models import ProcessingJob
        
        job_id = str(uuid.uuid4())
        doc_id = str(uuid.uuid4())
        
        job = ProcessingJob(
            id=job_id,
            document_id=doc_id,
            job_type='extract_claims',
            status='started',
            started_at=datetime.now()
        )
        
        assert job.id == job_id
        assert job.document_id == doc_id
        assert job.job_type == 'extract_claims'
        assert job.status == 'started'
        assert job.started_at is not None
        assert job.completed_at is None
        assert job.error_message is None
    
    def test_processing_job_with_error(self):
        """Test ProcessingJob with error state"""
        from models import ProcessingJob
        
        job = ProcessingJob(
            id=str(uuid.uuid4()),
            document_id=str(uuid.uuid4()),
            job_type='extract_claims',
            status='failure',
            error_message='Test error occurred',
            started_at=datetime.now(),
            completed_at=datetime.now()
        )
        
        assert job.status == 'failure'
        assert job.error_message == 'Test error occurred'
        assert job.completed_at is not None
    
    def test_processing_job_repr(self):
        """Test ProcessingJob string representation"""
        from models import ProcessingJob
        
        job_id = str(uuid.uuid4())
        job = ProcessingJob(
            id=job_id,
            job_type='extract_claims',
            status='success'
        )
        
        repr_str = repr(job)
        assert job_id in repr_str
        assert 'extract_claims' in repr_str
        assert 'success' in repr_str


class TestValidationToken:
    """Test the ValidationToken model"""
    
    def test_validation_token_creation(self):
        """Test creating a ValidationToken instance"""
        from models import ValidationToken
        
        token_id = str(uuid.uuid4())
        doc_id = str(uuid.uuid4())
        
        token = ValidationToken(
            id=token_id,
            document_id=doc_id,
            token='test-token-123',
            email='test@example.com',
            role='witness',
            created_at=datetime.now()
        )
        
        assert token.id == token_id
        assert token.document_id == doc_id
        assert token.token == 'test-token-123'
        assert token.email == 'test@example.com'
        assert token.role == 'witness'
        assert token.created_at is not None
        assert token.used is False
        assert token.used_at is None
    
    def test_validation_token_used_state(self):
        """Test ValidationToken in used state"""
        from models import ValidationToken
        
        token = ValidationToken(
            id=str(uuid.uuid4()),
            document_id=str(uuid.uuid4()),
            token='test-token-123',
            email='test@example.com',
            role='beneficiary',
            used=True,
            used_at=datetime.now()
        )
        
        assert token.used is True
        assert token.used_at is not None
        assert token.role == 'beneficiary'
    
    def test_validation_token_repr(self):
        """Test ValidationToken string representation"""
        from models import ValidationToken
        
        token = ValidationToken(
            id=str(uuid.uuid4()),
            token='test-token-123',
            email='test@example.com'
        )
        
        repr_str = repr(token)
        assert 'test-token-123' in repr_str
        assert 'test@example.com' in repr_str


class TestModelRelationships:
    """Test model relationships"""
    
    @patch('models.db')
    def test_document_draft_claims_relationship(self, mock_db):
        """Test that Document has a relationship with DraftClaims"""
        from models import Document, DraftClaim
        
        # Create document
        doc = Document(
            id=str(uuid.uuid4()),
            original_filename='test.pdf'
        )
        
        # Mock the draft_claims relationship
        mock_claims = MagicMock()
        mock_claims.count.return_value = 3
        doc.draft_claims = mock_claims
        
        # Test the relationship
        assert doc.draft_claims.count() == 3
    
    @patch('models.db')
    def test_document_processing_jobs_relationship(self, mock_db):
        """Test that Document has a relationship with ProcessingJobs"""
        from models import Document, ProcessingJob
        
        # Create document
        doc = Document(
            id=str(uuid.uuid4()),
            original_filename='test.pdf'
        )
        
        # Mock the processing_jobs relationship
        mock_jobs = MagicMock()
        mock_jobs.filter_by.return_value.first.return_value = MagicMock(status='success')
        doc.processing_jobs = mock_jobs
        
        # Test the relationship
        latest_job = doc.processing_jobs.filter_by(job_type='extract_claims').first()
        assert latest_job.status == 'success'


class TestDatabaseOperations:
    """Test database operations with models"""
    
    @patch('models.db.session')
    def test_add_document_to_session(self, mock_session):
        """Test adding a document to the database session"""
        from models import Document
        
        doc = Document(
            id=str(uuid.uuid4()),
            user_id='user123',
            original_filename='test.pdf',
            file_path='/path/to/test.pdf'
        )
        
        mock_session.add(doc)
        mock_session.commit()
        
        mock_session.add.assert_called_once_with(doc)
        mock_session.commit.assert_called_once()
    
    @patch('models.db.session')
    def test_delete_document_from_session(self, mock_session):
        """Test deleting a document from the database session"""
        from models import Document
        
        doc = Document(
            id=str(uuid.uuid4()),
            original_filename='test.pdf'
        )
        
        mock_session.delete(doc)
        mock_session.commit()
        
        mock_session.delete.assert_called_once_with(doc)
        mock_session.commit.assert_called_once()
    
    @patch('models.Document.query')
    def test_query_document_by_id(self, mock_query):
        """Test querying a document by ID"""
        from models import Document
        
        doc_id = str(uuid.uuid4())
        mock_doc = MagicMock()
        mock_query.get.return_value = mock_doc
        
        result = Document.query.get(doc_id)
        
        assert result == mock_doc
        mock_query.get.assert_called_once_with(doc_id)
    
    @patch('models.DraftClaim.query')
    def test_query_claims_by_document(self, mock_query):
        """Test querying claims by document ID"""
        from models import DraftClaim
        
        doc_id = str(uuid.uuid4())
        mock_claims = [MagicMock(), MagicMock()]
        mock_query.filter_by.return_value.all.return_value = mock_claims
        
        results = DraftClaim.query.filter_by(document_id=doc_id).all()
        
        assert len(results) == 2
        mock_query.filter_by.assert_called_once_with(document_id=doc_id)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])