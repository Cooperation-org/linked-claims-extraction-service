"""
Common extraction logic shared between Celery tasks and synchronous processing
"""
import os
import logging
import re
import fitz  # PyMuPDF
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

logger = logging.getLogger(__name__)


def verify_api_key() -> str:
    """
    Verify that the ANTHROPIC_API_KEY is configured
    
    Returns:
        The API key
        
    Raises:
        ValueError: If API key is not configured
    """
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        logger.error("ANTHROPIC_API_KEY environment variable not set!")
        raise ValueError("ANTHROPIC_API_KEY not configured")
    logger.info("ANTHROPIC_API_KEY is configured")
    return api_key


def extract_pdf_text_batches(file_path: str, batch_size: int = 5) -> Tuple[int, List[List[Tuple[int, str]]]]:
    """
    Extract text from PDF in batches
    
    Args:
        file_path: Path to the PDF file
        batch_size: Number of pages to process at once
        
    Returns:
        Tuple of (total_pages, list of batches where each batch is list of (page_num, text) tuples)
    """
    with fitz.open(file_path) as pdf:
        total_pages = len(pdf)
    
    all_batches = []
    
    for start_page in range(0, total_pages, batch_size):
        end_page = min(start_page + batch_size, total_pages)
        logger.info(f"Processing pages {start_page + 1} to {end_page} of {total_pages}")
        
        # Extract text from batch of pages
        batch_texts = []
        with fitz.open(file_path) as pdf:
            for page_num in range(start_page, end_page):
                page = pdf.load_page(page_num)
                page_text = page.get_text()
                # Clean up the text
                cleaned_text = re.sub(r'\s+', ' ', page_text).strip()
                if cleaned_text:  # Only process pages with text
                    batch_texts.append((page_num + 1, cleaned_text))
        
        all_batches.append(batch_texts)
    
    return total_pages, all_batches


def extract_claims_from_page(
    extractor: Any,
    page_num: int,
    text: str,
    min_text_length: int = 50
) -> List[Dict[str, Any]]:
    """
    Extract claims from a single page of text
    
    Args:
        extractor: ClaimExtractor instance
        page_num: Page number
        text: Page text
        min_text_length: Minimum text length to process
        
    Returns:
        List of extracted claims
    """
    if not text or len(text) < min_text_length:
        logger.info(f"Skipping page {page_num} - too short ({len(text)} chars)")
        return []
    
    try:
        # Log what we're sending to the API
        logger.info(f"Extracting claims from page {page_num} with {len(text)} characters")
        logger.debug(f"Page {page_num} text preview: {text[:200]}...")
        
        # Extract claims from page text
        try:
            page_claims = extractor.extract_claims(text)
        except Exception as api_error:
            logger.error(f"API call failed for page {page_num}: {api_error}")
            logger.error(f"Error type: {type(api_error).__name__}")
            logger.error(f"Error details: {str(api_error)}")
            # Check if it's an authentication error
            if "401" in str(api_error) or "authentication" in str(api_error).lower() or "api-key" in str(api_error).lower():
                raise ValueError(f"API Authentication failed - check your ANTHROPIC_API_KEY: {api_error}")
            page_claims = []
        
        # Log the API response
        logger.info(f"Page {page_num} returned {len(page_claims) if page_claims else 0} claims")
        if page_claims:
            logger.debug(f"Claims from page {page_num}: {page_claims}")
        else:
            logger.warning(f"No claims extracted from page {page_num}")
        
        return page_claims
        
    except Exception as e:
        logger.error(f"Error extracting claims from page {page_num}: {e}")
        if "API Authentication failed" in str(e):
            raise
        return []


def process_claim_data(
    claim_data: Dict[str, Any],
    text: str,
    document_id: str,
    public_url: str,
    page_num: int
) -> Dict[str, Any]:
    """
    Process a single claim data, improving URLs and creating the draft claim structure
    
    Args:
        claim_data: Raw claim data from extractor
        text: Page text for context
        document_id: Document ID
        public_url: Document's public URL
        page_num: Page number
        
    Returns:
        Processed claim data ready for database insertion
    """
    # Import URL generation utility
    from url_generator import improve_claim_urls
    
    # Improve URLs using our enhanced logic
    improved_claim = improve_claim_urls(claim_data, text)
    
    # Extract subject, statement, object from improved claim data
    subject = improved_claim.get('subject', '')
    statement = improved_claim.get('statement', '') or improved_claim.get('claim', '')
    obj = improved_claim.get('object', '')
    
    # Fallback to document-based URIs if still not URLs
    if subject and not subject.startswith(('http://', 'https://')):
        subject = f"{public_url}#subject-{subject[:50]}"
    
    if obj and not obj.startswith(('http://', 'https://')):
        obj = f"{public_url}#object-{obj[:50]}"
    
    return {
        'document_id': document_id,
        'subject': subject,
        'statement': statement,
        'object': obj,
        'claim_data': {
            'claim': claim_data.get('claim'),  # The predicate (e.g., 'impact', 'rated', 'same_as')
            'howKnown': claim_data.get('howKnown', 'DOCUMENT'),
            'confidence': claim_data.get('confidence'),
            'aspect': claim_data.get('aspect'),
            'score': claim_data.get('score'),
            'stars': claim_data.get('stars'),
            'amt': claim_data.get('amt'),
            'unit': claim_data.get('unit'),
            'howMeasured': claim_data.get('howMeasured'),
            'subject_entity_type': improved_claim.get('subject_entity_type'),
            'object_entity_type': improved_claim.get('object_entity_type'),
            'subject_suggested': improved_claim.get('subject_suggested'),
            'object_suggested': improved_claim.get('object_suggested'),
            'urls_need_verification': improved_claim.get('urls_need_verification', False)
        },
        'page_number': page_num,
        'page_text_snippet': text[:500] if len(text) > 500 else text,
        'status': 'draft'
    }


def prepare_linkedtrust_claim_payload(
    claim: Any,
    doc: Any
) -> Dict[str, Any]:
    """
    Prepare claim data for LinkedTrust API
    
    Args:
        claim: DraftClaim object
        doc: Document object
        
    Returns:
        Dictionary ready for LinkedTrust API
    """
    claim_payload = {
        'subject': claim.subject,
        'statement': claim.statement,
        'object': claim.object,
        'sourceURI': doc.public_url,
        'effectiveDate': doc.effective_date.isoformat(),
        'howKnown': claim.claim_data.get('howKnown', 'DOCUMENT'),
        'issuerId': 'https://extract.linkedtrust.us',
        'issuerIdType': 'URL'
    }
    
    # Add optional fields from claim_data
    if claim.claim_data:
        for key in ['confidence', 'aspect', 'score', 'stars', 'amt', 'unit', 'howMeasured']:
            if key in claim.claim_data and claim.claim_data[key] is not None:
                claim_payload[key] = claim.claim_data[key]
    
    return claim_payload