"""
Database configuration and initialization
"""
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv

load_dotenv()

def init_database(app: Flask, db: SQLAlchemy):
    """Initialize database with Flask app"""
    
    # Database configuration
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        # Default to SQLite in current working directory for local development
        database_url = "sqlite:///local.db"
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Only set PostgreSQL-specific options for PostgreSQL databases
    if database_url.startswith('postgresql'):
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': 10,
            'pool_recycle': 3600,
            'pool_pre_ping': True
        }
    
    db.init_app(app)
    
    # Initialize Flask-Migrate for database migrations
    migrate = Migrate(app, db)
    
    return migrate

def create_tables(app: Flask, db: SQLAlchemy):
    """Create all database tables"""
    with app.app_context():
        db.create_all()
        print("✅ Database tables created successfully")

def drop_tables(app: Flask, db: SQLAlchemy):
    """Drop all database tables (use with caution!)"""
    with app.app_context():
        db.drop_all()
        print("⚠️ All database tables dropped")