"""
Unit tests for URL generation functionality
"""
import pytest
import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from url_generator import (
    detect_entity_type,
    generate_wikipedia_url,
    generate_url_for_entity,
    improve_claim_urls,
    is_real_url,
    extract_entity_from_url,
    get_url_correction_suggestions
)


class TestEntityTypeDetection:
    """Test entity type detection"""
    
    def test_detect_person(self):
        """Test detection of person entities"""
        assert detect_entity_type("Coletta Kemboi") == "person"
        assert detect_entity_type("Daniel") == "person"
        assert detect_entity_type("Dr. Smith") == "person"
    
    def test_detect_organization(self):
        """Test detection of organization entities"""
        assert detect_entity_type("MoreMilk") == "organization"
        assert detect_entity_type("Bill & Melinda Gates Foundation") == "organization"
        assert detect_entity_type("dairy board") == "organization"
        assert detect_entity_type("University of Kenya") == "organization"
    
    def test_detect_location(self):
        """Test detection of location entities"""
        assert detect_entity_type("Kenya") == "location"
        assert detect_entity_type("Ethiopia") == "location" 
        assert detect_entity_type("Maili Nne") == "location"
        assert detect_entity_type("United States") == "location"
    
    def test_detect_concept(self):
        """Test detection of concept entities"""
        assert detect_entity_type("iodized salt") == "concept"
        assert detect_entity_type("folic acid") == "concept"
        assert detect_entity_type("vitamin A deficiency") == "concept"
    
    def test_detect_unknown(self):
        """Test unknown entity type"""
        assert detect_entity_type("random thing") == "unknown"


class TestUrlGeneration:
    """Test URL generation functions"""
    
    def test_generate_wikipedia_url(self):
        """Test Wikipedia URL generation"""
        url = generate_wikipedia_url("Test Entity")
        assert url == "https://en.wikipedia.org/wiki/Test_Entity"
        
        # Test with special characters
        url = generate_wikipedia_url("Bill & Melinda Gates Foundation")
        assert "Bill_%26_Melinda_Gates_Foundation" in url
    
    def test_generate_url_for_known_entity(self):
        """Test URL generation for known entities"""
        url, is_guessed, entity_type = generate_url_for_entity("Kenya")
        assert url == "https://en.wikipedia.org/wiki/Kenya"
        assert is_guessed == False  # Should not be guessed for known entities
        assert entity_type == "location"
        
        url, is_guessed, entity_type = generate_url_for_entity("MoreMilk")
        assert url == "https://en.wikipedia.org/wiki/MoreMilk"
        assert is_guessed == False
        assert entity_type == "organization"
    
    def test_generate_url_for_unknown_entity(self):
        """Test URL generation for unknown entities"""
        url, is_guessed, entity_type = generate_url_for_entity("Unknown Company")
        assert url == "https://en.wikipedia.org/wiki/Unknown_Company"
        assert is_guessed == True  # Should be guessed for unknown entities
        assert entity_type == "organization"


class TestUrlValidation:
    """Test URL validation functions"""
    
    def test_is_real_url(self):
        """Test real URL detection"""
        assert is_real_url("https://www.gatesfoundation.org") == True
        assert is_real_url("https://en.wikipedia.org/wiki/Kenya") == True
        
        # Fake URLs should return False
        assert is_real_url("https://example.com/test") == False
        assert is_real_url("https://fake.com/entity") == False
        assert is_real_url("https://placeholder.com/item") == False
    
    def test_extract_entity_from_url(self):
        """Test entity name extraction from URLs"""
        # Fragment URLs
        entity = extract_entity_from_url("https://doc.url#subject-TestEntity")
        assert entity == "TestEntity"
        
        # Path-based URLs
        entity = extract_entity_from_url("https://en.wikipedia.org/wiki/Test_Entity")
        assert entity == "Test Entity"
        
        # Handle underscores and dashes
        entity = extract_entity_from_url("https://en.wikipedia.org/wiki/Bill_and_Melinda_Gates_Foundation")
        assert entity == "Bill and Melinda Gates Foundation"


class TestClaimUrlImprovement:
    """Test claim URL improvement functionality"""
    
    def test_improve_claim_with_non_url_subject(self):
        """Test improving a claim where subject is not a URL"""
        claim = {
            'subject': 'Kenya',
            'statement': 'Test statement about Kenya',
            'claim': 'impact'
        }
        
        context = "This is about Kenya, a country in Africa"
        improved = improve_claim_urls(claim, context)
        
        assert improved['subject'] == "https://en.wikipedia.org/wiki/Kenya"
        assert improved['subject_suggested'] == "https://en.wikipedia.org/wiki/Kenya"
        assert improved['subject_entity_type'] == "location"
        assert improved['urls_need_verification'] == False  # Known entity
    
    def test_improve_claim_with_unknown_entity(self):
        """Test improving a claim with unknown entity"""
        claim = {
            'subject': 'Unknown Organization',
            'statement': 'Test statement',
            'claim': 'impact'
        }
        
        improved = improve_claim_urls(claim)
        
        assert improved['subject'] == "https://en.wikipedia.org/wiki/Unknown_Organization"
        assert improved['urls_need_verification'] == True  # Unknown entity needs verification
    
    def test_improve_claim_with_fake_url(self):
        """Test improving a claim with a fake URL"""
        claim = {
            'subject': 'https://example.com/fake-entity',
            'statement': 'Test statement',
            'claim': 'impact'
        }
        
        improved = improve_claim_urls(claim)
        
        # Should have generated a new URL
        assert improved['subject'] != 'https://example.com/fake-entity'
        assert improved['subject'].startswith('https://en.wikipedia.org/')
        assert improved['urls_need_verification'] == True
    
    def test_improve_claim_with_real_url(self):
        """Test that real URLs are not modified"""
        claim = {
            'subject': 'https://www.gatesfoundation.org/',
            'statement': 'Test statement',
            'claim': 'impact'
        }
        
        improved = improve_claim_urls(claim)
        
        # Should keep the original URL
        assert improved['subject'] == 'https://www.gatesfoundation.org/'
        assert 'subject_suggested' not in improved
        assert improved.get('urls_need_verification', False) == False
    
    def test_improve_claim_with_object(self):
        """Test improving a claim that has both subject and object"""
        claim = {
            'subject': 'MoreMilk',
            'object': 'dairy farmers',
            'statement': 'MoreMilk helps dairy farmers',
            'claim': 'impact'
        }
        
        improved = improve_claim_urls(claim)
        
        # Both should be converted to URLs
        assert improved['subject'] == "https://en.wikipedia.org/wiki/MoreMilk"
        assert improved['object'].startswith('https://en.wikipedia.org/')
        assert improved['object_entity_type'] == "unknown"  # "dairy farmers" is unknown type


class TestUrlSuggestions:
    """Test URL correction suggestions"""
    
    def test_get_url_suggestions_for_organization(self):
        """Test getting URL suggestions for organizations"""
        suggestions = get_url_correction_suggestions("Test Company", "organization")
        
        # Should include Wikipedia and common org patterns
        assert len(suggestions) > 1
        assert "https://en.wikipedia.org/wiki/Test_Company" in suggestions
        assert any(".org" in s or ".com" in s for s in suggestions)
    
    def test_get_url_suggestions_for_location(self):
        """Test getting URL suggestions for locations"""
        suggestions = get_url_correction_suggestions("Kenya", "location")
        
        # Should include Wikipedia
        assert "https://en.wikipedia.org/wiki/Kenya" in suggestions
        # May include government site
        assert len(suggestions) >= 1
    
    def test_url_suggestions_no_duplicates(self):
        """Test that URL suggestions don't contain duplicates"""
        suggestions = get_url_correction_suggestions("Test Entity", "organization")
        
        # No duplicates
        assert len(suggestions) == len(set(suggestions))


if __name__ == "__main__":
    pytest.main([__file__])