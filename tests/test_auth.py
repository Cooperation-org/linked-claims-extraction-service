"""
Comprehensive unit tests for the authentication system
"""
import pytest
import json
import tempfile
import os
import sys
from unittest.mock import patch, MagicMock

# Set test database URL before imports
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from flask import Flask
from flask_cors import CORS
from models import db, User
from database import init_database
from auth import init_auth, create_auth_routes


def create_test_app(db_uri=None):
    """Create a test Flask app"""
    app = Flask(__name__, template_folder='../src/templates')
    
    # Test configuration - override database URL before any database initialization
    app.config.update({
        'TESTING': True,
        'SECRET_KEY': 'test-secret-key',
        'WTF_CSRF_ENABLED': False,
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'UPLOAD_FOLDER': '/tmp/test_uploads',
        'MAX_CONTENT_LENGTH': 80 * 1024 * 1024,
        'SQLALCHEMY_DATABASE_URI': db_uri or 'sqlite:///:memory:',
        'DATABASE_URL': db_uri or 'sqlite:///:memory:',
        # Override PostgreSQL-specific settings for SQLite
        'SQLALCHEMY_ENGINE_OPTIONS': {}
    })
    
    # Initialize CORS
    CORS(app)
    
    # Initialize database
    migrate = init_database(app, db)
    
    # Initialize authentication
    init_auth(app)
    create_auth_routes(app)
    
    # Add a simple index route for testing redirects
    @app.route('/')
    def index():
        return 'Test Index Page'
    
    return app


@pytest.fixture
def app():
    """Create a test Flask app with temporary database"""
    # Create temporary database file
    db_fd, db_path = tempfile.mkstemp()
    db_uri = f'sqlite:///{db_path}'
    
    app = create_test_app(db_uri)
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()
    
    # Clean up
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """Create a test client"""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a test CLI runner"""
    return app.test_cli_runner()


class TestAuthRoutes:
    """Test authentication routes"""
    
    def test_login_page_loads(self, client):
        """Test that login page loads correctly"""
        response = client.get('/auth/login')
        assert response.status_code == 200
        assert b'Sign in to continue' in response.data
        assert b'LinkedTrust Claims' in response.data
        assert b'Sign in with LinkedTrust' in response.data
    
    def test_login_page_with_oauth_config(self, client, app):
        """Test login page with OAuth configuration"""
        app.config['GOOGLE_CLIENT_ID'] = 'test-google-id'
        app.config['GITHUB_CLIENT_ID'] = 'test-github-id'
        
        response = client.get('/auth/login')
        assert response.status_code == 200
        assert b'Continue with Google' in response.data
        assert b'Continue with GitHub' in response.data
        assert b'OR' in response.data
    
    def test_login_missing_credentials(self, client):
        """Test login with missing credentials"""
        response = client.post('/auth/login', data={})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Email and password required' in data['error']
    
    def test_login_missing_email(self, client):
        """Test login with missing email"""
        response = client.post('/auth/login', data={'password': 'test123'})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Email and password required' in data['error']
    
    def test_login_missing_password(self, client):
        """Test login with missing password"""
        response = client.post('/auth/login', data={'email': 'test@example.com'})
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Email and password required' in data['error']
    
    @patch('src.auth.LinkedTrustClient')
    def test_login_success(self, mock_client_class, client, app):
        """Test successful login"""
        # Mock the LinkedTrust client
        mock_client = MagicMock()
        mock_client.authenticate.return_value = {
            'accessToken': 'test-access-token',
            'refreshToken': 'test-refresh-token',
            'user': {
                'id': 123,
                'email': 'test@example.com',
                'name': 'Test User'
            }
        }
        mock_client_class.return_value = mock_client
        
        with app.app_context():
            response = client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'password123'
            })
            
            assert response.status_code == 302  # Redirect
            assert response.location == '/'
            
            # Check that user was created in database
            user = User.query.filter_by(email='test@example.com').first()
            assert user is not None
            assert user.name == 'Test User'
            assert user.access_token == 'test-access-token'
    
    @patch('src.auth.LinkedTrustClient')
    def test_login_authentication_failure(self, mock_client_class, client):
        """Test login with invalid credentials"""
        mock_client = MagicMock()
        mock_client.authenticate.side_effect = Exception('Authentication failed')
        mock_client_class.return_value = mock_client
        
        response = client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'wrongpassword'
        })
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Authentication failed' in data['error']
    
    def test_logout_route(self, client):
        """Test logout route"""
        response = client.get('/auth/logout')
        assert response.status_code == 302  # Redirect
        assert response.location == '/'
    
    def test_current_user_unauthenticated(self, client):
        """Test current user info when not authenticated"""
        response = client.get('/auth/user')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['authenticated'] == False
    
    def test_google_oauth_without_config(self, client):
        """Test Google OAuth when not configured"""
        response = client.get('/auth/google')
        assert response.status_code == 302  # Redirect to login
        assert '/auth/login' in response.location
    
    def test_github_oauth_without_config(self, client):
        """Test GitHub OAuth when not configured"""
        response = client.get('/auth/github')
        assert response.status_code == 302  # Redirect to login
        assert '/auth/login' in response.location
    
    def test_google_oauth_with_config(self, client, app):
        """Test Google OAuth initiation"""
        app.config['GOOGLE_CLIENT_ID'] = 'test-google-client-id'
        
        response = client.get('/auth/google')
        assert response.status_code == 302  # Redirect to Google
        assert 'accounts.google.com' in response.location
        assert 'test-google-client-id' in response.location
    
    def test_github_oauth_with_config(self, client, app):
        """Test GitHub OAuth initiation"""
        app.config['GITHUB_CLIENT_ID'] = 'test-github-client-id'
        
        response = client.get('/auth/github')
        assert response.status_code == 302  # Redirect to GitHub
        assert 'github.com' in response.location
        assert 'test-github-client-id' in response.location
    
    @patch('src.auth.LinkedTrustClient')
    def test_google_oauth_callback_success(self, mock_client_class, client, app):
        """Test successful Google OAuth callback"""
        mock_client = MagicMock()
        mock_client.oauth_callback.return_value = {
            'accessToken': 'google-access-token',
            'refreshToken': 'google-refresh-token',
            'user': {
                'id': 456,
                'email': 'google@example.com',
                'name': 'Google User'
            }
        }
        mock_client_class.return_value = mock_client
        
        with app.app_context():
            response = client.get('/auth/google/callback?code=test-auth-code')
            
            assert response.status_code == 302  # Redirect
            assert response.location == '/'
            
            # Check that user was created
            user = User.query.filter_by(email='google@example.com').first()
            assert user is not None
            assert user.provider == 'google'
    
    def test_google_oauth_callback_no_code(self, client):
        """Test Google OAuth callback without authorization code"""
        response = client.get('/auth/google/callback')
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'No authorization code' in data['error']
    
    @patch('src.auth.LinkedTrustClient')
    def test_github_oauth_callback_success(self, mock_client_class, client, app):
        """Test successful GitHub OAuth callback"""
        mock_client = MagicMock()
        mock_client.oauth_callback.return_value = {
            'accessToken': 'github-access-token',
            'refreshToken': 'github-refresh-token',
            'user': {
                'id': 789,
                'email': 'github@example.com',
                'name': 'GitHub User'
            },
            'githubData': {
                'username': 'githubuser',
                'email': 'github@example.com'
            }
        }
        mock_client_class.return_value = mock_client
        
        with app.app_context():
            response = client.get('/auth/github/callback?code=test-auth-code')
            
            assert response.status_code == 302  # Redirect
            assert response.location == '/'
            
            # Check that user was created
            user = User.query.filter_by(email='github@example.com').first()
            assert user is not None
            assert user.provider == 'github'


class TestAuthUser:
    """Test AuthUser class"""
    
    def test_auth_user_creation(self, app):
        """Test AuthUser wrapper creation"""
        from src.auth import AuthUser
        
        with app.app_context():
            # Create a database user
            db_user = User(
                id='test-user-123',
                email='test@example.com',
                name='Test User',
                access_token='test-token',
                refresh_token='refresh-token'
            )
            db.session.add(db_user)
            db.session.commit()
            
            # Create AuthUser wrapper
            auth_user = AuthUser(db_user)
            
            assert auth_user.id == 'test-user-123'
            assert auth_user.email == 'test@example.com'
            assert auth_user.name == 'Test User'
            assert auth_user.access_token == 'test-token'
            assert auth_user.authenticated == True
            assert auth_user.get_id() == 'test-user-123'
    
    def test_auth_user_linkedtrust_client(self, app):
        """Test AuthUser LinkedTrust client creation"""
        from src.auth import AuthUser
        
        with app.app_context():
            db_user = User(
                id='test-user-123',
                email='test@example.com',
                access_token='test-token',
                refresh_token='refresh-token'
            )
            
            auth_user = AuthUser(db_user)
            client = auth_user.get_linkedtrust_client()
            
            assert client.access_token == 'test-token'
            assert client.refresh_token == 'refresh-token'


class TestUserModel:
    """Test User database model"""
    
    def test_user_creation(self, app):
        """Test creating a user"""
        with app.app_context():
            user = User(
                id='test-123',
                email='test@example.com',
                name='Test User',
                provider='linkedtrust'
            )
            db.session.add(user)
            db.session.commit()
            
            # Query the user back
            found_user = User.query.filter_by(email='test@example.com').first()
            assert found_user is not None
            assert found_user.id == 'test-123'
            assert found_user.name == 'Test User'
            assert found_user.provider == 'linkedtrust'
    
    def test_user_to_dict(self, app):
        """Test user to_dict method"""
        with app.app_context():
            user = User(
                id='test-123',
                email='test@example.com',
                name='Test User',
                provider='linkedtrust'
            )
            db.session.add(user)
            db.session.commit()
            
            user_dict = user.to_dict()
            assert user_dict['id'] == 'test-123'
            assert user_dict['email'] == 'test@example.com'
            assert user_dict['name'] == 'Test User'
            assert user_dict['provider'] == 'linkedtrust'
            assert 'created_at' in user_dict


class TestGetOrCreateUser:
    """Test get_or_create_user function"""
    
    def test_create_new_user(self, app):
        """Test creating a new user"""
        from src.auth import get_or_create_user
        
        with app.app_context():
            user = get_or_create_user(
                user_id='new-user-123',
                email='new@example.com',
                name='New User',
                provider='linkedtrust',
                access_token='access-token',
                refresh_token='refresh-token'
            )
            
            assert user.id == 'new-user-123'
            assert user.email == 'new@example.com'
            assert user.name == 'New User'
            assert user.provider == 'linkedtrust'
            assert user.access_token == 'access-token'
    
    def test_update_existing_user_by_id(self, app):
        """Test updating an existing user by ID"""
        from src.auth import get_or_create_user
        
        with app.app_context():
            # Create initial user
            existing_user = User(
                id='existing-123',
                email='old@example.com',
                name='Old Name'
            )
            db.session.add(existing_user)
            db.session.commit()
            
            # Update the user
            updated_user = get_or_create_user(
                user_id='existing-123',
                email='updated@example.com',
                name='Updated Name',
                access_token='new-token'
            )
            
            assert updated_user.id == 'existing-123'
            assert updated_user.email == 'updated@example.com'
            assert updated_user.name == 'Updated Name'
            assert updated_user.access_token == 'new-token'
    
    def test_find_user_by_email(self, app):
        """Test finding user by email when ID doesn't match"""
        from src.auth import get_or_create_user
        
        with app.app_context():
            # Create user with one ID
            existing_user = User(
                id='old-id-123',
                email='same@example.com',
                name='Same Email User'
            )
            db.session.add(existing_user)
            db.session.commit()
            
            # Try to create with different ID but same email
            found_user = get_or_create_user(
                user_id='new-id-456',
                email='same@example.com',
                name='Updated Name'
            )
            
            # Should update the existing user, not create new one
            assert found_user.id == 'old-id-123'  # ID stays the same
            assert found_user.email == 'same@example.com'
            assert found_user.name == 'Updated Name'  # Name gets updated


if __name__ == '__main__':
    pytest.main([__file__, '-v'])