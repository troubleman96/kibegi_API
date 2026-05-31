import uuid

from django.conf import settings
from django.db import models

from apps.core.utils.code_generator import generate_unique_code


class LibraryCategory(models.Model):
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


class LibraryItem(models.Model):
    FILE_TYPE_CHOICES = [
        ('book', 'Book'),
        ('past_paper', 'Past Paper'),
        ('note', 'Note'),
        ('slide', 'Slide'),
        ('project', 'Project'),
        ('assignment', 'Assignment'),
        ('research', 'Research'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('public', 'Public'),
        ('archived', 'Archived'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item_code = models.CharField(max_length=8, unique=True, editable=False, db_index=True)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='library/items/')
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, default='other')
    subject = models.CharField(max_length=160, blank=True)
    course_code = models.CharField(max_length=80, blank=True)
    author_name = models.CharField(max_length=160, blank=True)
    category = models.ForeignKey(LibraryCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='items')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='library_items',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='public', db_index=True)
    is_featured = models.BooleanField(default=False)
    view_count = models.PositiveIntegerField(default=0)
    download_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['uploaded_by', 'status']),
            models.Index(fields=['file_type', 'status']),
        ]

    def __str__(self):
        return f'{self.title} ({self.item_code})'

    def save(self, *args, **kwargs):
        if not self.item_code:
            self.item_code = generate_unique_code(LibraryItem, 'item_code', 8)
        super().save(*args, **kwargs)

    @property
    def file_name(self):
        return self.file.name.split('/')[-1] if self.file else ''

    def increment_views(self):
        self.view_count += 1
        self.save(update_fields=['view_count', 'updated_at'])

    def increment_downloads(self):
        self.download_count += 1
        self.save(update_fields=['download_count', 'updated_at'])
