"""
Database models for the Linked Claims Extraction Service
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class User(db.Model):
    """User model for authentication and session management"""
    __tablename__ = 'users'
    
    id = db.Column(db.String(255), primary_key=True)  # UUID or user ID from OAuth
    email = db.Column(db.String(255), unique=True, nullable=True)
    name = db.Column(db.String(255), nullable=True)
    
    # OAuth tokens
    access_token = db.Column(db.Text, nullable=True)
    refresh_token = db.Column(db.Text, nullable=True)
    
    # OAuth provider info
    provider = db.Column(db.String(50), nullable=True)  # 'google', 'github', 'linkedtrust'
    provider_id = db.Column(db.String(255), nullable=True)  # ID from provider
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    documents = db.relationship('Document', backref='uploader', lazy='dynamic', 
                               foreign_keys='Document.user_id')
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'provider': self.provider,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

class Document(db.Model):
    """Track uploaded PDF documents"""
    __tablename__ = 'documents'
    
    id = db.Column(db.String(36), primary_key=True)  # UUID
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    
    # Public URL for the document (this becomes the source URI for all claims)
    public_url = db.Column(db.String(500), nullable=False)

    # Organization/subject URL (used as default subject when extractor returns blank)
    subject_url = db.Column(db.String(500), nullable=True)

    # Document metadata
    effective_date = db.Column(db.Date, nullable=False)
    user_id = db.Column(db.String(255), db.ForeignKey('users.id'), nullable=False)  # User who uploaded the document
    upload_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Processing status
    status = db.Column(db.String(50), default='pending', nullable=False)
    # Status values: 'pending', 'processing', 'completed', 'failed'
    
    # Error tracking
    error_message = db.Column(db.Text, nullable=True)
    
    # Timestamps
    processing_started_at = db.Column(db.DateTime, nullable=True)
    processing_completed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    draft_claims = db.relationship('DraftClaim', backref='document', lazy='dynamic', cascade='all, delete-orphan')
    processing_jobs = db.relationship('ProcessingJob', backref='document', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        # Derive total claims count from actual draft claims
        total_claims = self.draft_claims.count()
        
        return {
            'id': self.id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'public_url': self.public_url,
            'effective_date': self.effective_date.isoformat() if self.effective_date else None,
            'upload_time': self.upload_time.isoformat() if self.upload_time else None,
            'status': self.status,
            'total_claims_found': total_claims,
            'error_message': self.error_message,
            'processing_started_at': self.processing_started_at.isoformat() if self.processing_started_at else None,
            'processing_completed_at': self.processing_completed_at.isoformat() if self.processing_completed_at else None
        }


class DraftClaim(db.Model):
    """Store draft claims extracted from documents before publishing"""
    __tablename__ = 'draft_claims'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    document_id = db.Column(db.String(36), db.ForeignKey('documents.id'), nullable=False)
    
    # Core claim components (following linked claims spec)
    subject = db.Column(db.String(500), nullable=False)  # Must be a URI
    statement = db.Column(db.Text, nullable=False)
    object = db.Column(db.String(500), nullable=True)  # Must be a URI if present
    
    # Additional claim data (stored as JSON for flexibility)
    claim_data = db.Column(db.JSON, nullable=True)
    # Can include: howKnown, confidence, aspect, score, stars, amt, unit, howMeasured
    
    # Context
    page_number = db.Column(db.Integer, nullable=True)
    page_text_snippet = db.Column(db.Text, nullable=True)  # Context from the page
    
    # Status tracking
    status = db.Column(db.String(50), default='draft', nullable=False)
    # Status values: 'draft', 'approved', 'published', 'rejected'
    
    # LinkedTrust tracking (after publishing)
    published_at = db.Column(db.DateTime, nullable=True)
    linkedtrust_claim_url = db.Column(db.String(500), nullable=True)  # The claim's URI on LinkedTrust
    linkedtrust_response = db.Column(db.JSON, nullable=True)  # Full response from LinkedTrust API
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        # Build the full claim including inherited document properties
        claim = {
            'id': self.id,
            'subject': self.subject,
            'statement': self.statement,
            'object': self.object,
            'sourceURI': self.document.public_url,  # Always from document
            'effectiveDate': self.document.effective_date.isoformat() if self.document.effective_date else None,  # Always from document
            'page_number': self.page_number,
            'page_text_snippet': self.page_text_snippet,
            'status': self.status,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'linkedtrust_claim_url': self.linkedtrust_claim_url,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        # Add any additional claim data
        if self.claim_data:
            claim.update(self.claim_data)
        
        return claim


class ProcessingJob(db.Model):
    """Track background processing jobs"""
    __tablename__ = 'processing_jobs'
    
    id = db.Column(db.String(36), primary_key=True)  # Celery task ID
    document_id = db.Column(db.String(36), db.ForeignKey('documents.id'), nullable=False)
    
    job_type = db.Column(db.String(50), nullable=False)
    # Job types: 'extract_claims', 'publish_claims'
    
    status = db.Column(db.String(50), default='pending', nullable=False)
    # Status values: 'pending', 'started', 'success', 'failure', 'retry'
    
    # Job metadata (for batching if needed)
    page_start = db.Column(db.Integer, nullable=True)
    page_end = db.Column(db.Integer, nullable=True)
    
    # Tracking
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    retry_count = db.Column(db.Integer, default=0)
    
    def to_dict(self):
        return {
            'id': self.id,
            'document_id': self.document_id,
            'job_type': self.job_type,
            'status': self.status,
            'page_start': self.page_start,
            'page_end': self.page_end,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message,
            'retry_count': self.retry_count
        }


class ClaimCache(db.Model):
    """
    READ-ONLY cache of claims and validations from live.linkedtrust.us
    This is populated by periodic queries to the LinkedTrust API
    """
    __tablename__ = 'claim_cache'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # The claim URI on LinkedTrust
    claim_url = db.Column(db.String(500), unique=True, nullable=False)
    
    # Full claim data from LinkedTrust
    claim_data = db.Column(db.JSON, nullable=False)
    
    # Track if this claim originated from our service
    origin_document_id = db.Column(db.String(36), db.ForeignKey('documents.id'), nullable=True)
    
    # Validation claims that reference this claim
    validation_claims = db.Column(db.JSON, nullable=True)  # Array of validation claim URLs
    
    # Cache metadata
    fetched_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_checked = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def to_dict(self):
        return {
            'claim_url': self.claim_url,
            'claim_data': self.claim_data,
            'validation_claims': self.validation_claims,
            'fetched_at': self.fetched_at.isoformat() if self.fetched_at else None,
            'last_checked': self.last_checked.isoformat() if self.last_checked else None
        }


class VerifiedOrganization(db.Model):
    """
    Store verified organization name -> URL mappings to avoid repeated web searches
    """
    __tablename__ = 'verified_organizations'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # Organization name as it appears in documents (normalized)
    organization_name = db.Column(db.String(255), unique=True, nullable=False, index=True)
    
    # Verified official URL
    official_url = db.Column(db.String(500), nullable=False)
    
    # Optional: organization type or category
    organization_type = db.Column(db.String(100), nullable=True)
    
    # Who verified this mapping
    verified_by_user_id = db.Column(db.String(255), db.ForeignKey('users.id'), nullable=True)
    
    # When it was verified
    verified_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Track usage
    times_used = db.Column(db.Integer, default=0, nullable=False)
    last_used = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'organization_name': self.organization_name,
            'official_url': self.official_url,
            'organization_type': self.organization_type,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'times_used': self.times_used,
            'last_used': self.last_used.isoformat() if self.last_used else None
        }
    
    @staticmethod
    def normalize_name(name):
        """Normalize organization name for consistent lookup"""
        return name.lower().strip().replace('_', ' ').replace('-', ' ')
    
    @classmethod
    def get_verified_url(cls, org_name):
        """Get verified URL for an organization name"""
        normalized = cls.normalize_name(org_name)
        org = cls.query.filter_by(organization_name=normalized).first()
        if org:
            # Update usage tracking
            org.times_used += 1
            org.last_used = datetime.utcnow()
            db.session.commit()
            return org.official_url
        return None
    
    @classmethod 
    def add_verified_organization(cls, org_name, official_url, user_id=None, org_type=None):
        """Add a new verified organization mapping"""
        normalized = cls.normalize_name(org_name)
        
        # Check if already exists
        existing = cls.query.filter_by(organization_name=normalized).first()
        if existing:
            # Update existing
            existing.official_url = official_url
            existing.verified_by_user_id = user_id
            existing.verified_at = datetime.utcnow()
            existing.organization_type = org_type
        else:
            # Create new
            org = cls(
                organization_name=normalized,
                official_url=official_url,
                verified_by_user_id=user_id,
                organization_type=org_type
            )
            db.session.add(org)
        
        db.session.commit()
        return True