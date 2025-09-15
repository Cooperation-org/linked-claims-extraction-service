#!/usr/bin/env python3
"""
Simple script to check what's in the database
"""
import os
import sqlite3
from pathlib import Path

def check_sqlite_database():
    """Check if there's a local SQLite database"""
    possible_paths = [
        'instance/local.db',
        'instance/test.db', 
        'instance/extractor.db',
        'extractor.db',
        'src/extractor.db'
    ]
    
    for db_path in possible_paths:
        if os.path.exists(db_path):
            print(f"Found SQLite database: {db_path}")
            
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Check what tables exist
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                print(f"Tables in database: {[t[0] for t in tables]}")
                
                # Check for claims with ILRI URLs
                try:
                    cursor.execute("SELECT id, subject FROM draft_claims WHERE subject LIKE '%ilri.org%'")
                    claims = cursor.fetchall()
                    print(f"Claims with ILRI URLs: {len(claims)}")
                    for claim_id, subject in claims:
                        print(f"  Claim {claim_id}: {subject}")
                except:
                    print("No draft_claims table or no ILRI claims found")
                
                # Check for verified organizations table
                try:
                    cursor.execute("SELECT * FROM verified_organizations")
                    orgs = cursor.fetchall()
                    print(f"Verified organizations: {len(orgs)}")
                    for org in orgs:
                        print(f"  {org}")
                except:
                    print("No verified_organizations table found")
                
                conn.close()
                return True
                
            except Exception as e:
                print(f"Error reading database {db_path}: {e}")
    
    print("No SQLite database found")
    return False

def check_postgresql_config():
    """Check PostgreSQL configuration"""
    from dotenv import load_dotenv
    load_dotenv()
    
    database_url = os.getenv('DATABASE_URL', 'Not set')
    print(f"DATABASE_URL: {database_url}")
    
    if 'postgresql' in database_url:
        print("App is configured for PostgreSQL")
        return True
    elif 'sqlite' in database_url:
        print("App is configured for SQLite")
        return True
    else:
        print("Database configuration unclear")
        return False

if __name__ == "__main__":
    print("=== DATABASE CHECK ===")
    print()
    
    print("1. Checking database configuration...")
    check_postgresql_config()
    print()
    
    print("2. Looking for local database files...")
    check_sqlite_database()
    print()
    
    print("3. Checking directory structure...")
    print(f"Current directory: {os.getcwd()}")
    print(f"Files in current directory: {os.listdir('.')}")
    if os.path.exists('instance'):
        print(f"Files in instance/: {os.listdir('instance')}")