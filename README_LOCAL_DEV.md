# Local Development Setup

This guide helps you set up the Linked Claims Extraction Service for local development.

## Prerequisites

- Python 3.9+ 
- Git
- An Anthropic API key (get one at https://console.anthropic.com/)

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/Cooperation-org/linked-claims-extraction-service.git
cd linked-claims-extraction-service

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment configuration
cp .env.example .env
```

### 2. Configure Environment

Edit `.env` and add your API key:
```bash
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx  # Your actual key
```

The default configuration uses:
- SQLite database (no setup needed!)
- Port 5050
- Dev LinkedTrust instance

### 3. Initialize Database

```bash
# Apply database migrations
export FLASK_APP=src/app.py
flask db upgrade

# The local SQLite database (local.db) will be created automatically
```

### 4. Run the Application

```bash
# Start the development server
python src/app.py
```

Visit http://localhost:5050 in your browser!

## Development Workflow

### Daily Development

```bash
# Always activate virtual environment first
source venv/bin/activate

# Run the app
python src/app.py
```

### Creating Database Migrations

When you change models in `src/models.py`:

```bash
# Generate a new migration
flask db migrate -m "Description of changes"

# Review the generated file in migrations/versions/
# Apply it locally
flask db upgrade

# Commit the migration to git
git add migrations/versions/*.py
git commit -m "Add migration: Description of changes"
```

### Running with Background Processing (Optional)

If you need to test background job processing:

1. Install Redis locally:
   ```bash
   # macOS
   brew install redis
   brew services start redis
   
   # Ubuntu/Debian
   sudo apt-get install redis-server
   ```

2. Uncomment Redis settings in `.env`:
   ```bash
   REDIS_URL=redis://localhost:6379/0
   CELERY_BROKER_URL=redis://localhost:6379/0
   CELERY_RESULT_BACKEND=redis://localhost:6379/0
   ```

3. Run Celery worker (in a separate terminal):
   ```bash
   source venv/bin/activate
   cd src
   celery -A celery_app.celery_app worker --loglevel=info
   ```

## Testing

### Manual Testing
1. Upload a PDF through the web interface
2. Review extracted claims
3. Test publishing to LinkedTrust (requires valid credentials)

### Running Tests
```bash
pytest tests/
```

## Common Issues

### Port Already in Use
If port 5050 is taken, change it in `.env`:
```bash
FLASK_PORT=5051
```

### Database Issues
Reset your local database:
```bash
rm local.db
flask db upgrade
```

### Import Errors
Make sure you're in the virtual environment:
```bash
which python  # Should show venv/bin/python
```

## Project Structure

```
linked-claims-extraction-service/
├── src/
│   ├── app.py              # Main Flask application
│   ├── models.py            # Database models
│   ├── auth.py              # Authentication logic
│   ├── linkedtrust_client.py # LinkedTrust API client
│   ├── pdf_parser/          # PDF processing modules
│   └── templates/           # HTML templates
├── migrations/              # Database migrations (tracked in git)
├── tests/                   # Test files
├── .env.example            # Environment template
├── .env                    # Your local configuration (git-ignored)
├── requirements.txt        # Python dependencies
└── local.db               # SQLite database (git-ignored)
```

## Tips

- The app works without Redis/Celery for most development
- Use SQLite locally - it's simpler than PostgreSQL
- Migrations are already in git, just run `flask db upgrade`
- Check `CLAUDE.md` for project-specific guidelines

## Need Help?

- Check existing issues: https://github.com/Cooperation-org/linked-claims-extraction-service/issues
- Review the main documentation in `README.md`
- Look at `CLAUDE.md` for development guidelines