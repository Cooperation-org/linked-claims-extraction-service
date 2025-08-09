#!/usr/bin/env python
"""
Initialize database migrations
Run this script to set up Flask-Migrate for the first time
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from flask import Flask
from models import db
from database import init_database

app = Flask(__name__)
app.config['SECRET_KEY'] = 'temp-key-for-migrations'

# Initialize database
migrate = init_database(app, db)

if __name__ == '__main__':
    with app.app_context():
        from flask_migrate import init, migrate as migrate_cmd, upgrade
        
        # Initialize migrations
        try:
            init()
            print("✅ Migrations initialized. Run 'flask db migrate' to create the first migration.")
        except:
            print("Migrations already initialized")
        
        # Create initial migration
        try:
            migrate_cmd(message="Initial migration with documents and draft claims")
            print("✅ Initial migration created")
        except Exception as e:
            print(f"Error creating migration: {e}")
        
        # Apply migration
        try:
            upgrade()
            print("✅ Database schema updated")
        except Exception as e:
            print(f"Error applying migration: {e}")