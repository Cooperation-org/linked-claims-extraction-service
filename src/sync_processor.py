"""
Synchronous claim processor for local development (no Celery required)
"""
import os
import logging
from datetime import datetime
import fitz  # PyMuPDF
import re
from claim_extractor import ClaimExtractor

logger = logging.getLogger(__name__)


class SyncClaimProcessor:
    """Process claims synchronously without Celery"""
    
    def __init__(self, db=None):
        self.db = db
        self.extractor = ClaimExtractor()
        
    def extract_claims_from_document(self, document_id: str, batch_size: int = 5):
        """
        Extract claims from a PDF document synchronously
        
        Args:
            document_id: UUID of the document
            batch_size: Number of pages to process at once
        """
        logger.info(f"Starting sync extraction for document {document_id}")
        
        if self.db:
            from models import Document, DraftClaim
            
            # Get document
            doc = Document.query.get(document_id)
            if not doc:
                raise ValueError(f"Document {document_id} not found")
            
            # Update status
            doc.status = 'processing'
            doc.processing_started_at = datetime.utcnow()
            self.db.session.commit()
            
            file_path = doc.file_path
            public_url = doc.public_url
        else:
            # For testing without database
            file_path = document_id  # Assume document_id is the path
            public_url = f"https://example.com/doc/{document_id}"
        
        total_claims_extracted = 0
        
        try:
            # Get total page count
            with fitz.open(file_path) as pdf:
                total_pages = len(pdf)
            
            # Process pages in batches
            for start_page in range(0, total_pages, batch_size):
                end_page = min(start_page + batch_size, total_pages)
                logger.info(f"Processing pages {start_page + 1} to {end_page}")
                
                # Extract text from batch
                batch_texts = []
                with fitz.open(file_path) as pdf:
                    for page_num in range(start_page, end_page):
                        page = pdf.load_page(page_num)
                        page_text = page.get_text()
                        cleaned_text = re.sub(r'\s+', ' ', page_text).strip()
                        if cleaned_text and len(cleaned_text) >= 50:
                            batch_texts.append((page_num + 1, cleaned_text))
                
                # Extract claims from each page
                for page_num, text in batch_texts:
                    try:
                        logger.info(f"Extracting from page {page_num}")
                        page_claims = self.extractor.extract_claims(text)
                        
                        if not page_claims:
                            continue
                        
                        for claim_data in page_claims:
                            # Store or process claim
                            if self.db:
                                self._store_claim(document_id, claim_data, page_num, text[:500])
                            else:
                                # Just count for testing
                                total_claims_extracted += 1
                                logger.info(f"Claim: {claim_data.get('subject')} - {claim_data.get('claim')} - {claim_data.get('object')}")
                    
                    except Exception as e:
                        logger.error(f"Error extracting from page {page_num}: {e}")
                        continue
                
                if self.db:
                    self.db.session.commit()
            
            # Update document status
            if self.db:
                doc.status = 'completed'
                doc.processing_completed_at = datetime.utcnow()
                self.db.session.commit()
            
            logger.info(f"Completed: {total_claims_extracted} claims from {total_pages} pages")
            return {
                'document_id': document_id,
                'total_pages': total_pages,
                'total_claims': total_claims_extracted,
                'status': 'completed'
            }
            
        except Exception as e:
            logger.error(f"Error processing document: {e}")
            if self.db:
                doc.status = 'failed'
                doc.error_message = str(e)
                self.db.session.commit()
            raise
    
    def _store_claim(self, document_id, claim_data, page_num, text_snippet):
        """Store claim in database"""
        from models import DraftClaim
        
        draft_claim = DraftClaim(
            document_id=document_id,
            subject=claim_data.get('subject', ''),
            statement=claim_data.get('claim', '') or claim_data.get('statement', ''),
            object=claim_data.get('object', ''),
            claim_data={
                'howKnown': claim_data.get('howKnown', 'DOCUMENT'),
                'confidence': claim_data.get('confidence'),
                'aspect': claim_data.get('aspect'),
                'score': claim_data.get('score'),
                'stars': claim_data.get('stars'),
                'amt': claim_data.get('amt'),
                'unit': claim_data.get('unit'),
                'howMeasured': claim_data.get('howMeasured')
            },
            page_number=page_num,
            page_text_snippet=text_snippet,
            status='draft'
        )
        self.db.session.add(draft_claim)