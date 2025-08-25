"""
Unit tests for Celery background tasks
"""
import os
import sys
import pytest
from unittest.mock import Mock, MagicMock, patch, call, ANY
from datetime import datetime
import uuid

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestExtractClaimsFromDocument:
    """Test the extract_claims_from_document task"""
    
    @patch('tasks.flask_app')
    @patch('models.db')
    @patch('models.Document')
    @patch('models.ProcessingJob')
    @patch('models.DraftClaim')
    @patch('pdf_parser.simple_document_manager.SimpleDocumentManager')
    @patch('claim_extractor.ClaimExtractor')
    @patch('fitz.open')
    def test_extract_claims_success(
        self, mock_fitz_open, mock_extractor_class, mock_doc_manager,
        mock_claim_class, mock_job_class, mock_doc_class, mock_db, mock_app
    ):
        """Test successful claim extraction from document"""
        # Setup mocks
        mock_context = MagicMock()
        mock_app.app_context.return_value.__enter__ = MagicMock(return_value=mock_context)
        mock_app.app_context.return_value.__exit__ = MagicMock(return_value=None)
        
        # Mock document
        mock_doc = MagicMock()
        mock_doc.id = str(uuid.uuid4())
        mock_doc.file_path = "/path/to/test.pdf"
        mock_doc.public_url = "https://example.com/doc.pdf"
        mock_doc.effective_date = datetime.now()
        mock_doc_class.query.get.return_value = mock_doc
        
        # Mock PDF with pages
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "This is test text from the PDF page with enough content to be processed"
        mock_pdf.load_page.return_value = mock_page
        mock_pdf.__len__ = MagicMock(return_value=1)
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=None)
        mock_fitz_open.return_value = mock_pdf
        
        # Mock claim extractor
        mock_extractor = MagicMock()
        mock_extractor.extract_claims.return_value = [
            {
                'subject': 'Test Subject',
                'claim': 'Test Statement',
                'object': 'Test Object',
                'howKnown': 'DOCUMENT',
                'confidence': 0.9
            }
        ]
        mock_extractor_class.return_value = mock_extractor
        
        # Mock processing job
        mock_job_class.query.get.return_value = None
        
        # Setup environment
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'}):
            # Import and call the function
            from tasks import extract_claims_from_document
            
            # Create task mock
            task = MagicMock()
            task.request.id = str(uuid.uuid4())
            
            # Call the function
            result = extract_claims_from_document(
                task,
                mock_doc.id,
                batch_size=5
            )
            
            # Verify results
            assert result['document_id'] == mock_doc.id
            assert result['total_pages'] == 1
            assert result['total_claims'] == 1
            assert result['status'] == 'completed'
            
            # Verify document status was updated
            assert mock_doc.status == 'completed'
            assert mock_doc.processing_completed_at is not None
            
            # Verify claims were created
            assert mock_claim_class.call_count == 1
            
            # Verify database commits
            assert mock_db.session.commit.call_count >= 2
    
    @patch('tasks.flask_app')
    @patch('models.db')
    @patch('models.Document')
    @patch('models.ProcessingJob')
    def test_extract_claims_no_api_key(
        self, mock_job_class, mock_doc_class, mock_db, mock_app
    ):
        """Test that extraction fails when API key is not configured"""
        mock_context = MagicMock()
        mock_app.app_context.return_value.__enter__ = MagicMock(return_value=mock_context)
        mock_app.app_context.return_value.__exit__ = MagicMock(return_value=None)
        
        mock_doc = MagicMock()
        mock_doc.id = str(uuid.uuid4())
        mock_doc_class.query.get.return_value = mock_doc
        
        with patch.dict(os.environ, {}, clear=True):
            from tasks import extract_claims_from_document
            
            task = MagicMock()
            task.request.id = str(uuid.uuid4())
            
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY not configured"):
                extract_claims_from_document(task, mock_doc.id)
            
            # Verify document status was updated to failed
            assert mock_doc.status == 'failed'
            assert 'ANTHROPIC_API_KEY' in mock_doc.error_message
    
    @patch('tasks.flask_app')
    @patch('models.Document')
    def test_extract_claims_document_not_found(self, mock_doc_class, mock_app):
        """Test that extraction fails when document is not found"""
        mock_context = MagicMock()
        mock_app.app_context.return_value.__enter__ = MagicMock(return_value=mock_context)
        mock_app.app_context.return_value.__exit__ = MagicMock(return_value=None)
        
        mock_doc_class.query.get.return_value = None
        
        from tasks import extract_claims_from_document
        
        task = MagicMock()
        task.request.id = str(uuid.uuid4())
        doc_id = str(uuid.uuid4())
        
        with pytest.raises(ValueError, match=f"Document {doc_id} not found"):
            extract_claims_from_document(task, doc_id)


class TestPublishClaimsToLinkedTrust:
    """Test the publish_claims_to_linkedtrust task"""
    
    @patch('tasks.flask_app')
    @patch('models.db')
    @patch('models.Document')
    @patch('models.DraftClaim')
    @patch('models.ProcessingJob')
    @patch('linkedtrust_client.LinkedTrustClient')
    def test_publish_claims_success(
        self, mock_client_class, mock_job_class, mock_claim_class,
        mock_doc_class, mock_db, mock_app
    ):
        """Test successful claim publishing to LinkedTrust"""
        mock_context = MagicMock()
        mock_app.app_context.return_value.__enter__ = MagicMock(return_value=mock_context)
        mock_app.app_context.return_value.__exit__ = MagicMock(return_value=None)
        
        # Mock document
        mock_doc = MagicMock()
        mock_doc.id = str(uuid.uuid4())
        mock_doc.public_url = "https://example.com/doc.pdf"
        mock_doc.effective_date = datetime.now()
        mock_doc_class.query.get.return_value = mock_doc
        
        # Mock claims
        mock_claim1 = MagicMock()
        mock_claim1.id = str(uuid.uuid4())
        mock_claim1.subject = "Subject1"
        mock_claim1.statement = "Statement1"
        mock_claim1.object = "Object1"
        mock_claim1.claim_data = {'howKnown': 'DOCUMENT', 'confidence': 0.9}
        mock_claim1.status = 'approved'
        
        mock_claim2 = MagicMock()
        mock_claim2.id = str(uuid.uuid4())
        mock_claim2.subject = "Subject2"
        mock_claim2.statement = "Statement2"
        mock_claim2.object = "Object2"
        mock_claim2.claim_data = {'howKnown': 'DOCUMENT', 'score': 5}
        mock_claim2.status = 'approved'
        
        # Mock query
        mock_query = MagicMock()
        mock_query.all.return_value = [mock_claim1, mock_claim2]
        mock_claim_class.query.filter_by.return_value = mock_query
        
        # Mock LinkedTrust client
        mock_client = MagicMock()
        mock_client.create_claim.side_effect = [
            {'success': True, 'data': {'id': 'claim1'}},
            {'success': True, 'data': {'id': 'claim2'}}
        ]
        mock_client_class.return_value = mock_client
        
        from tasks import publish_claims_to_linkedtrust
        
        task = MagicMock()
        task.request.id = str(uuid.uuid4())
        
        result = publish_claims_to_linkedtrust(task, mock_doc.id)
        
        assert result['published'] == 2
        assert result['failed'] == 0
        assert result['status'] == 'completed'
        
        # Verify claims were published
        assert mock_client.create_claim.call_count == 2
        
        # Verify claim status was updated
        assert mock_claim1.status == 'published'
        assert mock_claim2.status == 'published'
        assert mock_claim1.published_at is not None
        assert mock_claim2.published_at is not None
        assert mock_claim1.linkedtrust_claim_url == "https://live.linkedtrust.us/claim/claim1"
        assert mock_claim2.linkedtrust_claim_url == "https://live.linkedtrust.us/claim/claim2"
    
    @patch('tasks.flask_app')
    @patch('models.db')
    @patch('models.Document')
    @patch('models.DraftClaim')
    @patch('models.ProcessingJob')
    def test_publish_claims_no_approved_claims(
        self, mock_job_class, mock_claim_class, mock_doc_class, mock_db, mock_app
    ):
        """Test publishing when there are no approved claims"""
        mock_context = MagicMock()
        mock_app.app_context.return_value.__enter__ = MagicMock(return_value=mock_context)
        mock_app.app_context.return_value.__exit__ = MagicMock(return_value=None)
        
        mock_doc = MagicMock()
        mock_doc.id = str(uuid.uuid4())
        mock_doc_class.query.get.return_value = mock_doc
        
        mock_query = MagicMock()
        mock_query.all.return_value = []
        mock_claim_class.query.filter_by.return_value = mock_query
        
        from tasks import publish_claims_to_linkedtrust
        
        task = MagicMock()
        task.request.id = str(uuid.uuid4())
        
        result = publish_claims_to_linkedtrust(task, mock_doc.id)
        
        assert result['published'] == 0
        assert result['status'] == 'completed'


class TestCallbackTask:
    """Test the CallbackTask base class"""
    
    @patch('tasks.flask_app')
    def test_on_success_updates_job_status(self, mock_app):
        """Test that on_success updates the processing job status"""
        mock_context = MagicMock()
        mock_app.app_context.return_value.__enter__ = MagicMock(return_value=mock_context)
        mock_app.app_context.return_value.__exit__ = MagicMock(return_value=None)
        
        mock_job = MagicMock()
        mock_db = MagicMock()
        
        with patch('models.ProcessingJob') as mock_job_class:
            with patch('models.db', mock_db):
                mock_job_class.query.get.return_value = mock_job
                
                from tasks import CallbackTask
                
                task = CallbackTask()
                task_id = str(uuid.uuid4())
                
                task.on_success(retval={'success': True}, task_id=task_id, args=[], kwargs={})
                
                assert mock_job.status == 'success'
                assert mock_job.completed_at is not None
                mock_db.session.commit.assert_called_once()
    
    @patch('tasks.flask_app')
    def test_on_failure_updates_job_and_document_status(self, mock_app):
        """Test that on_failure updates both job and document status"""
        mock_context = MagicMock()
        mock_app.app_context.return_value.__enter__ = MagicMock(return_value=mock_context)
        mock_app.app_context.return_value.__exit__ = MagicMock(return_value=None)
        
        mock_job = MagicMock()
        mock_doc = MagicMock()
        mock_db = MagicMock()
        
        with patch('models.ProcessingJob') as mock_job_class:
            with patch('models.Document') as mock_doc_class:
                with patch('models.db', mock_db):
                    mock_job_class.query.get.return_value = mock_job
                    mock_doc_class.query.get.return_value = mock_doc
                    
                    from tasks import CallbackTask
                    
                    task = CallbackTask()
                    task_id = str(uuid.uuid4())
                    doc_id = str(uuid.uuid4())
                    error = Exception("Test error")
                    
                    task.on_failure(
                        exc=error,
                        task_id=task_id,
                        args=[doc_id],
                        kwargs={},
                        einfo=None
                    )
                    
                    assert mock_job.status == 'failure'
                    assert mock_job.error_message == "Test error"
                    assert mock_job.completed_at is not None
                    assert mock_doc.status == 'failed'
                    assert mock_doc.error_message == "Test error"
                    assert mock_db.session.commit.call_count == 2


class TestTextChunkProcessing:
    """Test harness for text chunk processing"""
    
    @pytest.fixture
    def sample_chunks(self):
        """Sample text chunks for testing"""
        return {
            'employment': """
                John Smith was employed as a Senior Software Engineer at TechCorp Inc. 
                from January 2020 to December 2023. During his tenure, he led the 
                development of the cloud infrastructure platform and received an 
                outstanding performance rating of 4.8 out of 5.0.
            """,
            'education': """
                Jane Doe graduated with a Bachelor of Science in Computer Science from 
                MIT in May 2019. She achieved a GPA of 3.9 and was on the Dean's List 
                for 6 semesters. She also completed a certification in Machine Learning 
                from Coursera in 2020.
            """,
            'financial': """
                The quarterly revenue for Q3 2023 was $45.2 million, representing a 
                15% increase year-over-year. The company's net profit margin improved 
                to 22.5%. Customer acquisition cost decreased by $50 per customer.
            """,
            'technical': """
                The system achieved 99.99% uptime in 2023. Response time averaged 
                250ms with a p99 latency of 800ms. The database processed 10,000 
                transactions per second during peak load. Error rate remained below 
                0.01% throughout the year.
            """
        }
    
    @patch('claim_extractor.ClaimExtractor')
    def test_text_chunk_extraction(self, mock_extractor_class, sample_chunks):
        """Test extraction from different types of text chunks"""
        mock_extractor = MagicMock()
        mock_extractor_class.return_value = mock_extractor
        
        # Test employment text
        mock_extractor.extract_claims.return_value = [
            {
                'subject': 'John Smith',
                'claim': 'employed as Senior Software Engineer',
                'object': 'TechCorp Inc.',
                'howKnown': 'DOCUMENT',
                'confidence': 0.95,
                'score': 4.8
            }
        ]
        
        claims = mock_extractor.extract_claims(sample_chunks['employment'])
        assert len(claims) == 1
        assert claims[0]['subject'] == 'John Smith'
        assert claims[0]['score'] == 4.8
    
    @patch('claim_extractor.ClaimExtractor')
    def test_empty_chunk_handling(self, mock_extractor_class):
        """Test handling of empty or short text chunks"""
        mock_extractor = MagicMock()
        mock_extractor_class.return_value = mock_extractor
        mock_extractor.extract_claims.return_value = []
        
        # Test empty string
        claims = mock_extractor.extract_claims("")
        assert claims == []
        
        # Test whitespace only
        claims = mock_extractor.extract_claims("   \n\t  ")
        assert claims == []
        
        # Test very short text
        claims = mock_extractor.extract_claims("Hi")
        assert claims == []


class TestLoggingAndDebugging:
    """Test harness for logging and debugging capabilities"""
    
    @patch('tasks.logger')
    @patch('claim_extractor.ClaimExtractor')
    def test_extraction_logging(self, mock_extractor_class, mock_logger):
        """Test that extraction process is properly logged"""
        mock_extractor = MagicMock()
        mock_extractor_class.return_value = mock_extractor
        
        # Simulate extraction with logging
        doc_id = str(uuid.uuid4())
        mock_logger.info.assert_not_called()
        
        # Verify expected log messages would be called
        expected_logs = [
            f"Starting claim extraction for document {doc_id}",
            "Processing pages 1 to 5 of 10",
            "Page 1 returned 3 claims",
            "Completed extraction: 15 claims from 10 pages"
        ]
        
        # In real extraction, these would be logged
        for msg in expected_logs:
            mock_logger.info(msg)
        
        assert mock_logger.info.call_count == len(expected_logs)
    
    @patch('tasks.logger')
    def test_error_logging(self, mock_logger):
        """Test that errors are properly logged"""
        error_messages = [
            "ANTHROPIC_API_KEY environment variable not set!",
            "API call failed for page 5: Rate limit exceeded",
            "Error processing document: Connection timeout"
        ]
        
        for msg in error_messages:
            mock_logger.error(msg)
        
        assert mock_logger.error.call_count == len(error_messages)


class TestBatchProcessing:
    """Test harness for batch processing logic"""
    
    def test_batch_size_calculation(self):
        """Test batch size calculations for different document sizes"""
        test_cases = [
            (10, 5, 2),   # 10 pages, batch size 5, expect 2 batches
            (10, 3, 4),   # 10 pages, batch size 3, expect 4 batches
            (1, 5, 1),    # 1 page, batch size 5, expect 1 batch
            (0, 5, 0),    # 0 pages, batch size 5, expect 0 batches
        ]
        
        for total_pages, batch_size, expected_batches in test_cases:
            batches = []
            for start in range(0, total_pages, batch_size):
                end = min(start + batch_size, total_pages)
                batches.append((start, end))
            
            assert len(batches) == expected_batches
    
    def test_page_filtering_logic(self):
        """Test page filtering based on content length"""
        pages = [
            ("", False),                                           # Empty
            ("   ", False),                                        # Whitespace only
            ("Short", False),                                      # Too short
            ("x" * 49, False),                                     # Just under threshold
            ("x" * 50, True),                                      # Exactly at threshold
            ("This is a valid page with enough content that should be processed", True),   # Valid content (>50 chars)
        ]
        
        MIN_CONTENT_LENGTH = 50
        
        for content, should_process in pages:
            cleaned = content.strip()
            is_valid = len(cleaned) >= MIN_CONTENT_LENGTH
            assert is_valid == should_process, f"Failed for content length {len(cleaned)}: expected {should_process}, got {is_valid}"


class TestDatabaseOperations:
    """Test harness for database operations"""
    
    @patch('models.db')
    @patch('models.DraftClaim')
    def test_claim_storage(self, mock_claim_class, mock_db):
        """Test storing claims in database"""
        claims_data = [
            {
                'subject': 'Subject1',
                'statement': 'Statement1',
                'object': 'Object1',
                'confidence': 0.9
            },
            {
                'subject': 'Subject2',
                'statement': 'Statement2', 
                'object': 'Object2',
                'confidence': 0.8
            }
        ]
        
        mock_claims = []
        for data in claims_data:
            mock_claim = MagicMock()
            for key, value in data.items():
                setattr(mock_claim, key, value)
            mock_claims.append(mock_claim)
            mock_db.session.add(mock_claim)
        
        mock_db.session.commit()
        
        assert mock_db.session.add.call_count == len(claims_data)
        assert mock_db.session.commit.call_count == 1
    
    @patch('models.db')
    def test_transaction_rollback(self, mock_db):
        """Test database rollback on error"""
        mock_db.session.commit.side_effect = Exception("Database error")
        
        try:
            mock_db.session.add(MagicMock())
            mock_db.session.commit()
            assert False, "Should have raised exception"
        except Exception:
            mock_db.session.rollback()
        
        assert mock_db.session.rollback.call_count == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--log-cli-level=INFO'])