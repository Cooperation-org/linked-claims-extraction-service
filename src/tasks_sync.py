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
    from models import db, Document, DraftClaim
    from claim_extractor_fixed import ClaimExtractor
    
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
        
        # Initialize extractor
        extractor = ClaimExtractor()
        logger.info("ClaimExtractor initialized successfully")
        
        # Extract FULL DOCUMENT TEXT for complete story context
        logger.info("Extracting full document text to preserve complete stories")
        full_document_text = ""
        
        with fitz.open(doc.file_path) as pdf:
            total_pages = len(pdf)
            for page_num in range(total_pages):
                page = pdf.load_page(page_num)
                page_text = page.get_text()
                # Clean up the text
                cleaned_text = re.sub(r'\s+', ' ', page_text).strip()
                if cleaned_text:  # Only include pages with text
                    full_document_text += cleaned_text + "\n\n"
        
        if not full_document_text or len(full_document_text) < 100:
            logger.warning("No substantial text found in document")
            doc.status = 'completed'
            doc.processing_completed_at = datetime.utcnow()
            db.session.commit()
            return {'document_id': document_id, 'total_pages': total_pages, 'total_claims': 0, 'status': 'completed'}
        
        logger.info(f"Processing complete document with {len(full_document_text)} characters")
        total_claims_extracted = 0
        
        try:
            # Extract claims from FULL DOCUMENT TEXT
            logger.info(f"Extracting claims from full document with {len(full_document_text)} characters")
            
            try:
                document_claims = extractor.extract_claims(full_document_text)
            except Exception as api_error:
                logger.error(f"API call failed for document: {api_error}")
                # Check if it's an authentication error
                if "401" in str(api_error) or "authentication" in str(api_error).lower() or "api-key" in str(api_error).lower():
                    raise ValueError(f"API Authentication failed - check your ANTHROPIC_API_KEY: {api_error}")
                document_claims = []
            
            logger.info(f"Full document returned {len(document_claims) if document_claims else 0} claims")
            
            if not document_claims:
                doc.status = 'completed'
                doc.processing_completed_at = datetime.utcnow()
                db.session.commit()
                return {'document_id': document_id, 'total_pages': total_pages, 'total_claims': 0, 'status': 'completed'}
            
            # POST-PROCESSING: Resolve URN schemes to real URLs with document context
            from url_resolver import resolve_organization_urls
            
            document_claims = resolve_organization_urls(document_claims, context=full_document_text, document_url=doc.public_url)
            logger.info(f"URL resolution completed for {len(document_claims)} claims")
                
            for claim_data in document_claims:
                # URL resolver already handled URN conversion to real URLs
                # Only use URL generator for non-URN strings that need enhancement
                improved_claim = claim_data  # URL resolver already did the work
                
                # Extract subject, statement, object from improved claim data
                subject = improved_claim.get('subject', '')
                statement = improved_claim.get('statement', '') or improved_claim.get('claim', '')
                obj = improved_claim.get('object', '')
                
                # URL resolver should have already converted URNs to real URLs
                # Only fallback to document URIs if something went wrong
                if subject and not subject.startswith(('urn:', 'http://', 'https://')):
                    subject = f"{doc.public_url}#subject-{subject[:50]}"
                
                if obj and not obj.startswith(('urn:', 'http://', 'https://')):
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
                        'testimonial_source': claim_data.get('testimonial_source'),  # For organizational impact approach
                        'subject_entity_type': improved_claim.get('subject_entity_type'),
                        'object_entity_type': improved_claim.get('object_entity_type'),
                        'subject_suggested': improved_claim.get('subject_suggested'),
                        'object_suggested': improved_claim.get('object_suggested'),
                        'urls_need_verification': improved_claim.get('urls_need_verification', False),
                        'subject_url_candidates': improved_claim.get('subject_url_candidates', []),
                        'object_url_candidates': improved_claim.get('object_url_candidates', [])
                    },
                    page_number=1,  # Full document processing - use page 1 as reference
                    page_text_snippet=full_document_text[:500] if len(full_document_text) > 500 else full_document_text,
                    status='draft'
                )
                db.session.add(draft_claim)
                total_claims_extracted += 1
                
        except Exception as e:
            logger.error(f"Error extracting claims from document: {e}")
            doc.status = 'failed'
            doc.error_message = str(e)
            db.session.commit()
            raise
        
        # Commit all claims
        db.session.commit()
        logger.info(f"Extracted {total_claims_extracted} claims from full document")
        
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