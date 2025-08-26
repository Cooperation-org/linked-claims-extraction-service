"""
URL generation utilities for claims extraction
"""

import re
from urllib.parse import quote
from typing import Tuple, Optional, Dict, Any, List

# Known entity mappings
ENTITY_MAPPINGS = {
    # Organizations
    'moremilk': 'https://en.wikipedia.org/wiki/MoreMilk',
    'bill & melinda gates foundation': 'https://www.gatesfoundation.org/',
    'gates foundation': 'https://www.gatesfoundation.org/',
    'linkedtrust': 'https://linkedtrust.us/',
    
    # Locations
    'kenya': 'https://en.wikipedia.org/wiki/Kenya',
    'ethiopia': 'https://en.wikipedia.org/wiki/Ethiopia',
    'maili nne': 'https://en.wikipedia.org/wiki/Maili_Nne',
    'united states': 'https://en.wikipedia.org/wiki/United_States',
    'switzerland': 'https://en.wikipedia.org/wiki/Switzerland',
    
    # Concepts/Products
    'iodized salt': 'https://en.wikipedia.org/wiki/Iodised_salt',
    'folic acid': 'https://en.wikipedia.org/wiki/Folic_acid',
    'vitamin a': 'https://en.wikipedia.org/wiki/Vitamin_A',
    'neural tube defects': 'https://en.wikipedia.org/wiki/Neural_tube_defect',
}

def detect_entity_type(entity_name: str, context: str = "") -> str:
    """
    Detect what type of entity this might be based on the name and context
    Returns: 'person', 'organization', 'location', 'concept', 'unknown'
    """
    entity_lower = entity_name.lower()
    context_lower = context.lower()
    
    # Check for person indicators
    if any(indicator in entity_lower for indicator in ['coletta', 'daniel', 'dr.', 'mr.', 'mrs.', 'ms.']):
        return 'person'
    
    # Check for organization indicators
    if any(indicator in entity_lower for indicator in [
        'foundation', 'organization', 'company', 'corp', 'inc', 'ltd',
        'university', 'institute', 'agency', 'department', 'ministry',
        'moremilk', 'dairy board'
    ]):
        return 'organization'
    
    # Check for location indicators
    if any(indicator in entity_lower for indicator in [
        'kenya', 'ethiopia', 'country', 'city', 'town', 'village',
        'united states', 'switzerland', 'maili nne', 'africa'
    ]):
        return 'location'
    
    # Check for concept/product indicators
    if any(indicator in entity_lower for indicator in [
        'salt', 'acid', 'vitamin', 'defect', 'deficiency', 'fortification'
    ]):
        return 'concept'
    
    return 'unknown'

def generate_wikipedia_url(entity_name: str) -> str:
    """Generate a Wikipedia URL for an entity"""
    # Clean the entity name
    clean_name = entity_name.strip()
    # Replace spaces with underscores for Wikipedia URLs
    clean_name = clean_name.replace(' ', '_')
    return f"https://en.wikipedia.org/wiki/{quote(clean_name)}"

def generate_url_for_entity(entity_name: str, context: str = "") -> Tuple[str, bool, str]:
    """
    Generate a reasonable URL for an entity
    
    Returns:
        Tuple of (url, is_guessed, entity_type)
        - url: Generated URL
        - is_guessed: True if this is a guess that needs verification
        - entity_type: The detected type of entity
    """
    entity_lower = entity_name.lower().strip()
    
    # Check if we have a known mapping
    if entity_lower in ENTITY_MAPPINGS:
        return ENTITY_MAPPINGS[entity_lower], False, detect_entity_type(entity_name, context)
    
    # Check for partial matches in known mappings
    for known_entity, url in ENTITY_MAPPINGS.items():
        if known_entity in entity_lower or entity_lower in known_entity:
            return url, False, detect_entity_type(entity_name, context)
    
    # Detect entity type and generate appropriate URL
    entity_type = detect_entity_type(entity_name, context)
    
    if entity_type == 'person':
        # For people, we might want to use a more generic approach
        # or ask user for LinkedIn/personal website
        return generate_wikipedia_url(entity_name), True, entity_type
    
    elif entity_type == 'organization':
        # For organizations, try Wikipedia first, but mark as guessed
        return generate_wikipedia_url(entity_name), True, entity_type
    
    elif entity_type == 'location':
        # For locations, Wikipedia is usually reliable
        return generate_wikipedia_url(entity_name), True, entity_type
    
    elif entity_type == 'concept':
        # For concepts, Wikipedia is usually good
        return generate_wikipedia_url(entity_name), True, entity_type
    
    else:
        # Unknown type, default to Wikipedia but mark as highly uncertain
        return generate_wikipedia_url(entity_name), True, entity_type

def improve_claim_urls(claim_data: Dict[str, Any], context: str = "") -> Dict[str, Any]:
    """
    Improve URLs in claim data and mark which ones need verification
    
    Args:
        claim_data: The claim dictionary
        context: Additional context (e.g., page text)
        
    Returns:
        Updated claim data with improved URLs and verification flags
    """
    improved_claim = claim_data.copy()
    needs_verification = False
    
    # Handle subject
    if 'subject' in improved_claim and improved_claim['subject']:
        subject = improved_claim['subject']
        if not subject.startswith(('http://', 'https://')):
            # Not a URL, generate one
            url, is_guessed, entity_type = generate_url_for_entity(subject, context)
            improved_claim['subject'] = url
            improved_claim['subject_suggested'] = url
            improved_claim['subject_entity_type'] = entity_type
            if is_guessed:
                needs_verification = True
        elif not is_real_url(subject):
            # It's a URL but might be fake (example.com, etc.)
            # Extract entity name from the URL and regenerate
            entity_name = extract_entity_from_url(subject)
            url, is_guessed, entity_type = generate_url_for_entity(entity_name, context)
            improved_claim['subject'] = url
            improved_claim['subject_suggested'] = url
            improved_claim['subject_entity_type'] = entity_type
            if is_guessed:
                needs_verification = True
    
    # Handle object (if present)
    if 'object' in improved_claim and improved_claim['object']:
        obj = improved_claim['object']
        if not obj.startswith(('http://', 'https://')):
            # Not a URL, generate one
            url, is_guessed, entity_type = generate_url_for_entity(obj, context)
            improved_claim['object'] = url
            improved_claim['object_suggested'] = url
            improved_claim['object_entity_type'] = entity_type
            if is_guessed:
                needs_verification = True
        elif not is_real_url(obj):
            # It's a URL but might be fake
            entity_name = extract_entity_from_url(obj)
            url, is_guessed, entity_type = generate_url_for_entity(entity_name, context)
            improved_claim['object'] = url
            improved_claim['object_suggested'] = url
            improved_claim['object_entity_type'] = entity_type
            if is_guessed:
                needs_verification = True
    
    improved_claim['urls_need_verification'] = needs_verification
    return improved_claim

def is_real_url(url: str) -> bool:
    """Check if a URL looks like a real, non-placeholder URL"""
    fake_patterns = [
        'example.com', 'test.com', 'placeholder.com', 'fake.com',
        'dummy.com', 'sample.com', 'mock.com'
    ]
    
    url_lower = url.lower()
    return not any(pattern in url_lower for pattern in fake_patterns)

def extract_entity_from_url(url: str) -> str:
    """Extract entity name from a URL for regeneration"""
    # Simple extraction - get the last part of the path or domain
    if '#' in url:
        # Fragment identifier URLs like "doc.url#subject-EntityName"
        fragment = url.split('#')[-1]
        if '-' in fragment:
            return fragment.split('-', 1)[-1].replace('_', ' ')
    
    # Extract from path
    path_parts = url.split('/')
    if path_parts:
        return path_parts[-1].replace('_', ' ').replace('-', ' ')
    
    return "Unknown Entity"

def get_url_correction_suggestions(entity_name: str, entity_type: str) -> List[str]:
    """
    Get multiple URL suggestions for an entity to present to user
    """
    suggestions = []
    
    # Always include Wikipedia
    suggestions.append(generate_wikipedia_url(entity_name))
    
    if entity_type == 'organization':
        # Add common organization URL patterns
        clean_name = entity_name.lower().replace(' ', '').replace('&', 'and')
        suggestions.extend([
            f"https://www.{clean_name}.org",
            f"https://www.{clean_name}.com", 
            f"https://{clean_name}.org"
        ])
    
    elif entity_type == 'location':
        # For locations, Wikipedia is usually best, but add government sites
        if 'kenya' in entity_name.lower():
            suggestions.append("https://www.kenya.go.ke")
        elif 'ethiopia' in entity_name.lower():
            suggestions.append("https://www.ethiopia.gov.et")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_suggestions = []
    for url in suggestions:
        if url not in seen:
            seen.add(url)
            unique_suggestions.append(url)
    
    return unique_suggestions[:5]  # Limit to 5 suggestions