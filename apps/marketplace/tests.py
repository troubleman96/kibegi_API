from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .models import Category, Listing, ListingOrder

User = get_user_model()


@override_settings(ALLOWED_HOSTS=['testserver'])
class MarketplaceAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.password = 'StrongPass123!'
        self.seller = User.objects.create_user(
            email='seller@test.com',
            password=self.password,
            full_name='Seller One',
            user_type='student',
        )
        self.buyer = User.objects.create_user(
            email='buyer@test.com',
            password=self.password,
            full_name='Buyer One',
            user_type='student',
        )
        self.category = Category.objects.create(
            name='Textbooks',
            slug='textbooks',
            description='Books and study materials',
        )
        self.listing = Listing.objects.create(
            title='Calculus Textbook',
            description='Second edition in good condition',
            price=Decimal('150.00'),
            quantity=2,
            condition='good',
            status='active',
            category=self.category,
            seller=self.seller,
        )

    def authenticate(self, user):
        response = self.client.post(
            '/api/v1/auth/login/',
            {'email': user.email, 'password': self.password},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.data['data']['tokens']['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_category_list_returns_categories(self):
        self.authenticate(self.buyer)
        response = self.client.get(reverse('marketplace:categories'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        slugs = [item['slug'] for item in response.data['data']]
        self.assertIn('textbooks', slugs)

    def test_default_categories_are_seeded(self):
        self.authenticate(self.buyer)
        response = self.client.get(reverse('marketplace:categories'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slugs = {item['slug'] for item in response.data['data']}
        self.assertTrue({'electronics', 'books', 'stationery', 'fashion', 'furniture'}.issubset(slugs))

    def test_listing_creation_sets_authenticated_seller(self):
        self.authenticate(self.seller)
        response = self.client.post(
            reverse('marketplace:listings'),
            {
                'title': 'Graphing Calculator',
                'description': 'Barely used',
                'price': '80.00',
                'quantity': 1,
                'condition': 'like_new',
                'category': self.category.id,
                'location': 'Main campus',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['seller']['id'], self.seller.id)
        self.assertEqual(Listing.objects.filter(title='Graphing Calculator', seller=self.seller).count(), 1)

    def test_listing_purchase_creates_order_and_reduces_stock(self):
        self.authenticate(self.buyer)
        response = self.client.post(
            reverse('marketplace:listing-purchase', kwargs={'listing_code': self.listing.listing_code}),
            {'quantity': 1},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.sold_quantity, 1)
        self.assertEqual(self.listing.available_quantity, 1)
        self.assertTrue(ListingOrder.objects.filter(listing=self.listing, buyer=self.buyer, status='completed').exists())

    def test_listing_purchase_rejects_own_listing(self):
        self.authenticate(self.seller)
        response = self.client.post(
            reverse('marketplace:listing-purchase', kwargs={'listing_code': self.listing.listing_code}),
            {'quantity': 1},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])

    def test_my_listings_returns_only_owned_items(self):
        self.authenticate(self.seller)
        response = self.client.get(reverse('marketplace:my-listings'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)
        self.assertEqual(response.data['data'][0]['listing_code'], self.listing.listing_code)

    def test_orders_endpoint_can_filter_purchases(self):
        ListingOrder.objects.create(
            listing=self.listing,
            buyer=self.buyer,
            seller=self.seller,
            quantity=1,
            unit_price=self.listing.price,
            total_price=self.listing.price,
            status='completed',
        )

        self.authenticate(self.buyer)
        response = self.client.get(reverse('marketplace:orders'), {'type': 'purchases'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)
        self.assertEqual(response.data['data'][0]['buyer']['id'], self.buyer.id)
