# youthpolicypulse

# Youth Policy Pulse

**Study statutes. Spark solutions.**

Youth Policy Pulse is a civic engagement platform designed to help young people track congressional legislation, engage with bills, and participate in democratic processes. Built with Flask and deployed on AWS Elastic Beanstalk.

## 🎯 Mission

Youth Policy Pulse is where young people turn curiosity into change. We spotlight the laws that shape your daily life. Every bill comes with verified sources and simple ways to engage: follow a bill's progress, share your perspective, and find concrete steps to get involved in your community.

## ✨ Features

### Bill Tracking & Discovery
- **Real-time Congressional Data**: Integration with Congress.gov API for up-to-date bill information
- **Advanced Search & Filtering**: Search by keywords, filter by topic or chamber (House/Senate)
- **Pagination**: View 10, 20, or 50 bills per page for optimal performance
- **Bill Details**: Comprehensive information including sponsor, status, introduced date, and full text

### User Engagement
- **Watchlist**: Save bills to track their progress
- **Comments**: Share thoughts and opinions on bills (with moderation)
- **Voting**: Support or oppose bills to express your opinion
- **Topic Alerts**: Get notified about new bills in areas you care about

### User Management
- **Secure Authentication**: Registration, login, and password reset functionality
- **User Dashboard**: Track your watchlist, comments, votes, and topic alerts
- **Profile Management**: Store personal information and preferences

### Educational Resources
- **Civics 101**: Educational content about how government works
- **Action Center**: Tools and resources for civic engagement
- **Event Registration**: Sign up for upcoming events and opportunities

### Contact & Communication
- **Contact Form**: Reach out with email verification for non-logged-in users
- **Email Notifications**: AWS SES integration for production email delivery

## 🛠️ Technology Stack

### Backend
- **Flask 2.3.3**: Web framework
- **Flask-SQLAlchemy 3.0.5**: Database ORM
- **Flask-Login 0.6.3**: User authentication
- **Flask-WTF 1.2.1**: Form handling and CSRF protection
- **Werkzeug 2.3.7**: Security utilities (password hashing)

### Database
- **SQLite**: Default database for local development
- **MySQL**: Production database (RDS on AWS)
- **PyMySQL 1.1.0**: MySQL connector

### APIs & Services
- **Congress.gov API**: Real-time congressional bill data
- **AWS SES**: Email delivery service (production)
- **SMTP**: Email fallback (development)

### Frontend
- **Bootstrap 5.3.0**: Responsive UI framework
- **Font Awesome 6.0.0**: Icon library
- **JavaScript**: Interactive features and AJAX calls
- **Jinja2**: Template engine

### Deployment
- **AWS Elastic Beanstalk**: Platform-as-a-Service deployment
- **Gunicorn**: Production WSGI server
- **Nginx**: Reverse proxy and static file serving

## 📋 Prerequisites

- Python 3.11 or higher
- pip (Python package installer)
- AWS account (for production deployment)
- Congress.gov API key

## 🚀 Installation & Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd PythonProject
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
# Flask Configuration
SECRET_KEY=your-secret-key-here

# Database Configuration (MySQL for production)
MYSQL_HOST=your-mysql-host
MYSQL_PORT=3306
MYSQL_USER=your-mysql-user
MYSQL_PASSWORD=your-mysql-password
MYSQL_DATABASE=your-database-name

# Congress.gov API
CONGRESS_API_KEY=your-congress-api-key

# Email Configuration (AWS SES)
AWS_SES_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
USE_AWS_SES=true
FROM_EMAIL=youthpolicypulse@gmail.com

# SMTP Fallback (Development)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### 5. Initialize Database

```bash
python init_db.py
```

### 6. Run the Application

```bash
python app.py
```

The application will be available at: `http://127.0.0.1:8000`

## 📁 Project Structure

```
PythonProject/
├── app.py                      # Main Flask application
├── application.py              # WSGI entry point for production
├── requirements.txt            # Python dependencies
├── init_db.py                 # Database initialization script
├── .ebextensions/             # Elastic Beanstalk configuration
│   ├── 01-packages.config     # System packages
│   ├── 02-python.config       # Python settings
│   ├── 03-environment.config  # Environment variables
│   ├── 04-logs.config         # Logging configuration
│   └── 05-https.config        # HTTPS settings
├── templates/                 # HTML templates
│   ├── base.html              # Base template
│   ├── index.html             # Homepage with bill listings
│   ├── bill_detail.html       # Individual bill details
│   ├── dashboard.html         # User dashboard
│   ├── login.html             # Login page
│   ├── register.html          # Registration page
│   ├── about.html             # About page
│   ├── contact.html           # Contact form
│   ├── civics101.html         # Educational content
│   └── action_center.html     # Action center
├── static/                    # Static files
│   ├── css/
│   │   └── style.css          # Custom styles
│   ├── js/
│   │   └── main.js            # JavaScript functionality
│   └── images/                # Images and favicon
│       ├── favicon.svg        # Browser icon
│       ├── GavinVernon.JPG    # Team member photo
│       └── Michael_Zhang_Headshot7.jpeg  # Team member photo
└── instance/                   # Database files (SQLite)
    └── congress_tracker.db    # SQLite database (if used)
```

## 🔧 Configuration

### Database Configuration

The application automatically selects the appropriate database:

1. **MySQL** (Production): If all MySQL environment variables are set
2. **SQLite** (Development): Default fallback if MySQL is unavailable

### API Configuration

- **Congress.gov API**: Requires API key from [Congress.gov](https://api.congress.gov/)
- Rate limiting handled with caching (30-minute cache duration)
- Optimized API calls: lightweight processing for homepage, detailed calls for bill pages

### Email Configuration

- **Production**: AWS SES (requires AWS credentials)
- **Development**: SMTP (Gmail or other SMTP server)
- **Fallback**: Console output for testing

## 🚢 Deployment

### AWS Elastic Beanstalk

1. **Create Deployment Package**:
   ```bash
   zip -r deploy.zip app.py requirements.txt application.py .ebextensions/ templates/ static/ .ebignore eb-config.yml
   ```

2. **Deploy to Elastic Beanstalk**:
   - Upload `deploy.zip` to your Elastic Beanstalk environment
   - Configure environment variables in EB console
   - Deploy

3. **Environment Variables Required**:
   - `SECRET_KEY`: Flask secret key
   - `CONGRESS_API_KEY`: Congress.gov API key
   - `MYSQL_HOST`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`: Database credentials
   - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`: For AWS SES
   - `USE_AWS_SES`: Set to `true` for production

## 📊 API Endpoints

### Bills API
- `GET /api/bills` - Get all bills
- `GET /api/bills/fetch` - Fetch bills from Congress.gov API
- `GET /api/bills/search` - Search bills
- `GET /bill/<bill_id>` - Get bill details

### User Interaction API
- `POST /api/bills/<bill_id>/comments` - Add comment (requires login)
- `GET /api/bills/<bill_id>/comments` - Get comments
- `POST /api/bills/<bill_id>/vote` - Vote on bill (requires login)
- `GET /api/bills/<bill_id>/votes` - Get vote counts

### Watchlist API
- `POST /api/watchlist` - Add to watchlist (requires login)
- `DELETE /api/watchlist/<bill_id>` - Remove from watchlist (requires login)

### Topic Alerts API
- `POST /api/topic-alerts` - Update topic alerts (requires login)

### Events API
- `POST /api/events/register` - Register for event (requires login)
- `GET /api/events/registrations` - Get user registrations (requires login)
- `POST /api/events/cancel` - Cancel registration (requires login)

## 🎨 Features Explained

### Bill Categorization
Bills are automatically categorized into topics:
- Education
- Student Loans
- Mental Health
- Youth Voting Rights
- Environment
- Healthcare
- Economy
- Technology
- Immigration
- Criminal Justice

### Performance Optimizations
- **Caching**: 30-minute cache for API responses
- **Pagination**: Configurable page sizes (10, 20, 50)
- **Lazy Loading**: Detailed bill info fetched only when needed
- **File-based Cache**: Persists across server restarts

### Security Features
- Password hashing with Werkzeug
- CSRF protection with Flask-WTF
- Email verification for contact forms
- IP tracking for comments
- Content moderation for comments

## 🐛 Troubleshooting

### Common Issues

1. **Port Already in Use**:
   ```bash
   lsof -ti:8000 | xargs kill -9
   ```

2. **Database Connection Issues**:
   - Check MySQL credentials in environment variables
   - Verify database server is accessible
   - Application will fallback to SQLite if MySQL fails

3. **API Rate Limiting**:
   - Check Congress.gov API key is valid
   - Review cache settings (30-minute default)
   - Monitor API call logs

4. **Email Not Sending**:
   - Verify AWS SES credentials (production)
   - Check SMTP settings (development)
   - Review email service logs

## 👥 Team

- **Gavin Vernon**: Founder, Brownell Talbot School, Omaha, Nebraska
- **Michael Zhang**: Youth Leader, Cherry Creek High School, Denver, Colorado

## 📝 License

This project is open source and available for educational purposes.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## 📧 Contact

For questions or support, please contact: **youthpolicypulse@gmail.com**

---

**Built with ❤️ for young people who want to make a difference.**

Technology that turns legislative transparency into citizen power.
