# Database Migration Guide: SQLite to PostgreSQL

This guide will help you migrate the Kibegi project from SQLite to PostgreSQL for production deployment.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Database Setup](#database-setup)
- [Configuration](#configuration)
- [Migration Steps](#migration-steps)
- [Data Migration (Optional)](#data-migration-optional)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before starting, ensure you have:

- ✅ PostgreSQL installed (version 12 or higher)
- ✅ Python 3.12+ with virtual environment
- ✅ Access to create databases and users in PostgreSQL
- ✅ Backup of existing SQLite database (if migrating data)

### Check PostgreSQL Installation

```bash
# Check if PostgreSQL is installed
psql --version

# Check if PostgreSQL service is running
sudo systemctl status postgresql  # Linux
brew services list | grep postgresql  # macOS
```

---

## Installation

### 1. Install PostgreSQL (if not installed)

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**macOS:**
```bash
brew install postgresql
brew services start postgresql
```

**Windows:**
Download and install from [PostgreSQL Official Website](https://www.postgresql.org/download/windows/)

### 2. Install Python Dependencies

```bash
# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Install PostgreSQL adapter
pip install psycopg2-binary

# Or install all requirements
pip install -r requirements.txt
```

---

## Database Setup

### 1. Create PostgreSQL Database and User

```bash
# Switch to postgres user
sudo -u postgres psql  # Linux
# or just
psql postgres  # macOS/Windows (if you have access)

# In PostgreSQL prompt, run:
```

```sql
-- Create database
CREATE DATABASE kibegi_db;

-- Create user
CREATE USER kibegi_user WITH PASSWORD 'your_secure_password_here';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE kibegi_db TO kibegi_user;

-- Grant schema privileges (PostgreSQL 15+)
\c kibegi_db
GRANT ALL ON SCHEMA public TO kibegi_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO kibegi_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO kibegi_user;

-- Exit
\q
```

### 2. Verify Database Creation

```bash
# Test connection
psql -U kibegi_user -d kibegi_db -h localhost

# If successful, you'll see:
# kibegi_db=>
# Type \q to exit
```

---

## Configuration

### 1. Update Environment Variables

Create or update your `.env` file in the project root:

```env
# Database Configuration
DB_ENGINE=django.db.backends.postgresql
DB_NAME=kibegi_db
DB_USER=kibegi_user
DB_PASSWORD=your_secure_password_here
DB_HOST=localhost
DB_PORT=5432

# Other existing environment variables...
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=Kibegi <your-email@gmail.com>
```

**⚠️ Security Note:** Never commit `.env` file to version control!

### 2. Verify Settings

The `settings.py` file is already configured to read from environment variables:

```python
DB_ENGINE = config('DB_ENGINE', default='django.db.backends.postgresql')
DB_NAME = config('DB_NAME', default='kibegi_db')
DB_USER = config('DB_USER', default='kibegi_user')
DB_PASSWORD = config('DB_PASSWORD', default='')
DB_HOST = config('DB_HOST', default='localhost')
DB_PORT = config('DB_PORT', default='5432', cast=int)
```

---

## Migration Steps

### Step 1: Backup Existing Data (If Needed)

If you have important data in SQLite:

```bash
# Create backup
cp db.sqlite3 db.sqlite3.backup

# Export data (optional, for reference)
python manage.py dumpdata > data_backup.json
```

### Step 2: Test Database Connection

```bash
# Activate virtual environment
source venv/bin/activate

# Test connection
python manage.py dbshell
# Should connect to PostgreSQL
# Type \q to exit
```

### Step 3: Run Migrations

```bash
# Create all migration files (if not already created)
python manage.py makemigrations

# Apply migrations to PostgreSQL
python manage.py migrate

# Create superuser (if needed)
python manage.py createsuperuser
```

### Step 4: Verify Migration

```bash
# Check database tables
python manage.py dbshell
# In PostgreSQL prompt:
\dt  # List all tables
\q   # Exit

# Or use Django shell
python manage.py shell
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()
>>> User.objects.count()  # Should show 0 or your user count
```

---

## Data Migration (Optional)

If you need to migrate existing data from SQLite to PostgreSQL:

### Option 1: Using Django's dumpdata/loaddata

```bash
# 1. Switch back to SQLite temporarily
# Edit .env: DB_ENGINE=django.db.backends.sqlite3
# Or comment out PostgreSQL config in settings.py

# 2. Export data from SQLite
python manage.py dumpdata --exclude auth.permission --exclude contenttypes > data_export.json

# 3. Switch to PostgreSQL
# Edit .env: DB_ENGINE=django.db.backends.postgresql

# 4. Load data into PostgreSQL
python manage.py loaddata data_export.json
```

### Option 2: Using pgloader (Advanced)

```bash
# Install pgloader
sudo apt install pgloader  # Ubuntu/Debian
brew install pgloader      # macOS

# Migrate data
pgloader db.sqlite3 postgresql://kibegi_user:password@localhost/kibegi_db
```

**Note:** pgloader requires careful mapping of SQLite types to PostgreSQL types.

---

## Verification

### 1. Test Application

```bash
# Run development server
python manage.py runserver

# Test endpoints
curl http://localhost:8000/api/v1/auth/login/
```

### 2. Check Database

```bash
# Connect to database
psql -U kibegi_user -d kibegi_db

# Check tables
\dt

# Check user count
SELECT COUNT(*) FROM authentication_user;

# Check classes
SELECT COUNT(*) FROM classes_class;

# Exit
\q
```

### 3. Run Tests

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test authentication
python manage.py test classes
python manage.py test sharing
```

---

## Production Configuration

For production, update your `.env` file with production database credentials:

```env
# Production Database
DB_ENGINE=django.db.backends.postgresql
DB_NAME=kibegi_production
DB_USER=kibegi_prod_user
DB_PASSWORD=very_secure_production_password
DB_HOST=your-db-host.com
DB_PORT=5432
```

### Additional Production Settings

In `settings.py`, you can add connection pooling:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': DB_NAME,
        'USER': DB_USER,
        'PASSWORD': DB_PASSWORD,
        'HOST': DB_HOST,
        'PORT': DB_PORT,
        'OPTIONS': {
            'connect_timeout': 10,
        },
        'CONN_MAX_AGE': 600,  # Reuse connections for 10 minutes
        # For production with connection pooling:
        # 'CONN_MAX_AGE': 0,  # Use connection pooler instead
    }
}
```

---

## Troubleshooting

### Error: "FATAL: password authentication failed"

**Solution:**
```bash
# Check PostgreSQL authentication
sudo nano /etc/postgresql/*/main/pg_hba.conf

# Ensure this line exists:
# local   all             all                                     md5
# host    all             all             127.0.0.1/32            md5

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### Error: "database does not exist"

**Solution:**
```bash
# Create database
sudo -u postgres psql
CREATE DATABASE kibegi_db;
\q
```

### Error: "permission denied for schema public"

**Solution:**
```sql
-- Connect as postgres superuser
psql -U postgres -d kibegi_db

-- Grant privileges
GRANT ALL ON SCHEMA public TO kibegi_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO kibegi_user;
\q
```

### Error: "psycopg2 not installed"

**Solution:**
```bash
# Install psycopg2
pip install psycopg2-binary

# Or if binary doesn't work:
sudo apt install libpq-dev python3-dev  # Linux
pip install psycopg2
```

### Error: "connection refused"

**Solution:**
```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Start PostgreSQL
sudo systemctl start postgresql

# Check if port 5432 is listening
netstat -tuln | grep 5432
```

### Migration Errors

**Solution:**
```bash
# Reset migrations (CAUTION: Only for development!)
# This will delete all data!

# 1. Drop all tables
python manage.py dbshell
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO kibegi_user;
\q

# 2. Re-run migrations
python manage.py migrate
```

---

## Rollback to SQLite (Development Only)

If you need to switch back to SQLite for development:

```env
# In .env file, comment out PostgreSQL config:
# DB_ENGINE=django.db.backends.postgresql
# DB_NAME=kibegi_db
# DB_USER=kibegi_user
# DB_PASSWORD=password
# DB_HOST=localhost
# DB_PORT=5432

# Or set:
DB_ENGINE=django.db.backends.sqlite3
```

Then run migrations:
```bash
python manage.py migrate
```

---

## Performance Tips

### 1. Index Optimization

PostgreSQL automatically creates indexes, but you can verify:

```sql
-- Check indexes
\di

-- Analyze tables for query optimization
ANALYZE;
```

### 2. Connection Pooling

For high-traffic production, consider using:
- **PgBouncer**: Lightweight connection pooler
- **Django connection pooling**: Already configured with `CONN_MAX_AGE`

### 3. Database Maintenance

```sql
-- Vacuum database (reclaim space)
VACUUM ANALYZE;

-- Check database size
SELECT pg_size_pretty(pg_database_size('kibegi_db'));
```

---

## Checklist

Before going to production, verify:

- [ ] PostgreSQL installed and running
- [ ] Database and user created
- [ ] Environment variables configured in `.env`
- [ ] All migrations applied successfully
- [ ] Superuser created
- [ ] Application connects to database
- [ ] All tests pass
- [ ] Database backup strategy in place
- [ ] Production credentials are secure
- [ ] `.env` file is in `.gitignore`

---

## Next Steps

After successful migration:

1. **Update Production Environment Variables**
   - Set production database credentials
   - Configure connection pooling if needed

2. **Set Up Database Backups**
   ```bash
   # Add to crontab for daily backups
   0 2 * * * pg_dump -U kibegi_user kibegi_db > /backups/kibegi_$(date +\%Y\%m\%d).sql
   ```

3. **Monitor Database Performance**
   - Use PostgreSQL's built-in monitoring tools
   - Set up logging for slow queries

4. **Update Documentation**
   - Update deployment docs
   - Document database backup/restore procedures

---

**Last Updated**: November 2025  
**Version**: 1.0  
**Maintainer**: Kibegi Development Team

