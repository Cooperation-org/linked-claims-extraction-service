"""
Synchronous versions of tasks for local development without Celery
"""
import os
import logging
import re
import fitz  # PyMuPDF
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

def extract_claims_from_document_sync(document_id: str, batch_size: int = 5):
    """
    Synchronous version of claim extraction for local development
    
    Args:
        document_id: UUID of the document
        batch_size: Number of pages to process at once
    """
    logger.info(f"Starting synchronous claim extraction for document {document_id}")
    
    # Just use the existing database connection - we're already in the app context
    from flask import current_app
    from models import db, Document, DraftClaim
    from claim_extractor import ClaimExtractor
    
    # Get document
    doc = Document.query.get(document_id)
    if not doc:
        raise ValueError(f"Document {document_id} not found")
    
    # Update document status
    doc.status = 'processing'
    doc.processing_started_at = datetime.utcnow()
    db.session.commit()
    
    try:
        # Check if API key is available
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            logger.error("ANTHROPIC_API_KEY environment variable not set!")
            raise ValueError("ANTHROPIC_API_KEY not configured")
        
        # Initialize extractor with prompt configuration
        extractor = ClaimExtractor(
            message_prompt=current_app.config.get('LT_MESSAGE_PROMPT'),
            extra_system_instructions=current_app.config.get('LT_EXTRA_SYSTEM_PROMPT', '')
        )
        logger.info("ClaimExtractor initialized with prompt configuration")
        
        # Get total page count
        with fitz.open(doc.file_path) as pdf:
            total_pages = len(pdf)
        
        # Process pages in batches
        total_claims_extracted = 0
        
        for start_page in range(0, total_pages, batch_size):
            end_page = min(start_page + batch_size, total_pages)
            logger.info(f"Processing pages {start_page + 1} to {end_page} of {total_pages}")
            
            # Extract text from batch of pages
            batch_texts = []
            with fitz.open(doc.file_path) as pdf:
                for page_num in range(start_page, end_page):
                    page = pdf.load_page(page_num)
                    page_text = page.get_text()
                    # Clean up the text
                    cleaned_text = re.sub(r'\s+', ' ', page_text).strip()
                    if cleaned_text:  # Only process pages with text
                        batch_texts.append((page_num + 1, cleaned_text))
            
            # Extract claims from each page
            for page_num, text in batch_texts:
                if not text or len(text) < 50:  # Skip empty or very short pages
                    logger.info(f"Skipping page {page_num} - too short ({len(text)} chars)")
                    continue
                
                try:
                    logger.info(f"Extracting claims from page {page_num} with {len(text)} characters")
                    
                    # Extract claims from page text
                    try:
                        page_claims = extractor.extract_claims(text)
                    except Exception as api_error:
                        logger.error(f"API call failed for page {page_num}: {api_error}")
                        # Check if it's an authentication error
                        if "401" in str(api_error) or "authentication" in str(api_error).lower() or "api-key" in str(api_error).lower():
                            raise ValueError(f"API Authentication failed - check your ANTHROPIC_API_KEY: {api_error}")
                        page_claims = []
                    
                    logger.info(f"Page {page_num} returned {len(page_claims) if page_claims else 0} claims")
                    
                    if not page_claims:
                        continue
                        
                    for claim_data in page_claims:
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
                            subject = f"{doc.public_url}#subject-{subject[:50]}"
                        
                        if obj and not obj.startswith(('http://', 'https://')):
                            obj = f"{doc.public_url}#object-{obj[:50]}"
                        
                        # Create draft claim
                        draft_claim = DraftClaim(
                            document_id=document_id,
                            subject=subject,
                            statement=statement,
                            object=obj,
                            claim_data={
                                'claim': claim_data.get('claim'),
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
                            page_number=page_num,
                            page_text_snippet=text[:500] if len(text) > 500 else text,
                            status='draft'
                        )
                        db.session.add(draft_claim)
                        total_claims_extracted += 1
                        
                except Exception as e:
                    logger.error(f"Error extracting claims from page {page_num}: {e}")
                    continue
            
            # Commit batch
            db.session.commit()
            logger.info(f"Extracted {total_claims_extracted} claims so far")
        
        # Update document status
        doc.status = 'completed'
        doc.processing_completed_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Completed extraction: {total_claims_extracted} claims from {total_pages} pages")
        return {
            'document_id': document_id,
            'total_pages': total_pages,
            'total_claims': total_claims_extracted,
            'status': 'completed'
        }
        
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}")
        doc.status = 'failed'
        doc.error_message = str(e)
        db.session.commit()
        raise