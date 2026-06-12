#!/usr/bin/env bash
# Run this script ON the media.camelcreatives.com server as root/sudo.
# It creates an nginx reverse-proxy for the MinIO S3 API and issues a
# Let's Encrypt certificate, then creates the 'kibegi' bucket.
#
# Usage:  sudo bash setup_minio_nginx.sh

set -euo pipefail

S3_DOMAIN="s3.media.camelcreatives.com"
MINIO_API_PORT=9000
BUCKET="kibegi"
ACCESS_KEY="camel"
SECRET_KEY="Camelcreatives@#2026"
REGION="us-east-1"

echo "==> 1/4  Writing nginx config for ${S3_DOMAIN}"

cat > /etc/nginx/sites-available/minio-s3 <<NGINX
server {
    listen 80;
    server_name ${S3_DOMAIN};

    # Let's Encrypt challenge
    location /.well-known/acme-challenge/ { root /var/www/html; }

    location / { return 301 https://\$host\$request_uri; }
}

server {
    listen 443 ssl;
    server_name ${S3_DOMAIN};

    ssl_certificate     /etc/letsencrypt/live/${S3_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${S3_DOMAIN}/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # Required for large file uploads (50 MB)
    client_max_body_size 55m;

    # Disable buffering for streaming uploads
    proxy_buffering    off;
    proxy_request_buffering off;

    location / {
        proxy_pass         http://127.0.0.1:${MINIO_API_PORT};
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header   Connection "";

        # Fix chunked transfer for S3 API
        chunked_transfer_encoding on;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/minio-s3 /etc/nginx/sites-enabled/minio-s3
nginx -t
echo "==> 2/4  nginx config OK — obtaining TLS certificate"

systemctl reload nginx

# Issue cert (requires port 80 to be open for the ACME challenge)
certbot --nginx -d "${S3_DOMAIN}" --non-interactive --agree-tos \
    -m admin@camelcreatives.com --redirect 2>&1 | tail -10

systemctl reload nginx
echo "==> 3/4  TLS cert issued — creating MinIO bucket '${BUCKET}'"

# Install boto3 if needed, then create the bucket
python3 - <<PYEOF
import boto3, json
from botocore.exceptions import ClientError

s3 = boto3.client(
    "s3",
    endpoint_url="https://${S3_DOMAIN}",
    aws_access_key_id="${ACCESS_KEY}",
    aws_secret_access_key="${SECRET_KEY}",
    region_name="${REGION}",
    config=boto3.session.Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"}
    ),
)

# Create bucket
try:
    s3.create_bucket(Bucket="${BUCKET}")
    print("Bucket '${BUCKET}' created.")
except ClientError as e:
    code = e.response["Error"]["Code"]
    if code in ("BucketAlreadyExists", "BucketAlreadyOwnedByYou"):
        print("Bucket '${BUCKET}' already exists.")
    else:
        raise

# Public-read policy
policy = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "PublicRead",
        "Effect": "Allow",
        "Principal": "*",
        "Action": "s3:GetObject",
        "Resource": "arn:aws:s3:::${BUCKET}/*"
    }]
})
s3.put_bucket_policy(Bucket="${BUCKET}", Policy=policy)
print("Public-read policy applied.")

# CORS (needed for browser direct uploads)
cors = {
    "CORSRules": [{
        "AllowedOrigins": ["https://kibegi.com", "https://www.kibegi.com", "http://localhost:*"],
        "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
        "AllowedHeaders": ["*"],
        "MaxAgeSeconds": 3600
    }]
}
s3.put_bucket_cors(Bucket="${BUCKET}", CORSConfiguration=cors)
print("CORS policy applied.")
print("Done — bucket is ready at https://${S3_DOMAIN}/${BUCKET}/")
PYEOF

echo "==> 4/4  All done."
echo ""
echo "Update your API .env:"
echo "  MINIO_API_ENDPOINT=https://${S3_DOMAIN}"
echo "  MINIO_PUBLIC_BASE_URL=https://${S3_DOMAIN}/${BUCKET}/"
