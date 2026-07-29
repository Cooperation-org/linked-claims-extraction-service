"""
Batch ingest: extract claims from many PDFs listed in a manifest CSV.

Runs the same extraction path as the web app (page-by-page ClaimExtractor with
the configured prompts, duplicate skipping, verifiability labels) but from the
command line, sequentially, with a per-document summary. Claims are stored as
DraftClaims for review; nothing is published.

Manifest CSV columns (header required):
    pdf_path      path to the PDF on disk (required)
    public_url    public URL of the document; becomes sourceURI (required)
    effective_date  document date, YYYY-MM-DD (required)
    subject_url   org URL used as default claim subject (optional)

Usage:
    python batch_ingest.py manifest.csv --user-email you@example.org

Requires DATABASE_URL and ANTHROPIC_API_KEY in the environment (or .env).
The user must already exist (log in to the web app once); documents are
attributed to that user.
"""
import argparse
import csv
import logging
import os
import sys
import uuid
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask

load_dotenv()
logger = logging.getLogger(__name__)


def build_app() -> Flask:
    """Minimal Flask app context for DB + prompt config (mirrors tasks.get_app)."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set for batch ingest")
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    from models import db
    db.init_app(app)

    from app_config import configure_prompts
    configure_prompts(app)
    return app


def read_manifest(path: str) -> list:
    rows = []
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        required = {'pdf_path', 'public_url', 'effective_date'}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Manifest is missing columns: {sorted(missing)}")
        for lineno, row in enumerate(reader, start=2):
            pdf_path = (row.get('pdf_path') or '').strip()
            public_url = (row.get('public_url') or '').strip()
            date_str = (row.get('effective_date') or '').strip()
            if not (pdf_path and public_url and date_str):
                raise ValueError(f"Manifest line {lineno}: pdf_path, public_url and effective_date are required")
            if not os.path.isfile(pdf_path):
                raise ValueError(f"Manifest line {lineno}: file not found: {pdf_path}")
            rows.append({
                'pdf_path': pdf_path,
                'public_url': public_url,
                'effective_date': datetime.strptime(date_str, '%Y-%m-%d').date(),
                'subject_url': (row.get('subject_url') or '').strip() or None,
            })
    return rows


def ingest_document(db, models, entry: dict, user_id: str, extractor) -> dict:
    """Create a Document row and run page-by-page extraction on it."""
    from extraction_common import (
        extract_pdf_text_batches, process_claim_data,
        existing_statement_keys, is_new_statement)
    from extractor import extract_claims as run_extractor

    doc = models.Document(
        id=str(uuid.uuid4()),
        filename=os.path.basename(entry['pdf_path']),
        original_filename=os.path.basename(entry['pdf_path']),
        file_path=entry['pdf_path'],
        public_url=entry['public_url'],
        subject_url=entry['subject_url'],
        effective_date=entry['effective_date'],
        user_id=user_id,
        status='processing',
        processing_started_at=datetime.utcnow(),
    )
    db.session.add(doc)
    db.session.commit()

    seen = existing_statement_keys(models.DraftClaim, doc.id)
    claims_added = 0
    duplicates = 0
    total_pages, batches = extract_pdf_text_batches(entry['pdf_path'])
    try:
        for batch in batches:
            for page_num, text in batch:
                if not text or len(text) < 50:
                    continue
                try:
                    page_claims = run_extractor(extractor, text) or []
                except Exception as e:
                    logger.error(f"Extraction failed on page {page_num}: {e}")
                    continue
                for claim in page_claims:
                    processed = process_claim_data(
                        claim, text, doc.id, doc.public_url, page_num)
                    if not processed['subject'] and doc.subject_url:
                        processed['subject'] = doc.subject_url
                    if not is_new_statement(seen, processed['statement']):
                        duplicates += 1
                        continue
                    db.session.add(models.DraftClaim(**processed))
                    claims_added += 1
            db.session.commit()
        doc.status = 'completed'
        doc.processing_completed_at = datetime.utcnow()
    except Exception as e:
        doc.status = 'failed'
        doc.error_message = str(e)
        raise
    finally:
        db.session.commit()
    return {'document_id': doc.id, 'pages': total_pages,
            'claims': claims_added, 'duplicates_skipped': duplicates}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument('manifest', help='CSV manifest of PDFs to ingest')
    parser.add_argument('--user-email', required=True,
                        help='Email of an existing user to attribute documents to')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')

    if not os.getenv('ANTHROPIC_API_KEY'):
        print("ANTHROPIC_API_KEY is not set", file=sys.stderr)
        return 2

    entries = read_manifest(args.manifest)
    app = build_app()

    with app.app_context():
        import models
        from models import db
        from claim_extractor import ClaimExtractor

        user = models.User.query.filter_by(email=args.user_email).first()
        if not user:
            print(f"No user with email {args.user_email}; log in to the web app once first",
                  file=sys.stderr)
            return 2

        extractor = ClaimExtractor(
            message_prompt=app.config.get('LT_MESSAGE_PROMPT'),
            extra_system_instructions=app.config.get('LT_EXTRA_SYSTEM_PROMPT', ''))

        failures = 0
        for i, entry in enumerate(entries, 1):
            label = f"[{i}/{len(entries)}] {entry['pdf_path']}"
            try:
                result = ingest_document(db, models, entry, user.id, extractor)
                print(f"{label}: {result['claims']} claims, "
                      f"{result['duplicates_skipped']} duplicates skipped, "
                      f"{result['pages']} pages (document {result['document_id']})")
            except Exception as e:
                failures += 1
                logger.exception(f"{label}: FAILED: {e}")
        print(f"Done: {len(entries) - failures}/{len(entries)} documents ingested")
        return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
