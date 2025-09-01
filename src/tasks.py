"""
Celery background tasks for PDF processing and claim extraction
"""
import os
import logging
from datetime import datetime
from celery import Task
from celery_app import celery_app
import fitz  # PyMuPDF
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Import Flask app and create context for database operations
from flask import Flask
from dotenv import load_dotenv
load_dotenv()

def get_app():
    """Get or create Flask app for Celery context"""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://extractor:fluffyHedgehog2025@localhost/extractor')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    from models import db
    db.init_app(app)
    
    return app

# Create app for context
flask_app = get_app()

class CallbackTask(Task):
    """Base task with callbacks for status tracking"""
    
    def on_success(self, retval, task_id, args, kwargs):
        """Success handler"""
        with flask_app.app_context():
            from models import db, ProcessingJob
            job = ProcessingJob.query.get(task_id)
            if job:
                job.status = 'success'
                job.completed_at = datetime.utcnow()
                db.session.commit()
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Failure handler"""
        with flask_app.app_context():
            from models import db, Document, ProcessingJob
            job = ProcessingJob.query.get(task_id)
            if job:
                job.status = 'failure'
                job.error_message = str(exc)
                job.completed_at = datetime.utcnow()
                db.session.commit()
            
            # Update document status
            document_id = kwargs.get('document_id') or args[0] if args else None
            if document_id:
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
    
    with flask_app.app_context():
        from models import db, Document, DraftClaim, ProcessingJob
        from pdf_parser.simple_document_manager import SimpleDocumentManager
        from claim_extractor import ClaimExtractor
        
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
            # Check if API key is available
            import os
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if not api_key:
                logger.error("ANTHROPIC_API_KEY environment variable not set!")
                raise ValueError("ANTHROPIC_API_KEY not configured")
            else:
                logger.info("ANTHROPIC_API_KEY is configured")
            
            # Initialize extractor
            extractor = ClaimExtractor()
            logger.info("ClaimExtractor initialized successfully")
            
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
    
    with flask_app.app_context():
        from models import db, Document, DraftClaim, ProcessingJob
        from linkedtrust_client import LinkedTrustClient
        
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
                    
                    # Add optional fields from claim_data
                    if claim.claim_data:
                        for key in ['confidence', 'aspect', 'score', 'stars', 'amt', 'unit', 'howMeasured']:
                            if key in claim.claim_data and claim.claim_data[key] is not None:
                                claim_payload[key] = claim.claim_data[key]
                    
                    # Publish to LinkedTrust
                    result = client.create_claim(claim_payload)
                    
                    if result.get('success'):
                        # Update claim status
                        claim.status = 'published'
                        claim.published_at = datetime.utcnow()
                        claim.linkedtrust_response = result.get('data')
                        # Extract claim URL from response
                        if result.get('data', {}).get('id'):
                            claim.linkedtrust_claim_url = f"https://live.linkedtrust.us/claim/{result['data']['id']}"
                        published_count += 1
                    else:
                        logger.error(f"Failed to publish claim {claim.id}: {result.get('error')}")
                        failed_count += 1
                    
                except Exception as e:
                    logger.error(f"Error publishing claim {claim.id}: {e}")
                    failed_count += 1
                
                # Commit after each claim
                db.session.commit()
            
            logger.info(f"Publishing complete: {published_count} published, {failed_count} failed")
            return {
                'document_id': document_id,
                'published': published_count,
                'failed': failed_count,
                'status': 'completed'
            }
            
        except Exception as e:
            logger.error(f"Error publishing claims for document {document_id}: {e}")
            job.status = 'failure'
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.session.commit()
            raise