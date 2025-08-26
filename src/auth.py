"""
Authentication and user session management
"""
import os
import secrets
from flask import session, redirect, url_for, request, jsonify, render_template_string
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user
from datetime import datetime, timedelta
from linkedtrust_client import LinkedTrustClient
import logging

logger = logging.getLogger(__name__)

# Initialize Flask-Login
login_manager = LoginManager()

class AuthUser(UserMixin):
    """User class for Flask-Login that wraps database User model"""
    
    def __init__(self, db_user):
        self.db_user = db_user
        self.id = db_user.id
        self.email = db_user.email
        self.name = db_user.name
        self.access_token = db_user.access_token
        self.refresh_token = db_user.refresh_token
        self.authenticated = True
    
    def get_id(self):
        return self.id
    
    def get_linkedtrust_client(self):
        """Get a LinkedTrustClient configured with user's tokens"""
        client = LinkedTrustClient(access_token=self.access_token)
        if self.refresh_token:
            client.refresh_token = self.refresh_token
        return client


@login_manager.user_loader
def load_user(user_id):
    """Load user from database"""
    from models import User, db
    db_user = db.session.get(User, user_id)
    if db_user:
        return AuthUser(db_user)
    return None


def init_auth(app):
    """Initialize authentication for Flask app"""
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    
    # Session configuration
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
    
    # OAuth configuration
    app.config['GOOGLE_CLIENT_ID'] = os.getenv('GOOGLE_CLIENT_ID')
    app.config['GOOGLE_CLIENT_SECRET'] = os.getenv('GOOGLE_CLIENT_SECRET')
    app.config['GITHUB_CLIENT_ID'] = os.getenv('GITHUB_CLIENT_ID')
    app.config['GITHUB_CLIENT_SECRET'] = os.getenv('GITHUB_CLIENT_SECRET')
    
    return login_manager


def get_or_create_user(user_id, email=None, name=None, provider='linkedtrust', 
                       access_token=None, refresh_token=None):
    """Get or create user in database"""
    from models import User, db
    
    # Try to find user by ID first, then by email
    db_user = db.session.get(User, user_id)
    if not db_user and email:
        db_user = User.query.filter_by(email=email).first()
    
    if not db_user:
        # Create new user
        db_user = User(
            id=user_id,
            email=email,
            name=name,
            access_token=access_token,
            refresh_token=refresh_token,
            provider=provider,
            provider_id=user_id
        )
        db.session.add(db_user)
    else:
        # Update existing user
        if email:
            db_user.email = email
        if name:
            db_user.name = name
        if access_token:
            db_user.access_token = access_token
        if refresh_token:
            db_user.refresh_token = refresh_token
        db_user.last_login = datetime.utcnow()
    
    db.session.commit()
    return db_user

def create_auth_routes(app):
    """Create authentication routes"""
    
    @app.route('/auth/login', methods=['GET', 'POST'], endpoint='login')
    def login():
        """Login page and handler"""
        if request.method == 'GET':
            # Check if OAuth is configured
            google_client_id = app.config.get('GOOGLE_CLIENT_ID')
            github_client_id = app.config.get('GITHUB_CLIENT_ID')
            
            # Return login page with template variables
            from flask import render_template
            return render_template('login.html', google_client_id=google_client_id, github_client_id=github_client_id)
        
        # Handle email/password login
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        try:
            # Authenticate with LinkedTrust backend
            client = LinkedTrustClient()
            auth_response = client.authenticate(email, password)
            
            # Get or create user in database
            user_data = auth_response.get('user', {})
            # Convert user ID to string since LinkedTrust returns an integer
            user_id = str(user_data.get('id')) if user_data.get('id') else f"user_{secrets.token_hex(8)}"
            
            db_user = get_or_create_user(
                user_id=user_id,
                email=email,
                name=user_data.get('name'),
                provider='linkedtrust',
                access_token=auth_response.get('accessToken'),
                refresh_token=auth_response.get('refreshToken')
            )
            
            # Login user with wrapper
            auth_user = AuthUser(db_user)
            login_user(auth_user, remember=True)
            
            # Redirect to main page
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
            
        except Exception as e:
            logger.error(f"Login failed: {e}")
            error_msg = str(e)
            # Extract the actual error message if it's an AuthenticationError
            if '401:' in error_msg:
                error_msg = error_msg.split('401: ', 1)[-1]
            return jsonify({'error': error_msg or 'Authentication failed'}), 401
    
    @app.route('/auth/google', endpoint='google_login')
    def google_login():
        """Initiate Google OAuth"""
        client_id = app.config.get('GOOGLE_CLIENT_ID')
        
        if not client_id:
            # OAuth not configured, redirect to login with message
            from flask import flash
            flash('Google OAuth is not configured. Please use email/password login.')
            return redirect('/auth/login')
        
        redirect_uri = url_for('google_callback', _external=True)
        
        # Build Google OAuth URL
        oauth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
            f"&scope=openid%20email%20profile"
        )
        
        return redirect(oauth_url)
    
    @app.route('/auth/google/callback', endpoint='google_callback')
    def google_callback():
        """Handle Google OAuth callback"""
        code = request.args.get('code')
        if not code:
            return jsonify({'error': 'No authorization code'}), 400
        
        try:
            # Send code to LinkedTrust backend
            client = LinkedTrustClient()
            auth_response = client.oauth_callback('google', code)
            
            # Get or create user in database
            user_data = auth_response.get('user', {})
            # Convert user ID to string since LinkedTrust returns an integer
            user_id = str(user_data.get('id')) if user_data.get('id') else f"google_{secrets.token_hex(8)}"
            
            db_user = get_or_create_user(
                user_id=user_id,
                email=user_data.get('email'),
                name=user_data.get('name'),
                provider='google',
                access_token=auth_response.get('accessToken'),
                refresh_token=auth_response.get('refreshToken')
            )
            
            # Login user with wrapper
            auth_user = AuthUser(db_user)
            login_user(auth_user, remember=True)
            
            return redirect(url_for('index'))
            
        except Exception as e:
            logger.error(f"Google OAuth failed: {e}")
            return jsonify({'error': 'OAuth authentication failed'}), 401
    
    @app.route('/auth/github', endpoint='github_login')
    def github_login():
        """Initiate GitHub OAuth"""
        client_id = app.config.get('GITHUB_CLIENT_ID')
        
        if not client_id:
            # OAuth not configured, redirect to login with message
            from flask import flash
            flash('GitHub OAuth is not configured. Please use email/password login.')
            return redirect('/auth/login')
        
        redirect_uri = url_for('github_callback', _external=True)
        
        # Build GitHub OAuth URL
        oauth_url = (
            f"https://github.com/login/oauth/authorize?"
            f"client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&scope=user:email"
        )
        
        return redirect(oauth_url)
    
    @app.route('/auth/github/callback', endpoint='github_callback')
    def github_callback():
        """Handle GitHub OAuth callback"""
        code = request.args.get('code')
        if not code:
            return jsonify({'error': 'No authorization code'}), 400
        
        try:
            # Send code to LinkedTrust backend
            client = LinkedTrustClient()
            auth_response = client.oauth_callback('github', code)
            
            # Get or create user in database
            user_data = auth_response.get('user', {})
            github_data = auth_response.get('githubData', {})
            # Convert user ID to string since LinkedTrust returns an integer
            user_id = str(user_data.get('id')) if user_data.get('id') else f"github_{github_data.get('username', secrets.token_hex(8))}"
            
            db_user = get_or_create_user(
                user_id=user_id,
                email=user_data.get('email') or github_data.get('email'),
                name=user_data.get('name') or github_data.get('name'),
                provider='github',
                access_token=auth_response.get('accessToken'),
                refresh_token=auth_response.get('refreshToken')
            )
            
            # Login user with wrapper
            auth_user = AuthUser(db_user)
            login_user(auth_user, remember=True)
            
            return redirect(url_for('index'))
            
        except Exception as e:
            logger.error(f"GitHub OAuth failed: {e}")
            return jsonify({'error': 'OAuth authentication failed'}), 401
    
    @app.route('/auth/logout')
    def logout():
        """Logout user"""
        logout_user()
        return redirect(url_for('index'))
    
    @app.route('/auth/user')
    def current_user_info():
        """Get current user info"""
        if current_user.is_authenticated:
            return jsonify({
                'id': current_user.id,
                'email': current_user.email,
                'name': current_user.name,
                'authenticated': True
            })
        return jsonify({'authenticated': False})