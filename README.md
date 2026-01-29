# DevMate

<div align="center">

![DevMate Logo](static/assets/devmate-favicon.png)

**Developers Don't Wait — They Connect.**

[![Django](https://img.shields.io/badge/Django-6.0-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)

[🌐 Live Site](https://devmate.space) • [📧 Contact](mailto:devmate.teams@gmail.com)

</div>

---

## 📖 About DevMate

**DevMate** is a developer journaling and collaboration platform designed for students, indie hackers, and professionals to document their building process, share logs, track progress, and collaborate on real-world projects. Build transparently, grow consistently.

Initially launched exclusively for CIT Chennai students, DevMate creates a space where developers can:
- 📝 **Journal their coding journey** with daily logs
- 🤝 **Connect with fellow developers** in their community
- 🚀 **Share project updates** with snapshots and code snippets
- 💬 **Engage through comments and reactions** on development logs
- 🔔 **Stay updated** with real-time push notifications
- 🌍 **Discover local developers** with location-based feeds

---

## ✨ Key Features

### 🔐 Authentication & Social Integration
- Email/password authentication with Django Allauth
- Google OAuth integration
- GitHub OAuth integration
- Password reset & email verification
- Session management & security features

### 📝 Developer Logs (MindLogs)
- Create short-form development logs (up to 280 characters)
- Add code snippets (up to 10,000 characters)
- Attach project screenshots
- Include project links
- Emoji reactions (❤️ 🚀 👍 👀 🔥 🎉)
- Nested comments with reply functionality
- Real-time interaction tracking

### 👥 User Profiles & Networking
- Customizable profile with bio, about, and profile/banner images
- Social links (GitHub, LinkedIn, Twitter, Stack Overflow)
- Skills & coding style badges
- Years of experience tracking
- Education & experience sections
- Follow/unfollow functionality
- User discovery with "Explore Developers" feed

### 🔔 Smart Notifications
- In-app notification system
- Real-time notifications
- Notification types:
  - New likes on logs
  - Comments on logs
  - Replies to comments
  - New followers
  - Mentions in logs
- User-controlled notification preferences

### 🌍 Location-Based Features
- Browser-based geolocation (24-hour freshness)
- Local developer discovery
- Location-aware feeds
- Privacy-focused (browser permission required)

### 🎨 Modern UI/UX
- Dark mode optimized interface
- Responsive design (mobile, tablet, desktop)
- TailwindCSS styling
- Smooth animations & transitions
- Toast notifications
- Reward/achievement celebration animations

### 🔒 Security & Privacy
- Environment-based configuration (no hardcoded secrets)
- HTTPS enforcement in production
- CSRF protection
- SQL injection prevention
- Admin honeypot for security
- Rate limiting ready
- Secure password validation

### 📦 Additional Features
- Django REST Framework API support
- JWT authentication ready
- Phone number field support
- Select2 integration for enhanced dropdowns
- Cloudflare R2 storage support
- WhiteNoise for static file serving
- Brevo email backend for production

---

## 🏗️ Tech Stack

### Backend
- **Framework:** Django 6.0
- **Database:** PostgreSQL (Production), SQLite (Development)
- **ORM:** Django ORM
- **Authentication:** Django Allauth + OAuth (Google, GitHub)
- **Email:** Brevo API (Production), Console (Development)
- **Storage:** Cloudflare R2 (optional) / Local filesystem

### Frontend
- **CSS Framework:** TailwindCSS
- **JavaScript:** Vanilla JS + jQuery
- **Icons:** Font Awesome
- **UI Components:** Custom components with TailwindCSS
- **Forms:** Django Widget Tweaks

### Infrastructure
- **Web Server:** Gunicorn (Production)
- **Static Files:** WhiteNoise
- **Deployment:** Render

### Development Tools
- **Python:** 3.13+
- **Package Manager:** pip
- **Virtual Environment:** venv
- **Version Control:** Git

---

## 🚀 Getting Started

### Prerequisites
- Python 3.13 or higher
- PostgreSQL (for production) or SQLite (for development)
- pip package manager
- Virtual environment tool

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/devmate.git
   cd devmate/DevMate
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv myvenv
   source myvenv/bin/activate  # On Windows: myvenv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   
   Create a `.env` file in the DevMate directory:
   ```env
   # Django Settings
   SECRET_KEY=your-secret-key-here
   IS_DEVELOPMENT=True
   DEBUG=True
   ALLOWED_HOST=localhost,127.0.0.1
   CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
   SITE_ID=1
   
   # Database (Development - SQLite is default)
   # For PostgreSQL:
   DB_NAME=devmate_db
   DB_USER=your_db_user
   DB_PASSWORD=your_db_password
- **Email:** [devmate.teams@gmail.com](mailto:devmate.teams@gmail.com)
- **Website:** [devmate.space](https://devmate.space)
- **Feedback:** [Submit Feedback](https://devmate.space/feedback/)

   DB_HOST=localhost
   DB_PORT=5432
   
   # Production Database
   # DB_DATABASE_URL=postgres://user:password@host:port/database
   
   # OAuth Keys
   # Google OAuth (get from Google Cloud Console)
   # GOOGLE_CLIENT_ID=your-google-client-id
   # GOOGLE_CLIENT_SECRET=your-google-client-secret
   
   # GitHub OAuth (get from GitHub Developer Settings)
   # GITHUB_CLIENT_ID=your-github-client-id
   # GITHUB_CLIENT_SECRET=your-github-client-secret
   
   # Email (Production)
   # BREVO_API_KEY=your-brevo-api-key
   
   # Cloudflare R2 Storage (Optional)
   USE_CLOUDFLARE=False
   # CLOUDFLARE_R2_BUCKET=devmate
   # CLOUDFLARE_R2_ACCESS_KEY=your-access-key
   # CLOUDFLARE_R2_BUCKET_ENDPOINT=your-endpoint-url
   # CLOUDFLARE_R2_SECRET_KEY=your-secret-key
   # CLOUDFLARE_R2_PUBLIC_URL=your-public-url
   
   # Security (Production)
   REQUIRE_HTTPS=False
   ```

5. **Run migrations**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Create superuser**
   ```bash
   python manage.py createsuperuser
   ```

7. **Collect static files**
   ```bash
   python manage.py collectstatic --noinput
   ```

8. **Run the development server**
   ```bash
   python manage.py runserver
   ```

9. **Access the application**
   - Main site: http://localhost:8000
   - Admin panel: http://localhost:8000/admin-project-x/

---

## 📁 Project Structure

```
DevMate/
├── DevMate/                 # Main project directory
│   ├── settings.py         # Django settings
│   ├── urls.py             # URL routing
│   ├── wsgi.py             # WSGI config
│   ├── asgi.py             # ASGI config
│   └── context_processors.py  # Custom context processors
│
├── myapp/                   # Main application
│   ├── models/             # Data models
│   │   ├── users.py        # User-related models
│   │   └── filter.py       # Skills, status, coding style
│   ├── views.py            # View functions
│   ├── urls.py             # App URL patterns
│   ├── forms.py            # Django forms
│   ├── middleware.py       # Custom middleware
│   ├── validators.py       # Custom validators
│   ├── utils/              # Utility functions
│   ├── templates/          # HTML templates
│   └── templatetags/       # Custom template tags
│
├── logs/                    # Logging/MindLog app
│   ├── models.py           # Log, Comment, Reaction, Notification models
│   ├── views.py            # Log-related views
│   ├── signals.py          # Notification signals
│   ├── forms.py            # Log forms
│   └── urls.py             # Log URL patterns
│
├── static/                  # Static files
│   ├── assets/             # Images, icons
│   ├── scripts/            # JavaScript files
│   ├── styles/             # CSS files
│   └── sounds/             # Audio files
│
├── templates/              # Global templates
│   ├── account/            # Allauth templates (login, signup, etc.)
│   └── socialaccount/      # Social auth templates
│
├── uploads/                # User-uploaded media
│   ├── user_profile_img/   # Profile images
│   ├── log_snap_shot/      # Log screenshots
│   └── user-posts/         # User post attachments
│
├── helpers/                # Helper modules
│   └── cloudflare/         # Cloudflare R2 storage
│
├── manage.py               # Django management script
├── requirements.txt        # Python dependencies
├── db.sqlite3             # SQLite database (development)
└── README.md              # This file
```

---

## 🔧 Configuration

### OAuth Setup

#### Google OAuth
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google+ API
4. Create OAuth 2.0 credentials
5. Add authorized redirect URI: `http://localhost:8000/accounts/google/login/callback/`
6. Add credentials to `.env` file

#### GitHub OAuth
1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Create new OAuth App
3. Set Authorization callback URL: `http://localhost:8000/accounts/github/login/callback/`
4. Add credentials to `.env` file

---

## 📊 Database Models

### Core Models

#### `userinfo` (User Profile)
- Extended user profile with bio, location, skills
- Social media links
- Geolocation support (browser-based)
- Profile/banner images
- Education & experience tracking

#### `Log` (MindLog)
- User development logs
- Content (280 chars), code snippets (10,000 chars)
- Screenshots and links
- Unique signature ID
- Reactions and comments

#### `Comment`
- Comments on logs
- Nested reply support
- Like functionality
- Timestamps

#### `Reaction`
- Emoji reactions on logs
- Multiple reaction types
- User-reaction tracking

#### `Notification`
- Real-time notifications
- Multiple notification types
- Read/unread status
- Generic foreign key for flexibility

#### `follow`
- User following system
- Follower/following relationships

---

## 🎯 API Endpoints

### Authentication
- `/accounts/login/` - User login
- `/accounts/signup/` - User registration
- `/accounts/logout/` - User logout
- `/accounts/password/reset/` - Password reset
- `/accounts/google/login/` - Google OAuth
- `/accounts/github/login/` - GitHub OAuth

### User & Profile
- `/profile/<username>/` - User profile view
- `/settings/profile/` - Profile settings
- `/settings/account/` - Account settings
- `/explore-developers/` - Discover developers

### Logs
- `/logs/` - View all logs
- `/logs/create/` - Create new log
- `/logs/<sig>/` - View specific log
- `/logs/<sig>/edit/` - Edit log
- `/logs/<sig>/delete/` - Delete log

---

## 🧪 Testing

### Run Django Tests
```bash
python manage.py test
```

---

## 🚀 Deployment

### Production Checklist

1. **Environment Variables**
   - Set `IS_DEVELOPMENT=False`
   - Set `DEBUG=False`
   - Configure production database URL
   - Add production domain to `ALLOWED_HOST`
   - Set `REQUIRE_HTTPS=True`

2. **Database**
   - Set up PostgreSQL database
   - Run migrations
   - Create superuser

3. **Static Files**
   - Run `python manage.py collectstatic`
   - Configure Cloudflare R2 (optional)

4. **Email**
   - Configure Brevo API key
   - Set `DEFAULT_FROM_EMAIL`

5. **Security**
   - Generate new `SECRET_KEY`
   - Enable HTTPS
   - Set secure cookie flags
   - Configure CSRF trusted origins

6. **Web Server**
   - Use Gunicorn: `gunicorn DevMate.wsgi:application`
   - Configure reverse proxy (Nginx/Apache)

### Deployment Platforms

#### Railway
```bash
# Install Railway CLI
npm i -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```

#### Render
1. Connect GitHub repository
2. Select "Web Service"
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `gunicorn DevMate.wsgi:application`
5. Add environment variables

#### Heroku
```bash
# Install Heroku CLI and login
heroku login

# Create app
heroku create your-app-name

# Add PostgreSQL
heroku addons:create heroku-postgresql:mini

# Deploy
git push heroku main

# Run migrations
heroku run python manage.py migrate
```

---

## 🤝 Contributing

We welcome contributions! Here's how you can help:

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. **Make your changes**
4. **Commit your changes**
   ```bash
   git commit -m 'Add amazing feature'
   ```
5. **Push to the branch**
   ```bash
   git push origin feature/amazing-feature
   ```
6. **Open a Pull Request**

### Development Guidelines
- Follow PEP 8 style guide
- Write meaningful commit messages
- Add tests for new features
- Update documentation
- **Email:** [devmate.teams@gmail.com](mailto:devmate.teams@gmail.com)
- **Website:** [devmate.space](https://devmate.space)
- **Feedback:** [Submit Feedback](https://devmate.space/feedback/)

- Keep code DRY (Don't Repeat Yourself)

---

## 📝 License

This project is currently unlicensed. All rights reserved by the DevMate team.

---

## 👥 Team & Contact

**DevMate** is built and maintained with ❤️ by student developers.

- **Email:** [devmate.teams@gmail.com](mailto:devmate.teams@gmail.com)
- **Website:** [devmate.space](https://devmate.space)
- **Feedback:** [Submit Feedback](https://devmate.space/feedback/)

---

## 🙏 Acknowledgments

- Django framework and community
- TailwindCSS for the beautiful UI
- All contributors and users who make DevMate better

---

## 🐛 Bug Reports & Feature Requests

Found a bug or have a feature request? Please:

1. Check existing issues first
2. Create a new issue with detailed description
3. Use our [feedback form](https://devmate.space/feedback/)
4. Email us at devmate.teams@gmail.com

---

---

<div align="center">

**Made with 💚 by developers, for developers**

⭐ Star this repo if you find it helpful!

</div>
