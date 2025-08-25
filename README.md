# Linked Claims Extraction Service

Web service for extracting structured claims from PDF documents and pushing them to LinkedTrust.

**Live Demo**: [https://extract.linkedtrust.us](https://extract.linkedtrust.us)

## Architecture Overview

### Publishing Architecture

This service uses a **direct frontend publishing approach**:

- **Local Service**: Extracts claims from PDFs, stores draft claims for review
- **Frontend Publishing**: Users authenticate directly with LinkedTrust and publish claims under their own account
- **No Service-Side Credentials**: The service never stores or uses LinkedTrust credentials
- **User-Controlled Publishing**: Each user publishes claims using their own LinkedTrust identity

### Data Storage Philosophy

- **Local PostgreSQL Database**: Stores ONLY draft claims, uploaded PDFs metadata, and processing status
- **LinkedTrust Backend**: Stores ALL published claims and validations under user accounts  
- **Key Point**: Claims are published directly by users, not by the service

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

### LinkedTrust Account
You need a LinkedTrust account to publish claims. **Register at [dev.linkedtrust.us](https://dev.linkedtrust.us)** for testing, or [live.linkedtrust.us](https://live.linkedtrust.us) for production.

**Publishing Flow:** When you publish claims, the frontend will prompt for your LinkedTrust credentials and publish directly to the LinkedTrust API under your user account (not a service account).

### Environment Setup
Edit `.env` file with your API keys:

```env
# AI API keys (required for claim extraction)
ANTHROPIC_API_KEY=your-anthropic-key
# OPENAI_API_KEY=your-openai-key  # Optional alternative

# Flask configuration
FLASK_SECRET_KEY=any-random-string-here
FLASK_PORT=5050
FLASK_DEBUG=False

# LinkedTrust backend URL (dev for testing, live for production)
LINKEDTRUST_BASE_URL=https://dev.linkedtrust.us
```

**Note:** No LinkedTrust credentials needed in `.env` - users enter their own credentials when publishing.

## Usage

1. Start the service with `python run.py`
2. Open http://localhost:5050 in your browser
3. Upload a PDF file
4. Review and approve the extracted claims
5. Click "Publish to LinkedTrust" 
6. Enter your LinkedTrust credentials when prompted
7. Claims are published directly to LinkedTrust under your user account

## Troubleshooting

- **ImportError**: Make sure you activated the virtual environment
- **API Key errors**: Check your `.env` file has valid API keys
- **Connection errors**: Check your LinkedTrust credentials are correct

## Production Deployment

See [pdf_parser_DEPLOYMENT_GUIDE.MD](pdf_parser_DEPLOYMENT_GUIDE.MD) for production deployment.
