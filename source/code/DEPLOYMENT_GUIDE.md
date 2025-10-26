# Deployment Guide

This guide explains how to deploy Youth Policy Pulse both locally and on AWS Elastic Beanstalk.

## 📦 Deployment Packages

Two deployment packages have been created:

1. **`deploy_local.zip`** (5.2 MB) - For local development deployment
2. **`deploy_aws.zip`** (861 KB) - For AWS Elastic Beanstalk deployment

## 🏠 Local Deployment

### Package Contents
- `app.py` - Main Flask application
- `requirements.txt` - Python dependencies
- `init_db.py` - Database initialization script
- `README.md` - Full documentation
- `flask_requirements.txt` - Flask-specific dependencies
- `.env.example` - Environment variable template
- `templates/` - All HTML templates
- `static/` - CSS, JavaScript, and images (including all headshots)

### Steps to Deploy Locally

1. **Extract the package**:
   ```bash
   unzip deploy_local.zip
   cd PythonProject
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env file with your API keys and credentials
   ```

5. **Initialize database**:
   ```bash
   python init_db.py
   ```

6. **Run the application**:
   ```bash
   python app.py
   ```

7. **Access the application**:
   Open browser to `http://127.0.0.1:8000`

## ☁️ AWS Elastic Beanstalk Deployment

### Package Contents
- `app.py` - Main Flask application
- `application.py` - WSGI entry point for production
- `requirements.txt` - Python dependencies
- `eb-config.yml` - Elastic Beanstalk configuration
- `.ebextensions/` - EB configuration files
  - `01-packages.config` - System packages
  - `02-python.config` - Python settings
  - `03-environment.config` - Environment variables template
  - `04-logs.config` - Logging configuration
  - `05-https.config` - HTTPS settings
- `templates/` - All HTML templates
- `static/` - CSS, JavaScript, and optimized images (only active headshots)
- `.ebignore` - Files to exclude from deployment

### Steps to Deploy on AWS

1. **Prerequisites**:
   - AWS account
   - AWS Elastic Beanstalk CLI installed (`pip install awsebcli`)
   - Congress.gov API key

2. **Extract the package**:
   ```bash
   unzip deploy_aws.zip
   cd PythonProject
   ```

3. **Create Elastic Beanstalk environment**:
   ```bash
   eb init -p python-3.11 youth-policy-pulse --region us-east-1
   ```

4. **Create environment**:
   ```bash
   eb create youth-policy-pulse-env
   ```

5. **Set environment variables** (via AWS Console or CLI):
   ```bash
   eb setenv SECRET_KEY=your-secret-key \
            CONGRESS_API_KEY=your-congress-api-key \
            MYSQL_HOST=your-rds-endpoint \
            MYSQL_USER=your-mysql-user \
            MYSQL_PASSWORD=your-mysql-password \
            MYSQL_DATABASE=your-database-name \
            AWS_ACCESS_KEY_ID=your-aws-access-key \
            AWS_SECRET_ACCESS_KEY=your-aws-secret-key \
            USE_AWS_SES=true \
            FROM_EMAIL=youthpolicypulse@gmail.com
   ```

6. **Deploy**:
   ```bash
   eb deploy
   ```

7. **Open the application**:
   ```bash
   eb open
   ```

### Environment Variables Required

#### Essential
- `SECRET_KEY` - Flask secret key for sessions
- `CONGRESS_API_KEY` - Congress.gov API key

#### Database (MySQL)
- `MYSQL_HOST` - RDS endpoint
- `MYSQL_PORT` - Port (default: 3306)
- `MYSQL_USER` - Database username
- `MYSQL_PASSWORD` - Database password
- `MYSQL_DATABASE` - Database name

#### Email (AWS SES)
- `AWS_SES_REGION` - SES region (default: us-east-1)
- `AWS_ACCESS_KEY_ID` - AWS access key
- `AWS_SECRET_ACCESS_KEY` - AWS secret key
- `USE_AWS_SES` - Set to `true` for production
- `FROM_EMAIL` - Verified sender email

### Alternative: Manual Upload

If you prefer not to use EB CLI:

1. **Log into AWS Console**
2. **Navigate to Elastic Beanstalk**
3. **Select your environment**
4. **Click "Upload and Deploy"**
5. **Upload `deploy_aws.zip`**
6. **Click "Deploy"**

### Post-Deployment Checklist

- [ ] Database connection established
- [ ] API key configured
- [ ] Environment variables set
- [ ] HTTPS certificate configured
- [ ] Email service (SES) verified
- [ ] Domain name configured (optional)
- [ ] Logs accessible in CloudWatch

## 🔍 Troubleshooting

### Local Deployment Issues

**Port Already in Use**:
```bash
lsof -ti:8000 | xargs kill -9
```

**Database Errors**:
- Check `.env` file configuration
- Ensure SQLite file permissions are correct
- Run `python init_db.py` to recreate database

**Import Errors**:
```bash
pip install -r requirements.txt --upgrade
```

### AWS Deployment Issues

**Deployment Failed**:
- Check EB logs: `eb logs`
- Verify environment variables are set correctly
- Check RDS security group allows EB instances

**Database Connection Failed**:
- Verify RDS endpoint is correct
- Check security group rules
- Ensure MySQL credentials are correct

**API Not Working**:
- Verify Congress.gov API key is valid
- Check API rate limits
- Review CloudWatch logs for API errors

**Email Not Sending**:
- Verify AWS SES credentials
- Check SES email verification status
- Review SES sending limits

## 📊 Performance Optimization

### Caching
- API responses cached for 30 minutes
- File-based cache persists across restarts
- Cache stored in `/tmp` on Elastic Beanstalk

### Pagination
- Default: 10 bills per page
- Options: 10, 20, or 50 bills per page
- Reduces initial load time

### Database Optimization
- Indexes on frequently queried fields
- Connection pooling enabled
- Query optimization for large datasets

## 🔐 Security Considerations

### Production Checklist
- [ ] Secret key changed from default
- [ ] HTTPS enabled
- [ ] Database credentials secured
- [ ] API keys stored in environment variables
- [ ] CSRF protection enabled
- [ ] Rate limiting configured
- [ ] Logging enabled for security events

### Best Practices
- Never commit `.env` file to version control
- Use strong passwords for database
- Rotate API keys regularly
- Monitor CloudWatch logs for suspicious activity
- Keep dependencies updated

## 📞 Support

For deployment issues or questions:
- Email: youthpolicypulse@gmail.com
- Check AWS Elastic Beanstalk documentation
- Review application logs in CloudWatch

---

**Last Updated**: October 25, 2025

