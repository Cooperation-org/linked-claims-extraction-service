"""
Celery background tasks for PDF processing and claim extraction
"""
import os
import logging
from datetime import datetime
from celery import Task
from celery_app import celery_app
from extraction_common import (
    verify_api_key,
    extract_pdf_text_batches,
    extract_claims_from_page,
    process_claim_data,
    prepare_linkedtrust_claim_payload
)

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
                    claim_payload = prepare_linkedtrust_claim_payload(claim, doc)
                    
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