"""
Minimal PDF text extraction for claim processing
"""
import fitz  # PyMuPDF
from typing import List, Dict, Any
import re

class SimplePDFExtractor:
    """Simple PDF text extraction without ML dependencies"""
    
    def extract_text_from_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """Extract all text from PDF"""
        text = ""
        
        try:
            with fitz.open(pdf_path) as doc:
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    text += page.get_text()
            
            # Clean up the text
            text = re.sub(r'\s+', ' ', text).strip()
            
            return {
                'cleaned_text': text,
                'sentences': text.split('. '),
                'entities': []  # Placeholder - no NLP processing
            }
        except Exception as e:
            print(f"Error extracting text: {e}")
            return {'cleaned_text': '', 'sentences': [], 'entities': []}
    
    def extract_text_from_pdf_per_page(self, pdf_path: str) -> List[Dict[int, str]]:
        """Extract text from each page separately"""
        pages_text = []
        
        try:
            with fitz.open(pdf_path) as doc:
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    page_text = page.get_text()
                    # Clean up the text
                    cleaned_text = re.sub(r'\s+', ' ', page_text).strip()
                    pages_text.append({page_num: cleaned_text})
        except Exception as e:
            print(f"Error extracting text: {e}")
            
        return pages_text


class SimpleDocumentManager:
    """Simplified DocumentManager that only does text extraction"""
    
    def __init__(self, *args, **kwargs):
        # Ignore all the ML-related parameters
        self.extractor = SimplePDFExtractor()
    
    def process_pdf_all_or_pages(self, pdf_path: str, type: str = "all"):
        """Process PDF and return text"""
        if type == "all":
            return self.extractor.extract_text_from_pdf(pdf_path)
        else:
            return self.extractor.extract_text_from_pdf_per_page(pdf_path)
