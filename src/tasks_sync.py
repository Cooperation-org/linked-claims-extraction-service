"""
Synchronous versions of tasks for local development without Celery
"""
import logging
from datetime import datetime
from dotenv import load_dotenv
from extraction_common import (
    verify_api_key,
    extract_pdf_text_batches,
    extract_claims_from_page,
    process_claim_data
)

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
        # Verify API key
        verify_api_key()
        
        # Initialize extractor
        extractor = ClaimExtractor()
        logger.info("ClaimExtractor initialized successfully")
        
        # Extract text from PDF in batches
        total_pages, all_batches = extract_pdf_text_batches(doc.file_path, batch_size)
        
        # Process pages in batches
        total_claims_extracted = 0
        
        for batch_texts in all_batches:
            # Extract claims from each page
            for page_num, text in batch_texts:
                # Extract claims from page
                page_claims = extract_claims_from_page(extractor, page_num, text)
                
                if not page_claims:
                    continue
                
                # Process each claim
                for claim_data in page_claims:
                    processed_claim = process_claim_data(
                        claim_data, text, document_id, doc.public_url, page_num
                    )
                    
                    # Create draft claim
                    draft_claim = DraftClaim(**processed_claim)
                    db.session.add(draft_claim)
                    total_claims_extracted += 1
            
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