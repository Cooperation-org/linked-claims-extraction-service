"""
Celery background tasks for PDF processing and claim extraction
"""
import os
import logging
from datetime import datetime
from celery import Task
from celery_app import celery_app
from models import db, Document, DraftClaim, ProcessingJob
from pdf_parser import SimpleDocumentManager
from claim_extractor import ClaimExtractor
import fitz  # PyMuPDF
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class CallbackTask(Task):
    """Base task with callbacks for status tracking"""
    
    def on_success(self, retval, task_id, args, kwargs):
        """Success handler"""
        job = ProcessingJob.query.get(task_id)
        if job:
            job.status = 'success'
            job.completed_at = datetime.utcnow()
            db.session.commit()
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Failure handler"""
        job = ProcessingJob.query.get(task_id)
        if job:
            job.status = 'failure'
            job.error_message = str(exc)
            job.completed_at = datetime.utcnow()
            db.session.commit()
        
        # Update document status
        document_id = kwargs.get('document_id') or args[0]
        doc = Document.query.get(document_id)
        if doc:
            doc.status = 'failed'
            doc.error_message = str(exc)
            db.session.commit()


@celery_app.task(base=CallbackTask, bind=True, name='tasks.extract_claims_from_document')
def extract_claims_from_document(self, document_id: str, batch_size: int = 5):
    """
    Extract claims from a PDF document in batches
    
    Args:
        document_id: UUID of the document
        batch_size: Number of pages to process at once
    """
    logger.info(f"Starting claim extraction for document {document_id}")
    
    # Get document
    doc = Document.query.get(document_id)
    if not doc:
        raise ValueError(f"Document {document_id} not found")
    
    # Create or update processing job
    job = ProcessingJob.query.get(self.request.id)
    if not job:
        job = ProcessingJob(
            id=self.request.id,
            document_id=document_id,
            job_type='extract_claims',
            status='started',
            started_at=datetime.utcnow()
        )
        db.session.add(job)
    else:
        job.status = 'started'
        job.started_at = datetime.utcnow()
    
    # Update document status
    doc.status = 'processing'
    doc.processing_started_at = datetime.utcnow()
    db.session.commit()
    
    try:
        # Initialize extractor
        extractor = ClaimExtractor()
        
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
                    continue
                
                try:
                    # Extract claims from page text
                    page_claims = extractor.extract_claims(text)
                    
                    for claim_data in page_claims:
                        # Extract subject, statement, object from claim data
                        subject = claim_data.get('subject', '')
                        statement = claim_data.get('claim', '') or claim_data.get('statement', '')
                        obj = claim_data.get('object', '')
                        
                        # Infer URIs if needed
                        if subject and not subject.startswith(('http://', 'https://')):
                            # If subject is not a URI, try to make it one
                            subject = f"{doc.public_url}#subject-{subject[:50]}"
                        
                        if obj and not obj.startswith(('http://', 'https://')):
                            # If object is not a URI, try to make it one
                            obj = f"{doc.public_url}#object-{obj[:50]}"
                        
                        # Create draft claim
                        draft_claim = DraftClaim(
                            document_id=document_id,
                            subject=subject,
                            statement=statement,
                            object=obj,
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


@celery_app.task(base=CallbackTask, bind=True, name='tasks.publish_claims_to_linkedtrust')
def publish_claims_to_linkedtrust(self, document_id: str, claim_ids: list = None):
    """
    Publish approved draft claims to LinkedTrust
    
    Args:
        document_id: UUID of the document
        claim_ids: Optional list of specific claim IDs to publish (if None, publishes all approved)
    """
    logger.info(f"Starting claim publishing for document {document_id}")
    
    # Get document
    doc = Document.query.get(document_id)
    if not doc:
        raise ValueError(f"Document {document_id} not found")
    
    # Create processing job
    job = ProcessingJob(
        id=self.request.id,
        document_id=document_id,
        job_type='publish_claims',
        status='started',
        started_at=datetime.utcnow()
    )
    db.session.add(job)
    db.session.commit()
    
    try:
        # Get claims to publish
        query = DraftClaim.query.filter_by(document_id=document_id, status='approved')
        if claim_ids:
            query = query.filter(DraftClaim.id.in_(claim_ids))
        
        claims_to_publish = query.all()
        
        if not claims_to_publish:
            logger.info("No approved claims to publish")
            return {'published': 0, 'status': 'completed'}
        
        # Initialize LinkedTrust client
        from linkedtrust_client import LinkedTrustClient
        client = LinkedTrustClient()
        
        published_count = 0
        failed_count = 0
        
        for claim in claims_to_publish:
            try:
                # Prepare claim data for LinkedTrust
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
                
                # Add optional fields if present
                if claim.claim_data:
                    for field in ['confidence', 'aspect', 'score', 'stars', 'amt', 'unit', 'howMeasured']:
                        if field in claim.claim_data and claim.claim_data[field] is not None:
                            claim_payload[field] = claim.claim_data[field]
                
                # Publish to LinkedTrust
                response = client.create_claim(claim_payload)
                
                if response.get('success'):
                    # Update claim status
                    claim.status = 'published'
                    claim.published_at = datetime.utcnow()
                    claim.linkedtrust_claim_url = response.get('data', {}).get('url') or response.get('data', {}).get('id')
                    claim.linkedtrust_response = response.get('data')
                    published_count += 1
                    logger.info(f"Published claim {claim.id} to LinkedTrust")
                else:
                    logger.error(f"Failed to publish claim {claim.id}: {response.get('error')}")
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"Error publishing claim {claim.id}: {e}")
                failed_count += 1
        
        db.session.commit()
        
        result = {
            'document_id': document_id,
            'published': published_count,
            'failed': failed_count,
            'status': 'completed'
        }
        
        logger.info(f"Publishing complete: {published_count} published, {failed_count} failed")
        return result
        
    except Exception as e:
        logger.error(f"Error publishing claims for document {document_id}: {e}")
        job.status = 'failure'
        job.error_message = str(e)
        job.completed_at = datetime.utcnow()
        db.session.commit()
        raise