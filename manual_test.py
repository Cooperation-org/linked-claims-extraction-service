#!/usr/bin/env python
"""
Local test script for claim extraction without Celery
"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
load_dotenv()

import fitz  # PyMuPDF
from claim_extractor import ClaimExtractor
import json


def extract_from_pdf(pdf_path, max_pages=5):
    """Extract claims from PDF file"""
    print(f"\n📄 Processing: {pdf_path}")
    
    # Initialize extractor
    extractor = ClaimExtractor()
    print("✅ ClaimExtractor initialized")
    
    all_claims = []
    
    # Open PDF
    with fitz.open(pdf_path) as pdf:
        total_pages = min(len(pdf), max_pages)
        print(f"📖 Processing {total_pages} pages...")
        
        for page_num in range(total_pages):
            page = pdf.load_page(page_num)
            text = page.get_text()
            
            if len(text.strip()) < 50:
                print(f"  Page {page_num + 1}: Skipped (too short)")
                continue
            
            print(f"  Page {page_num + 1}: Extracting claims...")
            try:
                claims = extractor.extract_claims(text)
                if claims:
                    print(f"    ✓ Found {len(claims)} claims")
                    for claim in claims:
                        claim['page'] = page_num + 1
                    all_claims.extend(claims)
                else:
                    print(f"    - No claims found")
            except Exception as e:
                print(f"    ✗ Error: {e}")
    
    return all_claims


def extract_from_text(text):
    """Extract claims from text"""
    print("\n📝 Processing text...")
    
    extractor = ClaimExtractor()
    print("✅ ClaimExtractor initialized")
    
    try:
        claims = extractor.extract_claims(text)
        if claims:
            print(f"✓ Found {len(claims)} claims")
        else:
            print("No claims found")
        return claims
    except Exception as e:
        print(f"✗ Error: {e}")
        return []


def main():
    """Test extraction locally"""
    
    # Check for API key
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("❌ ERROR: ANTHROPIC_API_KEY not set in environment")
        print("Please set: export ANTHROPIC_API_KEY=your-key")
        return
    
    print("🚀 Local Claim Extraction Test")
    print("=" * 50)
    
    # Test with sample text
    sample_text = """
    John Smith was the CEO of TechCorp from 2020 to 2023. 
    Under his leadership, the company increased revenue by 40% 
    and expanded to 15 new markets globally.
    """
    
    print("\n1. Testing with sample text:")
    claims = extract_from_text(sample_text)
    if claims:
        print("\nExtracted claims:")
        print(json.dumps(claims, indent=2))
    
    # Test with PDF if exists
    pdf_files = ["example-p16.pdf", "example.pdf"]
    for pdf_file in pdf_files:
        if Path(pdf_file).exists():
            print(f"\n2. Testing with PDF: {pdf_file}")
            claims = extract_from_pdf(pdf_file, max_pages=3)
            if claims:
                print(f"\nExtracted {len(claims)} total claims from PDF")
                print("\nFirst claim:")
                print(json.dumps(claims[0], indent=2))
            break
    else:
        print("\n2. No PDF files found for testing")
    
    print("\n" + "=" * 50)
    print("✅ Test complete!")


if __name__ == "__main__":
    main()