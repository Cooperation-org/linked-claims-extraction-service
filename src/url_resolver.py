"""
URL Resolver for Claims - Post-processing to find real organizational URLs
"""
import requests
import time
import re
import logging
import json
from urllib.parse import urljoin, urlparse, quote
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Cache for successful URL resolutions to avoid duplicate searches
URL_CACHE = {}

# Rate limiting for web searches
LAST_SEARCH_TIME = 0
SEARCH_DELAY = 1.0  # seconds between searches

# Known high-confidence organizational URLs (minimal set)
KNOWN_ORGS = {
    # Only include organizations with very high confidence
    'unicef': 'https://www.unicef.org',
    'who': 'https://www.who.int',
    'world_bank': 'https://www.worldbank.org',
    'gates_foundation': 'https://www.gatesfoundation.org'
}

def extract_org_name_from_urn(urn_string: str) -> str:
    """Extract organization name from URN format"""
    if urn_string.startswith('urn:local:org:'):
        return urn_string.replace('urn:local:org:', '')
    elif urn_string.startswith('urn:local:program:'):
        # Extract program name, e.g. "urn:local:program:LEAP:Location" -> "LEAP"
        parts = urn_string.replace('urn:local:program:', '').split(':')
        return parts[0] if parts else ''
    return urn_string

def normalize_org_name(org_name: str) -> str:
    """Normalize organization name for lookup"""
    return org_name.lower().replace(' ', '_').replace('-', '_')

def rate_limit_search():
    """Apply rate limiting between searches"""
    global LAST_SEARCH_TIME
    current_time = time.time()
    time_since_last = current_time - LAST_SEARCH_TIME
    if time_since_last < SEARCH_DELAY:
        sleep_time = SEARCH_DELAY - time_since_last
        logger.debug(f"Rate limiting: sleeping {sleep_time:.2f} seconds")
        time.sleep(sleep_time)
    LAST_SEARCH_TIME = time.time()

def search_via_scraping(query: str) -> List[Tuple[str, str]]:
    """
    Search via web scraping (fallback method)
    
    Args:
        query: Search query
        
    Returns:
        List of (title, url) tuples
    """
    try:
        rate_limit_search()
        
        # Use a search that returns results we can parse
        search_url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(search_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        results = []
        
        # Simple regex to extract URLs from search results
        import re
        
        # Look for patterns like href="/l/?uddg=https://example.com..." 
        url_pattern = r'href="/l/\?uddg=([^"&]+)'
        urls = re.findall(url_pattern, response.text)
        
        # Also look for direct links
        direct_pattern = r'href="(https?://[^"]+)"'
        direct_urls = re.findall(direct_pattern, response.text)
        
        all_urls = list(set(urls + direct_urls))  # Remove duplicates
        
        for url in all_urls[:5]:  # Limit to first 5
            try:
                # Decode URL if needed
                from urllib.parse import unquote
                decoded_url = unquote(url)
                
                # Skip unwanted domains
                if any(skip in decoded_url.lower() for skip in ['duckduckgo.com', 'javascript:', 'mailto:']):
                    continue
                    
                # Extract a simple title (domain name)
                domain = urlparse(decoded_url).netloc
                title = f"Search result from {domain}"
                
                results.append((title, decoded_url))
                
            except Exception as e:
                logger.debug(f"Error processing URL {url}: {e}")
                continue
        
        logger.info(f"Scraping search for '{query}' returned {len(results)} results")
        return results
        
    except Exception as e:
        logger.error(f"Scraping search failed for '{query}': {e}")
        return []

def search_duckduckgo(query: str) -> List[Tuple[str, str]]:
    """
    Search DuckDuckGo for organization URLs
    
    Args:
        query: Search query
        
    Returns:
        List of (title, url) tuples
    """
    try:
        rate_limit_search()
        
        # DuckDuckGo Instant Answer API (free, no API key required)
        search_url = f"https://api.duckduckgo.com/?q={quote(query)}&format=json&no_html=1&skip_disambig=1"
        
        headers = {
            'User-Agent': 'LinkedClaims-URLResolver/1.0 (https://extract.linkedtrust.us)'
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        results = []
        
        # Debug: log the response structure
        logger.debug(f"DuckDuckGo API response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        
        if not isinstance(data, dict):
            logger.warning(f"DuckDuckGo returned non-dict response for '{query}': {type(data)}")
            return []
        
        # Check for instant answer with URL
        if data.get('AbstractURL'):
            results.append((data.get('AbstractText', 'Official site'), data['AbstractURL']))
        
        # Check for related topics with URLs
        for topic in data.get('RelatedTopics', []):
            if isinstance(topic, dict) and topic.get('FirstURL'):
                results.append((topic.get('Text', 'Related'), topic['FirstURL']))
        
        # Check for infobox - it can be a string or dict
        infobox = data.get('Infobox')
        if infobox and isinstance(infobox, dict) and infobox.get('content'):
            for item in infobox['content']:
                if isinstance(item, dict) and item.get('data_type') == 'string' and 'http' in str(item.get('value', '')):
                    # Extract URL from text
                    url_match = re.search(r'https?://[^\s<>"]+', item['value'])
                    if url_match:
                        results.append((item.get('label', 'Website'), url_match.group()))
        
        logger.info(f"DuckDuckGo search for '{query}' returned {len(results)} results")
        return results[:5]  # Limit to top 5 results
        
    except Exception as e:
        logger.error(f"DuckDuckGo search failed for '{query}': {e}")
        return []

def expand_organization_name(org_name: str, context: str = "") -> List[str]:
    """
    Expand organization name with additional context and variations
    
    Args:
        org_name: Base organization name
        context: Document context that might contain full name
        
    Returns:
        List of expanded search terms
    """
    base_name = org_name.replace('_', ' ').replace('-', ' ').strip()
    expanded_names = [base_name]
    
    # Known organization expansions
    expansions = {
        'global fund': [
            'Global Fund to Fight AIDS Tuberculosis and Malaria',
            'Global Fund to Fight AIDS',
            'The Global Fund'
        ],
        'gavi': [
            'GAVI the Vaccine Alliance',
            'GAVI Alliance',
            'Gavi Vaccine Alliance'
        ],
        'amurt': [
            'AMURT Ananda Marga Universal Relief Team',
            'Ananda Marga Universal Relief Team'
        ],
        'leap': [
            'LEAP Livelihood Enhancement Action Plan',
            'Livelihood Enhancement Action Plan'
        ],
        'moremilk': [
            'MoreMilk dairy program',
            'MoreMilk Kenya',
            'MoreMilk CGIAR'
        ],
        'who': [
            'World Health Organization',
            'WHO World Health Organization'
        ],
        'unicef': [
            'UNICEF United Nations Children Fund',
            'United Nations Children Fund'
        ]
    }
    
    # Check if we have known expansions
    org_lower = base_name.lower()
    for key, variations in expansions.items():
        if key in org_lower or org_lower in key:
            expanded_names.extend(variations)
    
    # Extract expanded name from context if available
    if context:
        context_lower = context.lower()
        
        # Look for patterns like "Gavi, the Vaccine Alliance" or "Global Fund to Fight AIDS, Tuberculosis, and Malaria"
        patterns = [
            rf"{re.escape(base_name.lower())}[,\s]+([^.!?]*?)(?:\.|!|\?|,\s+which|,\s+that|$)",
            rf"({re.escape(base_name.lower())}[^.!?]*?)(?:\.|!|\?|,\s+which|,\s+that|$)",
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, context_lower, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match[0] else match[1]
                
                # Clean up the match
                expanded = match.strip().strip(',').strip()
                if len(expanded) > len(base_name) and len(expanded) < 100:  # Reasonable length
                    # Capitalize properly
                    expanded_clean = ' '.join(word.capitalize() for word in expanded.split())
                    if expanded_clean not in expanded_names:
                        expanded_names.append(expanded_clean)
    
    return expanded_names

def search_organization_urls(org_name: str, context: str = "") -> List[Tuple[str, str, float]]:
    """
    Search for organization URLs using multiple web search strategies
    
    Args:
        org_name: Organization name to search for
        context: Document context to help expand organization names
        
    Returns:
        List of (title, url, confidence_score) tuples, sorted by confidence
    """
    try:
        logger.info(f"Searching for URLs for organization: {org_name}")
        
        # Get expanded organization names with context
        expanded_names = expand_organization_name(org_name, context)
        logger.info(f"Expanded search terms: {expanded_names}")
        
        # Prepare search queries using the best expanded names
        queries = []
        
        # Use top 2 expanded names to avoid too many searches
        for name in expanded_names[:2]:
            queries.extend([
                f"{name} official website",
                f"{name} organization"
            ])
        
        # Add some targeted queries for common organization types
        base_name = org_name.replace('_', ' ').replace('-', ' ').strip()
        if any(term in base_name.lower() for term in ['fund', 'foundation']):
            queries.append(f"{base_name} foundation")
        if any(term in base_name.lower() for term in ['program', 'initiative']):
            queries.append(f"{base_name} program")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_queries = []
        for query in queries:
            if query.lower() not in seen:
                seen.add(query.lower())
                unique_queries.append(query)
        
        queries = unique_queries[:4]  # Limit to 4 queries to avoid rate limits
        
        all_results = []
        
        for query in queries[:2]:  # Limit to 2 queries to avoid rate limits
            try:
                # Try DuckDuckGo API first
                search_results = search_duckduckgo(query)
                
                # If no results, try scraping fallback
                if not search_results:
                    logger.info(f"No API results for '{query}', trying scraping fallback...")
                    search_results = search_via_scraping(query)
                
                for title, url in search_results:
                    confidence = calculate_url_confidence(org_name, title, url)
                    if confidence >= 0.2:  # Include results with exactly 0.2 confidence
                        all_results.append((title, url, confidence))
            except Exception as e:
                logger.warning(f"Search query '{query}' failed: {e}")
                continue
        
        # Remove duplicates and sort by confidence
        seen_urls = set()
        unique_results = []
        for title, url, confidence in all_results:
            if url not in seen_urls:
                seen_urls.add(url)
                unique_results.append((title, url, confidence))
        
        # Sort by confidence (highest first)
        unique_results.sort(key=lambda x: x[2], reverse=True)
        
        logger.info(f"Found {len(unique_results)} candidate URLs for {org_name}")
        for title, url, conf in unique_results[:3]:
            logger.info(f"  {conf:.2f}: {url} ({title})")
        
        return unique_results[:5]  # Return top 5 candidates
        
    except Exception as e:
        logger.error(f"Error searching for organization URLs for {org_name}: {e}")
        return []

def calculate_url_confidence(org_name: str, title: str, url: str) -> float:
    """
    Calculate confidence score for a URL match
    
    Args:
        org_name: Original organization name
        title: Page title from search results
        url: URL from search results
        
    Returns:
        Confidence score between 0.0 and 1.0
    """
    try:
        confidence = 0.0
        org_lower = org_name.lower().replace('_', ' ').replace('-', ' ')
        title_lower = title.lower() if title else ''
        url_lower = url.lower()
        domain = urlparse(url).netloc.lower()
        
        # Split org name into parts for better matching
        org_parts = [part.strip() for part in org_lower.split() if len(part.strip()) > 2]
        
        # Check if any part of org name appears in URL domain
        domain_normalized = domain.replace('-', '').replace('.', '')
        for part in org_parts:
            part_normalized = part.replace(' ', '')
            if part_normalized in domain_normalized:
                confidence += 0.5  # Higher base score for domain match
                break
        
        # Check full org name in domain (fallback)
        org_normalized = org_lower.replace(' ', '').replace('_', '')
        if org_normalized in domain_normalized:
            confidence += 0.4
        
        # Check if org name or parts appear in title
        for part in org_parts:
            if part in title_lower:
                confidence += 0.3
                break
        
        # Check for URL path matching
        url_path = url_lower.replace(domain, '').replace('http://', '').replace('https://', '')
        for part in org_parts:
            if part.replace(' ', '') in url_path.replace('-', '').replace('_', ''):
                confidence += 0.2
                break
        
        # Boost confidence for official-looking domains
        if any(indicator in url_lower for indicator in ['.org', '.gov', 'official', 'www.']):
            confidence += 0.2
        
        # Boost confidence for foundation/NGO/alliance indicators  
        if any(indicator in title_lower for indicator in ['foundation', 'organization', 'ngo', 'official', 'alliance']):
            confidence += 0.1
        
        # Special handling for common organization patterns
        if 'vaccine' in org_lower and 'vaccine' in domain:
            confidence += 0.3
        if 'alliance' in org_lower and ('alliance' in domain or 'vaccine' in domain):
            confidence += 0.3
        
        # Penalize social media and generic platforms
        if any(platform in domain for platform in ['facebook.com', 'twitter.com', 'linkedin.com', 'youtube.com', 'wikipedia.org']):
            confidence *= 0.5
        
        # Penalize very generic domains
        if any(generic in domain for generic in ['blogspot', 'wordpress', 'medium.com', 'github.com']):
            confidence *= 0.7
        
        return min(confidence, 1.0)
        
    except Exception as e:
        logger.error(f"Error calculating confidence for {url}: {e}")
        return 0.0

def search_organization_url(org_name: str) -> Optional[str]:
    """
    Search for the best organization URL
    
    Args:
        org_name: Organization name to search for
        
    Returns:
        Best URL if found with sufficient confidence, None otherwise
    """
    try:
        candidates = search_organization_urls(org_name)
        
        if not candidates:
            logger.info(f"No URLs found via web search for organization: {org_name}")
            return None
        
        # Return the highest confidence result if it meets threshold
        best_title, best_url, best_confidence = candidates[0]
        
        if best_confidence >= 0.5:  # High confidence threshold
            logger.info(f"Found high-confidence URL for {org_name}: {best_url} (confidence: {best_confidence:.2f})")
            return best_url
        elif best_confidence >= 0.3:  # Medium confidence
            logger.info(f"Found medium-confidence URL for {org_name}: {best_url} (confidence: {best_confidence:.2f})")
            return best_url
        else:
            logger.info(f"No high-confidence URL found for {org_name} (best: {best_confidence:.2f})")
            return None
        
    except Exception as e:
        logger.error(f"Error searching for organization URL {org_name}: {e}")
        return None

def find_real_org_url(org_name: str) -> Optional[str]:
    """
    Search for real organization URL using multiple strategies (legacy function)
    
    Args:
        org_name: Organization name extracted from URN
        
    Returns:
        Real URL if found, None otherwise
    """
    url, candidates = find_real_org_url_with_candidates(org_name)
    return url

def validate_url(url: str) -> bool:
    """Validate that a URL is properly formatted and accessible"""
    try:
        parsed = urlparse(url)
        return bool(parsed.netloc) and parsed.scheme in ['http', 'https']
    except Exception:
        return False

def find_real_org_url_with_candidates(org_name: str, save_for_verification: bool = True, context: str = "") -> Tuple[Optional[str], List[Tuple[str, str, float]]]:
    """
    Search for real organization URL and return best match plus candidates
    
    Args:
        org_name: Organization name extracted from URN
        save_for_verification: Whether to save candidates for user verification
        
    Returns:
        Tuple of (best_url, candidates_list) where candidates is list of (title, url, confidence)
    """
    from url_verification import url_verification_manager
    
    cache_key = normalize_org_name(org_name)
    
    # FIRST: Check database for verified organization URLs
    try:
        from models import VerifiedOrganization
        verified_url = VerifiedOrganization.get_verified_url(org_name)
        if verified_url:
            logger.info(f"Found verified URL in database for {org_name}: {verified_url}")
            return verified_url, [("Database verified", verified_url, 1.0)]
    except Exception as db_error:
        logger.warning(f"Could not check database for verified URL: {db_error}")
    
    # SECOND: Check verification manager for pending verifications
    verified_url = url_verification_manager.get_verified_url(cache_key)
    if verified_url:
        logger.info(f"Found verified URL for {org_name}: {verified_url}")
        return verified_url, [("User verified", verified_url, 1.0)]
    
    # Check legacy cache
    if cache_key in URL_CACHE:
        cached_result = URL_CACHE[cache_key]
        if isinstance(cached_result, str):
            # Legacy cache entry
            logger.info(f"Found cached URL for {org_name}: {cached_result}")
            return cached_result, [("Cached result", cached_result, 1.0)]
        else:
            # New cache format with candidates
            best_url, candidates = cached_result
            logger.info(f"Found cached URL for {org_name}: {best_url}")
            return best_url, candidates
    
    # Check known organizations (high confidence pre-verified)
    if cache_key in KNOWN_ORGS:
        url = KNOWN_ORGS[cache_key]
        candidates = [("Known organization", url, 1.0)]
        URL_CACHE[cache_key] = (url, candidates)
        logger.info(f"Found known URL for {org_name}: {url}")
        return url, candidates
    
    # Try web search with context
    candidates = search_organization_urls(org_name, context)
    best_url = None
    
    if candidates:
        # Save candidates for user verification if enabled
        if save_for_verification and len(candidates) > 0:
            url_candidates = url_verification_manager.add_url_candidates(cache_key, candidates)
            logger.info(f"Saved {len(url_candidates)} URL candidates for verification: {org_name}")
        
        # For user approval workflow, always save candidates for verification
        # Only use very high confidence URLs (0.95+) automatically for known organizations
        best_title, best_url, best_confidence = candidates[0]
        
        # Check if this is a known high-confidence organization pattern
        is_known_pattern = any(known in org_name.lower() for known in ['gavi', 'who', 'unicef', 'world_bank'])
        
        if best_confidence >= 0.95 and is_known_pattern:
            # Only auto-use for very well-known organizations with perfect matches
            URL_CACHE[cache_key] = (best_url, candidates)
            logger.info(f"Auto-using URL for known organization {org_name}: {best_url} (confidence: {best_confidence:.2f})")
        elif best_confidence >= 0.3:
            # All other URLs need user verification, including high confidence ones
            logger.info(f"URL found for {org_name}: {best_url} (confidence: {best_confidence:.2f}) - needs user verification")
            best_url = None  # Don't use automatically, require user verification
        else:
            best_url = None
            logger.info(f"No confident URL found for {org_name} (best confidence: {best_confidence:.2f})")
    else:
        logger.info(f"No URL candidates found for organization: {org_name}")
    
    # Cache the result even if no URL found (to avoid repeated searches)
    URL_CACHE[cache_key] = (best_url, candidates)
    
    return best_url, candidates

def resolve_claim_urls(claim_data: Dict, context: str = "", document_url: str = "") -> Dict:
    """
    Resolve URN schemes to real URLs in claim data
    
    Args:
        claim_data: Dictionary containing claim information
        context: Document context for better organization name expansion
        document_url: Document source URL to use as fallback for objects
        
    Returns:
        Updated claim data with real URLs where found, plus URL metadata
    """
    try:
        from url_verification import url_verification_manager
        
        # Process subject field (organizations)
        subject = claim_data.get('subject', '')
        if subject.startswith('urn:local:org:') or subject.startswith('urn:local:program:'):
            org_name = extract_org_name_from_urn(subject)
            real_url, candidates = find_real_org_url_with_candidates(org_name, context=context)
            
            if real_url and validate_url(real_url):
                claim_data['subject'] = real_url
                claim_data['subject_url_confidence'] = candidates[0][2] if candidates else 0.0
                claim_data['subject_url_verified'] = True
                logger.info(f"Resolved subject URN to real URL: {org_name} -> {real_url}")
            else:
                # Keep original URN but add verification candidates
                claim_data['urls_need_verification'] = True
                claim_data['subject_url_verified'] = False
                claim_data['subject_suggested'] = True  # Flag that URL suggestions are available
                
                # Always include URL candidates for verification (both from verification manager and current search)
                url_candidates_for_api = []
                
                # Get candidates from verification manager
                verification_candidates = url_verification_manager.get_pending_verifications(limit=10)
                org_candidates = next((org for org in verification_candidates if org['organization'] == normalize_org_name(org_name)), None)
                
                if org_candidates:
                    url_candidates_for_api.extend(org_candidates['candidates'])
                    claim_data['subject_organization_display'] = org_candidates['display_name']
                
                # Also include current search candidates (in case verification manager doesn't have them yet)
                for title, url, confidence in candidates[:5]:  # Include top 5 candidates
                    # Check if this URL is already in the verification candidates
                    existing_urls = [c.get('url') for c in url_candidates_for_api]
                    if url not in existing_urls:
                        url_candidates_for_api.append({
                            'url': url,
                            'title': title, 
                            'confidence': confidence,
                            'status': 'unverified',
                            'candidate_id': f'search_{hash(url)}'  # Temporary ID for search results
                        })
                
                claim_data['subject_url_candidates'] = url_candidates_for_api
                logger.info(f"No verified URL found for subject organization: {org_name} - {len(url_candidates_for_api)} candidates available for verification")
        
        # Process object field
        obj = claim_data.get('object', '')
        if obj.startswith('urn:local:org:') or obj.startswith('urn:local:program:'):
            # Object is an organization - try to resolve URL
            org_name = extract_org_name_from_urn(obj)
            real_url, candidates = find_real_org_url_with_candidates(org_name, context=context)
            
            if real_url and validate_url(real_url):
                claim_data['object'] = real_url
                claim_data['object_url_confidence'] = candidates[0][2] if candidates else 0.0
                claim_data['object_url_verified'] = True
                logger.info(f"Resolved object URN to real URL: {org_name} -> {real_url}")
            else:
                claim_data['urls_need_verification'] = True
                claim_data['object_url_verified'] = False
                
                # Get URL candidates for verification
                verification_candidates = url_verification_manager.get_pending_verifications(limit=10)
                org_candidates = next((org for org in verification_candidates if org['organization'] == normalize_org_name(org_name)), None)
                
                if org_candidates:
                    claim_data['object_url_candidates'] = org_candidates['candidates']
                    claim_data['object_organization_display'] = org_candidates['display_name']
                else:
                    claim_data['object_url_candidates'] = [{'title': t, 'url': u, 'confidence': c} for t, u, c in candidates[:3]]
        
        elif obj.startswith('urn:local:person:') or obj.startswith('urn:local:population:'):
            # Object is a person or population - use document source as URL if available
            if document_url and validate_url(document_url):
                claim_data['object'] = document_url
                claim_data['object_url_source'] = 'document'
                logger.info(f"Using document URL for object: {obj} -> {document_url}")
            else:
                logger.info(f"No document URL available for object: {obj}")
                # Keep original URN if no document URL available
        
        return claim_data
        
    except Exception as e:
        logger.error(f"Error resolving URLs in claim data: {e}")
        return claim_data

def add_known_organization(name: str, url: str):
    """Add a known organization to the lookup table"""
    key = normalize_org_name(name)
    KNOWN_ORGS[key] = url
    URL_CACHE[key] = url
    logger.info(f"Added known organization: {name} -> {url}")

def resolve_organization_urls(claims_list: List[Dict], context: str = "", document_url: str = "") -> List[Dict]:
    """
    Resolve organization URNs to real URLs for a list of claims
    
    Args:
        claims_list: List of claim dictionaries
        
    Returns:
        Updated claims list with real URLs where found
    """
    if not claims_list:
        return claims_list
    
    resolved_count = 0
    for i, claim_data in enumerate(claims_list):
        original_claim = claim_data.copy()
        resolved_claim = resolve_claim_urls(claim_data, context, document_url)
        
        # Check if any URLs were resolved
        if (resolved_claim.get('subject') != original_claim.get('subject') or 
            resolved_claim.get('object') != original_claim.get('object')):
            resolved_count += 1
        
        claims_list[i] = resolved_claim
    
    logger.info(f"URL resolution: {resolved_count}/{len(claims_list)} claims had URLs resolved")
    return claims_list

def get_resolution_stats():
    """Get statistics about URL resolution"""
    successful_resolutions = 0
    for cache_value in URL_CACHE.values():
        if isinstance(cache_value, tuple):
            url, candidates = cache_value
            if url:
                successful_resolutions += 1
        elif cache_value:  # Legacy string format
            successful_resolutions += 1
    
    return {
        'known_orgs': len(KNOWN_ORGS),
        'cached_searches': len(URL_CACHE),
        'successful_resolutions': successful_resolutions,
        'success_rate': successful_resolutions / max(len(URL_CACHE), 1),
        'cache_hit_ratio': len([k for k in URL_CACHE if k in KNOWN_ORGS]) / max(len(URL_CACHE), 1)
    }