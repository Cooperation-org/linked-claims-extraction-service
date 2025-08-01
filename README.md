# Linked Claims Extraction Service

Web service for extracting structured claims from PDF documents and pushing them to LinkedTrust.

**Live Demo**: [https://extract.linkedtrust.us](https://extract.linkedtrust.us)

## Overview

This service provides a web interface and API for:
- Uploading PDF documents
- Extracting verifiable claims using AI
- Reviewing and editing claims
- Publishing claims to the LinkedTrust platform

## Installation

### Quick Start (Development)

```bash
# Clone the repository
git clone git@github.com:Cooperation-org/linked-claims-extraction-service.git
cd linked-claims-extraction-service

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# Run the service
python src/app.py
```

### Production Deployment

See [pdf_parser_DEPLOYMENT_GUIDE.MD](pdf_parser_DEPLOYMENT_GUIDE.MD) for detailed production deployment instructions.

## Configuration

Create a `.env` file with:

```env
# LinkedTrust API credentials
LINKEDTRUST_EMAIL=your-email@example.com
LINKEDTRUST_PASSWORD=your-password
LINKEDTRUST_BASE_URL=https://dev.linkedtrust.us

# AI API keys
ANTHROPIC_API_KEY=your-anthropic-key
# OPENAI_API_KEY=your-openai-key  # Optional

# Flask configuration
FLASK_SECRET_KEY=your-secret-key
FLASK_PORT=5050
FLASK_DEBUG=False
```

## API Endpoints

- `GET /` - Upload interface
- `POST /upload` - Upload and process PDF
- `GET /claims` - View extracted claims
- `POST /api/claims/<claim_id>/publish` - Publish all claims
- `POST /api/claims/<claim_id>/publish/<claim_index>` - Publish single claim

## Architecture

```
linked-claims-extraction-service/
├── src/
│   ├── app.py              # Flask application
│   ├── templates/          # HTML templates
│   └── pdf_parser/         # PDF processing logic
├── requirements.txt        # Python dependencies
└── gunicorn.conf.py       # Production server config
```

## Dependencies

- [linked-claims-extractor](https://pypi.org/project/linked-claims-extractor/) - Core extraction library
- Flask - Web framework
- PyMuPDF & pdfplumber - PDF processing
- Gunicorn - Production WSGI server

## License

MIT License - see LICENSE file
