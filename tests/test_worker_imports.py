"""
Test ONLY the imports needed for the Celery worker to run
This is what actually matters for fixing the ModuleNotFoundError
"""
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

def test_celery_worker_imports():
    """Test the exact imports that the Celery worker needs"""
    
    print("Testing Celery worker imports...")
    
    # 1. Test that tasks can be imported
    from tasks import extract_claims_from_document, publish_claims_to_linkedtrust
    print("✓ Tasks imported")
    
    # 2. Test the imports that happen INSIDE the extract_claims_from_document task
    # These are from lines 80-82 in tasks.py
    from models import db, Document, DraftClaim, ProcessingJob
    print("✓ Models imported")
    
    from pdf_parser.simple_document_manager import SimpleDocumentManager
    print("✓ SimpleDocumentManager imported")
    
    from claim_extractor import ClaimExtractor
    print("✓ ClaimExtractor imported")
    
    # 3. Test PyMuPDF which is used for PDF processing
    import fitz
    print("✓ PyMuPDF (fitz) imported")
    
    # 4. Test the publish task imports
    from linkedtrust_client import LinkedTrustClient
    print("✓ LinkedTrustClient imported")
    
    print("\n✅ ALL CELERY WORKER IMPORTS WORKING!")
    print("The worker should now run without ModuleNotFoundError.")
    return True


if __name__ == '__main__':
    try:
        test_celery_worker_imports()
    except ImportError as e:
        print(f"\n❌ IMPORT ERROR: {e}")
        print("This is the issue preventing the Celery worker from running!")
        sys.exit(1)