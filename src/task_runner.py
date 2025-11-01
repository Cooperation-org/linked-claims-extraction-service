"""
Task runner that switches between synchronous and asynchronous execution
based on environment configuration.
"""
import os
import logging
from typing import Any, Dict
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class TaskRunner:
    """Wrapper for running tasks synchronously or asynchronously based on environment"""
    
    def __init__(self):
        # Explicit flag for local development mode - defaults to False for safety
        self.is_local_dev = os.getenv('LOCAL_DEV_MODE', 'false').lower() == 'true'
        
        if self.is_local_dev:
            logger.info("🏠 Running in LOCAL DEVELOPMENT MODE - tasks will run synchronously")
        else:
            logger.info("🚀 Running in PRODUCTION MODE - tasks will use Celery")
    
    def run_extraction(self, document_id: str) -> Dict[str, Any]:
        """
        Run claim extraction task
        
        Args:
            document_id: The document ID to process
            
        Returns:
            Dict with task information including ID
        """
        if self.is_local_dev:
            # Run synchronously for local development
            logger.info(f"Running extraction synchronously for document {document_id}")
            logger.info("⏳ PROCESSING CLAIMS NOW - Note: Please use only short documents (1-2 pages) for local testing")
            
            # Import the actual extraction logic directly
            from tasks_sync import extract_claims_from_document_sync
            
            # Generate a unique ID for this sync task
            sync_task_id = f"sync-{document_id}-{datetime.now().timestamp()}"
            
            # Call the extraction function directly
            result = extract_claims_from_document_sync(document_id)
            
            logger.info(f"Synchronous extraction completed for document {document_id}")
            
            return {
                'id': sync_task_id,
                'result': result,
                'is_sync': True,
                'message': 'Processing claims now - Note: Please use only short documents (1-2 pages) for local testing'
            }
        else:
            # Run with Celery in production
            logger.info(f"Queueing extraction with Celery for document {document_id}")
            
            from tasks import extract_claims_from_document
            task = extract_claims_from_document.delay(document_id)
            
            return {
                'id': task.id,
                'task': task,
                'is_sync': False
            }
    
    def run_publish(self, document_id: str, claim_ids: list = None) -> Dict[str, Any]:
        """
        Run claim publishing task
        
        Args:
            document_id: The document ID with claims to publish
            claim_ids: Optional list of specific claim IDs to publish
            
        Returns:
            Dict with task information including ID
        """
        if self.is_local_dev:
            # Run synchronously for local development
            logger.info(f"Running publishing synchronously for document {document_id}")
            
            from tasks import publish_claims_to_linkedtrust
            
            # Create a mock request object
            class MockRequest:
                def __init__(self, doc_id):
                    self.id = f"sync-publish-{doc_id}-{datetime.now().timestamp()}"
            
            task_instance = publish_claims_to_linkedtrust
            task_instance.request = MockRequest(document_id)
            
            try:
                result = publish_claims_to_linkedtrust(document_id, claim_ids)
                
                logger.info(f"Synchronous publishing completed for document {document_id}")
                
                return {
                    'id': task_instance.request.id,
                    'result': result,
                    'is_sync': True
                }
            except Exception as e:
                logger.error(f"Error in synchronous publishing: {e}")
                raise
        else:
            # Run with Celery in production
            logger.info(f"Queueing publishing with Celery for document {document_id}")
            
            from tasks import publish_claims_to_linkedtrust
            task = publish_claims_to_linkedtrust.delay(document_id, claim_ids)
            
            return {
                'id': task.id,
                'task': task,
                'is_sync': False
            }


# Create global instance
task_runner = TaskRunner()
