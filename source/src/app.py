#!/usr/bin/env python3

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, EmailField, BooleanField, SubmitField, SelectMultipleField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from datetime import datetime, timedelta, timezone
import os
import requests
from typing import Dict, List, Optional
import json
import re
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import boto3
from botocore.exceptions import ClientError
from werkzeug.security import generate_password_hash, check_password_hash
import openai

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

# Database Configuration - Use SQLite by default for Elastic Beanstalk
# This ensures the application starts successfully even without MySQL
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///congress_tracker.db'

# Try to use MySQL if all environment variables are properly set
mysql_host = os.environ.get('MYSQL_HOST')
mysql_port = os.environ.get('MYSQL_PORT', '3306')
mysql_user = os.environ.get('MYSQL_USER')
mysql_password = os.environ.get('MYSQL_PASSWORD')
mysql_database = os.environ.get('MYSQL_DATABASE')

# Only use MySQL if all required variables are set and not empty
if all([mysql_host, mysql_user, mysql_password, mysql_database]) and mysql_host != 'localhost':
    try:
        # Test MySQL connection before switching
        import pymysql
        connection = pymysql.connect(
            host=mysql_host,
            port=int(mysql_port),
            user=mysql_user,
            password=mysql_password,
            database=mysql_database
        )
        connection.close()
        # If connection successful, use MySQL
        app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{mysql_user}:{mysql_password}@{mysql_host}:{mysql_port}/{mysql_database}'
        print("✅ Using MySQL database")
    except Exception as e:
        print(f"⚠️  MySQL connection failed: {e}")
        print("✅ Falling back to SQLite database")
else:
    print("✅ Using SQLite database (default)")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database and login manager
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    zip_code = db.Column(db.String(10))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True)
    email_verified = db.Column(db.Boolean, default=False)
    
    # Relationships
    comments = db.relationship('Comment', backref='user', lazy=True)
    votes = db.relationship('Vote', backref='user', lazy=True)
    watchlist_items = db.relationship('WatchlistItem', backref='user', lazy=True)
    topic_alerts = db.relationship('TopicAlert', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'zip_code': self.zip_code,
            'created_at': self.created_at.isoformat(),
        }

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.String(50), nullable=False)
    author_name = db.Column(db.String(100), nullable=False)
    author_email = db.Column(db.String(120), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    ip_address = db.Column(db.String(45))  # Store IP for moderation
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Optional user association
    
    def to_dict(self):
        return {
            'id': self.id,
            'bill_id': self.bill_id,
            'author_name': self.author_name,
            'content': self.content,
            'is_approved': self.is_approved,
            'created_at': self.created_at.isoformat(),
            'user_id': self.user_id,
        }

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(db.String(50), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)
    vote_type = db.Column(db.String(10), nullable=False)  # 'up' or 'down'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Optional user association
    
    # Ensure one vote per user per bill (since login is required)
    __table_args__ = (db.UniqueConstraint('bill_id', 'user_id', name='unique_vote_per_user'),)
    
    def to_dict(self):
        return {
            'id': self.id,
            'bill_id': self.bill_id,
            'vote_type': self.vote_type,
            'created_at': self.created_at.isoformat(),
            'user_id': self.user_id,
        }

class WatchlistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    bill_id = db.Column(db.String(50), nullable=False)
    bill_title = db.Column(db.String(200), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)  # User's personal notes about the bill
    
    # Ensure one watchlist entry per user per bill
    __table_args__ = (db.UniqueConstraint('user_id', 'bill_id', name='unique_watchlist_per_user'),)
    
    def to_dict(self):
        return {
            'id': self.id,
            'bill_id': self.bill_id,
            'bill_title': self.bill_title,
            'added_at': self.added_at.isoformat(),
            'notes': self.notes,
        }

class TopicAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    topic = db.Column(db.String(50), nullable=False)  # education, environment, etc.
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_notified = db.Column(db.DateTime, nullable=True)
    
    # Ensure one alert per user per topic
    __table_args__ = (db.UniqueConstraint('user_id', 'topic', name='unique_alert_per_user'),)
    
    def to_dict(self):
        return {
            'id': self.id,
            'topic': self.topic,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'last_notified': self.last_notified.isoformat() if self.last_notified else None,
        }

class EventRegistration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_name = db.Column(db.String(200), nullable=False)
    event_date = db.Column(db.String(50), nullable=False)
    event_time = db.Column(db.String(50), nullable=False)
    event_location = db.Column(db.String(200), nullable=False)
    registration_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), default='registered')  # registered, cancelled
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'event_name': self.event_name,
            'event_date': self.event_date,
            'event_time': self.event_time,
            'event_location': self.event_location,
            'registration_date': self.registration_date.isoformat(),
            'status': self.status
        }

class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Nullable for non-logged-in users
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now())
    is_verified = db.Column(db.Boolean, default=False)  # For non-logged-in users
    verification_token = db.Column(db.String(100), nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'email': self.email,
            'message': self.message,
            'created_at': self.created_at.isoformat(),
            'is_verified': self.is_verified
        }

class PasswordResetToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    
    def is_valid(self):
        """Check if token is valid and not expired"""
        return not self.is_used and datetime.now() < self.expires_at
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'token': self.token,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'is_used': self.is_used,
        }

class EmailVerificationToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    
    def is_valid(self):
        """Check if token is valid and not expired"""
        return not self.is_used and datetime.now() < self.expires_at
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'token': self.token,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'is_used': self.is_used,
        }

# Login manager user loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Form Classes
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=20)])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=2, max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=2, max=50)])
    zip_code = StringField('ZIP Code', validators=[Length(min=5, max=10)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Login')

class TopicAlertForm(FlaskForm):
    topics = SelectMultipleField('Topics to Track', choices=[
        ('education', 'Education'),
        ('student_loans', 'Student Loans'),
        ('mental_health', 'Mental Health'),
        ('youth_voting', 'Youth Voting Rights'),
        ('environment', 'Environment')
    ])
    submit = SubmitField('Update Alerts')

class ForgotPasswordForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Send Reset Link')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')

# Congress.gov API configuration
CONGRESS_API_KEY = os.getenv('CONGRESS_API_KEY', 'your-api-key-here')
CONGRESS_BASE_URL = 'https://api.congress.gov/v3'

# OpenAI configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
openai.api_key = OPENAI_API_KEY

# Email configuration
# AWS SES Configuration
AWS_SES_REGION = os.getenv('AWS_SES_REGION', 'us-east-1')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', '')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'youthpolicypulse@gmail.com')

# Fallback SMTP configuration (for development)
SMTP_SERVER = os.getenv('SMTP_SERVER', os.getenv('MAIL_SERVER', 'smtp.gmail.com'))
SMTP_PORT = int(os.getenv('SMTP_PORT', os.getenv('MAIL_PORT', '587')))
SMTP_USERNAME = os.getenv('SMTP_USERNAME', os.getenv('MAIL_USERNAME', ''))
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', os.getenv('MAIL_PASSWORD', ''))

# Email service selection
USE_AWS_SES = os.getenv('USE_AWS_SES', 'false').lower() == 'true'

# Topic keywords for filtering
TOPIC_KEYWORDS = {
    'education': ['education', 'school', 'university', 'college', 'student', 'teacher', 'learning', 'academic', 'campus', 'scholarship', 'degree', 'curriculum', 'classroom', 'textbook', 'tuition', 'enrollment'],
    'student_loans': ['student loan', 'student debt', 'federal student aid', 'pell grant', 'financial aid', 'tuition', 'borrower', 'repayment', 'forgiveness', 'default', 'interest rate'],
    'mental_health': ['mental health', 'mental illness', 'psychiatric', 'therapy', 'counseling', 'depression', 'anxiety', 'suicide prevention', 'behavioral', 'psychological', 'wellness', 'crisis', 'treatment'],
    'youth_voting': ['youth voting', 'voting age', 'student voting', 'campus voting', 'voter registration', 'election access', 'democracy', 'civic', 'participation', 'franchise'],
    'environment': ['environment', 'climate', 'green energy', 'renewable', 'carbon', 'emissions', 'pollution', 'conservation', 'sustainability', 'clean air', 'water', 'wildlife', 'ecosystem', 'renewable energy', 'solar', 'wind'],
    'healthcare': ['health', 'healthcare', 'medical', 'hospital', 'doctor', 'nurse', 'insurance', 'medicare', 'medicaid', 'pharmaceutical', 'drug', 'prescription', 'treatment', 'patient'],
    'economy': ['economy', 'economic', 'business', 'job', 'employment', 'unemployment', 'wage', 'salary', 'income', 'tax', 'budget', 'deficit', 'inflation', 'recession'],
    'technology': ['technology', 'tech', 'digital', 'internet', 'cyber', 'data', 'privacy', 'artificial intelligence', 'ai', 'computer', 'software', 'hardware', 'innovation'],
    'immigration': ['immigration', 'immigrant', 'border', 'visa', 'citizenship', 'asylum', 'refugee', 'deportation', 'naturalization'],
    'criminal_justice': ['criminal', 'justice', 'police', 'law enforcement', 'prison', 'jail', 'incarceration', 'rehabilitation', 'reform', 'sentencing']
}

# Cache for API responses
api_bills_cache = None
api_bills_cache_time = None
processed_bills_cache = None
processed_bills_cache_time = None
CACHE_DURATION = 1800  # 30 minutes in seconds (extended for better performance)

# File-based cache for persistence across server restarts
import json
import os
import tempfile

# Use a more robust cache file path for AWS Elastic Beanstalk
def get_cache_file_path():
    """Get the appropriate cache file path for the current environment"""
    # Try to use /tmp directory first (available in most environments)
    try:
        # Test if we can write to /tmp
        test_file = os.path.join(tempfile.gettempdir(), 'test_write.tmp')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        # If successful, use /tmp
        return os.path.join(tempfile.gettempdir(), 'bills_cache.json')
    except:
        # Fallback to current directory
        return 'bills_cache.json'

CACHE_FILE = get_cache_file_path()

# Sample data removed - using real Congress.gov API data only

def clear_bills_cache():
    """Clear all cached bill data"""
    global api_bills_cache, api_bills_cache_time, processed_bills_cache, processed_bills_cache_time
    api_bills_cache = None
    api_bills_cache_time = None
    processed_bills_cache = None
    processed_bills_cache_time = None
    print("🗑️ Cleared all bill caches")

def load_cache_from_file():
    """Load cache from file if it exists and is valid"""
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
            
            import time
            cache_time = cache_data.get('timestamp', 0)
            if time.time() - cache_time < CACHE_DURATION:
                print(f"📦 Using cached processed bills from file: {CACHE_FILE}")
                return cache_data.get('bills', [])
            else:
                print("⏰ Cache file expired, will fetch fresh data")
        else:
            print(f"📁 No cache file found at: {CACHE_FILE}")
    except Exception as e:
        print(f"❌ Error loading cache file: {e}")
        # Try to remove corrupted cache file
        try:
            if os.path.exists(CACHE_FILE):
                os.remove(CACHE_FILE)
                print(f"🗑️ Removed corrupted cache file: {CACHE_FILE}")
        except:
            pass
    return None

def save_cache_to_file(bills):
    """Save processed bills to cache file"""
    try:
        import time
        cache_data = {
            'timestamp': time.time(),
            'bills': bills
        }
        
        # Create directory if it doesn't exist
        cache_dir = os.path.dirname(CACHE_FILE)
        if cache_dir and not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)
        
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache_data, f)
        print(f"💾 Saved processed bills to cache file: {CACHE_FILE}")
    except Exception as e:
        print(f"❌ Error saving cache file: {e}")
        print(f"📁 Cache file path: {CACHE_FILE}")
        print(f"📁 Current working directory: {os.getcwd()}")
        print(f"📁 Directory exists: {os.path.exists(os.path.dirname(CACHE_FILE) or '.')}")
        print(f"📁 Directory writable: {os.access(os.path.dirname(CACHE_FILE) or '.', os.W_OK)}")

def get_processed_bills_cached_with_stats(chamber='both', congress=118, limit=None):
    """Get processed bills with real API statistics (optimized for homepage)"""
    global processed_bills_cache, processed_bills_cache_time
    import time
    
    try:
        print("🌐 Fetching bills with real API statistics")
        headers = {'X-API-Key': CONGRESS_API_KEY}
        
        # Make API call with minimal data to get statistics
        url = f"{CONGRESS_BASE_URL}/bill"
        response = requests.get(url, headers=headers, params={'limit': limit or 10, 'offset': 0})
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract real statistics from API response
            pagination = data.get('pagination', {})
            total_bills = pagination.get('count', 0)
            
            # Get House and Senate counts separately
            house_response = requests.get(url, headers=headers, params={'limit': 1, 'chamber': 'house'})
            senate_response = requests.get(url, headers=headers, params={'limit': 1, 'chamber': 'senate'})
            
            house_bills = 0
            senate_bills = 0
            
            if house_response.status_code == 200:
                house_data = house_response.json()
                house_pagination = house_data.get('pagination', {})
                house_bills = house_pagination.get('count', 0)
            
            if senate_response.status_code == 200:
                senate_data = senate_response.json()
                senate_pagination = senate_data.get('pagination', {})
                senate_bills = senate_pagination.get('count', 0)
            
            # Process bills for current page
            bills = data.get('bills', [])
            processed_bills = []
            
            for bill in bills:
                processed_bill = process_congress_bill_lightweight(bill)
                if processed_bill:
                    processed_bills.append(processed_bill)
            
            # Return bills and real statistics
            api_stats = {
                'total_bills': total_bills,
                'house_bills': house_bills,
                'senate_bills': senate_bills
            }
            
            print(f"📊 Real API Statistics:")
            print(f"   Total bills: {total_bills}")
            print(f"   House bills: {house_bills}")
            print(f"   Senate bills: {senate_bills}")
            
            return processed_bills, api_stats
        else:
            print(f"❌ API call failed: {response.status_code}")
            return [], {'total_bills': 0, 'house_bills': 0, 'senate_bills': 0}
            
    except Exception as e:
        print(f"Error fetching bills with stats: {e}")
        return [], {'total_bills': 0, 'house_bills': 0, 'senate_bills': 0}

def get_processed_bills_cached(chamber='both', congress=118, limit=None):
    """Get processed bills with comprehensive caching (lightweight for statistics)"""
    global processed_bills_cache, processed_bills_cache_time
    
    # First check in-memory cache
    if processed_bills_cache and processed_bills_cache_time:
        import time
        if time.time() - processed_bills_cache_time < CACHE_DURATION:
            print("📦 Using cached processed bills from memory")
            return processed_bills_cache
    
    # Then check file cache
    file_cache = load_cache_from_file()
    if file_cache:
        # Load into memory cache
        processed_bills_cache = file_cache
        import time
        processed_bills_cache_time = time.time()
        return file_cache
    
    # If no cached processed bills, fetch and process
    print("🌐 Fetching and processing bills from Congress.gov API")
    api_bills = fetch_bills_from_api(chamber, congress)
    
    if api_bills:
        # Process bills from Congress.gov API (lightweight processing)
        processed_bills = []
        for i, bill in enumerate(api_bills):
            # Apply limit if specified
            if limit and i >= limit:
                break
                
            processed_bill = process_congress_bill_lightweight(bill)
            if processed_bill:
                processed_bills.append(processed_bill)
        
        # Only cache if we're not using a limit (full dataset)
        if not limit:
            # Cache the processed bills in memory and file
            processed_bills_cache = processed_bills
            import time
            processed_bills_cache_time = time.time()
            save_cache_to_file(processed_bills)
        
        return processed_bills
    else:
        return []

def get_detailed_bills_for_page(bills_for_page):
    """Fetch detailed information only for bills on the current page"""
    import time
    detailed_bills = []
    total_api_time = 0
    api_calls_made = 0
    
    print(f"🔍 Starting detailed API calls for {len(bills_for_page)} bills...")
    
    for i, bill in enumerate(bills_for_page):
        try:
            # Extract bill details for detailed API call
            bill_id = bill.get('bill_id', '')
            if not bill_id:
                detailed_bills.append(bill)  # Keep original if no bill_id
                continue
                
            # Parse bill_id to get components for detailed API call
            # Format: hr1234-118 or s1234-118
            parts = bill_id.split('-')
            if len(parts) >= 2:
                bill_identifier = parts[0]  # hr1234 or s1234
                congress_number = parts[1]  # 118
                
                # Extract bill type and number
                if bill_identifier.startswith('hr'):
                    bill_type = 'hr'
                    bill_number = bill_identifier[2:]
                elif bill_identifier.startswith('s'):
                    bill_type = 's'
                    bill_number = bill_identifier[1:]
                else:
                    detailed_bills.append(bill)  # Keep original if can't parse
                    continue
                
                # Make detailed API call with timing
                detail_url = f"{CONGRESS_BASE_URL}/bill/{congress_number}/{bill_type}/{bill_number}"
                headers = {'X-API-Key': CONGRESS_API_KEY}
                
                print(f"🌐 API call {i+1}/{len(bills_for_page)}: {bill_id}")
                api_start = time.time()
                detail_response = requests.get(detail_url, headers=headers)
                api_duration = time.time() - api_start
                total_api_time += api_duration
                api_calls_made += 1
                
                print(f"⏱️  API call took: {api_duration:.2f}s")
                
                if detail_response.status_code == 200:
                    detail_data = detail_response.json()
                    bill_detail = detail_data.get('bill', {})
                    
                    # Update bill with detailed information
                    detailed_bill = bill.copy()
                    
                    # Extract sponsor from detailed response
                    if bill_detail.get('sponsors') and len(bill_detail.get('sponsors', [])) > 0:
                        primary_sponsor = bill_detail.get('sponsors', [])[0]
                        detailed_bill['sponsor'] = primary_sponsor.get('fullName', 'Sponsor information not available')
                    
                    # Get the correct introduced date from detailed response
                    if bill_detail.get('introducedDate'):
                        detailed_bill['introduced_date'] = bill_detail.get('introducedDate', '')
                    
                    # Get more detailed status information
                    if bill_detail.get('latestAction', {}).get('text'):
                        detailed_bill['status'] = bill_detail.get('latestAction', {}).get('text', '')
                        detailed_bill['latest_action'] = bill_detail.get('latestAction', {}).get('text', '')
                    
                    detailed_bills.append(detailed_bill)
                    print(f"✅ Fetched detailed info for {bill_id}")
                else:
                    print(f"⚠️ Could not fetch detailed info for {bill_id} (status: {detail_response.status_code})")
                    detailed_bills.append(bill)  # Keep original if API call fails
            else:
                detailed_bills.append(bill)  # Keep original if can't parse bill_id
                
        except Exception as e:
            print(f"❌ Error fetching detailed info for {bill.get('bill_id', 'unknown')}: {e}")
            detailed_bills.append(bill)  # Keep original if error occurs
    
    print(f"📊 API Performance Summary:")
    print(f"   Total API calls made: {api_calls_made}")
    print(f"   Total API time: {total_api_time:.2f}s")
    if api_calls_made > 0:
        print(f"   Average per API call: {total_api_time/api_calls_made:.2f}s")
    
    return detailed_bills

def fetch_bills_from_api(chamber='both', congress=118, offset=0):
    """Fetch bills from Congress.gov API with caching"""
    global api_bills_cache, api_bills_cache_time
    import time
    
    # Check if we have cached data that's still valid
    if api_bills_cache and api_bills_cache_time:
        if time.time() - api_bills_cache_time < CACHE_DURATION:
            print("📦 Using cached API data")
            return api_bills_cache
    
    try:
        print("🌐 Fetching fresh data from Congress.gov API")
        headers = {'X-API-Key': CONGRESS_API_KEY}
        
        # Time the main API call
        main_api_start = time.time()
        
        if chamber == 'both':
            # Fetch from both House and Senate
            house_url = f"{CONGRESS_BASE_URL}/bill"
            senate_url = f"{CONGRESS_BASE_URL}/bill"
            
            bills = []
            
            # Fetch House bills
            print("🏛️ Fetching House bills...")
            house_start = time.time()
            house_response = requests.get(house_url, headers=headers, params={'limit': 50, 'offset': offset})
            house_duration = time.time() - house_start
            print(f"⏱️  House API call took: {house_duration:.2f}s")
            
            if house_response.status_code == 200:
                house_data = house_response.json()
                bills.extend(house_data.get('bills', []))
                print(f"✅ Got {len(house_data.get('bills', []))} House bills")
            else:
                print(f"❌ House API failed: {house_response.status_code}")
            
            # Fetch Senate bills
            print("🏛️ Fetching Senate bills...")
            senate_start = time.time()
            senate_response = requests.get(senate_url, headers=headers, params={'limit': 50, 'offset': offset})
            senate_duration = time.time() - senate_start
            print(f"⏱️  Senate API call took: {senate_duration:.2f}s")
            
            if senate_response.status_code == 200:
                senate_data = senate_response.json()
                bills.extend(senate_data.get('bills', []))
                print(f"✅ Got {len(senate_data.get('bills', []))} Senate bills")
            else:
                print(f"❌ Senate API failed: {senate_response.status_code}")
            
            # Cache the results
            api_bills_cache = bills
            api_bills_cache_time = time.time()
            
            total_main_api_time = time.time() - main_api_start
            print(f"📊 Main API Performance:")
            print(f"   Total time: {total_main_api_time:.2f}s")
            print(f"   House API: {house_duration:.2f}s")
            print(f"   Senate API: {senate_duration:.2f}s")
            print(f"   Total bills fetched: {len(bills)}")
            
            return bills
        else:
            # Fetch from specific chamber
            url = f"{CONGRESS_BASE_URL}/bill"
            response = requests.get(url, headers=headers, params={'limit': 250, 'offset': offset, 'chamber': chamber})
            
            if response.status_code == 200:
                data = response.json()
                bills = data.get('bills', [])
                
                # Cache the results
                api_bills_cache = bills
                import time
                api_bills_cache_time = time.time()
                
                return bills
            else:
                print(f"API Error: {response.status_code}")
                return []
                
    except Exception as e:
        print(f"Error fetching bills: {e}")
        return []

def process_congress_bill_lightweight(congress_bill):
    """Process Congress.gov API bill data for homepage (lightweight version)"""
    try:
        # Extract basic bill information from Congress.gov API response
        title = congress_bill.get('title', '')
        
        # Congress.gov API doesn't provide real summaries, so always show "Text not available"
        summary = 'Text not available'
        
        # Extract introduced date from Congress.gov API
        introduced_date = congress_bill.get('introducedDate', '')
        
        # Use placeholder for sponsor (will be fetched on detail page)
        sponsor = 'Click to view sponsor details'
        
        # Extract status from latestAction
        status = ''
        if congress_bill.get('latestAction'):
            if isinstance(congress_bill.get('latestAction'), dict):
                status = congress_bill.get('latestAction', {}).get('text', '')
            else:
                status = congress_bill.get('latestAction', '')
        
        chamber = congress_bill.get('originChamber', '').lower()
        
        # Construct bill_id from available fields
        bill_number = congress_bill.get('number', '')
        congress_number = congress_bill.get('congress', '118')
        bill_type = congress_bill.get('type', '').lower()
        
        if bill_number and bill_type and chamber:
            bill_id = f"{bill_type}{bill_number}-{congress_number}"
        else:
            bill_id = f"unknown-{congress_number}"
        
        # Convert chamber to expected format
        if chamber == 'house':
            chamber = 'House'
        elif chamber == 'senate':
            chamber = 'Senate'
        
        # Create processed bill in expected format (lightweight)
        processed_bill = {
            'bill_id': bill_id,
            'title': title,
            'summary': summary,
            'introduced_date': introduced_date,
            'status': status,
            'latest_action': status,  # Add latest_action field for template compatibility
            'chamber': chamber,
            'sponsor': sponsor,
            'topics': categorize_bill({'title': title, 'summary': ''}),  # Basic categorization
            'bill_type': congress_bill.get('type', ''),  # Store bill type for GovTrack URL
            'bill_number': congress_bill.get('number', ''),  # Store bill number
            'congress': congress_bill.get('congress', '118')  # Store congress number
        }
        
        # Generate Congress.gov URL after bill is created
        processed_bill['congress_url'] = generate_congress_url(processed_bill)
        
        return processed_bill
    except Exception as e:
        print(f"Error processing bill (lightweight): {e}")
        return None

def process_congress_bill(congress_bill):
    """Process Congress.gov API bill data to match application format (full details)"""
    try:
        # Extract bill information from Congress.gov API response
        title = congress_bill.get('title', '')
        
        # Congress.gov API doesn't provide real summaries, so always show "Text not available"
        summary = 'Text not available'
        
        # Extract introduced date from Congress.gov API
        introduced_date = congress_bill.get('introducedDate', '')
        
        # Extract sponsor information - fetch detailed info for bill detail pages
        sponsor = ''
        try:
            # Construct detailed API URL
            bill_number = congress_bill.get('number', '')
            bill_type = congress_bill.get('type', '').lower()
            congress_number = congress_bill.get('congress', '118')
            
            if bill_number and bill_type and congress_number:
                detail_url = f"{CONGRESS_BASE_URL}/bill/{congress_number}/{bill_type}/{bill_number}"
                headers = {'X-API-Key': CONGRESS_API_KEY}
                detail_response = requests.get(detail_url, headers=headers)
                
                if detail_response.status_code == 200:
                    detail_data = detail_response.json()
                    bill_detail = detail_data.get('bill', {})
                    
                    # Extract sponsor from detailed response
                    if bill_detail.get('sponsors') and len(bill_detail.get('sponsors', [])) > 0:
                        primary_sponsor = bill_detail.get('sponsors', [])[0]
                        sponsor = primary_sponsor.get('fullName', '')
                    
                    # Also get the correct introduced date from detailed response
                    if not introduced_date:
                        introduced_date = bill_detail.get('introducedDate', '')
        except Exception as e:
            print(f"Error fetching detailed bill info: {e}")
        
        if not sponsor:
            sponsor = 'Sponsor information not available from Congress.gov API'
        
        # Extract status from latestAction
        status = ''
        if congress_bill.get('latestAction'):
            if isinstance(congress_bill.get('latestAction'), dict):
                status = congress_bill.get('latestAction', {}).get('text', '')
            else:
                status = congress_bill.get('latestAction', '')
        
        chamber = congress_bill.get('originChamber', '').lower()
        
        # Construct bill_id from available fields
        bill_number = congress_bill.get('number', '')
        congress_number = congress_bill.get('congress', '118')
        bill_type = congress_bill.get('type', '').lower()
        
        if bill_number and bill_type and chamber:
            bill_id = f"{bill_type}{bill_number}-{congress_number}"
        else:
            bill_id = f"unknown-{congress_number}"
        
        # Convert chamber to expected format
        if chamber == 'house':
            chamber = 'House'
        elif chamber == 'senate':
            chamber = 'Senate'
        
        # Create processed bill in expected format
        processed_bill = {
            'bill_id': bill_id,
            'title': title,
            'summary': summary,
            'introduced_date': introduced_date,
            'status': status,
            'latest_action': status,  # Add latest_action field for template compatibility
            'chamber': chamber,
            'sponsor': sponsor,
            'topics': categorize_bill({'title': title, 'summary': summary}),
            'bill_type': congress_bill.get('type', ''),  # Store bill type for GovTrack URL
            'bill_number': congress_bill.get('number', ''),  # Store bill number
            'congress': congress_bill.get('congress', '118')  # Store congress number
        }
        
        # Generate Congress.gov URL after bill is created
        processed_bill['congress_url'] = generate_congress_url(processed_bill)
        
        return processed_bill
    except Exception as e:
        print(f"Error processing bill: {e}")
        return None

def categorize_bill(bill):
    """Categorize a bill based on its title and summary"""
    text = f"{bill.get('title', '')} {bill.get('summary', '')}".lower()
    topics = []
    
    # If no meaningful text, return empty topics
    if not text or len(text.strip()) < 10:
        return topics
    
    for topic, keywords in TOPIC_KEYWORDS.items():
        # Check for exact matches and partial matches
        for keyword in keywords:
            if keyword in text:
                topics.append(topic)
                break  # Only add each topic once
    
    # If no topics found, try to categorize based on common patterns
    if not topics:
        if any(word in text for word in ['act', 'law', 'bill', 'legislation']):
            topics.append('general_legislation')
        elif any(word in text for word in ['amendment', 'modify', 'change', 'update']):
            topics.append('legislative_reform')
    
    return topics

def moderate_comment(content):
    """Basic content moderation - check for inappropriate content"""
    # List of words/phrases to flag (you can expand this)
    inappropriate_words = [
        'spam', 'scam', 'fake', 'hate', 'violence', 'threat', 'abuse'
    ]
    
    content_lower = content.lower()
    
    # Check for inappropriate words
    for word in inappropriate_words:
        if word in content_lower:
            return False, f"Content contains inappropriate language: {word}"
    
    # Check for excessive caps (potential spam)
    caps_ratio = sum(1 for c in content if c.isupper()) / len(content) if content else 0
    if caps_ratio > 0.7:
        return False, "Content contains excessive capitalization"
    
    # Check minimum length
    if len(content.strip()) < 10:
        return False, "Comment is too short"
    
    # Check maximum length
    if len(content) > 1000:
        return False, "Comment is too long"
    
    return True, "Comment approved"

def get_client_ip():
    """Get client IP address"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0]
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr

def send_reset_email(user_email, reset_token, user_name):
    """Send password reset email"""
    try:
        # Create reset URL
        reset_url = f"{request.url_root}reset-password/{reset_token}"
        
        # Create email content
        subject = "Password Reset Request - Youth Policy Pulse"
        
        html_content = f"""
        <html>
        <body>
            <h2>Password Reset Request</h2>
            <p>Hello {user_name},</p>
            <p>You requested a password reset for your Youth Policy Pulse account.</p>
            <p>Click the link below to reset your password:</p>
            <p><a href="{reset_url}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Password</a></p>
            <p>Or copy and paste this link into your browser:</p>
            <p>{reset_url}</p>
            <p>This link will expire in 1 hour.</p>
            <p>If you didn't request this password reset, please ignore this email.</p>
            <br>
            <p>Best regards,<br>Youth Policy Pulse Team</p>
        </body>
        </html>
        """
        
        text_content = f"""
        Password Reset Request
        
        Hello {user_name},
        
        You requested a password reset for your Youth Policy Pulse account.
        
        Click this link to reset your password: {reset_url}
        
        This link will expire in 1 hour.
        
        If you didn't request this password reset, please ignore this email.
        
        Best regards,
        Youth Policy Pulse Team
        """
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = FROM_EMAIL
        msg['To'] = user_email
        
        # Add both text and HTML parts
        text_part = MIMEText(text_content, 'plain')
        html_part = MIMEText(html_content, 'html')
        
        msg.attach(text_part)
        msg.attach(html_part)
        
        # Send email using configured service
        if USE_AWS_SES and AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
            # Use AWS SES for production
            return send_email_aws_ses(user_email, subject, html_content, text_content)
        elif SMTP_USERNAME and SMTP_PASSWORD:
            # Use SMTP as fallback
            return send_email_smtp(user_email, subject, html_content, text_content)
        else:
            # Development mode - show reset URL in console
            print(f"📧 Password reset email for {user_email}:")
            print(f"🔗 Reset URL: {reset_url}")
            print(f"📝 Full email content:")
            print(f"Subject: {subject}")
            print(f"To: {user_email}")
            print(f"From: {FROM_EMAIL}")
            print("=" * 50)
            return True
            
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def generate_reset_token():
    """Generate a secure reset token"""
    return secrets.token_urlsafe(32)

def send_contact_verification_email(user_email, verification_token, user_name):
    """Send contact message verification email"""
    try:
        # Create verification URL
        verification_url = f"{request.url_root}verify-contact/{verification_token}"
        
        # Create email content
        subject = "Verify Your Contact Message - Youth Policy Pulse"
        
        html_content = f"""
        <html>
        <body>
            <h2>Verify Your Contact Message</h2>
            <p>Hello {user_name},</p>
            <p>You submitted a contact message to Youth Policy Pulse. To ensure this message is legitimate, please verify your email address by clicking the link below:</p>
            <p><a href="{verification_url}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Verify Message</a></p>
            <p>Or copy and paste this link into your browser:</p>
            <p>{verification_url}</p>
            <p>This link will expire in 24 hours.</p>
            <p>If you didn't submit a contact message, please ignore this email.</p>
            <br>
            <p>Best regards,<br>Youth Policy Pulse Team</p>
        </body>
        </html>
        """
        
        text_content = f"""
        Verify Your Contact Message
        
        Hello {user_name},
        
        You submitted a contact message to Youth Policy Pulse. To ensure this message is legitimate, please verify your email address by clicking this link: {verification_url}
        
        This link will expire in 24 hours.
        
        If you didn't submit a contact message, please ignore this email.
        
        Best regards,
        Youth Policy Pulse Team
        """
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = FROM_EMAIL
        msg['To'] = user_email
        
        # Add both text and HTML parts
        text_part = MIMEText(text_content, 'plain')
        html_part = MIMEText(html_content, 'html')
        
        msg.attach(text_part)
        msg.attach(html_part)
        
        # Send email using configured service
        if USE_AWS_SES and AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
            # Use AWS SES for production
            return send_email_aws_ses(user_email, subject, html_content, text_content)
        elif SMTP_USERNAME and SMTP_PASSWORD:
            # Use SMTP as fallback
            return send_email_smtp(user_email, subject, html_content, text_content)
        else:
            # Development mode - show verification URL in console
            print(f"📧 Contact verification email for {user_email}:")
            print(f"🔗 Verification URL: {verification_url}")
            print(f"📝 Full email content:")
            print(f"Subject: {subject}")
            print(f"To: {user_email}")
            print(f"From: {FROM_EMAIL}")
            print("=" * 50)
            return True
            
    except Exception as e:
        print(f"Error sending contact verification email: {e}")
        return False

def send_verification_email(user_email, verification_token, user_name):
    """Send email verification email"""
    try:
        # Create verification URL
        verification_url = f"{request.url_root}verify-email/{verification_token}"
        
        # Create email content
        subject = "Verify Your Email - Youth Policy Pulse"
        
        html_content = f"""
        <html>
        <body>
            <h2>Welcome to Youth Policy Pulse!</h2>
            <p>Hello {user_name},</p>
            <p>Thank you for registering with Youth Policy Pulse. To complete your registration, please verify your email address by clicking the link below:</p>
            <p><a href="{verification_url}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Verify Email</a></p>
            <p>Or copy and paste this link into your browser:</p>
            <p>{verification_url}</p>
            <p>This link will expire in 24 hours.</p>
            <p>If you didn't create an account with us, please ignore this email.</p>
            <br>
            <p>Best regards,<br>Youth Policy Pulse Team</p>
        </body>
        </html>
        """
        
        text_content = f"""
        Welcome to Youth Policy Pulse!
        
        Hello {user_name},
        
        Thank you for registering with Youth Policy Pulse. To complete your registration, please verify your email address by clicking this link: {verification_url}
        
        This link will expire in 24 hours.
        
        If you didn't create an account with us, please ignore this email.
        
        Best regards,
        Youth Policy Pulse Team
        """
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = FROM_EMAIL
        msg['To'] = user_email
        
        # Add both text and HTML parts
        text_part = MIMEText(text_content, 'plain')
        html_part = MIMEText(html_content, 'html')
        
        msg.attach(text_part)
        msg.attach(html_part)
        
        # Send email using configured service
        if USE_AWS_SES and AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
            # Use AWS SES for production
            return send_email_aws_ses(user_email, subject, html_content, text_content)
        elif SMTP_USERNAME and SMTP_PASSWORD:
            # Use SMTP as fallback
            return send_email_smtp(user_email, subject, html_content, text_content)
        else:
            # Development mode - show verification URL in console and flash message
            print(f"📧 Email verification email for {user_email}:")
            print(f"🔗 Verification URL: {verification_url}")
            print(f"📝 Full email content:")
            print(f"Subject: {subject}")
            print(f"To: {user_email}")
            print(f"From: {FROM_EMAIL}")
            print("=" * 50)
            return True
            
    except Exception as e:
        print(f"Error sending verification email: {e}")
        return False

def generate_verification_token():
    """Generate a secure random token for email verification"""
    return secrets.token_urlsafe(32)

def generate_plain_english_summary(bill_title, bill_summary, bill_status):
    """Generate a plain English summary of a bill using OpenAI"""
    if not OPENAI_API_KEY:
        return "Plain English summary not available (OpenAI API key not configured)"
    
    try:
        # Create a prompt for OpenAI
        # If summary is generic, focus on the title
        if bill_summary == "Text not available" or not bill_summary.strip():
            prompt = f"""
            Please provide a brief, plain English explanation of this Congressional bill in 2-3 sentences based on its title. 
            Make it easy for a high school student to understand what this bill might do and why it matters.
            
            Bill Title: {bill_title}
            Current Status: {bill_status}
            
            Based on the title, explain what this bill likely does:
            """
        else:
            prompt = f"""
            Please provide a brief, plain English summary of this Congressional bill in 2-3 sentences. 
            Make it easy for a high school student to understand what this bill does and why it matters.
            
            Bill Title: {bill_title}
            Bill Summary: {bill_summary}
            Current Status: {bill_status}
            
            Summary:
            """
        
        # Call OpenAI API using the new responses endpoint
        import requests
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
        
        data = {
            "model": "gpt-5-nano",
            "input": prompt,
            "store": True
        }
        
        response = requests.post("https://api.openai.com/v1/responses", headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "completed" and result.get("output"):
                # Extract the text from the output
                for output_item in result["output"]:
                    if output_item.get("type") == "message" and output_item.get("content"):
                        for content_item in output_item["content"]:
                            if content_item.get("type") == "output_text":
                                summary = content_item["text"].strip()
                                return summary
            
            # Fallback if structure is different
            return "Plain English summary generated but format unexpected"
        else:
            print(f"OpenAI API error: {response.status_code} - {response.text}")
            return "Plain English summary temporarily unavailable"
        
    except Exception as e:
        print(f"Error generating OpenAI summary: {e}")
        return "Plain English summary temporarily unavailable"

def send_email_aws_ses(to_email, subject, html_content, text_content):
    """Send email using AWS SES"""
    try:
        # Create SES client
        ses_client = boto3.client(
            'ses',
            region_name=AWS_SES_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )
        
        # Send email
        response = ses_client.send_email(
            Source=FROM_EMAIL,
            Destination={'ToAddresses': [to_email]},
            Message={
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {
                    'Html': {'Data': html_content, 'Charset': 'UTF-8'},
                    'Text': {'Data': text_content, 'Charset': 'UTF-8'}
                }
            }
        )
        
        print(f"✅ AWS SES email sent successfully. MessageId: {response['MessageId']}")
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        print(f"❌ AWS SES error ({error_code}): {e}")
        return False
    except Exception as e:
        print(f"❌ AWS SES error: {e}")
        return False

def send_email_smtp(to_email, subject, html_content, text_content):
    """Send email using SMTP (fallback method)"""
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = FROM_EMAIL
        msg['To'] = to_email
        
        # Add both text and HTML parts
        text_part = MIMEText(text_content, 'plain')
        html_part = MIMEText(html_content, 'html')
        
        msg.attach(text_part)
        msg.attach(html_part)
        
        # Send email
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"✅ SMTP email sent to {to_email}")
        return True
        
    except Exception as e:
        print(f"❌ SMTP error: {e}")
        return False

def get_bill_vote_counts(bill_id):
    """Get vote counts for a specific bill"""
    up_votes = Vote.query.filter_by(bill_id=bill_id, vote_type='up').count()
    down_votes = Vote.query.filter_by(bill_id=bill_id, vote_type='down').count()
    return up_votes, down_votes

def add_vote_counts_to_bills(bills):
    """Add vote counts to a list of bills"""
    for bill in bills:
        up_votes, down_votes = get_bill_vote_counts(bill['bill_id'])
        bill['up_votes'] = up_votes
        bill['down_votes'] = down_votes
        bill['total_votes'] = up_votes + down_votes
    return bills

def generate_congress_url(bill):
    """Generate correct Congress.gov URL for a bill"""
    try:
        # If bill is a dictionary with bill information
        if isinstance(bill, dict):
            bill_type = bill.get('bill_type', '').lower()
            bill_number = bill.get('bill_number', '')
            congress = bill.get('congress', '119')
            chamber = bill.get('chamber', '').lower()
            bill_id = bill.get('bill_id', '')
            
            # Determine the correct bill type prefix and chamber format
            if bill_type:
                # Use the bill type directly (e.g., 'hr', 's', 'hjres', etc.)
                bill_prefix = bill_type
            elif chamber == 'house':
                # Default to HR for House bills
                bill_prefix = 'hr'
            elif chamber == 'senate':
                # Default to S for Senate bills
                bill_prefix = 's'
            else:
                # Fallback to HR
                bill_prefix = 'hr'
            
            if bill_number and bill_id:
                # Format: https://www.congress.gov/bill/119th-congress/senate-bill/284?q=%7B%22search%22%3A%22s284-119%22%7D&s=1&r=1
                chamber_format = "house-bill" if chamber == 'house' else "senate-bill"
                encoded_bill_id = bill_id.replace('-', '%2D')  # URL encode the bill ID
                url = f"https://www.congress.gov/bill/{congress}th-congress/{chamber_format}/{bill_number}?q=%7B%22search%22%3A%22{bill_id}%22%7D&s=1&r=1"
                return url
        
        # Fallback: try to extract from bill_id
        if isinstance(bill, str):
            bill_id = bill
        else:
            bill_id = bill.get('bill_id', '') if hasattr(bill, 'get') else str(bill)
        
        parts = bill_id.split('-')
        if len(parts) >= 2:
            bill_number = parts[0]
            congress = parts[1]
            # Default to HR format
            return f"https://www.govtrack.us/congress/bills/{congress}/hr{bill_number}"
        
        # Final fallback
        return f"https://www.govtrack.us/congress/bills/119/{bill_id}"
        
    except Exception as e:
        print(f"Error generating GovTrack URL for {bill}: {e}")
        return f"https://www.govtrack.us/congress/bills/119/{bill_id if isinstance(bill, str) else 'unknown'}"

@app.route('/')
def index():
    """Home page - Congressional Bills Dashboard"""
    # Get filter parameters
    topic_filter = request.args.get('topic', '')
    chamber_filter = request.args.get('chamber', 'both')
    search_query = request.args.get('search', '')
    
    # Get pagination parameters
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))  # Default to 10 bills per page
    
    # Validate per_page options
    if per_page not in [10, 20, 50]:
        per_page = 10
    
    print(f"🎯 Fetching bills and applying filters")
    
    # Fetch all bills (without limit) to support proper filtering
    try:
        # Call with no limit parameter to fetch cached full dataset
        all_bills = get_processed_bills_cached(chamber='both', congress=118)
        if not all_bills:
            print("⚠️ No bills returned from API")
            all_bills = []
    except Exception as e:
        print(f"Error fetching bills from API: {e}")
        all_bills = []
    
    # Apply filters to ALL bills before pagination
    filtered_bills = all_bills
    
    if topic_filter:
        filtered_bills = [bill for bill in filtered_bills if topic_filter in bill.get('topics', [])]
    
    if chamber_filter != 'both':
        filtered_bills = [bill for bill in filtered_bills if bill.get('chamber', '').lower() == chamber_filter.lower()]
    
    if search_query:
        search_lower = search_query.lower()
        filtered_bills = [bill for bill in filtered_bills 
                        if search_lower in bill.get('title', '').lower() 
                        or search_lower in bill.get('summary', '').lower()]
    
    # Calculate pagination based on filtered results
    total_bills = len(filtered_bills)
    total_pages = (total_bills + per_page - 1) // per_page if total_bills > 0 else 1
    
    # Ensure page is within valid range
    page = max(1, min(page, total_pages)) if total_pages > 0 else 1
    
    # Paginate filtered results
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    bills_for_page = filtered_bills[start_idx:end_idx]
    
    print(f"⚡ Displaying {len(bills_for_page)} bills for page {page} (filtered from {total_bills} total bills)")
    
    # Get API statistics for stats display
    try:
        _, api_stats = get_processed_bills_cached_with_stats(chamber_filter, 118, per_page)
    except Exception as e:
        print(f"Error fetching stats: {e}")
        api_stats = {'total_bills': 0, 'house_bills': 0, 'senate_bills': 0}
    
    # Add vote counts to bills
    bills_for_page = add_vote_counts_to_bills(bills_for_page)
    
    # Use real API statistics
    total_bills_all = api_stats.get('total_bills', 0)
    
    # Fix House/Senate counts - API returns same total for both, so use realistic estimates
    if api_stats.get('house_bills', 0) == api_stats.get('senate_bills', 0) and total_bills_all > 0:
        # API returns same count for both chambers, use realistic distribution
        house_bills = int(total_bills_all * 0.6)  # ~60% House bills
        senate_bills = int(total_bills_all * 0.4)  # ~40% Senate bills
    else:
        house_bills = api_stats.get('house_bills', 0)
        senate_bills = api_stats.get('senate_bills', 0)
    
    # Use realistic estimates for status distribution (API doesn't provide this breakdown)
    # These are based on typical congressional bill status distributions
    status_counts = {
        'Introduced': int(total_bills_all * 0.3),  # ~30% of bills are introduced
        'In Committee': int(total_bills_all * 0.25),  # ~25% in committee
        'On Calendar': int(total_bills_all * 0.1),  # ~10% on calendar
        'Passed/Enacted': int(total_bills_all * 0.05),  # ~5% passed/enacted
        'Other': int(total_bills_all * 0.3)  # ~30% other statuses
    }
    
    # Calculate pagination info
    has_prev = page > 1
    has_next = page < total_pages
    
    return render_template('index.html', 
                         bills=bills_for_page, 
                         topics=TOPIC_KEYWORDS.keys(),
                         selected_topic=topic_filter,
                         selected_chamber=chamber_filter,
                         search_query=search_query,
                         # Pagination info
                         page=page,
                         per_page=per_page,
                         total_pages=total_pages,
                         total_bills=total_bills,
                         has_prev=has_prev,
                         has_next=has_next,
                         prev_page=page - 1 if has_prev else None,
                         next_page=page + 1 if has_next else None,
                         # Quick stats from all bills
                         total_bills_all=total_bills_all,
                         house_bills=house_bills,
                         senate_bills=senate_bills,
                         status_counts=status_counts)

@app.route('/about')
def about():
    """About page"""
    return render_template('about.html')

@app.route('/civics101')
def civics101():
    """Civics 101 mini-lessons page"""
    return render_template('civics101.html')

@app.route('/action-center')
def action_center():
    """Action Center page"""
    return render_template('action_center.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        # Check if user already exists
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists', 'error')
            return render_template('register.html', form=form)
        
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered', 'error')
            return render_template('register.html', form=form)
        
        # Create new user (email not verified initially)
        user = User(
            username=form.username.data,
            email=form.email.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            zip_code=form.zip_code.data,
            email_verified=True  # Disable email verification - set to True by default
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.flush()  # Get the user ID
        
        # Email verification disabled - users can login immediately
        db.session.commit()
        flash('Registration successful! You can now log in.', 'success')
        
        return redirect(url_for('login'))
    
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user and user.check_password(form.password.data):
            # Email verification disabled - allow login immediately
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('dashboard')
            return redirect(next_page)
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html', form=form)

@app.route('/verify-email/<token>')
def verify_email(token):
    """Email verification disabled - redirect to login"""
    flash('Email verification is currently disabled. You can log in directly.', 'info')
    return redirect(url_for('login'))

@app.route('/resend-verification', methods=['GET', 'POST'])
def resend_verification():
    """Email verification disabled - redirect to login"""
    flash('Email verification is currently disabled. You can log in directly.', 'info')
    return redirect(url_for('login'))

@app.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Forgot password page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user:
            # Generate reset token
            token = generate_reset_token()
            expires_at = datetime.now() + timedelta(hours=1)
            
            # Create or update reset token
            existing_token = PasswordResetToken.query.filter_by(user_id=user.id, is_used=False).first()
            if existing_token:
                existing_token.token = token
                existing_token.expires_at = expires_at
                existing_token.is_used = False
            else:
                reset_token = PasswordResetToken(
                    user_id=user.id,
                    token=token,
                    expires_at=expires_at
                )
                db.session.add(reset_token)
            
            db.session.commit()
            
            # Send reset email
            if send_reset_email(user.email, token, user.first_name):
                if SMTP_USERNAME and SMTP_PASSWORD:
                    flash('Password reset link has been sent to your email.', 'success')
                else:
                    # Development mode - show reset URL
                    reset_url = f"{request.url_root}reset-password/{token}"
                    flash(f'Password reset link generated! In development mode, please click this link to reset your password: {reset_url}', 'info')
            else:
                flash('Failed to send reset email. Please try again.', 'error')
        else:
            # Don't reveal if email exists or not for security
            flash('If an account with that email exists, a password reset link has been sent.', 'info')
        
        return redirect(url_for('login'))
    
    return render_template('forgot_password.html', form=form)

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    # Find valid token
    reset_token = PasswordResetToken.query.filter_by(token=token).first()
    
    if not reset_token or not reset_token.is_valid():
        flash('Invalid or expired reset token.', 'error')
        return redirect(url_for('forgot_password'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        # Update user password
        user = User.query.get(reset_token.user_id)
        if user:
            user.set_password(form.password.data)
            
            # Mark token as used
            reset_token.is_used = True
            
            db.session.commit()
            
            flash('Your password has been reset successfully. Please log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('User not found.', 'error')
            return redirect(url_for('forgot_password'))
    
    return render_template('reset_password.html', form=form, token=token)

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard"""
    # Get user's watchlist
    watchlist = WatchlistItem.query.filter_by(user_id=current_user.id).order_by(WatchlistItem.added_at.desc()).all()
    
    # Get user's comments (both with user_id and by email if they match)
    user_comments = Comment.query.filter(
        (Comment.user_id == current_user.id) | 
        (Comment.author_email == current_user.email)
    ).order_by(Comment.created_at.desc()).limit(10).all()
    
    # Get user's votes (both with user_id and by IP if they match)
    # Note: This is a simplified approach - in production you'd want better IP tracking
    user_votes = Vote.query.filter_by(user_id=current_user.id).order_by(Vote.created_at.desc()).limit(10).all()
    
    # Get user's topic alerts
    topic_alerts = TopicAlert.query.filter_by(user_id=current_user.id, is_active=True).all()
    
    return render_template('dashboard.html', 
                         watchlist=watchlist,
                         user_comments=user_comments,
                         user_votes=user_votes,
                         topic_alerts=topic_alerts)

@app.route('/api/send-email', methods=['POST'])
def api_send_email():
    """API endpoint to send emails to representatives"""
    data = request.get_json()
    
    if not data or not all(k in data for k in ['representative_email', 'subject', 'message', 'sender_name', 'sender_email']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # In a real application, you would integrate with an email service like SendGrid, Mailgun, or SMTP
    # For now, we'll simulate the email sending
    try:
        # Simulate email sending
        email_data = {
            'to': data['representative_email'],
            'subject': data['subject'],
            'message': data['message'],
            'sender_name': data['sender_name'],
            'sender_email': data['sender_email'],
            'sent_at': datetime.now(timezone.utc).isoformat()
        }
        
        # Log the email (in production, this would be sent via email service)
        print(f"Email sent: {email_data}")
        
        return jsonify({
            'success': True,
            'message': 'Email sent successfully!',
            'email_id': f"email_{datetime.now(timezone.utc).timestamp()}"
        })
        
    except Exception as e:
        return jsonify({'error': 'Failed to send email'}), 500

@app.route('/api/bills')
def api_bills():
    """API endpoint to get all bills"""
    bills_with_votes = add_vote_counts_to_bills(sample_bills.copy())
    return jsonify(bills_with_votes)

@app.route('/api/bills/fetch')
def api_fetch_bills():
    """API endpoint to fetch bills from Congress.gov API"""
    chamber = request.args.get('chamber', 'both')
    congress = request.args.get('congress', 118)
    
    bills = fetch_bills_from_api(chamber, congress)
    
    # Process and categorize bills from Congress.gov API
    processed_bills = []
    for bill in bills:
        processed_bill = process_congress_bill(bill)
        if processed_bill:
            processed_bills.append(processed_bill)
    
    return jsonify(processed_bills)

@app.route('/api/bills/search')
def api_search_bills():
    """API endpoint to search bills"""
    query = request.args.get('q', '')
    topic = request.args.get('topic', '')
    chamber = request.args.get('chamber', 'both')
    
    filtered_bills = sample_bills.copy()
    
    if query:
        query_lower = query.lower()
        filtered_bills = [bill for bill in filtered_bills 
                        if query_lower in bill.get('title', '').lower() 
                        or query_lower in bill.get('summary', '').lower()]
    
    if topic:
        filtered_bills = [bill for bill in filtered_bills if topic in bill.get('topics', [])]
    
    if chamber != 'both':
        filtered_bills = [bill for bill in filtered_bills if bill.get('chamber', '').lower() == chamber.lower()]
    
    # Add vote counts to bills
    filtered_bills = add_vote_counts_to_bills(filtered_bills)
    
    return jsonify(filtered_bills)

@app.route('/api/bills/<bill_id>/comments', methods=['POST'])
@login_required
def api_add_comment(bill_id):
    """API endpoint to add a comment to a bill - requires login"""
    data = request.get_json()
    
    if not data or 'content' not in data:
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Auto-approve comments from logged-in users
    is_approved = True
    message = "Comment added successfully!"
    
    # Create new comment
    comment = Comment(
        bill_id=bill_id,
        author_name=current_user.username,
        author_email=current_user.email,
        content=data['content'],
        is_approved=is_approved,
        ip_address=get_client_ip(),
        user_id=current_user.id
    )
    
    try:
        db.session.add(comment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': message,
            'comment': comment.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to save comment'}), 500

@app.route('/api/bills/<bill_id>/comments')
def api_get_comments(bill_id):
    """API endpoint to get approved comments for a bill"""
    comments = Comment.query.filter_by(bill_id=bill_id, is_approved=True).order_by(Comment.created_at.desc()).all()
    return jsonify([comment.to_dict() for comment in comments])

@app.route('/api/bills/<bill_id>/vote', methods=['POST'])
@login_required
def api_vote_bill(bill_id):
    """API endpoint to vote on a bill - requires login"""
    try:
        data = request.get_json()
        
        if not data or 'vote_type' not in data:
            return jsonify({'error': 'Missing vote_type'}), 400
        
        if data['vote_type'] not in ['up', 'down']:
            return jsonify({'error': 'Invalid vote_type. Must be "up" or "down"'}), 400
        
        client_ip = get_client_ip()
        
        # Check if user has already voted (user is guaranteed to be logged in)
        existing_vote = Vote.query.filter_by(bill_id=bill_id, user_id=current_user.id).first()
        
        if existing_vote:
            # Update existing vote
            existing_vote.vote_type = data['vote_type']
            existing_vote.created_at = datetime.now(timezone.utc)
        else:
            # Create new vote
            vote = Vote(
                bill_id=bill_id,
                ip_address=client_ip,
                vote_type=data['vote_type'],
                user_id=current_user.id
            )
            db.session.add(vote)
        
        db.session.commit()
        
        # Get updated vote counts
        up_votes = Vote.query.filter_by(bill_id=bill_id, vote_type='up').count()
        down_votes = Vote.query.filter_by(bill_id=bill_id, vote_type='down').count()
        
        return jsonify({
            'success': True,
            'up_votes': up_votes,
            'down_votes': down_votes,
            'user_vote': data['vote_type']
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to save vote: {str(e)}'}), 500

@app.route('/api/bills/<bill_id>/votes')
def api_get_votes(bill_id):
    """API endpoint to get vote counts for a bill"""
    up_votes = Vote.query.filter_by(bill_id=bill_id, vote_type='up').count()
    down_votes = Vote.query.filter_by(bill_id=bill_id, vote_type='down').count()
    
    # Check for user's vote (only if logged in)
    user_vote = None
    if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
        user_vote = Vote.query.filter_by(bill_id=bill_id, user_id=current_user.id).first()
    
    user_vote_type = user_vote.vote_type if user_vote else None
    
    return jsonify({
        'up_votes': up_votes,
        'down_votes': down_votes,
        'user_vote': user_vote_type
    })

@app.route('/api/watchlist', methods=['POST'])
@login_required
def api_add_to_watchlist():
    """API endpoint to add bill to user's watchlist"""
    data = request.get_json()
    
    if not data or not all(k in data for k in ['bill_id', 'bill_title']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Check if already in watchlist
    existing = WatchlistItem.query.filter_by(user_id=current_user.id, bill_id=data['bill_id']).first()
    if existing:
        return jsonify({'error': 'Bill already in watchlist'}), 400
    
    # Add to watchlist
    watchlist_item = WatchlistItem(
        user_id=current_user.id,
        bill_id=data['bill_id'],
        bill_title=data['bill_title'],
        notes=data.get('notes', '')
    )
    
    try:
        db.session.add(watchlist_item)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Bill added to watchlist'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to add to watchlist'}), 500

@app.route('/api/watchlist/<bill_id>', methods=['DELETE'])
@login_required
def api_remove_from_watchlist(bill_id):
    """API endpoint to remove bill from user's watchlist"""
    watchlist_item = WatchlistItem.query.filter_by(user_id=current_user.id, bill_id=bill_id).first()
    
    if not watchlist_item:
        return jsonify({'error': 'Bill not in watchlist'}), 404
    
    try:
        db.session.delete(watchlist_item)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Bill removed from watchlist'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to remove from watchlist'}), 500

@app.route('/api/topic-alerts', methods=['POST'])
@login_required
def api_update_topic_alerts():
    """API endpoint to update user's topic alerts"""
    data = request.get_json()
    
    if not data or 'topics' not in data:
        return jsonify({'error': 'Missing topics data'}), 400
    
    try:
        # Remove existing alerts
        TopicAlert.query.filter_by(user_id=current_user.id).delete()
        
        # Add new alerts
        for topic in data['topics']:
            alert = TopicAlert(user_id=current_user.id, topic=topic)
            db.session.add(alert)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Topic alerts updated'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update alerts'}), 500

@app.route('/api/user/activity')
@login_required
def api_user_activity():
    """API endpoint to get user's activity summary"""
    comments_count = Comment.query.filter_by(user_id=current_user.id).count()
    votes_count = Vote.query.filter_by(user_id=current_user.id).count()
    watchlist_count = WatchlistItem.query.filter_by(user_id=current_user.id).count()
    alerts_count = TopicAlert.query.filter_by(user_id=current_user.id, is_active=True).count()
    
    return jsonify({
        'comments_count': comments_count,
        'votes_count': votes_count,
        'watchlist_count': watchlist_count,
        'alerts_count': alerts_count,
        'user': current_user.to_dict()
    })

@app.route('/api/events/register', methods=['POST'])
@login_required
def api_register_event():
    """API endpoint to register for an event"""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ['event_name', 'event_date', 'event_time', 'event_location']):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Check if user is already registered for this event
        existing_registration = EventRegistration.query.filter_by(
            user_id=current_user.id,
            event_name=data['event_name'],
            event_date=data['event_date']
        ).first()
        
        if existing_registration:
            return jsonify({'error': 'You are already registered for this event'}), 400
        
        # Create new registration
        registration = EventRegistration(
            user_id=current_user.id,
            event_name=data['event_name'],
            event_date=data['event_date'],
            event_time=data['event_time'],
            event_location=data['event_location']
        )
        
        db.session.add(registration)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Successfully registered for the event!',
            'registration': registration.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to register for event: {str(e)}'}), 500

@app.route('/api/events/registrations')
@login_required
def api_get_user_registrations():
    """API endpoint to get user's event registrations"""
    registrations = EventRegistration.query.filter_by(
        user_id=current_user.id,
        status='registered'
    ).order_by(EventRegistration.registration_date.desc()).all()
    
    return jsonify([registration.to_dict() for registration in registrations])

@app.route('/api/events/cancel', methods=['POST'])
@login_required
def api_cancel_registration():
    """API endpoint to cancel event registration"""
    try:
        data = request.get_json()
        
        if not data or 'registration_id' not in data:
            return jsonify({'error': 'Missing registration ID'}), 400
        
        registration = EventRegistration.query.filter_by(
            id=data['registration_id'],
            user_id=current_user.id
        ).first()
        
        if not registration:
            return jsonify({'error': 'Registration not found'}), 404
        
        registration.status = 'cancelled'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Registration cancelled successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to cancel registration: {str(e)}'}), 500

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    """Contact form page"""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        
        if current_user.is_authenticated:
            # User is logged in - use their stored information and send immediately
            contact_msg = ContactMessage(
                user_id=current_user.id,
                name=current_user.first_name + ' ' + current_user.last_name,
                email=current_user.email,
                message=message,
                is_verified=True  # Logged-in users are automatically verified
            )
            db.session.add(contact_msg)
            db.session.commit()
            
            flash(f'Thank you {current_user.first_name}! Your message has been received.', 'success')
            return redirect(url_for('contact'))
        else:
            # User is not logged in - require email verification
            # Check if email already has a pending unverified message
            existing_msg = ContactMessage.query.filter_by(
                email=email, 
                is_verified=False
            ).first()
            
            if existing_msg:
                # Update existing message
                existing_msg.name = name
                existing_msg.message = message
                existing_msg.created_at = datetime.now()
            else:
                # Create new message
                verification_token = generate_verification_token()
                contact_msg = ContactMessage(
                    user_id=None,
                    name=name,
                    email=email,
                    message=message,
                    is_verified=False,
                    verification_token=verification_token
                )
                db.session.add(contact_msg)
                db.session.commit()
                
                # Send verification email
                if send_contact_verification_email(email, verification_token, name):
                    if SMTP_USERNAME and SMTP_PASSWORD:
                        flash('Please check your email and click the verification link to send your message.', 'info')
                    else:
                        # Development mode - show verification URL
                        verification_url = f"{request.url_root}verify-contact/{verification_token}"
                        flash(f'Please click this link to verify your message: {verification_url}', 'info')
                else:
                    flash('Failed to send verification email. Please try again.', 'error')
            
        return redirect(url_for('contact'))
    
    return render_template('contact.html')

@app.route('/verify-contact/<token>')
def verify_contact(token):
    """Verify contact message with token"""
    contact_msg = ContactMessage.query.filter_by(verification_token=token).first()
    
    if not contact_msg:
        flash('Invalid verification link', 'error')
        return redirect(url_for('contact'))
    
    if contact_msg.is_verified:
        flash('This message has already been verified', 'info')
        return redirect(url_for('contact'))
    
    # Mark message as verified
    contact_msg.is_verified = True
    contact_msg.verification_token = None  # Clear the token
    db.session.commit()
    
    flash('Your message has been verified and sent successfully!', 'success')
    return redirect(url_for('contact'))

@app.route('/bill/<bill_id>')
def bill_detail(bill_id):
    """Bill detail page"""
    print(f"🚀 BILL DETAIL ROUTE CALLED with bill_id: {bill_id}")
    # Make a targeted API call for this specific bill
    bill = None
    try:
        print(f"🔍 Fetching detailed information for bill: {bill_id}")
        print(f"🔍 Bill ID parts: {bill_id.split('-')}")
        # Make a targeted API call for this specific bill instead of fetching all bills
        # Parse bill_id to get components for targeted API call
        parts = bill_id.split('-')
        if len(parts) >= 2:
            bill_identifier = parts[0]  # hr1234 or s1234
            congress_number = parts[1]  # 118
            
            # Extract bill type and number - use the same logic as process_congress_bill
            if bill_identifier.startswith('hr'):
                bill_type = 'hr'
                bill_number = bill_identifier[2:]
            elif bill_identifier.startswith('s'):
                bill_type = 's'
                bill_number = bill_identifier[1:]
            elif bill_identifier.startswith('hjres'):
                bill_type = 'hjres'
                bill_number = bill_identifier[5:]
            elif bill_identifier.startswith('sjres'):
                bill_type = 'sjres'
                bill_number = bill_identifier[5:]
            elif bill_identifier.startswith('hconres'):
                bill_type = 'hconres'
                bill_number = bill_identifier[7:]
            elif bill_identifier.startswith('sconres'):
                bill_type = 'sconres'
                bill_number = bill_identifier[7:]
            elif bill_identifier.startswith('hres'):
                bill_type = 'hres'
                bill_number = bill_identifier[4:]
            elif bill_identifier.startswith('sres'):
                bill_type = 'sres'
                bill_number = bill_identifier[4:]
            else:
                bill_type = bill_identifier
                bill_number = '1'
            
            # Make targeted API call
            detail_url = f"{CONGRESS_BASE_URL}/bill/{congress_number}/{bill_type}/{bill_number}"
            headers = {'X-API-Key': CONGRESS_API_KEY}
            
            print(f"🌐 Making targeted API call: {detail_url}")
            print(f"🌐 Parsed - Congress: {congress_number}, Type: {bill_type}, Number: {bill_number}")
            detail_response = requests.get(detail_url, headers=headers)
            
            if detail_response.status_code == 200:
                detail_data = detail_response.json()
                api_bill = detail_data.get('bill', {})
                print(f"📄 API response contains bill: {bool(api_bill)}")
                if api_bill:
                    processed_bill = process_congress_bill(api_bill)
                    print(f"📄 Processed bill ID: {processed_bill.get('bill_id') if processed_bill else 'None'}")
                    print(f"📄 Expected bill ID: {bill_id}")
                    if processed_bill and processed_bill.get('bill_id') == bill_id:
                        bill = processed_bill
                        print(f"✅ Found detailed information for {bill_id}")
                    else:
                        print(f"❌ Bill ID mismatch: expected {bill_id}, got {processed_bill.get('bill_id') if processed_bill else 'None'}")
                else:
                    print(f"❌ No bill data in API response")
            else:
                print(f"❌ Targeted API call failed: {detail_response.status_code}")
                print(f"❌ Response text: {detail_response.text[:200]}")
    except Exception as e:
        print(f"Error fetching detailed bill info: {e}")
    
    # If bill not found, show error
    if not bill:
        print(f"❌ Bill not found: {bill_id}")
        flash('Bill not found', 'error')
        return redirect(url_for('index'))
    
    # Get approved comments for this bill
    comments = Comment.query.filter_by(bill_id=bill_id, is_approved=True).order_by(Comment.created_at.desc()).all()
    
    # Get vote counts
    up_votes = Vote.query.filter_by(bill_id=bill_id, vote_type='up').count()
    down_votes = Vote.query.filter_by(bill_id=bill_id, vote_type='down').count()
    
    # Check if current user has voted (only if logged in)
    user_vote = None
    if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
        user_vote = Vote.query.filter_by(bill_id=bill_id, user_id=current_user.id).first()
    
    user_vote_type = user_vote.vote_type if user_vote else None
    
    # Add vote counts to the bill object
    bill['up_votes'] = up_votes
    bill['down_votes'] = down_votes
    bill['total_votes'] = up_votes + down_votes
    
    # Don't generate summary here - let JavaScript fetch it asynchronously
    print(f"🎯 RENDERING TEMPLATE immediately for bill: {bill.get('title', '')}")
    return render_template('bill_detail.html', 
                         bill=bill, 
                         comments=comments,
                         up_votes=up_votes,
                         down_votes=down_votes,
                         user_vote_type=user_vote_type,
                         plain_english_summary=None,  # Will be fetched by JavaScript
                         generate_congress_url=generate_congress_url)

@app.route('/api/bill/<bill_id>/summary')
def get_bill_summary(bill_id):
    """API endpoint to get plain English summary for a bill"""
    try:
        print(f"🔍 API Summary Request for bill_id: {bill_id}")
        
        # Parse bill_id to get components
        parts = bill_id.split('-')
        print(f"🔍 Parsed parts: {parts}")
        
        if len(parts) >= 2:
            bill_identifier = parts[0]  # hr1234 or s1234
            congress_number = parts[1]  # 118
            
            print(f"🔍 Bill identifier: {bill_identifier}, Congress: {congress_number}")
            
            # Extract bill type and number - use the same logic as process_congress_bill
            if bill_identifier.startswith('hr'):
                bill_type = 'hr'
                bill_number = bill_identifier[2:]
            elif bill_identifier.startswith('s'):
                bill_type = 's'
                bill_number = bill_identifier[1:]
            elif bill_identifier.startswith('hjres'):
                bill_type = 'hjres'
                bill_number = bill_identifier[5:]
            elif bill_identifier.startswith('sjres'):
                bill_type = 'sjres'
                bill_number = bill_identifier[5:]
            elif bill_identifier.startswith('hconres'):
                bill_type = 'hconres'
                bill_number = bill_identifier[7:]
            elif bill_identifier.startswith('sconres'):
                bill_type = 'sconres'
                bill_number = bill_identifier[7:]
            elif bill_identifier.startswith('hres'):
                bill_type = 'hres'
                bill_number = bill_identifier[4:]
            elif bill_identifier.startswith('sres'):
                bill_type = 'sres'
                bill_number = bill_identifier[4:]
            else:
                bill_type = bill_identifier
                bill_number = '1'
            
            print(f"🔍 Bill type: {bill_type}, Bill number: {bill_number}")
            
            # Make targeted API call to get bill details
            detail_url = f"{CONGRESS_BASE_URL}/bill/{congress_number}/{bill_type}/{bill_number}"
            headers = {'X-API-Key': CONGRESS_API_KEY}
            
            print(f"🔍 API call to: {detail_url}")
            response = requests.get(detail_url, headers=headers, timeout=10)
            print(f"📡 API response status: {response.status_code}")
            
            if response.status_code == 200:
                bill_data = response.json()
                print(f"📡 API response data keys: {list(bill_data.keys())}")
                
                if bill_data.get('bill'):
                    bill = bill_data['bill']
                    print(f"📡 Found bill: {bill.get('title', 'No title')}")
                    
                    # Generate plain English summary
                    summary = generate_plain_english_summary(
                        bill.get('title', ''),
                        bill.get('summary', ''),
                        bill.get('status', '')
                    )
                    
                    print(f"📝 Generated summary: {summary[:100]}...")
                    
                    return jsonify({
                        'success': True,
                        'summary': summary
                    })
                else:
                    print(f"📡 No bill found in response")
            else:
                print(f"📡 API error: {response.status_code} - {response.text}")
        
        print(f"📡 Returning 'Bill not found' error")
        return jsonify({
            'success': False,
            'error': 'Bill not found'
        })
        
    except Exception as e:
        print(f"Error generating summary: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/test')
def test_minimal():
    """Test page to check for flashing issues"""
    return render_template('test_minimal.html')

# Initialize database when app is imported (for Elastic Beanstalk)
with app.app_context():
    try:
        db.create_all()
        print("✅ Database initialized successfully!")
    except Exception as e:
        print(f"⚠️  Database initialization failed: {e}")

if __name__ == '__main__':
    # Create templates and static directories if they don't exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    
    app.run(debug=True, host='127.0.0.1', port=8000)
