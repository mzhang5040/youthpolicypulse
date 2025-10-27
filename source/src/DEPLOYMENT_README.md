# Youth Policy Pulse - AWS Elastic Beanstalk Deployment

This package contains all files necessary for deploying the Youth Policy Pulse application to AWS Elastic Beanstalk.

## Setup Instructions

1. **Environment Variables**: Copy `.ebextensions/07-environment-variables.config.example` to `.ebextensions/07-environment-variables.config` and replace placeholder values with your actual API keys and credentials.

2. **Required Environment Variables**:
   - `OPENAI_API_KEY`: Your OpenAI API key for bill summaries
   - `CONGRESS_API_KEY`: Your Congress.gov API key (optional)
   - `SMTP_USERNAME` & `SMTP_PASSWORD`: Email credentials (optional)
   - `AWS_ACCESS_KEY_ID` & `AWS_SECRET_ACCESS_KEY`: AWS credentials (optional)
   - `MYSQL_*`: MySQL database credentials (optional)

3. **Deployment**: Upload this zip file to AWS Elastic Beanstalk.

## Files Included

- `app.py`: Main Flask application
- `application.py`: WSGI entry point
- `requirements.txt`: Python dependencies
- `templates/`: HTML templates
- `static/`: CSS, JS, and images
- `.ebextensions/`: AWS configuration files
- `instance/`: SQLite database (for development)

## Security Note

All sensitive information has been masked with placeholder values. You must configure your actual API keys and credentials before deployment.
