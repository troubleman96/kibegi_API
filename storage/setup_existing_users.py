"""
Script to create storage records for existing users who don't have one.
Run this once after adding the storage app to existing installations.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kibegi_api.settings')
django.setup()

from authentication.models import User
from storage.services import StorageService

def setup_storage_for_existing_users():
    """Create storage records for all existing users"""
    users = User.objects.all()
    created_count = 0
    existing_count = 0
    
    for user in users:
        storage, created = StorageService.get_or_create_user_storage(user)
        if created:
            created_count += 1
            print(f"✓ Created storage record for {user.email}")
        else:
            existing_count += 1
            print(f"  Storage record already exists for {user.email}")
    
    print(f"\nSummary:")
    print(f"  Created: {created_count} storage records")
    print(f"  Already existed: {existing_count} storage records")
    print(f"  Total users: {users.count()}")

if __name__ == '__main__':
    setup_storage_for_existing_users()

