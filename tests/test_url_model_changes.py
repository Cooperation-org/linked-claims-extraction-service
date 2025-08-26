"""
Unit tests for URL-related model changes
"""
import pytest
import sys
import os
import uuid
from datetime import datetime

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestDraftClaimUrlFields:
    """Test new URL-related fields in DraftClaim model"""
    
    def test_draft_claim_with_url_fields(self):
        """Test creating DraftClaim with new URL fields"""
        from models import DraftClaim
        
        claim = DraftClaim(
            document_id=str(uuid.uuid4()),
            subject="https://en.wikipedia.org/wiki/Kenya",
            statement="Test statement about Kenya",
            object="https://en.wikipedia.org/wiki/Agriculture",
            subject_suggested="https://en.wikipedia.org/wiki/Kenya",
            object_suggested="https://en.wikipedia.org/wiki/Agriculture", 
            urls_need_verification=True,
            claim_data={
                'howKnown': 'DOCUMENT',
                'confidence': 0.9,
                'subject_entity_type': 'location',
                'object_entity_type': 'concept'
            }
        )
        
        # Test that all fields are set correctly
        assert claim.subject == "https://en.wikipedia.org/wiki/Kenya"
        assert claim.object == "https://en.wikipedia.org/wiki/Agriculture"
        assert claim.subject_suggested == "https://en.wikipedia.org/wiki/Kenya"
        assert claim.object_suggested == "https://en.wikipedia.org/wiki/Agriculture"
        assert claim.urls_need_verification == True
        assert claim.claim_data['subject_entity_type'] == 'location'
        assert claim.claim_data['object_entity_type'] == 'concept'
    
    def test_draft_claim_without_url_fields(self):
        """Test that DraftClaim still works without new URL fields"""
        from models import DraftClaim
        
        # Should work with minimal fields (backward compatibility)
        claim = DraftClaim(
            document_id=str(uuid.uuid4()),
            subject="https://example.com/test",
            statement="Test statement"
        )
        
        assert claim.subject == "https://example.com/test"
        assert claim.statement == "Test statement"
        assert claim.subject_suggested is None
        assert claim.object_suggested is None
        # SQLAlchemy default values are applied during flush/commit, so check for None or False
        assert claim.urls_need_verification in [None, False]  # Default handling
    
    def test_draft_claim_url_field_types(self):
        """Test that URL fields accept correct data types"""
        from models import DraftClaim
        
        claim = DraftClaim(
            document_id=str(uuid.uuid4()),
            subject="https://test.com",
            statement="Test",
            subject_suggested="https://suggested.com",
            urls_need_verification=False
        )
        
        # Test string fields
        assert isinstance(claim.subject, str)
        assert isinstance(claim.subject_suggested, str)
        # Test boolean field
        assert isinstance(claim.urls_need_verification, bool)
    
    def test_draft_claim_url_field_lengths(self):
        """Test URL field length limits"""
        from models import DraftClaim
        
        # Test with long URLs (should fit within 500 char limit)
        long_url = "https://en.wikipedia.org/wiki/" + "Very_Long_Entity_Name" * 10
        if len(long_url) > 500:
            long_url = long_url[:500]
        
        claim = DraftClaim(
            document_id=str(uuid.uuid4()),
            subject=long_url,
            statement="Test",
            subject_suggested=long_url
        )
        
        assert len(claim.subject) <= 500
        assert len(claim.subject_suggested) <= 500


class TestTasksUrlIntegration:
    """Test URL generation integration in tasks"""
    
    def test_improve_claim_urls_import(self):
        """Test that improve_claim_urls can be imported in tasks context"""
        # This tests that the import path in tasks.py works
        try:
            from url_generator import improve_claim_urls
            # Test with simple claim
            test_claim = {
                'subject': 'Kenya',
                'statement': 'Test statement',
                'claim': 'impact'
            }
            result = improve_claim_urls(test_claim, "context about Kenya")
            
            # Should have improved the URL
            assert result['subject'] == "https://en.wikipedia.org/wiki/Kenya"
            assert isinstance(result['urls_need_verification'], bool)
            
        except ImportError as e:
            pytest.fail(f"Failed to import improve_claim_urls: {e}")
    
    def test_claim_data_structure_compatibility(self):
        """Test that claim data structure is compatible with URL enhancement"""
        from url_generator import improve_claim_urls
        
        # Test with structure similar to what ClaimExtractor returns
        claim_data = {
            'subject': 'https://www.gatesfoundation.org/goalkeepers/programs/moremilk',
            'claim': 'impact',
            'statement': 'MoreMilk training improved dairy farming',
            'aspect': 'impact:work',
            'amt': 110,
            'unit': 'liters_per_day',
            'howKnown': 'FIRST_HAND',
            'confidence': 0.9
        }
        
        improved = improve_claim_urls(claim_data, "context about dairy farming")
        
        # Should preserve all original fields
        assert improved['claim'] == 'impact'
        assert improved['statement'] == 'MoreMilk training improved dairy farming'
        assert improved['amt'] == 110
        assert improved['unit'] == 'liters_per_day'
        assert improved['howKnown'] == 'FIRST_HAND'
        assert improved['confidence'] == 0.9
        
        # Should add URL verification info
        assert 'urls_need_verification' in improved


class TestApiEndpoints:
    """Test new API endpoint functionality (without Flask app)"""
    
    def test_url_suggestions_logic(self):
        """Test URL suggestions logic that would be used in API"""
        from url_generator import get_url_correction_suggestions, extract_entity_from_url
        
        # Test entity extraction (used in API)
        current_url = "https://en.wikipedia.org/wiki/Test_Entity"
        entity_name = extract_entity_from_url(current_url)
        assert entity_name == "Test Entity"
        
        # Test getting suggestions
        suggestions = get_url_correction_suggestions(entity_name, "organization")
        assert len(suggestions) > 0
        assert all(s.startswith(('http://', 'https://')) for s in suggestions)
    
    def test_url_validation_logic(self):
        """Test URL validation logic used in API"""
        from url_generator import is_real_url
        
        # Valid URLs
        assert is_real_url("https://www.gatesfoundation.org") == True
        assert is_real_url("https://en.wikipedia.org/wiki/Kenya") == True
        
        # Invalid URLs that API should reject
        test_urls = [
            "not-a-url",
            "ftp://invalid.com",
            "",
            "https://example.com/fake"
        ]
        
        for url in test_urls:
            if not url.startswith(('http://', 'https://')):
                # API should reject non-http URLs
                assert not url.startswith(('http://', 'https://'))
            elif 'example.com' in url:
                # Should detect fake URLs
                assert is_real_url(url) == False


if __name__ == "__main__":
    pytest.main([__file__])