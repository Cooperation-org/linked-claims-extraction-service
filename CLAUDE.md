# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## IMPORTANT: Database Migrations

**CRITICAL**: Database migrations are checked into git in the `migrations/` directory. 
- NEVER auto-generate migrations on the server
- NEVER modify the deployment to create migrations
- ALWAYS create migrations locally and commit them to git
- When adding new model fields, ensure nullable=True or provide defaults to avoid breaking existing data

To create new migrations locally:
```bash
# Set up local environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create migration
export FLASK_APP=src/app.py
export DATABASE_URL="sqlite:///local.db"  # Use local SQLite for migration generation
flask db migrate -m "Description of changes"

# Review the generated migration file in migrations/versions/
# Commit to git
git add migrations/versions/*.py
git commit -m "Add migration: Description of changes"
```

## Project Overview

This is the Linked Claims Extraction Service - a Flask web application with background processing that extracts verifiable claims from PDF documents and publishes them to the decentralized LinkedTrust network at live.linkedtrust.us.

## New Architecture (Background Processing)

The service now includes:
- **PostgreSQL Database**: Stores documents, draft claims, and processing jobs
- **Redis + Celery**: Background processing for PDF extraction
- **OAuth Authentication**: Users login via LinkedTrust to manage their documents
- **Validation Flow**: Sharable URLs for claim validation by witnesses/beneficiaries

## Critical Architecture Principles

### Data Storage Philosophy (IMPORTANT)
- **Local PostgreSQL**: Stores ONLY draft claims, PDF metadata, and processing status
- **LinkedTrust API (live.linkedtrust.us)**: Stores ALL published claims and validations
- **Key Rule**: Once claims are published, they are NO LONGER stored locally - always query LinkedTrust API for published claims

### Core Dependencies
- Web Framework: Flask
- PDF Processing: PyMuPDF, pdfplumber
- Claim Extraction: linked-claims-extractor (PyPI package, separate repo)
- Background Processing: Celery + Redis (when configured)
- Database: PostgreSQL (for drafts/metadata only)

## Development Commands

### Local Development Setup

See `README_LOCAL_DEV.md` for detailed setup instructions.

#### Quick Start (Local)
```bash
# One-time setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Edit with your API keys
export FLASK_APP=src/app.py
flask db upgrade

# Run development server
python src/app.py
# Server runs on http://localhost:5050
```

#### Optional: With Background Processing
```bash
# Start Redis (if you have it installed)
redis-server

# Start Celery worker (in separate terminal)
source venv/bin/activate
cd src
celery -A celery_app.celery_app worker --loglevel=info
```

#### Production (Ansible Deployment)
```bash
# Deploy with Ansible
cd deploy
ansible-playbook -i inventory/production.yml playbooks/deploy-with-background.yml --ask-vault-pass

# Update existing deployment
ansible-playbook -i inventory/production.yml playbooks/update-with-background.yml --ask-vault-pass
```

### Testing
```bash
# Run tests with pytest
pytest tests/

# Run specific test file
pytest tests/test_document_manager.py
```

### Environment Setup
```bash
# Copy example environment file
cp .env.example .env

# Required environment variables:
# - ANTHROPIC_API_KEY: Claude API key for extraction
# - LINKEDTRUST_BASE_URL: API URL (default: https://live.linkedtrust.us)
# - FLASK_SECRET_KEY: Session security key
# - FLASK_PORT: Server port (default: 5050)
```

## Key Application Components

### Core Modules
- `src/app.py`: Main Flask application with routes, background processing, and LinkedTrust integration
- `src/pdf_parser/`: PDF processing and document management modules
- `src/claim_viz.py`: Claim visualization utilities
- `src/templates/`: Flask HTML templates

### API Integration Points
- LinkedTrust API: Claims are published via POST to `/api/v4/claims`
- Authentication: Currently uses service URL as issuerId (https://parse.linkedtrust.us)
- OAuth: Future implementation planned for user authentication

### Processing Flow
1. User uploads PDF via web interface
2. PDF stored locally with unique identifier
3. ClaimExtractor (from linked-claims-extractor package) processes PDF
4. Draft claims displayed for user review
5. User approves and publishes to LinkedTrust
6. Published claims removed from local storage

## Production Deployment

### Server Details
- Production URL: https://extract.linkedtrust.us
- Deployment: Ubuntu server with systemd service
- Service name: ai-pdf-extractor.service
- Application path: /root/ext/linked-claims-extractor

### Deployment Commands
```bash
# Pull latest changes
git pull origin main

# Restart service
sudo systemctl restart ai-pdf-extractor.service

# Check service status
sudo systemctl status ai-pdf-extractor.service

# View logs
sudo journalctl -u ai-pdf-extractor.service -f
```

## Important Notes

1. **linked-claims-extractor Package**: The ClaimExtractor is imported from the PyPI package `linked-claims-extractor`. This is maintained in a separate repository and can be updated via pip.

2. **File Upload Limits**: Maximum file size is 80MB (configurable in app.py)

3. **Supported Formats**: Only PDF files are currently supported

4. **Graph Queries**: For examples of querying published claims, refer to the talent project

5. **Security**: Never store API keys or sensitive data in code. Always use environment variables.

## Common Tasks

### Adding New Claim Types
1. Update the linked-claims-extractor package if extraction logic needs changes
2. Modify templates in `src/templates/` for UI changes
3. Update `app.py` for new API endpoints if needed

### Debugging PDF Processing
- Check `src/pdf_parser/pdf_processor.py` for extraction logic
- Use `src/pdf_parser/document_repl.py` for interactive debugging
- Test files available in `tests/fixtures/`

### Updating Dependencies
```bash
# Update specific package
pip install --upgrade linked-claims-extractor

# Freeze requirements
pip freeze > requirements.txt
```