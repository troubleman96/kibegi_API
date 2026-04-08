#!/usr/bin/env python
"""
Quick Manual Test Script for Sharing System

Run this to quickly test all endpoints with your existing data:
    python sharing/manual_test.py

Or from Django shell:
    python manage.py shell < sharing/manual_test.py
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kibegi_api.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.uploads.models import Upload
from apps.classes.models import Class, Membership
from apps.sharing.models import SharedFile
from apps.sharing.services import SharingService
import requests
import json

User = get_user_model()

# Configuration
BASE_URL = "http://localhost:8000/api/v1"
TEST_EMAIL = input("Enter your email (or press Enter for 'test@example.com'): ").strip() or "test@example.com"
TEST_PASSWORD = input("Enter your password (or press Enter for 'password123'): ").strip() or "password123"

print("\n" + "="*70)
print("KIBEGI FILE SHARING SYSTEM - MANUAL TEST SUITE")
print("="*70)

# Helper function
def print_response(response, test_name):
    """Print formatted response"""
    print(f"\n{'='*70}")
    print(f"TEST: {test_name}")
    print(f"{'='*70}")
    print(f"Status Code: {response.status_code}")
    print(f"Response:")
    print(json.dumps(response.json(), indent=2))
    print()

def get_token(email, password):
    """Get JWT token"""
    response = requests.post(f"{BASE_URL}/auth/login/", json={
        "email": email,
        "password": password
    })
    if response.status_code == 200:
        return response.json()['data']['access']
    return None

# Step 1: Login
print("\n🔐 Step 1: Authenticating...")
TOKEN = get_token(TEST_EMAIL, TEST_PASSWORD)

if not TOKEN:
    print("❌ LOGIN FAILED!")
    print("Please check your credentials or create a user first.")
    print("\nTo create a test user:")
    print("    python manage.py createsuperuser")
    sys.exit(1)

print(f"✅ Logged in successfully!")
print(f"   Token: {TOKEN[:50]}...")

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# Step 2: Check if we have data
print("\n📊 Step 2: Checking test data...")
user = User.objects.filter(email=TEST_EMAIL).first()
uploads = Upload.objects.filter(uploaded_by=user, is_deleted=False)
classes = Class.objects.filter(
    membership__user=user
).distinct()

print(f"   Your uploads: {uploads.count()}")
print(f"   Your classes: {classes.count()}")

if uploads.count() == 0:
    print("\n⚠️  No uploads found!")
    print("Please upload a file first:")
    print("    POST /api/v1/uploads/")
    print("\nOr use the Swagger UI: http://localhost:8000/api/schema/swagger-ui/")
    sys.exit(0)

if classes.count() == 0:
    print("\n⚠️  Not member of any class!")
    print("Please join or create a class first.")
    sys.exit(0)

# Get test data
test_upload = uploads.first()
test_class = classes.first()
other_members = User.objects.filter(
    membership__class_obj=test_class
).exclude(id=user.id)

if other_members.count() == 0:
    print("\n⚠️  No other members in your class!")
    print("Please add more members to test sharing.")
    sys.exit(0)

recipient = other_members.first()

print(f"\n✅ Test data ready:")
print(f"   File: {test_upload.file_name} ({test_upload.file_code})")
print(f"   Class: {test_class.name}")
print(f"   Recipient: {recipient.full_name} ({recipient.email})")

# Run Tests
print("\n" + "="*70)
print("STARTING ENDPOINT TESTS")
print("="*70)

# Test 1: Share a file
print("\n📤 TEST 1: Share File")
response = requests.post(
    f"{BASE_URL}/sharing/",
    headers=headers,
    json={
        "file_code": test_upload.file_code,
        "shared_with_id": recipient.id,
        "message": "Automated test share"
    }
)
print_response(response, "Share File with Single User")

if response.status_code == 201:
    share_id = response.json()['data']['id']
    print(f"✅ Share created! ID: {share_id}")
else:
    print(f"⚠️  Share failed (might be duplicate)")
    # Try to find existing share
    existing = SharedFile.objects.filter(
        upload=test_upload,
        shared_with=recipient
    ).first()
    if existing:
        share_id = str(existing.id)
        print(f"   Using existing share: {share_id}")

# Test 2: Bulk Share
if other_members.count() >= 2:
    print("\n📤 TEST 2: Bulk Share")
    recipient_ids = [m.id for m in other_members[:3]]
    response = requests.post(
        f"{BASE_URL}/sharing/bulk/",
        headers=headers,
        json={
            "file_code": test_upload.file_code,
            "user_ids": recipient_ids,
            "message": "Bulk test share"
        }
    )
    print_response(response, "Bulk Share with Multiple Users")
else:
    print("\n⏭️  TEST 2: SKIPPED (need more class members)")

# Test 3: List Pending Requests
print("\n📥 TEST 3: List Pending Requests")
response = requests.get(
    f"{BASE_URL}/sharing/requests/",
    headers=headers
)
print_response(response, "List Pending Share Requests")

# Test 4: List Shared With Me
print("\n📥 TEST 4: List Shared With Me")
response = requests.get(
    f"{BASE_URL}/sharing/shared-with-me/",
    headers=headers
)
print_response(response, "List Files Shared With Me")

# Test 5: List My Shares
print("\n📤 TEST 5: List My Shares")
response = requests.get(
    f"{BASE_URL}/sharing/my-shares/",
    headers=headers
)
print_response(response, "List Files I Shared")

# Test 6: Get Share Details
if 'share_id' in locals():
    print("\n🔍 TEST 6: Get Share Details")
    response = requests.get(
        f"{BASE_URL}/sharing/{share_id}/",
        headers=headers
    )
    print_response(response, "Get Specific Share Details")

# Test 7: Accept Share (as recipient)
print("\n✅ TEST 7: Accept Share")
print("   Logging in as recipient to test accept...")
recipient_token = get_token(recipient.email, TEST_PASSWORD)

if recipient_token:
    recipient_headers = {
        "Authorization": f"Bearer {recipient_token}",
        "Content-Type": "application/json"
    }
    
    # Find a pending share for recipient
    pending_share = SharedFile.objects.filter(
        shared_with=recipient,
        status='pending'
    ).first()
    
    if pending_share:
        response = requests.post(
            f"{BASE_URL}/sharing/{pending_share.id}/accept/",
            headers=recipient_headers
        )
        print_response(response, "Accept Share Request")
    else:
        print("   ⏭️  No pending shares to accept")
else:
    print("   ⚠️  Could not login as recipient")
    print(f"   Please set password for {recipient.email}")

# Test 8: Reject Share (as recipient)
print("\n❌ TEST 8: Reject Share")
if recipient_token:
    # Create a new share to reject
    new_upload = uploads.exclude(id=test_upload.id).first()
    if new_upload:
        # Create share via API
        requests.post(
            f"{BASE_URL}/sharing/",
            headers=headers,
            json={
                "file_code": new_upload.file_code,
                "shared_with_id": recipient.id,
                "message": "For rejection test"
            }
        )
        
        # Get the share
        reject_share = SharedFile.objects.filter(
            shared_with=recipient,
            status='pending'
        ).last()
        
        if reject_share:
            response = requests.post(
                f"{BASE_URL}/sharing/{reject_share.id}/reject/",
                headers=recipient_headers
            )
            print_response(response, "Reject Share Request")
        else:
            print("   ⏭️  No share to reject")
    else:
        print("   ⏭️  Need another upload to test rejection")

# Summary
print("\n" + "="*70)
print("TEST SUMMARY")
print("="*70)

total_shares = SharedFile.objects.filter(shared_by=user).count()
pending_count = SharedFile.objects.filter(shared_by=user, status='pending').count()
accepted_count = SharedFile.objects.filter(shared_by=user, status='accepted').count()
rejected_count = SharedFile.objects.filter(shared_by=user, status='rejected').count()

print(f"\n📊 Your Sharing Statistics:")
print(f"   Total shares created: {total_shares}")
print(f"   Pending: {pending_count}")
print(f"   Accepted: {accepted_count}")
print(f"   Rejected: {rejected_count}")

received_count = SharedFile.objects.filter(shared_with=user).count()
print(f"\n📥 Shares received by you: {received_count}")

print("\n✅ ALL MANUAL TESTS COMPLETED!")
print("\nTo run automated tests:")
print("    python manage.py test sharing.tests")
print("\nTo see Swagger UI:")
print("    http://localhost:8000/api/schema/swagger-ui/")
print("="*70)
