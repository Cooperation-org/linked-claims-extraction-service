import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sync_processor import SyncClaimProcessor


class TestSyncProcessor(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        self.processor = SyncClaimProcessor()
        
    @patch('sync_processor.fitz.open')
    @patch('sync_processor.ClaimExtractor')
    def test_extract_claims_from_document_no_db(self, mock_extractor_class, mock_fitz):
        """Test document processing without database"""
        # Mock PDF
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "This is test content with enough text to be processed by the extractor."
        mock_pdf.load_page.return_value = mock_page
        mock_pdf.__len__ = MagicMock(return_value=1)
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=None)
        mock_fitz.return_value = mock_pdf
        
        # Mock extractor
        mock_extractor = MagicMock()
        mock_extractor.extract_claims.return_value = [
            {
                'subject': 'https://example.com/test',
                'claim': 'validated',
                'object': 'https://example.com/content',
                'confidence': 0.9
            }
        ]
        mock_extractor_class.return_value = mock_extractor
        
        # Test
        result = self.processor.extract_claims_from_document("test.pdf")
        
        # Verify
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['total_pages'], 1)
        self.assertGreater(result['total_claims'], 0)
        
    @patch('sync_processor.fitz.open')
    @patch('sync_processor.ClaimExtractor')
    def test_extract_claims_empty_page(self, mock_extractor_class, mock_fitz):
        """Test handling of empty pages"""
        # Mock PDF with empty page
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = ""  # Empty page
        mock_pdf.load_page.return_value = mock_page
        mock_pdf.__len__ = MagicMock(return_value=1)
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=None)
        mock_fitz.return_value = mock_pdf
        
        mock_extractor = MagicMock()
        mock_extractor_class.return_value = mock_extractor
        
        result = self.processor.extract_claims_from_document("test.pdf")
        
        # Should complete but with no claims
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['total_claims'], 0)
        # Extractor should not be called for empty pages
        mock_extractor.extract_claims.assert_not_called()
        
    @patch('sync_processor.fitz.open')
    def test_extract_claims_file_error(self, mock_fitz):
        """Test handling of file errors"""
        mock_fitz.side_effect = Exception("File not found")
        
        with self.assertRaises(Exception):
            self.processor.extract_claims_from_document("nonexistent.pdf")


if __name__ == '__main__':
    unittest.main()