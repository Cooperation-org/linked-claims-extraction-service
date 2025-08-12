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
import tasks  # Import tasks to register them with Celery

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, template_folder='templates')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here')

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

# Initialize Celery
celery = create_celery_app(app)

# Initialize authentication
login_manager = init_auth(app)
create_auth_routes(app)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Main page - redirect to login if not authenticated"""
    if not current_user.is_authenticated:
        return redirect('/auth/login')
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
        return render_template('upload.html')
    
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
            effective_date=effective_date,
            user_id=current_user.id,
            status='pending'
        )
        db.session.add(document)
        db.session.commit()
        
        # Queue background task for claim extraction
        from tasks import extract_claims_from_document
        task = extract_claims_from_document.delay(document.id)
        
        # Create processing job record
        job = ProcessingJob(
            id=task.id,
            document_id=document.id,
            job_type='extract_claims',
            status='pending'
        )
        db.session.add(job)
        db.session.commit()
        
        logger.info(f"Document {document.id} uploaded by user {current_user.id}, processing task {task.id} queued")
        
        # Flash success message and redirect
        flash('File uploaded successfully. Processing will begin shortly.', 'success')
        return redirect(url_for('document_status', document_id=document.id))
        
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
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
    from tasks import extract_claims_from_document
    task = extract_claims_from_document.delay(document_id)
    
    # Create processing job record
    job = ProcessingJob(
        id=task.id,
        document_id=document_id,
        job_type='extract_claims',
        status='pending'
    )
    db.session.add(job)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'task_id': task.id,
        'message': 'Document queued for reprocessing'
    })

@app.route('/api/jobs')
@login_required  
def api_jobs_status():
    """Quick endpoint to see all processing jobs"""
    jobs = ProcessingJob.query.order_by(ProcessingJob.created_at.desc()).limit(20).all()
    return jsonify({
        'jobs': [
            {
                'id': job.id,
                'document_id': job.document_id,
                'status': job.status,
                'job_type': job.job_type,
                'created': job.created_at.isoformat() if job.created_at else None,
                'updated': job.updated_at.isoformat() if job.updated_at else None,
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

@app.route('/api/document/<document_id>/publish', methods=['POST'])
@login_required
def publish_claims(document_id):
    """Publish approved claims to LinkedTrust"""
    document = Document.query.filter_by(id=document_id, user_id=current_user.id).first()
    
    if not document:
        return jsonify({'error': 'Document not found or access denied'}), 404
    
    # Get specific claim IDs if provided, otherwise all approved
    claim_ids = request.json.get('claim_ids') if request.json else None
    
    # Check if there are approved claims
    query = DraftClaim.query.filter_by(document_id=document_id, status='approved')
    if claim_ids:
        query = query.filter(DraftClaim.id.in_(claim_ids))
    
    approved_count = query.count()
    
    if approved_count == 0:
        return jsonify({'error': 'No approved claims to publish'}), 400
    
    # Queue publishing task
    from tasks import publish_claims_to_linkedtrust
    task = publish_claims_to_linkedtrust.delay(document_id, claim_ids)
    
    # Create processing job record
    job = ProcessingJob(
        id=task.id,
        document_id=document_id,
        job_type='publish_claims',
        status='pending'
    )
    db.session.add(job)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'task_id': task.id,
        'message': f'Publishing {approved_count} claims to LinkedTrust'
    })

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