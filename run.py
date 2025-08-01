#!/usr/bin/env python
"""
Run the Linked Claims Extraction Service
"""
import os
import sys

# Add src to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app import app

if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5050))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    print("🚀 Starting Linked Claims Extraction Service")
    print(f"📍 Server running on http://localhost:{port}")
    print("📄 Upload PDFs to extract claims")
    
    app.run(debug=debug, host="0.0.0.0", port=port)
