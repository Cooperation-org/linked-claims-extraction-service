# Linked Claims Extraction Service

Web service for extracting structured claims from PDF documents and pushing them to LinkedTrust.

**Live Demo**: [https://extract.linkedtrust.us](https://extract.linkedtrust.us)

## Architecture Overview

### Important: Data Storage Philosophy

This service uses a **hybrid storage approach**:

- **Local PostgreSQL Database**: Stores ONLY draft claims, uploaded PDFs metadata, and processing status
- **Decentralized Backend (live.linkedtrust.us)**: Stores ALL published claims and validations
- **Key Point**: Once claims are published to LinkedTrust, they are NO LONGER stored locally. All queries for published claims use the LinkedTrust API.

For detailed architecture and purpose, see [PURPOSE.md](PURPOSE.md)

## Quick Start

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
python run.py
```

The service will start on http://localhost:5050

## Configuration

Edit `.env` file with your credentials:

```env
# LinkedTrust API credentials
LINKEDTRUST_EMAIL=your-email@example.com
LINKEDTRUST_PASSWORD=your-password
LINKEDTRUST_BASE_URL=https://dev.linkedtrust.us

# AI API keys (need at least one)
ANTHROPIC_API_KEY=your-anthropic-key
# OPENAI_API_KEY=your-openai-key  # Optional

# Flask configuration
FLASK_SECRET_KEY=any-random-string-here
FLASK_PORT=5050
FLASK_DEBUG=False
```

## Usage

1. Start the service with `python run.py`
2. Open http://localhost:5050 in your browser
3. Upload a PDF file
4. Review the extracted claims
5. Click "Publish to LinkedTrust" to send claims to the API

## Troubleshooting

- **ImportError**: Make sure you activated the virtual environment
- **API Key errors**: Check your `.env` file has valid API keys
- **Connection errors**: Check your LinkedTrust credentials are correct

## Production Deployment

See [pdf_parser_DEPLOYMENT_GUIDE.MD](pdf_parser_DEPLOYMENT_GUIDE.MD) for production deployment.
