"""
Authentication and user session management
"""
import os
import secrets
from flask import session, redirect, url_for, request, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user
from datetime import datetime, timedelta
from linkedtrust_client import LinkedTrustClient
import logging

logger = logging.getLogger(__name__)

# Initialize Flask-Login
login_manager = LoginManager()

class User(UserMixin):
    """User class for Flask-Login"""
    
    def __init__(self, user_id: str, email: str = None, name: str = None, 
                 access_token: str = None, refresh_token: str = None):
        self.id = user_id  # This will be used as user_id in documents table
        self.email = email
        self.name = name
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.authenticated = True
    
    def get_id(self):
        return self.id
    
    def get_linkedtrust_client(self):
        """Get a LinkedTrustClient configured with user's tokens"""
        client = LinkedTrustClient(access_token=self.access_token)
        if self.refresh_token:
            client.refresh_token = self.refresh_token
        return client


# User storage (in production, this should be in database or Redis)
_user_store = {}


@login_manager.user_loader
def load_user(user_id):
    """Load user from session"""
    return _user_store.get(user_id)


def init_auth(app):
    """Initialize authentication for Flask app"""
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    # Session configuration
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
    
    # OAuth configuration
    app.config['GOOGLE_CLIENT_ID'] = os.getenv('GOOGLE_CLIENT_ID')
    app.config['GOOGLE_CLIENT_SECRET'] = os.getenv('GOOGLE_CLIENT_SECRET')
    app.config['GITHUB_CLIENT_ID'] = os.getenv('GITHUB_CLIENT_ID')
    app.config['GITHUB_CLIENT_SECRET'] = os.getenv('GITHUB_CLIENT_SECRET')
    
    return login_manager


def create_auth_routes(app):
    """Create authentication routes"""
    
    @app.route('/auth/login', methods=['GET', 'POST'])
    def login():
        """Login page and handler"""
        if request.method == 'GET':
            # Return login page
            return '''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Login - Linked Claims Extraction</title>
                <style>
                    body { font-family: Arial, sans-serif; max-width: 400px; margin: 100px auto; padding: 20px; }
                    .login-box { border: 1px solid #ddd; padding: 30px; border-radius: 8px; }
                    h2 { text-align: center; color: #333; }
                    .oauth-buttons { margin-top: 20px; }
                    .oauth-btn { 
                        display: block; 
                        width: 100%; 
                        padding: 12px; 
                        margin: 10px 0;
                        border: 1px solid #ddd;
                        border-radius: 4px;
                        text-align: center;
                        text-decoration: none;
                        color: #333;
                        background: white;
                        cursor: pointer;
                        transition: background 0.3s;
                    }
                    .oauth-btn:hover { background: #f5f5f5; }
                    .google-btn { border-color: #4285f4; color: #4285f4; }
                    .github-btn { border-color: #333; color: #333; }
                    .divider { text-align: center; margin: 20px 0; color: #999; }
                    .email-form input { 
                        width: 100%; 
                        padding: 10px; 
                        margin: 5px 0;
                        border: 1px solid #ddd;
                        border-radius: 4px;
                        box-sizing: border-box;
                    }
                    .submit-btn {
                        width: 100%;
                        padding: 12px;
                        background: #4CAF50;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        cursor: pointer;
                        margin-top: 10px;
                    }
                    .submit-btn:hover { background: #45a049; }
                </style>
            </head>
            <body>
                <div class="login-box">
                    <h2>Login to Linked Claims Extraction</h2>
                    
                    <div class="oauth-buttons">
                        <a href="/auth/google" class="oauth-btn google-btn">
                            Login with Google
                        </a>
                        <a href="/auth/github" class="oauth-btn github-btn">
                            Login with GitHub
                        </a>
                    </div>
                    
                    <div class="divider">OR</div>
                    
                    <form method="POST" class="email-form">
                        <input type="email" name="email" placeholder="Email" required>
                        <input type="password" name="password" placeholder="Password" required>
                        <button type="submit" class="submit-btn">Login with LinkedTrust</button>
                    </form>
                </div>
            </body>
            </html>
            '''
        
        # Handle email/password login
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        try:
            # Authenticate with LinkedTrust backend
            client = LinkedTrustClient()
            auth_response = client.authenticate(email, password)
            
            # Create user session
            user_id = auth_response.get('user', {}).get('id') or f"user_{secrets.token_hex(8)}"
            user = User(
                user_id=user_id,
                email=email,
                name=auth_response.get('user', {}).get('name'),
                access_token=auth_response.get('accessToken'),
                refresh_token=auth_response.get('refreshToken')
            )
            
            # Store user
            _user_store[user_id] = user
            
            # Login user
            login_user(user, remember=True)
            
            # Redirect to main page
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
            
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return jsonify({'error': 'Authentication failed'}), 401
    
    @app.route('/auth/google')
    def google_login():
        """Initiate Google OAuth"""
        client_id = app.config['GOOGLE_CLIENT_ID']
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
    
    @app.route('/auth/google/callback')
    def google_callback():
        """Handle Google OAuth callback"""
        code = request.args.get('code')
        if not code:
            return jsonify({'error': 'No authorization code'}), 400
        
        try:
            # Send code to LinkedTrust backend
            client = LinkedTrustClient()
            auth_response = client.oauth_callback('google', code)
            
            # Create user session
            user_data = auth_response.get('user', {})
            user_id = user_data.get('id') or f"google_{secrets.token_hex(8)}"
            
            user = User(
                user_id=user_id,
                email=user_data.get('email'),
                name=user_data.get('name'),
                access_token=auth_response.get('accessToken'),
                refresh_token=auth_response.get('refreshToken')
            )
            
            # Store user
            _user_store[user_id] = user
            
            # Login user
            login_user(user, remember=True)
            
            return redirect(url_for('index'))
            
        except Exception as e:
            logger.error(f"Google OAuth failed: {e}")
            return jsonify({'error': 'OAuth authentication failed'}), 401
    
    @app.route('/auth/github')
    def github_login():
        """Initiate GitHub OAuth"""
        client_id = app.config['GITHUB_CLIENT_ID']
        redirect_uri = url_for('github_callback', _external=True)
        
        # Build GitHub OAuth URL
        oauth_url = (
            f"https://github.com/login/oauth/authorize?"
            f"client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&scope=user:email"
        )
        
        return redirect(oauth_url)
    
    @app.route('/auth/github/callback')
    def github_callback():
        """Handle GitHub OAuth callback"""
        code = request.args.get('code')
        if not code:
            return jsonify({'error': 'No authorization code'}), 400
        
        try:
            # Send code to LinkedTrust backend
            client = LinkedTrustClient()
            auth_response = client.oauth_callback('github', code)
            
            # Create user session
            user_data = auth_response.get('user', {})
            github_data = auth_response.get('githubData', {})
            user_id = user_data.get('id') or f"github_{github_data.get('username', secrets.token_hex(8))}"
            
            user = User(
                user_id=user_id,
                email=user_data.get('email') or github_data.get('email'),
                name=user_data.get('name') or github_data.get('name'),
                access_token=auth_response.get('accessToken'),
                refresh_token=auth_response.get('refreshToken')
            )
            
            # Store user
            _user_store[user_id] = user
            
            # Login user
            login_user(user, remember=True)
            
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