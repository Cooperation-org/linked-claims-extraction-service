"""
Final test to verify the Celery worker ModuleNotFoundError is fixed
"""
import os
import sys
import unittest
from unittest.mock import Mock, patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))


class TestCeleryWorkerFix(unittest.TestCase):
    """Test that the ModuleNotFoundError is fixed"""
    
    def test_import_chain(self):
        """Test the complete import chain that was causing the error"""
        
        # This was the original error:
        # ModuleNotFoundError: No module named 'pdf_parser'
        # It happened at line 81 of tasks.py
        
        # Test that we can import tasks without error
        from tasks import extract_claims_from_document
        self.assertIsNotNone(extract_claims_from_document)
        
        # Test that we can import what tasks.py needs
        from pdf_parser.simple_document_manager import SimpleDocumentManager
        self.assertIsNotNone(SimpleDocumentManager)
    
    def test_celery_task_registration(self):
        """Test that tasks are properly registered with Celery"""
        from celery_app import celery_app
        from tasks import extract_claims_from_document, publish_claims_to_linkedtrust
        
        # Check tasks are registered
        self.assertIn('tasks.extract_claims_from_document', celery_app.tasks)
        self.assertIn('tasks.publish_claims_to_linkedtrust', celery_app.tasks)
    
    @patch('tasks.flask_app.app_context')
    def test_task_imports_in_context(self, mock_context):
        """Test that imports work inside the task context"""
        mock_context.return_value.__enter__ = Mock()
        mock_context.return_value.__exit__ = Mock()
        
        # These are the imports from inside the task (lines 80-82 of tasks.py)
        with mock_context():
            from models import db, Document, DraftClaim, ProcessingJob
            from pdf_parser.simple_document_manager import SimpleDocumentManager
            from claim_extractor import ClaimExtractor
            
            self.assertIsNotNone(db)
            self.assertIsNotNone(Document)
            self.assertIsNotNone(DraftClaim)
            self.assertIsNotNone(ProcessingJob)
            self.assertIsNotNone(SimpleDocumentManager)
            self.assertIsNotNone(ClaimExtractor)
    
    def test_no_heavy_dependencies_needed(self):
        """Verify we don't need transformers, torch, etc for basic operation"""
        # The SimpleDocumentManager should not require ML libraries
        from pdf_parser.simple_document_manager import SimpleDocumentManager
        
        # This should work without importing transformers or torch
        manager = SimpleDocumentManager()
        self.assertIsNotNone(manager)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)