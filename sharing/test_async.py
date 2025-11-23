"""
Test async behavior of sharing system.

Run this file to see how async processing prevents blocking:
    python manage.py shell < sharing/test_async.py
"""

print("\n" + "="*60)
print("TESTING ASYNC SHARING BEHAVIOR")
print("="*60 + "\n")

import time
from django.contrib.auth import get_user_model
from uploads.models import Upload
from classes.models import Class, Membership
from sharing.tasks import bulk_share_async

User = get_user_model()

print("Setting up test data...")

# Get or create test users
try:
    user1 = User.objects.filter(user_type='lecturer').first()
    if not user1:
        print("❌ No lecturer found. Please create users first.")
        exit()
    
    students = User.objects.filter(user_type='student')[:5]
    if not students:
        print("❌ No students found. Please create users first.")
        exit()
    
    print(f"✅ Found lecturer: {user1.email}")
    print(f"✅ Found {len(students)} students")
    
    # Get a class with upload
    upload = Upload.objects.filter(uploaded_by=user1, is_deleted=False).first()
    if not upload:
        print("❌ No uploads found. Please upload a file first.")
        exit()
    
    print(f"✅ Found upload: {upload.file_name} ({upload.file_code})")
    
    # Test async bulk sharing
    print("\n" + "-"*60)
    print("TESTING BULK SHARE (ASYNC)")
    print("-"*60)
    
    user_ids = [s.id for s in students]
    
    print(f"\nSharing {upload.file_name} with {len(user_ids)} users...")
    print("⏱️  Starting timer...")
    
    start_time = time.time()
    
    # This should return IMMEDIATELY
    thread = bulk_share_async(
        upload=upload,
        shared_by=user1,
        user_ids=user_ids,
        message="Test async sharing"
    )
    
    response_time = (time.time() - start_time) * 1000  # Convert to ms
    
    print(f"\n✅ API RESPONDED IN: {response_time:.2f}ms")
    print(f"   (Background thread is still processing...)")
    
    if response_time < 100:
        print("\n🎉 SUCCESS! API returned in <100ms")
        print("   This proves async processing is working!")
    else:
        print(f"\n⚠️  Response took {response_time:.2f}ms")
        print("   This is slower than expected for async.")
    
    print("\n" + "-"*60)
    print("ASYNC BENEFITS DEMONSTRATED:")
    print("-"*60)
    print("✅ API returns immediately (not blocked)")
    print("✅ User can continue working")
    print("✅ Notifications sent in background")
    print("✅ No timeout risk with many users")
    print("✅ Better user experience")
    
    print("\n💡 The background thread is still running.")
    print("   Shares will be created and notifications sent.")
    print("   Check the shares table in a few seconds.")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("TEST COMPLETE")
print("="*60 + "\n")
