"""
Elastic Beanstalk WSGI entry point for Congressional Bills Tracker
"""
import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from app import app as application

if __name__ == "__main__":
    application.run()

