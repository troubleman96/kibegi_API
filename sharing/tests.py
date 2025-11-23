"""
Comprehensive tests for File Sharing System.

Tests all endpoints with realistic scenarios:
- Share file with single user
- Bulk share with multiple users
- Accept/reject shares
- List operations (requests, shared-with-me, my-shares)
- Permission validation
- Error cases

Run tests:
    python manage.py test sharing.tests
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from uploads.models import Upload
from classes.models import Class, Membership
from sharing.models import SharedFile
from sharing.services import SharingService
import os
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()


class SharingEndpointTests(TestCase):
    """Test all sharing endpoints with realistic data"""
    
    def setUp(self):
        """Set up test data before each test"""
        # Create test users
        self.lecturer = User.objects.create_user(
            email='lecturer@test.com',
            password='test123',
            full_name='Dr. Smith',
            user_type='lecturer'
        )
        
        self.student1 = User.objects.create_user(
            email='student1@test.com',
            password='test123',
            full_name='John Doe',
            user_type='student'
        )
        
        self.student2 = User.objects.create_user(
            email='student2@test.com',
            password='test123',
            full_name='Jane Smith',
            user_type='student'
        )
        
        self.student3 = User.objects.create_user(
            email='student3@test.com',
            password='test123',
            full_name='Bob Johnson',
            user_type='student'
        )
        
        # Create a class
        self.test_class = Class.objects.create(
            name='Computer Science 101',
            code='CS101',
            description='Intro to CS',
            created_by=self.lecturer
        )
        
        # Add members to class
        Membership.objects.create(
            user=self.lecturer,
            class_obj=self.test_class,
            role='lecturer'
        )
        Membership.objects.create(
            user=self.student1,
            class_obj=self.test_class,
            role='student'
        )
        Membership.objects.create(
            user=self.student2,
            class_obj=self.test_class,
            role='student'
        )
        Membership.objects.create(
            user=self.student3,
            class_obj=self.test_class,
            role='student'
        )
        
        # Create a test file upload
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"file_content",
            content_type="application/pdf"
        )
        
        self.upload = Upload.objects.create(
            file_name='test_document.pdf',
            file=test_file,
            file_size=len(b"file_content"),
            file_type='document',
            uploaded_by=self.student1,
            class_obj=self.test_class
        )
        
        # Set up API client
        self.client = APIClient()
    
    def get_auth_token(self, user):
        """Helper to get JWT token for user"""
        response = self.client.post('/api/v1/auth/login/', {
            'email': user.email,
            'password': 'test123'
        })
        return response.data['data']['access']
    
    def test_01_share_file_success(self):
        """Test: Share a file with another user (SUCCESS)"""
        print("\n" + "="*60)
        print("TEST 1: Share File - Success Case")
        print("="*60)
        
        # Login as file owner
        token = self.get_auth_token(self.student1)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Share file with student2
        response = self.client.post('/api/v1/sharing/', {
            'file_code': self.upload.file_code,
            'shared_with_id': self.student2.id,
            'message': 'Check out this document!'
        })
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Data: {response.data}")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['status'], 'pending')
        self.assertEqual(response.data['data']['message'], 'Check out this document!')
        
        # Verify share was created in DB
        share = SharedFile.objects.filter(
            upload=self.upload,
            shared_with=self.student2
        ).first()
        self.assertIsNotNone(share)
        self.assertEqual(share.status, 'pending')
        
        print("✅ PASSED: File shared successfully")
    
    def test_02_share_file_not_owner(self):
        """Test: Share file you don't own (SHOULD FAIL)"""
        print("\n" + "="*60)
        print("TEST 2: Share File - Not Owner (Should Fail)")
        print("="*60)
        
        # Login as student2 (not the owner)
        token = self.get_auth_token(self.student2)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Try to share student1's file
        response = self.client.post('/api/v1/sharing/', {
            'file_code': self.upload.file_code,
            'shared_with_id': self.student3.id,
            'message': 'Test'
        })
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Data: {response.data}")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        
        print("✅ PASSED: Correctly prevented non-owner from sharing")
    
    def test_03_share_file_duplicate(self):
        """Test: Share same file twice (SHOULD FAIL)"""
        print("\n" + "="*60)
        print("TEST 3: Duplicate Share (Should Fail)")
        print("="*60)
        
        # Login as file owner
        token = self.get_auth_token(self.student1)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # First share - should succeed
        response1 = self.client.post('/api/v1/sharing/', {
            'file_code': self.upload.file_code,
            'shared_with_id': self.student2.id,
            'message': 'First share'
        })
        
        print(f"\nFirst Share Status: {response1.status_code}")
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        
        # Second share - should fail
        response2 = self.client.post('/api/v1/sharing/', {
            'file_code': self.upload.file_code,
            'shared_with_id': self.student2.id,
            'message': 'Duplicate share'
        })
        
        print(f"Duplicate Share Status: {response2.status_code}")
        print(f"Response Data: {response2.data}")
        
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        
        print("✅ PASSED: Correctly prevented duplicate share")
    
    def test_04_bulk_share(self):
        """Test: Share file with multiple users"""
        print("\n" + "="*60)
        print("TEST 4: Bulk Share")
        print("="*60)
        
        # Login as file owner
        token = self.get_auth_token(self.student1)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Share with multiple students
        response = self.client.post('/api/v1/sharing/bulk/', {
            'file_code': self.upload.file_code,
            'user_ids': [self.student2.id, self.student3.id],
            'message': 'Sharing with multiple users'
        })
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Data: {response.data}")
        
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['status'], 'processing')
        self.assertEqual(response.data['data']['user_count'], 2)
        
        print("✅ PASSED: Bulk share initiated")
    
    def test_05_list_pending_requests(self):
        """Test: List pending share requests"""
        print("\n" + "="*60)
        print("TEST 5: List Pending Requests")
        print("="*60)
        
        # Create a share from student1 to student2
        SharedFile.objects.create(
            upload=self.upload,
            shared_by=self.student1,
            shared_with=self.student2,
            status='pending',
            message='Test request'
        )
        
        # Login as student2 (recipient)
        token = self.get_auth_token(self.student2)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Get pending requests
        response = self.client.get('/api/v1/sharing/requests/')
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Number of Requests: {response.data['data']['count']}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertGreater(response.data['data']['count'], 0)
        
        print("✅ PASSED: Pending requests retrieved")
    
    def test_06_list_shared_with_me(self):
        """Test: List all files shared with me"""
        print("\n" + "="*60)
        print("TEST 6: List Shared With Me")
        print("="*60)
        
        # Create shares
        SharedFile.objects.create(
            upload=self.upload,
            shared_by=self.student1,
            shared_with=self.student2,
            status='accepted',
            message='Accepted share'
        )
        
        # Login as student2
        token = self.get_auth_token(self.student2)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Get all shares
        response = self.client.get('/api/v1/sharing/shared-with-me/')
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Number of Shares: {response.data['data']['count']}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data['data']['count'], 0)
        
        # Test filtering by status
        response_accepted = self.client.get('/api/v1/sharing/shared-with-me/?status=accepted')
        print(f"Accepted Shares: {response_accepted.data['data']['count']}")
        
        self.assertEqual(response_accepted.status_code, status.HTTP_200_OK)
        
        print("✅ PASSED: Shared files retrieved")
    
    def test_07_list_my_shares(self):
        """Test: List files I shared"""
        print("\n" + "="*60)
        print("TEST 7: List My Shares")
        print("="*60)
        
        # Create share
        SharedFile.objects.create(
            upload=self.upload,
            shared_by=self.student1,
            shared_with=self.student2,
            status='pending',
            message='My share'
        )
        
        # Login as student1 (sharer)
        token = self.get_auth_token(self.student1)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Get my shares
        response = self.client.get('/api/v1/sharing/my-shares/')
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Number of Shares: {response.data['data']['count']}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data['data']['count'], 0)
        
        print("✅ PASSED: My shares retrieved")
    
    def test_08_accept_share(self):
        """Test: Accept a share request"""
        print("\n" + "="*60)
        print("TEST 8: Accept Share")
        print("="*60)
        
        # Create pending share
        share = SharedFile.objects.create(
            upload=self.upload,
            shared_by=self.student1,
            shared_with=self.student2,
            status='pending',
            message='Please accept'
        )
        
        # Login as student2 (recipient)
        token = self.get_auth_token(self.student2)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Accept the share
        response = self.client.post(f'/api/v1/sharing/{share.id}/accept/')
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Data: {response.data}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['status'], 'accepted')
        
        # Verify in DB
        share.refresh_from_db()
        self.assertEqual(share.status, 'accepted')
        self.assertIsNotNone(share.accepted_at)
        
        print("✅ PASSED: Share accepted successfully")
    
    def test_09_reject_share(self):
        """Test: Reject a share request"""
        print("\n" + "="*60)
        print("TEST 9: Reject Share")
        print("="*60)
        
        # Create pending share
        share = SharedFile.objects.create(
            upload=self.upload,
            shared_by=self.student1,
            shared_with=self.student2,
            status='pending',
            message='Can reject'
        )
        
        # Login as student2 (recipient)
        token = self.get_auth_token(self.student2)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Reject the share
        response = self.client.post(f'/api/v1/sharing/{share.id}/reject/')
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Data: {response.data}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['status'], 'rejected')
        
        # Verify in DB
        share.refresh_from_db()
        self.assertEqual(share.status, 'rejected')
        self.assertIsNotNone(share.rejected_at)
        
        print("✅ PASSED: Share rejected successfully")
    
    def test_10_accept_not_recipient(self):
        """Test: Accept share you're not recipient of (SHOULD FAIL)"""
        print("\n" + "="*60)
        print("TEST 10: Accept Share - Not Recipient (Should Fail)")
        print("="*60)
        
        # Create share for student2
        share = SharedFile.objects.create(
            upload=self.upload,
            shared_by=self.student1,
            shared_with=self.student2,
            status='pending'
        )
        
        # Login as student3 (not the recipient)
        token = self.get_auth_token(self.student3)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Try to accept
        response = self.client.post(f'/api/v1/sharing/{share.id}/accept/')
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Data: {response.data}")
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        print("✅ PASSED: Correctly prevented non-recipient from accepting")
    
    def test_11_get_share_details(self):
        """Test: Get details of a specific share"""
        print("\n" + "="*60)
        print("TEST 11: Get Share Details")
        print("="*60)
        
        # Create share
        share = SharedFile.objects.create(
            upload=self.upload,
            shared_by=self.student1,
            shared_with=self.student2,
            status='accepted',
            message='Detailed share'
        )
        
        # Login as student2 (recipient)
        token = self.get_auth_token(self.student2)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Get share details
        response = self.client.get(f'/api/v1/sharing/{share.id}/')
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Share Status: {response.data['data']['status']}")
        print(f"Message: {response.data['data']['message']}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['id'], str(share.id))
        
        print("✅ PASSED: Share details retrieved")
    
    def test_12_unauthenticated_access(self):
        """Test: Access endpoints without authentication (SHOULD FAIL)"""
        print("\n" + "="*60)
        print("TEST 12: Unauthenticated Access (Should Fail)")
        print("="*60)
        
        # Clear credentials
        self.client.credentials()
        
        # Try to share
        response = self.client.post('/api/v1/sharing/', {
            'file_code': self.upload.file_code,
            'shared_with_id': self.student2.id
        })
        
        print(f"\nResponse Status: {response.status_code}")
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        print("✅ PASSED: Correctly blocked unauthenticated access")


class SharingServiceTests(TestCase):
    """Test sharing service layer functions"""
    
    def setUp(self):
        """Set up test data"""
        self.lecturer = User.objects.create_user(
            email='lecturer@service.com',
            password='test123',
            full_name='Dr. Service',
            user_type='lecturer'
        )
        
        self.student1 = User.objects.create_user(
            email='student1@service.com',
            password='test123',
            full_name='Service Student 1',
            user_type='student'
        )
        
        self.student2 = User.objects.create_user(
            email='student2@service.com',
            password='test123',
            full_name='Service Student 2',
            user_type='student'
        )
        
        self.test_class = Class.objects.create(
            name='Service Test Class',
            code='SVC001',
            created_by=self.lecturer
        )
        
        Membership.objects.create(
            user=self.student1,
            class_obj=self.test_class,
            role='student'
        )
        Membership.objects.create(
            user=self.student2,
            class_obj=self.test_class,
            role='student'
        )
        
        test_file = SimpleUploadedFile(
            "service_test.pdf",
            b"content",
            content_type="application/pdf"
        )
        
        self.upload = Upload.objects.create(
            file_name='service_test.pdf',
            file=test_file,
            file_size=7,
            file_type='document',
            uploaded_by=self.student1,
            class_obj=self.test_class
        )
    
    def test_can_share_file(self):
        """Test: Permission check for sharing"""
        print("\n" + "="*60)
        print("SERVICE TEST: Can Share File")
        print("="*60)
        
        # Owner can share
        can_share, msg = SharingService.can_share_file(self.student1, self.upload)
        print(f"\nOwner can share: {can_share}")
        self.assertTrue(can_share)
        
        # Non-owner cannot share
        can_share, msg = SharingService.can_share_file(self.student2, self.upload)
        print(f"Non-owner can share: {can_share}")
        print(f"Error message: {msg}")
        self.assertFalse(can_share)
        
        print("✅ PASSED: Share permission checks work")
    
    def test_share_exists(self):
        """Test: Check if share already exists"""
        print("\n" + "="*60)
        print("SERVICE TEST: Share Exists Check")
        print("="*60)
        
        # Initially doesn't exist
        exists = SharingService.share_exists(self.upload, self.student2)
        print(f"\nInitially exists: {exists}")
        self.assertFalse(exists)
        
        # Create share
        SharedFile.objects.create(
            upload=self.upload,
            shared_by=self.student1,
            shared_with=self.student2,
            status='pending'
        )
        
        # Now exists
        exists = SharingService.share_exists(self.upload, self.student2)
        print(f"After creation exists: {exists}")
        self.assertTrue(exists)
        
        print("✅ PASSED: Share existence check works")


def run_all_tests():
    """Helper function to run tests with detailed output"""
    import sys
    from django.test.utils import get_runner
    from django.conf import settings
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=False, keepdb=False)
    
    print("\n" + "="*60)
    print("RUNNING COMPREHENSIVE SHARING SYSTEM TESTS")
    print("="*60)
    
    failures = test_runner.run_tests(['sharing.tests'])
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    if failures:
        print(f"❌ {failures} test(s) FAILED")
        sys.exit(1)
    else:
        print("✅ ALL TESTS PASSED")
        print("\nSharing system is working correctly!")


if __name__ == '__main__':
    run_all_tests()
