#!/bin/bash
# PostgreSQL Setup Script for Kibegi
# This script helps set up PostgreSQL database for the Kibegi project

set -e  # Exit on error

echo "=========================================="
echo "Kibegi PostgreSQL Database Setup"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo -e "${RED}PostgreSQL is not installed.${NC}"
    echo "Please install PostgreSQL first:"
    echo "  Ubuntu/Debian: sudo apt install postgresql postgresql-contrib"
    echo "  macOS: brew install postgresql"
    echo "  Windows: Download from https://www.postgresql.org/download/windows/"
    exit 1
fi

echo -e "${GREEN}✓ PostgreSQL is installed${NC}"

# Check if PostgreSQL is running
if ! pg_isready -q; then
    echo -e "${YELLOW}⚠ PostgreSQL service is not running.${NC}"
    echo "Starting PostgreSQL..."
    sudo systemctl start postgresql 2>/dev/null || brew services start postgresql 2>/dev/null || echo "Please start PostgreSQL manually"
fi

echo -e "${GREEN}✓ PostgreSQL is running${NC}"
echo ""

# Get database configuration
read -p "Database name [kibegi_db]: " DB_NAME
DB_NAME=${DB_NAME:-kibegi_db}

read -p "Database user [kibegi_user]: " DB_USER
DB_USER=${DB_USER:-kibegi_user}

read -sp "Database password: " DB_PASSWORD
echo ""

read -p "Database host [localhost]: " DB_HOST
DB_HOST=${DB_HOST:-localhost}

read -p "Database port [5432]: " DB_PORT
DB_PORT=${DB_PORT:-5432}

echo ""
echo "Creating database and user..."

# Create database and user
sudo -u postgres psql <<EOF
-- Create database
CREATE DATABASE $DB_NAME;

-- Create user
CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;

-- Connect to database and grant schema privileges
\c $DB_NAME
GRANT ALL ON SCHEMA public TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DB_USER;
\q
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Database and user created successfully${NC}"
else
    echo -e "${RED}✗ Failed to create database/user${NC}"
    exit 1
fi

# Test connection
echo ""
echo "Testing database connection..."
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "SELECT version();" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Database connection successful${NC}"
else
    echo -e "${RED}✗ Database connection failed${NC}"
    exit 1
fi

# Update .env file
echo ""
echo "Updating .env file..."

ENV_FILE=".env"

# Check if .env exists
if [ ! -f "$ENV_FILE" ]; then
    echo "Creating .env file..."
    touch "$ENV_FILE"
fi

# Add or update database configuration
if grep -q "DB_ENGINE" "$ENV_FILE"; then
    # Update existing configuration
    sed -i.bak "s/^DB_ENGINE=.*/DB_ENGINE=django.db.backends.postgresql/" "$ENV_FILE"
    sed -i.bak "s/^DB_NAME=.*/DB_NAME=$DB_NAME/" "$ENV_FILE"
    sed -i.bak "s/^DB_USER=.*/DB_USER=$DB_USER/" "$ENV_FILE"
    sed -i.bak "s/^DB_PASSWORD=.*/DB_PASSWORD=$DB_PASSWORD/" "$ENV_FILE"
    sed -i.bak "s/^DB_HOST=.*/DB_HOST=$DB_HOST/" "$ENV_FILE"
    sed -i.bak "s/^DB_PORT=.*/DB_PORT=$DB_PORT/" "$ENV_FILE"
    rm -f "$ENV_FILE.bak"
else
    # Add new configuration
    cat >> "$ENV_FILE" <<EOF

# Database Configuration
DB_ENGINE=django.db.backends.postgresql
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
DB_HOST=$DB_HOST
DB_PORT=$DB_PORT
EOF
fi

echo -e "${GREEN}✓ .env file updated${NC}"

echo ""
echo "=========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Run migrations: python manage.py migrate"
echo "2. Create superuser: python manage.py createsuperuser"
echo "3. Test the application: python manage.py runserver"
echo ""
echo "Database credentials saved to .env file"
echo ""

