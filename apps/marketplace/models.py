import uuid

from django.conf import settings
from django.db import models

from apps.core.utils.code_generator import generate_unique_code


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active', 'name']),
        ]

    def __str__(self):
        return self.name


class Listing(models.Model):
    CONDITION_CHOICES = [
        ('new', 'New'),
        ('like_new', 'Like New'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('sold_out', 'Sold Out'),
        ('archived', 'Archived'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing_code = models.CharField(max_length=8, unique=True, editable=False, db_index=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    sold_quantity = models.PositiveIntegerField(default=0)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='good')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', db_index=True)
    image = models.ImageField(upload_to='marketplace/listings/', blank=True, null=True)
    location = models.CharField(max_length=200, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='listings')
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='marketplace_listings',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['seller', 'status']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f'{self.title} ({self.listing_code})'

    @property
    def available_quantity(self):
        return max(self.quantity - self.sold_quantity, 0)

    def save(self, *args, **kwargs):
        if not self.listing_code:
            self.listing_code = generate_unique_code(Listing, 'listing_code', 8)
        if self.sold_quantity >= self.quantity:
            self.status = 'sold_out'
        elif self.status == 'sold_out' and self.sold_quantity < self.quantity:
            self.status = 'active'
        super().save(*args, **kwargs)

    def can_purchase(self, quantity=1):
        return self.status == 'active' and quantity > 0 and self.available_quantity >= quantity

    def record_purchase(self, quantity=1):
        self.sold_quantity += quantity
        if self.available_quantity == 0:
            self.status = 'sold_out'
        self.save(update_fields=['sold_quantity', 'status', 'updated_at'])


class ListingOrder(models.Model):
    STATUS_CHOICES = [
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='orders')
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='marketplace_purchases',
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='marketplace_sales',
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['buyer', 'status']),
            models.Index(fields=['seller', 'status']),
            models.Index(fields=['listing', 'created_at']),
        ]

    def __str__(self):
        return f'{self.buyer.email} bought {self.quantity} of {self.listing.title}'
