from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .models import LibraryCategory, LibraryItem

User = get_user_model()


@override_settings(ALLOWED_HOSTS=['testserver'])
class LibraryAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.password = 'StrongPass123!'
        self.user = User.objects.create_user(
            email='uploader@test.com',
            password=self.password,
            full_name='Uploader One',
            user_type='student',
        )
        self.category = LibraryCategory.objects.get(slug='past-papers')
        self.item = LibraryItem.objects.create(
            title='Intro to Programming Past Paper',
            description='Useful revision material',
            file=SimpleUploadedFile('paper.pdf', b'paper content', content_type='application/pdf'),
            file_type='past_paper',
            subject='Computer Science',
            course_code='CSC 101',
            author_name='Department',
            category=self.category,
            uploaded_by=self.user,
        )

    def authenticate(self):
        response = self.client.post(
            '/api/v1/auth/login/',
            {'email': self.user.email, 'password': self.password},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.data['data']['tokens']['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_public_category_and_item_browse(self):
        categories_response = self.client.get(reverse('library:categories'))
        items_response = self.client.get(reverse('library:items'))

        self.assertEqual(categories_response.status_code, status.HTTP_200_OK)
        self.assertEqual(items_response.status_code, status.HTTP_200_OK)
        self.assertIn('data', categories_response.data)
        self.assertIn('data', items_response.data)

    def test_upload_sets_authenticated_user_and_keeps_separate_from_storage_quota(self):
        self.authenticate()
        file_obj = SimpleUploadedFile('notes.pdf', b'notes content', content_type='application/pdf')
        response = self.client.post(
            reverse('library:items'),
            {
                'title': 'Revision Notes',
                'description': 'Helpful notes for finals',
                'file': file_obj,
                'file_type': 'note',
                'subject': 'Math',
                'course_code': 'MTH 102',
                'author_name': 'Student Group',
                'category': self.category.id,
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['uploaded_by']['id'], self.user.id)
        self.assertEqual(LibraryItem.objects.filter(title='Revision Notes', uploaded_by=self.user).count(), 1)

    def test_anonymous_download_endpoint_reaches_public_item(self):
        response = self.client.get(reverse('library:item-download', kwargs={'item_code': self.item.item_code}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('attachment', response.headers.get('Content-Disposition', '').lower())
