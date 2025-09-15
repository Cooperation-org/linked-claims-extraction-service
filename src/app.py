"""
Linked Claims Extraction Service - Main Flask Application
With background processing, authentication, and database integration
"""
import os
import uuid
import logging
import urllib.parse
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_cors import CORS
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Import our modules
from models import db, User, Document, DraftClaim, ProcessingJob, ClaimCache
from database import init_database, create_tables
from celery_app import create_celery_app
from auth import init_auth, create_auth_routes, AuthUser
from linkedtrust_client import LinkedTrustClient
from task_runner import task_runner
import tasks  # Import tasks to register them with Celery

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here')

# Configure prompts from environment
from app_config import configure_prompts
configure_prompts(app)

# Configure upload settings
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONTENT_LENGTH = 80 * 1024 * 1024  # 80MB max file size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Create upload directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize CORS
CORS(app)

# Initialize database
migrate = init_database(app, db)

# Create tables if they don't exist (for local development)
with app.app_context():
    # Check if we're using SQLite (local dev)
    is_sqlite = 'sqlite' in app.config.get('SQLALCHEMY_DATABASE_URI', '').lower()
    
    if is_sqlite:
        # ONLY for SQLite/local dev - create tables automatically
        try:
            logger.info("SQLite detected - ensuring database tables exist...")
            
            # Disable foreign key constraints temporarily for SQLite
            try:
                db.session.execute(db.text("PRAGMA foreign_keys=OFF"))
            except:
                pass  # Ignore if this fails
            
            # Create all tables (this is safe - won't drop existing tables)
            db.create_all()

            # For SQLite, manually add missing columns (since create_all doesn't alter existing tables)
            try:
                # Check if subject_url column exists
                db.session.execute(db.text("SELECT subject_url FROM documents LIMIT 1"))
                logger.info("subject_url column already exists")
            except Exception:
                # Column doesn't exist, add it
                logger.info("Adding subject_url column to documents table...")
                try:
                    db.session.execute(db.text("ALTER TABLE documents ADD COLUMN subject_url VARCHAR(500)"))
                    db.session.commit()
                    logger.info("✅ Added subject_url column successfully")
                except Exception as alter_error:
                    logger.error(f"Failed to add subject_url column: {alter_error}")

            # Re-enable foreign key constraints
            try:
                db.session.execute(db.text("PRAGMA foreign_keys=ON"))
            except:
                pass

            db.session.commit()

            # Verify tables were actually created
            try:
                db.session.execute(db.text("SELECT 1 FROM documents LIMIT 1"))
                logger.info("✅ Database tables created successfully - documents table verified")
            except Exception as verify_error:
                logger.error(f"⚠️ WARNING: documents table not found after create_all()")
                logger.error(f"Verification error: {verify_error}")
                # Try to get more info about what tables exist
                try:
                    result = db.session.execute(db.text("SELECT name FROM sqlite_master WHERE type='table'"))
                    tables = [row[0] for row in result]
                    logger.info(f"Existing tables: {tables}")
                except:
                    pass
                    
        except Exception as create_error:
            logger.error(f"Failed to ensure database tables: {create_error}")
            logger.info("Try running manually: export FLASK_APP=src/app.py && flask db upgrade")
    else:
        # Production - do nothing, tables should already exist via migrations
        pass

# Initialize Celery
celery = create_celery_app(app)

# Initialize authentication
login_manager = init_auth(app)
create_auth_routes(app)

# Add URL verification API routes
from api_url_verification import add_url_verification_routes
add_url_verification_routes(app)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Landing page for non-authenticated users, dashboard for authenticated"""
    if not current_user.is_authenticated:
        return render_template('index.html')
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard showing their documents"""
    # Get user's documents
    user_documents = Document.query.filter_by(user_id=current_user.id).order_by(Document.upload_time.desc()).all()
    
    return render_template('dashboard.html', 
                         documents=user_documents,
                         user=current_user)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_file():
    """Handle file upload with metadata"""
    if request.method == 'GET':
        return render_template('upload.html', local_dev_mode=os.getenv('LOCAL_DEV_MODE', 'false').lower() == 'true')
    
    # Check for file
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Only PDF files are allowed'}), 400
    
    # Get metadata from form
    public_url = request.form.get('public_url', '').strip()
    subject_url = request.form.get('subject_url', '').strip()
    effective_date_str = request.form.get('effective_date', '').strip()

    # Validate required fields
    if not public_url:
        return jsonify({'error': 'Public URL is required'}), 400
    
    if not effective_date_str:
        return jsonify({'error': 'Effective date is required'}), 400
    
    # Validate URL format
    if not public_url.startswith(('http://', 'https://')):
        return jsonify({'error': 'Public URL must start with http:// or https://'}), 400
    
    # Parse effective date
    try:
        effective_date = datetime.strptime(effective_date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
    
    try:
        # Save uploaded file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())
        unique_filename = f"{timestamp}_{unique_id}-{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        
        # Create document record
        document = Document(
            id=unique_id,
            filename=unique_filename,
            original_filename=file.filename,
            file_path=file_path,
            public_url=public_url,
            subject_url=subject_url if subject_url else None,
            effective_date=effective_date,
            user_id=current_user.id,
            status='pending'
        )
        db.session.add(document)
        db.session.commit()
        
        # Queue background task for claim extraction
        task_result = task_runner.run_extraction(document.id)
        
        # Create processing job record
        job = ProcessingJob(
            id=task_result['id'],
            document_id=document.id,
            job_type='extract_claims',
            status='completed' if task_result.get('is_sync') else 'pending'
        )
        db.session.add(job)
        db.session.commit()
        
        logger.info(f"Document {document.id} uploaded by user {current_user.id}, processing task {task_result['id']} queued")
        
        # Flash success message and redirect
        if task_result.get('is_sync'):
            flash('File uploaded successfully. Claims have been extracted and are ready for review.', 'success')
        else:
            flash('File uploaded successfully. Processing will begin shortly.', 'success')
        return redirect(url_for('document_status', document_id=document.id))
        
    except Exception as e:
        logger.exception(f"Error uploading file: {str(e)}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/document/<document_id>')
@login_required
def document_status(document_id):
    """View document processing status and claims"""
    document = Document.query.filter_by(id=document_id, user_id=current_user.id).first()
    
    if not document:
        flash('Document not found or access denied')
        return redirect(url_for('dashboard'))
    
    # Get draft claims for this document
    draft_claims = DraftClaim.query.filter_by(document_id=document_id).order_by(DraftClaim.page_number, DraftClaim.id).all()
    
    # Get processing jobs
    jobs = ProcessingJob.query.filter_by(document_id=document_id).order_by(ProcessingJob.started_at.desc()).all()
    
    return render_template('document_status.html',
                         document=document,
                         claims=draft_claims,
                         jobs=jobs)

@app.route('/document/<document_id>/edit', methods=['POST'])
@login_required
def edit_document(document_id):
    """Edit document metadata (public_url and effective_date)"""
    document = Document.query.filter_by(id=document_id, user_id=current_user.id).first()
    
    if not document:
        return jsonify({'error': 'Document not found or access denied'}), 404
    
    # Get new values
    public_url = request.json.get('public_url', '').strip()
    effective_date_str = request.json.get('effective_date', '').strip()
    
    # Validate if provided
    if public_url:
        if not public_url.startswith(('http://', 'https://')):
            return jsonify({'error': 'Public URL must start with http:// or https://'}), 400
        document.public_url = public_url
    
    if effective_date_str:
        try:
            effective_date = datetime.strptime(effective_date_str, '%Y-%m-%d').date()
            document.effective_date = effective_date
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Document updated successfully',
        'document': document.to_dict()
    })

@app.route('/document/<document_id>/reprocess', methods=['POST'])
@login_required
def reprocess_document(document_id):
    """Reprocess a document to extract claims again"""
    document = Document.query.filter_by(id=document_id, user_id=current_user.id).first()
    
    if not document:
        return jsonify({'error': 'Document not found or access denied'}), 404
    
    # Delete existing draft claims (keep published ones)
    DraftClaim.query.filter_by(document_id=document_id, status='draft').delete()
    
    # Reset document status
    document.status = 'pending'
    document.error_message = None
    db.session.commit()
    
    # Queue new extraction task
    task_result = task_runner.run_extraction(document_id)
    
    # Create processing job record
    job = ProcessingJob(
        id=task_result['id'],
        document_id=document_id,
        job_type='extract_claims',
        status='completed' if task_result.get('is_sync') else 'pending'
    )
    db.session.add(job)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'task_id': task_result['id'],
        'message': 'Document queued for reprocessing' if not task_result.get('is_sync') else 'Document reprocessed'
    })

@app.route('/api/jobs')
@login_required  
def api_jobs_status():
    """Quick endpoint to see all processing jobs"""
    jobs = ProcessingJob.query.order_by(ProcessingJob.started_at.desc().nullslast()).limit(20).all()
    return jsonify({
        'jobs': [
            {
                'id': job.id,
                'document_id': job.document_id,
                'status': job.status,
                'job_type': job.job_type,
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'error': job.error_message
            } for job in jobs
        ]
    })

@app.route('/api/document/<document_id>/status')
@login_required
def api_document_status(document_id):
    """API endpoint for document processing status"""
    document = Document.query.filter_by(id=document_id, user_id=current_user.id).first()
    
    if not document:
        return jsonify({'error': 'Document not found or access denied'}), 404
    
    # Get counts
    total_claims = document.draft_claims.count()
    draft_claims = document.draft_claims.filter_by(status='draft').count()
    published_claims = document.draft_claims.filter_by(status='published').count()
    
    # Get latest job
    latest_job = ProcessingJob.query.filter_by(document_id=document_id).order_by(ProcessingJob.started_at.desc()).first()
    
    return jsonify({
        'document': document.to_dict(),
        'claims': {
            'total': total_claims,
            'draft': draft_claims,
            'published': published_claims
        },
        'latest_job': latest_job.to_dict() if latest_job else None
    })

@app.route('/api/claims/<document_id>')
@login_required
def api_get_claims(document_id):
    """API endpoint to get claims for a document"""
    document = Document.query.filter_by(id=document_id, user_id=current_user.id).first()
    
    if not document:
        return jsonify({'error': 'Document not found or access denied'}), 404
    
    # Get filter parameters
    status = request.args.get('status', 'all')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    
    # Build query
    query = DraftClaim.query.filter_by(document_id=document_id)
    
    if status != 'all':
        query = query.filter_by(status=status)
    
    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'claims': [claim.to_dict() for claim in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    })

@app.route('/api/claims/<int:claim_id>/approve', methods=['POST'])
@login_required
def approve_claim(claim_id):
    """Approve a draft claim for publishing"""
    claim = DraftClaim.query.get(claim_id)
    
    if not claim:
        return jsonify({'error': 'Claim not found'}), 404
    
    # Check document ownership
    document = Document.query.filter_by(id=claim.document_id, user_id=current_user.id).first()
    if not document:
        return jsonify({'error': 'Access denied'}), 403
    
    claim.status = 'approved'
    
    # Clear verification flags since user has approved the URLs
    if claim.claim_data:
        claim.claim_data['urls_need_verification'] = False
        claim.claim_data['subject_url_verified'] = True
    else:
        claim.claim_data = {
            'urls_need_verification': False,
            'subject_url_verified': True
        }
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Claim approved for publishing'
    })

@app.route('/api/claims/<int:claim_id>/reject', methods=['POST'])
@login_required  
def reject_claim(claim_id):
    """Reject a draft claim"""
    claim = DraftClaim.query.get(claim_id)
    
    if not claim:
        return jsonify({'error': 'Claim not found'}), 404
    
    # Check document ownership
    document = Document.query.filter_by(id=claim.document_id, user_id=current_user.id).first()
    if not document:
        return jsonify({'error': 'Access denied'}), 403
    
    claim.status = 'rejected'
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Claim rejected'
    })

@app.route('/api/document/<document_id>/claims', methods=['GET'])
@login_required
def get_document_claims(document_id):
    """Get all claims for a document"""
    document = Document.query.filter_by(id=document_id, user_id=current_user.id).first()
    
    if not document:
        return jsonify({'error': 'Document not found or access denied'}), 404
    
    claims = []
    for claim in document.draft_claims:
        claims.append({
            'id': claim.id,
            'subject': claim.subject,
            'statement': claim.statement,
            'object': claim.object,
            'status': claim.status,
            'claim_data': claim.claim_data,
            'page_number': claim.page_number
        })
    
    return jsonify({'claims': claims})

@app.route('/api/claims/<int:claim_id>/status', methods=['PATCH'])
@login_required
def update_claim_status(claim_id):
    """Update claim status"""
    claim = DraftClaim.query.get(claim_id)
    
    if not claim:
        return jsonify({'error': 'Claim not found'}), 404
    
    # Check document ownership
    document = Document.query.filter_by(id=claim.document_id, user_id=current_user.id).first()
    if not document:
        return jsonify({'error': 'Access denied'}), 403
    
    data = request.get_json()
    if 'status' in data:
        claim.status = data['status']
        db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/document/<document_id>/publish', methods=['POST'])
@login_required
def publish_claims(document_id):
    """Publish approved claims to LinkedTrust using user's stored tokens"""
    document = Document.query.filter_by(id=document_id, user_id=current_user.id).first()
    
    if not document:
        return jsonify({'error': 'Document not found or access denied'}), 404
    
    # Get approved claims
    approved_claims = DraftClaim.query.filter_by(document_id=document_id, status='approved').all()
    
    if not approved_claims:
        return jsonify({'error': 'No approved claims to publish'}), 400
    
    try:
        # Get user's LinkedTrust client with stored tokens
        client = current_user.get_linkedtrust_client()
        
        published_count = 0
        failed_count = 0
        
        for claim in approved_claims:
            try:
                # Prepare claim payload
                claim_payload = {
                    'subject': claim.subject,
                    'claim': claim.claim_data.get('claim') if claim.claim_data else None,  # The predicate
                    'statement': claim.statement,
                    'object': claim.object,
                    'sourceURI': document.public_url or f"{request.url_root}document/{document_id}",
                    'effectiveDate': document.effective_date.isoformat() if document.effective_date else datetime.utcnow().isoformat(),
                    'howKnown': claim.claim_data.get('howKnown', 'DOCUMENT') if claim.claim_data else 'DOCUMENT',
                    'confidence': claim.claim_data.get('confidence') if claim.claim_data else None,
                    'issuerId': current_user.email,
                    'issuerIdType': 'EMAIL'
                }
                
                # Add additional fields from claim_data if present
                if claim.claim_data:
                    # Add aspect if present
                    if claim.claim_data.get('aspect'):
                        claim_payload['aspect'] = claim.claim_data['aspect']
                    # Add quantitative fields
                    if claim.claim_data.get('amt') is not None:
                        claim_payload['amt'] = claim.claim_data['amt']
                    if claim.claim_data.get('unit'):
                        claim_payload['unit'] = claim.claim_data['unit']
                    # Add rating fields
                    if claim.claim_data.get('score') is not None:
                        claim_payload['score'] = claim.claim_data['score']
                    if claim.claim_data.get('stars') is not None:
                        claim_payload['stars'] = claim.claim_data['stars']
                
                # Remove None values
                claim_payload = {k: v for k, v in claim_payload.items() if v is not None}
                
                # Publish to LinkedTrust
                result = client.create_claim(claim_payload)
                
                if result.get('success', True):  # Assume success if no explicit success field
                    claim.status = 'published'
                    claim.published_at = datetime.utcnow()
                    claim.linkedtrust_response = result
                    published_count += 1
                else:
                    logger.error(f"Failed to publish claim {claim.id}: {result}")
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"Error publishing claim {claim.id}: {e}")
                failed_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Published {published_count} claims' + (f', {failed_count} failed' if failed_count > 0 else ''),
            'published': published_count,
            'failed': failed_count
        })
        
    except Exception as e:
        logger.error(f"Error publishing claims: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/document/<document_id>/delete', methods=['POST'])
@login_required
def delete_document(document_id):
    """Delete a document and its draft claims from local database only"""
    try:
        # Get the document - ensure user owns it
        document = Document.query.filter_by(id=document_id, user_id=current_user.id).first()
        
        if not document:
            return jsonify({'success': False, 'error': 'Document not found or access denied'}), 404
        
        # Delete all draft claims associated with this document
        DraftClaim.query.filter_by(document_id=document_id).delete()
        
        # Delete any processing jobs
        ProcessingJob.query.filter_by(document_id=document_id).delete()
        
        # Delete the document file from disk if it exists
        if document.file_path and os.path.exists(document.file_path):
            try:
                os.remove(document.file_path)
            except Exception as e:
                logger.warning(f"Could not delete file {document.file_path}: {e}")
        
        # Delete the document record
        db.session.delete(document)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Document deleted successfully'})
    
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/document/<document_id>/restart', methods=['POST'])
@login_required
def restart_extraction(document_id):
    """Restart the extraction process for a document"""
    logger.info(f"Restart extraction requested for document {document_id} by user {current_user.id if current_user.is_authenticated else 'anonymous'}")
    try:
        # Get the document - ensure user owns it
        document = Document.query.filter_by(id=document_id, user_id=current_user.id).first()
        
        if not document:
            return jsonify({'success': False, 'error': 'Document not found or access denied'}), 404
        
        # Delete existing draft claims (but not published ones)
        DraftClaim.query.filter_by(document_id=document_id, status='draft').delete()
        
        # Reset document status
        document.status = 'pending'
        document.error_message = None
        document.processing_started_at = None
        document.processing_completed_at = None
        db.session.commit()
        
        # Queue extraction task
        task_result = task_runner.run_extraction(document_id)
        
        # Create processing job record
        job = ProcessingJob(
            id=task_result['id'],
            document_id=document_id,
            job_type='extract_claims',
            status='completed' if task_result.get('is_sync') else 'pending'
        )
        db.session.add(job)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'task_id': task_result['id'],
            'message': 'Extraction restarted successfully'
        })
    
    except Exception as e:
        logger.error(f"Error restarting extraction for document {document_id}: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/published-claims')
@login_required
def get_published_claims():
    """Get published claims from LinkedTrust for current user"""
    try:
        # Get LinkedTrust client with user's auth
        client = current_user.get_linkedtrust_client()
        
        # Query for claims issued by this service
        claims = client.get_claims({
            'issuer_id': 'https://extract.linkedtrust.us',
            'limit': 100
        })
        
        return jsonify({
            'success': True,
            'claims': claims
        })
        
    except Exception as e:
        logger.error(f"Error fetching published claims: {e}")
        return jsonify({'error': 'Failed to fetch published claims'}), 500

@app.route('/api/claim/<claim_url>/validations')
@login_required
def get_claim_validations(claim_url):
    """Get validations for a specific claim"""
    try:
        # Get LinkedTrust client with user's auth
        client = current_user.get_linkedtrust_client()
        
        # Get validations for this claim
        validations = client.get_validations_for_claim(claim_url)
        
        return jsonify({
            'success': True,
            'validations': validations
        })
        
    except Exception as e:
        logger.error(f"Error fetching validations: {e}")
        return jsonify({'error': 'Failed to fetch validations'}), 500

@app.route('/validate/<path:claim_url>')
def validate_claim_page(claim_url):
    """Public validation page for a claim"""
    try:
        # Decode the claim URL if needed
        import urllib.parse
        claim_url = urllib.parse.unquote(claim_url)
        
        # Fetch claim details from LinkedTrust (public endpoint)
        # For now, we'll try to get it from our cache or draft claims
        # In production, this should query LinkedTrust directly
        
        # Check if it's one of our published claims
        draft_claim = DraftClaim.query.filter_by(linkedtrust_claim_url=claim_url).first()
        
        if draft_claim:
            claim_data = {
                'url': claim_url,
                'subject': draft_claim.subject,
                'statement': draft_claim.statement,
                'object': draft_claim.object,
                'sourceURI': draft_claim.document.public_url,
                'effectiveDate': draft_claim.document.effective_date.isoformat(),
                'amt': draft_claim.claim_data.get('amt') if draft_claim.claim_data else None,
                'unit': draft_claim.claim_data.get('unit') if draft_claim.claim_data else None
            }
        else:
            # Try to fetch from LinkedTrust API (public endpoint)
            # This would need a public API endpoint that doesn't require auth
            claim_data = {
                'url': claim_url,
                'statement': 'Claim details will be loaded from LinkedTrust',
                'sourceURI': '#'
            }
        
        return render_template('validate.html', claim=claim_data)
        
    except Exception as e:
        logger.error(f"Error loading validation page: {e}")
        flash('Error loading claim for validation')
        return redirect(url_for('index'))

@app.route('/api/validate-claim', methods=['POST'])
@login_required
def validate_claim():
    """Submit a validation claim"""
    try:
        data = request.json
        
        # Get the original claim URL (this becomes the subject)
        original_claim_url = data.get('claim_url')
        if not original_claim_url:
            return jsonify({'error': 'Original claim URL required'}), 400
        
        # Build the validation claim
        validation_claim = {
            'subject': original_claim_url,  # The claim being validated
            'claim': data.get('validation_type'),  # 'validated', 'impact', or 'disputed'
            'statement': data.get('statement'),
            'howKnown': data.get('how_known'),  # FIRST_HAND, SECOND_HAND, or FROM_SOURCE
            'confidence': 0.95 if data.get('validation_type') == 'validated' else 0.8
        }
        
        # Handle source
        if data.get('how_known') == 'FROM_SOURCE' and data.get('external_source'):
            # If citing an external source, that becomes the sourceURI
            validation_claim['sourceURI'] = data.get('external_source')
        else:
            # Otherwise, the validator is the source
            validation_claim['sourceURI'] = f"https://extract.linkedtrust.us/user/{current_user.id}"
        
        # Handle impact-specific fields
        if data.get('validation_type') == 'impact':
            # Determine the beneficiary (object)
            beneficiary_type = data.get('beneficiary_type')
            if beneficiary_type == 'self':
                validation_claim['object'] = f"https://extract.linkedtrust.us/user/{current_user.id}"
            elif beneficiary_type == 'other' and data.get('beneficiary_id'):
                # Try to make it a URI if it's not already
                beneficiary = data.get('beneficiary_id')
                if not beneficiary.startswith(('http://', 'https://')):
                    # Could be a Wikipedia entity or local identifier
                    if ' ' not in beneficiary and beneficiary.replace('_', '').replace('-', '').isalnum():
                        # Might be a Wikipedia handle
                        validation_claim['object'] = f"https://en.wikipedia.org/wiki/{beneficiary.replace(' ', '_')}"
                    else:
                        # Create a local identifier
                        validation_claim['object'] = f"https://extract.linkedtrust.us/entity/{urllib.parse.quote(beneficiary)}"
                else:
                    validation_claim['object'] = beneficiary
            elif beneficiary_type == 'community':
                # Use a community identifier
                validation_claim['object'] = f"https://extract.linkedtrust.us/community/{current_user.id}"
            
            # Add impact amount if provided
            if data.get('impact_amount'):
                validation_claim['amt'] = float(data.get('impact_amount'))
                if data.get('impact_unit'):
                    validation_claim['unit'] = data.get('impact_unit')
        
        # Add validator context as additional claims if provided
        if data.get('validator_context'):
            # This could be stored as a separate claim about the validator
            # For now, add it to the statement
            validation_claim['statement'] += f"\n\nValidator context: {data.get('validator_context')}"
        
        # Submit to LinkedTrust
        client = current_user.get_linkedtrust_client()
        response = client.create_claim(validation_claim)
        
        if response.get('success'):
            return jsonify({
                'success': True,
                'message': 'Validation submitted successfully',
                'validation_url': response.get('data', {}).get('url')
            })
        else:
            return jsonify({
                'success': False,
                'error': response.get('error', 'Failed to submit validation')
            }), 400
            
    except Exception as e:
        logger.error(f"Error submitting validation: {e}")
        return jsonify({'error': f'Validation failed: {str(e)}'}), 500

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(e):
    logger.error(f"Server error: {e}")
    return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/url-suggestions', methods=['POST'])
def get_url_suggestions():
    """Get URL suggestions for an entity"""
    try:
        data = request.get_json()
        current_url = data.get('currentUrl', '')
        entity_type = data.get('entityType', 'unknown')
        url_type = data.get('urlType', 'subject')
        
        # Import here to avoid circular imports
        from url_generator import get_url_correction_suggestions, extract_entity_from_url
        
        # Extract entity name from current URL
        entity_name = extract_entity_from_url(current_url)
        
        # Get suggestions
        suggestions = get_url_correction_suggestions(entity_name, entity_type)
        
        return jsonify({
            'success': True,
            'suggestions': suggestions,
            'entity_name': entity_name,
            'entity_type': entity_type
        })
        
    except Exception as e:
        logger.error(f"Error getting URL suggestions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/claims/<int:claim_id>/update-url', methods=['POST'])
@login_required
def update_claim_url(claim_id):
    """Update a claim's URL"""
    try:
        # Get the claim
        claim = DraftClaim.query.get(claim_id)
        if not claim:
            return jsonify({'success': False, 'error': 'Claim not found'}), 404
            
        # Check ownership
        document = Document.query.filter_by(id=claim.document_id, user_id=current_user.id).first()
        if not document:
            return jsonify({'success': False, 'error': 'Access denied'}), 403
            
        # Only allow editing draft claims
        if claim.status != 'draft':
            return jsonify({'success': False, 'error': 'Can only edit draft claims'}), 400
        
        data = request.get_json()
        url_type = data.get('urlType')  # 'subject' or 'object'
        new_url = data.get('newUrl')
        
        if not all([url_type, new_url]):
            return jsonify({'success': False, 'error': 'Missing required parameters'}), 400
            
        if not new_url.startswith(('http://', 'https://')):
            return jsonify({'success': False, 'error': 'URL must start with http:// or https://'}), 400
        
        # Update the appropriate field
        if url_type == 'subject':
            claim.subject = new_url
            logger.info(f"Setting subject to: {new_url}")
        elif url_type == 'object':
            claim.object = new_url
            logger.info(f"Setting object to: {new_url}")
        else:
            return jsonify({'success': False, 'error': 'Invalid URL type'}), 400
        
        try:
            db.session.commit()
            logger.info(f"Successfully committed {url_type} URL change for claim {claim_id}")
            
            # If this is a subject URL update, save it as a verified organization
            if url_type == 'subject' and claim.subject.startswith(('http://', 'https://')):
                try:
                    # Extract original organization name from the claim data or URN
                    original_subject = data.get('originalSubject', '')
                    if original_subject.startswith('urn:local:org:'):
                        org_name = original_subject.replace('urn:local:org:', '').replace('_', ' ')
                        
                        from models import VerifiedOrganization
                        VerifiedOrganization.add_verified_organization(
                            org_name=org_name,
                            official_url=new_url,
                            user_id=current_user.id if current_user else None,
                            org_type='organization'
                        )
                        logger.info(f"Added verified organization: {org_name} -> {new_url}")
                except Exception as org_save_error:
                    logger.warning(f"Could not save verified organization: {org_save_error}")
                    
        except Exception as commit_error:
            logger.error(f"Database commit failed: {commit_error}")
            db.session.rollback()
            return jsonify({'success': False, 'error': f'Database save failed: {str(commit_error)}'}), 500
        
        logger.info(f"Updated {url_type} URL for claim {claim_id} to {new_url}")
        
        return jsonify({
            'success': True,
            'message': f'URL updated successfully',
            'claim_id': claim_id,
            'url_type': url_type,
            'new_url': new_url
        })
        
    except Exception as e:
        logger.error(f"Error updating claim URL: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/search-urls', methods=['POST'])
@login_required
def search_urls():
    """Search for additional URLs using custom search terms"""
    try:
        data = request.get_json()
        search_term = data.get('searchTerm', '').strip()
        
        if not search_term:
            return jsonify({'success': False, 'error': 'Search term is required'}), 400
        
        # Import the URL search functionality
        from url_resolver import search_organization_urls
        
        logger.info(f"User search for URLs: '{search_term}'")
        
        # Search for URLs using the provided search term
        try:
            candidates = search_organization_urls(search_term)
            
            # Format results for the frontend
            results = []
            for title, url, confidence in candidates[:10]:  # Return top 10 results
                results.append({
                    'url': url,
                    'title': title,
                    'confidence': confidence
                })
            
            logger.info(f"User search returned {len(results)} results for '{search_term}'")
            
            return jsonify({
                'success': True,
                'results': results,
                'search_term': search_term,
                'total_results': len(results)
            })
            
        except Exception as search_error:
            logger.error(f"Search error for '{search_term}': {search_error}")
            return jsonify({
                'success': False,
                'error': f'Search failed: {str(search_error)}',
                'results': []
            }), 500
        
    except Exception as e:
        logger.error(f"Error in search URLs endpoint: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# CLI commands for database management
@app.cli.command()
def init_db():
    """Initialize the database"""
    create_tables(app, db)
    print("Database initialized!")

@app.cli.command()
def create_test_user():
    """Create a test user for development"""
    test_user = User(
        id='test_user_1',
        email='test@example.com',
        name='Test User',
        provider='test'
    )
    existing = db.session.get(User, 'test_user_1')
    if not existing:
        db.session.add(test_user)
        db.session.commit()
        print("Test user created: test@example.com")
    else:
        print("Test user already exists")

if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5050))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    print("🚀 Starting Linked Claims Extraction Service")
    print(f"📍 Server running on http://localhost:{port}")
    print("📄 Upload PDFs to extract claims")
    
    app.run(debug=debug, host="0.0.0.0", port=port)
