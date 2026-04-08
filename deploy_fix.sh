#!/bin/bash
# Quick deployment script for download fix
# Run this on your VPS server

echo "🚀 Deploying download fix to production..."

# Navigate to project directory
cd /root/projects/kibegi

# Pull latest changes
echo "📥 Pulling latest code..."
git pull origin master

# Activate virtual environment
echo "🐍 Activating virtual environment..."
source venv/bin/activate

# Install/update dependencies (if any changed)
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Run migrations (if any)
echo "🗄️  Running migrations..."
python manage.py migrate

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

# Update Nginx config for streaming
echo "⚙️  Updating Nginx configuration..."
sudo tee /etc/nginx/sites-available/kibegi > /dev/null << 'EOF'
server {
    listen 80;
    server_name api.kibegi.com;

    client_max_body_size 50M;
    
    # Disable buffering for streaming responses (important for file downloads)
    proxy_buffering off;

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
EOF

# Test Nginx configuration
echo "🧪 Testing Nginx configuration..."
sudo nginx -t

if [ $? -eq 0 ]; then
    echo "✅ Nginx config is valid"
    
    # Restart services
    echo "🔄 Restarting services..."
    sudo systemctl restart kibegi
    sudo systemctl reload nginx
    
    # Wait a moment for services to start
    sleep 3
    
    # Check service status
    echo ""
    echo "📊 Service Status:"
    echo "=================="
    sudo systemctl status kibegi --no-pager -n 5
    
    echo ""
    echo "✅ Deployment complete!"
    echo ""
    echo "📝 Recent logs:"
    echo "==============="
    journalctl -u kibegi -n 20 --no-pager
    
    echo ""
    echo "🎉 Done! File downloads should now work properly."
    echo "Test with: curl -I https://api.kibegi.com/api/v1/uploads/<file_code>/download/"
else
    echo "❌ Nginx config test failed! Not restarting services."
    exit 1
fi
