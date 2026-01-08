# Kibegi API - VPS Deployment Guide

Complete guide for deploying the Kibegi Django API on a VPS with Gunicorn, Nginx, and MinIO storage.

---

## 📋 Prerequisites

- Ubuntu 20.04+ VPS
- Domain name pointed to your VPS IP (e.g., api.kibegi.com)
- Root or sudo access
- MinIO server setup with credentials

---

## 🚀 Initial VPS Setup

### 1. Update System
```bash
sudo apt update
sudo apt upgrade -y
```

### 2. Install Required Packages
```bash
sudo apt install -y python3 python3-pip python3-venv nginx git postgresql-client
```

### 3. Clone Your Project
```bash
cd /root/projects
git clone https://github.com/yourusername/Kibegi.git kibegi
cd kibegi
```

---

## 🐍 Python Environment Setup

### 1. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn
```

### 3. Create `.env` File
```bash
cp .env.example .env
nano .env
```

**Configure these critical settings:**
```env
# Django
SECRET_KEY=your-super-secret-key-here
DEBUG=False
ALLOWED_HOSTS=api.kibegi.com,194.163.153.255

# Database
DB_ENGINE=django.db.backends.postgresql
DB_NAME=kibegi_db
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=your_db_host
DB_PORT=5432

# MinIO Storage
AWS_ACCESS_KEY_ID=your_minio_access_key
AWS_SECRET_ACCESS_KEY=your_minio_secret_key
AWS_STORAGE_BUCKET_NAME=kibegi-uploads
AWS_S3_ENDPOINT_URL=https://storage.kibegi.com
AWS_QUERYSTRING_AUTH=True

# Email (for OTP)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

### 4. Run Migrations & Collect Static Files
```bash
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
```

### 5. Create Logs Directory
```bash
mkdir -p logs
chmod 755 logs
```

---

## ⚙️ Systemd Service Configuration

### 1. Create Service File
```bash
sudo nano /etc/systemd/system/kibegi.service
```

### 2. Add This Configuration
```ini
[Unit]
Description=Gunicorn instance for Kibegi API
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/root/projects/kibegi

Environment="PYTHONUNBUFFERED=1"
Environment="DJANGO_SETTINGS_MODULE=kibegi_api.settings"

ExecStart=/bin/bash -c 'set -a; source /root/projects/kibegi/.env; set +a; \
    exec /root/projects/kibegi/venv/bin/gunicorn \
    --workers 3 \
    --bind 127.0.0.1:8001 \
    --timeout 300 \
    kibegi_api.wsgi:application'

Restart=always
RestartSec=10

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 3. Enable and Start Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable kibegi
sudo systemctl start kibegi
sudo systemctl status kibegi
```

### 4. Check Logs
```bash
# Real-time logs
journalctl -u kibegi -f

# Last 50 lines
journalctl -u kibegi -n 50
```

---

## 🌐 Nginx Configuration

### 1. Create Nginx Config
```bash
sudo nano /etc/nginx/sites-available/kibegi
```

### 2. Add This Configuration
```nginx
server {
    listen 80;
    server_name api.kibegi.com;

    client_max_body_size 50M;

    location = /favicon.ico { 
        access_log off; 
        log_not_found off; 
    }

    location /static/ {
        alias /root/projects/kibegi/staticfiles/;
    }

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }
}
```

### 3. Enable Site
```bash
sudo ln -s /etc/nginx/sites-available/kibegi /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 4. Test Your API
```bash
curl http://api.kibegi.com
```

---

## 🔒 SSL Setup (Recommended)

### 1. Install Certbot
```bash
sudo apt install certbot python3-certbot-nginx -y
```

### 2. Get SSL Certificate
```bash
sudo certbot --nginx -d api.kibegi.com
```

### 3. Auto-renewal is Configured
Certbot automatically adds a cron job for renewal.

---

## 🔄 Deploying Updates

### Method 1: Simple Update (Quick)
```bash
cd /root/projects/kibegi
source venv/bin/activate

# Pull latest code
git pull origin main

# Install new dependencies (if any)
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Restart service
sudo systemctl restart kibegi

# Check status
sudo systemctl status kibegi
journalctl -u kibegi -n 20
```

### Method 2: Zero-Downtime Update (Production)
```bash
cd /root/projects/kibegi
source venv/bin/activate

# Pull code
git pull origin main
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput

# Graceful reload (workers finish current requests)
sudo systemctl reload kibegi

# If reload doesn't work, use restart
sudo systemctl restart kibegi
```

### Method 3: Update with Backup
```bash
cd /root/projects/kibegi

# Backup database first
pg_dump -h your_db_host -U your_db_user kibegi_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Pull and update
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput

# Restart
sudo systemctl restart kibegi
sudo systemctl status kibegi
```

---

## 🔧 Common Maintenance Tasks

### View Logs
```bash
# Real-time
journalctl -u kibegi -f

# Last 100 lines
journalctl -u kibegi -n 100

# Errors only
journalctl -u kibegi -p err -n 50

# Nginx access log
sudo tail -f /var/log/nginx/access.log

# Nginx error log
sudo tail -f /var/log/nginx/error.log
```

### Restart Services
```bash
# Restart Django app
sudo systemctl restart kibegi

# Restart Nginx
sudo systemctl restart nginx

# Restart both
sudo systemctl restart kibegi nginx
```

### Check Service Status
```bash
sudo systemctl status kibegi
sudo systemctl status nginx
```

### Test Nginx Config
```bash
sudo nginx -t
```

### Check Django Configuration
```bash
cd /root/projects/kibegi
source venv/bin/activate
python manage.py check
python manage.py check --deploy
```

---

## 🐛 Troubleshooting

### Service Won't Start
```bash
# Check logs
journalctl -u kibegi -n 50

# Common issues:
# 1. .env file syntax errors
# 2. Python path incorrect
# 3. Port already in use

# Check if port 8001 is in use
sudo netstat -tlnp | grep 8001

# Kill process if needed
sudo kill -9 <PID>
```

### 502 Bad Gateway
```bash
# Check if Gunicorn is running
sudo systemctl status kibegi
ps aux | grep gunicorn

# Check Nginx logs
sudo tail -f /var/log/nginx/error.log

# Restart both services
sudo systemctl restart kibegi nginx
```

### Static Files Not Loading
```bash
# Recollect static files
cd /root/projects/kibegi
source venv/bin/activate
python manage.py collectstatic --noinput

# Check permissions
sudo chmod -R 755 /root/projects/kibegi/staticfiles

# Restart Nginx
sudo systemctl restart nginx
```

### Database Connection Issues
```bash
# Test database connection
cd /root/projects/kibegi
source venv/bin/activate
python manage.py dbshell

# Check .env file has correct credentials
cat .env | grep DB_
```

### MinIO Upload Failures
```bash
# Test MinIO connection
cd /root/projects/kibegi
source venv/bin/activate

# Run Python test
python -c "
import boto3
from decouple import config

s3 = boto3.client(
    's3',
    endpoint_url=config('AWS_S3_ENDPOINT_URL'),
    aws_access_key_id=config('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=config('AWS_SECRET_ACCESS_KEY')
)
print('MinIO Connection: OK')
print('Buckets:', s3.list_buckets())
"
```

### Check Django Errors
```bash
cd /root/projects/kibegi
source venv/bin/activate

# Check for errors
python manage.py check

# Test specific function
python manage.py shell
>>> from uploads.services import FileHandler
>>> # Test your code here
```

---

## 📊 Monitoring

### Check System Resources
```bash
# CPU and Memory
htop

# Disk space
df -h

# Check service resource usage
systemctl status kibegi
```

### Check API Health
```bash
# Test endpoint
curl http://api.kibegi.com/api/v1/

# Test with auth token
curl -H "Authorization: Bearer YOUR_TOKEN" http://api.kibegi.com/api/v1/classes/
```

---

## 🔐 Security Checklist

- [ ] `DEBUG=False` in production
- [ ] Strong `SECRET_KEY` set
- [ ] Database password is secure
- [ ] SSL certificate installed
- [ ] Firewall configured (UFW)
- [ ] Only necessary ports open (80, 443, 22)
- [ ] Regular backups scheduled
- [ ] MinIO credentials secured
- [ ] Email credentials secured
- [ ] `.env` file not in git (check .gitignore)

---

## 📝 Quick Reference Commands

```bash
# Update app
cd /root/projects/kibegi && git pull && source venv/bin/activate && pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput && sudo systemctl restart kibegi

# View logs
journalctl -u kibegi -f

# Restart all
sudo systemctl restart kibegi nginx

# Check status
sudo systemctl status kibegi nginx

# Test config
sudo nginx -t && python manage.py check
```

---

## 📞 Support

For issues or questions, check the logs first:
```bash
journalctl -u kibegi -n 100
sudo tail -f /var/log/nginx/error.log
```

---

**Last Updated:** January 8, 2026
