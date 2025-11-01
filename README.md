# Linked Claims Extraction Service

Extract verifiable claims from PDF impact reports and publish them to the LinkedTrust network.

## Quick Start (Local Development)

### 1. Setup

```bash
# Clone repository
git clone https://github.com/Cooperation-org/linked-claims-extraction-service.git
cd linked-claims-extraction-service

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY


# Register a username at https://dev.linkedtrust.us
# you will use this username and password to login (or use Metamask)
```

### 2. Database Setup

The app will automatically create database tables on first run. If you encounter any issues:

```bash
# Initialize database manually
export FLASK_APP=src/app.py
flask db upgrade
```

By default, it creates a `local.db` SQLite file in your current directory.

### 3. Run

```bash
# Start the application
python src/app.py
```

Visit http://localhost:5050

## Features

- **Extract Claims**: Upload PDF reports to extract structured claims
- **Edit URLs**: Review and edit subject/object URLs before publishing
- **Publish to LinkedTrust**: Send approved claims to the decentralized network
- **Enable Validation**: Share links for beneficiaries to validate claims

## Project Structure

```
linked-claims-extraction-service/
├── src/
│   ├── app.py                 # Main Flask application
│   ├── models.py              # Database models
│   ├── tasks.py               # Background tasks (Celery)
│   ├── auth.py                # Authentication
│   ├── linkedtrust_client.py  # LinkedTrust API client
│   ├── claim_extractor.py     # Claims extraction logic
│   ├── url_generator.py       # URL generation for entities
│   ├── pdf_parser/            # PDF processing
│   └── templates/             # HTML templates
├── migrations/                # Database migrations
├── tests/                     # Test suite
├── docs/                      # Documentation
└── requirements.txt           # Python dependencies
```

## Configuration

Key environment variables in `.env`:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx

# Optional (defaults work for local dev)
FLASK_PORT=5050
DATABASE_URL=sqlite:///local.db  # Defaults to sqlite:///local.db
LINKEDTRUST_API_URL=https://dev.linkedtrust.us/api

# Prompt Configuration (optional)
# Defaults to 'simple' prompt if not specified
LT_USE_PROMPT_FILE=simple              # Name of prompt file in prompts/ directory
LT_EXTRA_SYSTEM_PROMPT_FILE=           # Additional system instructions file
```

### Prompt Configuration

The service uses customizable prompts for claim extraction. Prompts are stored in the `prompts/` directory.

- **Default prompt**: `prompts/simple.md` is used by default
- **Custom prompts**: Create `.md` files in `prompts/` and reference by name (without extension)
- **Absolute paths**: Start with `/` to use prompts from anywhere on the filesystem
- **Relative paths**: All other paths are interpreted relative to the `prompts/` directory

Example:
```bash
# Use a custom prompt from prompts/ directory
LT_USE_PROMPT_FILE=detailed-extraction

# Use an absolute path
LT_USE_PROMPT_FILE=/path/to/my/custom-prompt.md

# Add extra system instructions
LT_EXTRA_SYSTEM_PROMPT_FILE=organization-specific
```

## Background Processing (Optional)

For production-like setup with background jobs:

1. Install Redis:
   ```bash
   # macOS
   brew install redis
   brew services start redis
   
   # Ubuntu
   sudo apt-get install redis-server
   ```

2. Add to `.env`:
   ```bash
   REDIS_URL=redis://localhost:6379/0
   ```

3. Run Celery worker (separate terminal):
   ```bash
   source .venv/bin/activate
   celery -A src.celery_app.celery_app worker --loglevel=info
   ```

## Development Workflow

### Making Model Changes

```bash
# Generate migration
flask db migrate -m "Add new field to DraftClaim"

# Apply migration
flask db upgrade

# Commit migration
git add migrations/
git commit -m "Add migration for new field"
```

### Testing

```bash
# Run tests
pytest tests/

# Run with coverage
pytest --cov=src tests/
```

## Deployment

See [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) for production deployment instructions.

## API Documentation

The service provides REST APIs for:
- Document upload and processing
- Claim management (CRUD operations)
- Publishing to LinkedTrust
- URL suggestions and validation

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see LICENSE file for details.

## Support

- Issues: https://github.com/Cooperation-org/linked-claims-extraction-service/issues
- LinkedTrust Network: https://linkedtrust.us
- LinkedClaims Standard: https://identity.foundation/linked-claims/
