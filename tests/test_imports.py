"""
Test all imports to ensure no ModuleNotFoundError
"""
import os
import sys
import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))


def test_all_pdf_parser_imports():
    """Test that all pdf_parser submodules import correctly"""
    # These should all work without error
    from pdf_parser.document_manager import DocumentManager
    from pdf_parser.simple_document_manager import SimpleDocumentManager
    from pdf_parser.document_repl import DocumentREPL
    from pdf_parser.pdf_processor import PDFProcessor
    from pdf_parser.cache_manager import CacheManager
    
    # Verify classes exist
    assert DocumentManager is not None
    assert SimpleDocumentManager is not None
    assert DocumentREPL is not None
    assert PDFProcessor is not None
    assert CacheManager is not None


def test_tasks_imports():
    """Test that tasks.py imports work correctly"""
    from tasks import extract_claims_from_document, publish_claims_to_linkedtrust
    
    # Verify tasks are registered
    assert extract_claims_from_document.name == 'tasks.extract_claims_from_document'
    assert publish_claims_to_linkedtrust.name == 'tasks.publish_claims_to_linkedtrust'


def test_models_imports():
    """Test that all model imports work"""
    from models import db, User, Document, DraftClaim, ProcessingJob
    
    assert db is not None
    assert User is not None
    assert Document is not None
    assert DraftClaim is not None
    assert ProcessingJob is not None


def test_app_imports():
    """Test that app.py imports work"""
    from app import app, login_manager
    
    assert app is not None
    assert login_manager is not None


def test_celery_imports():
    """Test that Celery app imports work"""
    from celery_app import celery_app
    
    assert celery_app is not None
    assert celery_app.main == 'linked_claims_extraction'


def test_claim_extractor_import():
    """Test that claim_extractor imports work"""
    from claim_extractor import ClaimExtractor
    
    assert ClaimExtractor is not None


def test_linkedtrust_client_import():
    """Test that LinkedTrust client imports work"""
    from linkedtrust_client import LinkedTrustClient
    
    assert LinkedTrustClient is not None


def test_main_py_imports():
    """Test that main.py imports work after fixes"""
    from main import main
    
    assert main is not None


def test_claim_viz_imports():
    """Test that claim_viz.py imports work after fixes"""
    from claim_viz import create_html_display, analyze_pdf_with_claims
    
    assert create_html_display is not None
    assert analyze_pdf_with_claims is not None


def test_critical_imports_in_task_context():
    """Test the exact imports that happen inside the Celery task"""
    # Simulate what happens inside the task
    from models import db, Document, DraftClaim, ProcessingJob
    from pdf_parser.simple_document_manager import SimpleDocumentManager
    from claim_extractor import ClaimExtractor
    import fitz  # PyMuPDF
    
    # These are the exact imports from tasks.py lines 80-82
    assert db is not None
    assert Document is not None
    assert DraftClaim is not None
    assert ProcessingJob is not None
    assert SimpleDocumentManager is not None
    assert ClaimExtractor is not None
    assert fitz is not None


if __name__ == '__main__':
    # Run all tests
    test_all_pdf_parser_imports()
    print("✓ PDF parser imports working")
    
    test_tasks_imports()
    print("✓ Tasks imports working")
    
    test_models_imports()
    print("✓ Models imports working")
    
    test_app_imports()
    print("✓ App imports working")
    
    test_celery_imports()
    print("✓ Celery imports working")
    
    test_claim_extractor_import()
    print("✓ Claim extractor import working")
    
    test_linkedtrust_client_import()
    print("✓ LinkedTrust client import working")
    
    test_main_py_imports()
    print("✓ main.py imports working")
    
    test_claim_viz_imports()
    print("✓ claim_viz.py imports working")
    
    test_critical_imports_in_task_context()
    print("✓ Critical task context imports working")
    
    print("\n✅ ALL IMPORTS WORKING! The Celery worker should now run without ModuleNotFoundError.")