#!/usr/bin/env python3

from app import app, db
import os
from sqlalchemy import inspect, create_engine, text

def init_database():
    """Initialize the MySQL database with proper schema"""
    with app.app_context():
        try:
            # Test database connection first
            engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
            with engine.connect() as connection:
                result = connection.execute(text("SELECT 1"))
                print("✅ MySQL database connection successful")
        except Exception as e:
            print(f"❌ MySQL database connection failed: {e}")
            print("Please ensure MySQL is running and the database exists")
            print("You may need to create the database first:")
            print("CREATE DATABASE congress_tracker;")
            return

        # Drop all tables first
        db.drop_all()
        print("Dropped all existing tables")
        
        # Create all tables with current schema
        db.create_all()
        print("Created all tables with proper schema")
        
        # Verify the schema
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"Tables created: {tables}")
        
        # Check comment table structure
        if 'comment' in tables:
            columns = [col['name'] for col in inspector.get_columns('comment')]
            print(f"Comment table columns: {columns}")
            
            if 'user_id' in columns:
                print("✅ user_id column exists in comment table")
            else:
                print("❌ user_id column missing in comment table")
        
        # Check password_reset_token table
        if 'password_reset_token' in tables:
            print("✅ PasswordResetToken table created")
        else:
            print("❌ PasswordResetToken table missing")
            
        # Check event_registration table
        if 'event_registration' in tables:
            print("✅ EventRegistration table created")
        else:
            print("❌ EventRegistration table missing")

if __name__ == '__main__':
    init_database()