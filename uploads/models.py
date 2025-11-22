import uuid
import os
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from core.utils.code_generator import generate_unique_code


def upload_file_path(instance, filename):
    """Generate upload path for files"""
    return f'uploads/{instance.uploader.id}/{filename}'


class Upload(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to=upload_file_path)
    file_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField()
    file_code = models.CharField(max_length=8, unique=True, editable=False, db_index=True)
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploads'
    )
    # Foreign key to classes app
    class_obj = models.ForeignKey(
        'classes.Class',  # String reference to avoid circular import
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploads'
    )
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.file_name} ({self.file_code})"
    
    def save(self, *args, **kwargs):
        if not self.file_code:
            self.file_code = generate_unique_code(Upload, 'file_code', 8)
        if not self.file_name and self.file:
            self.file_name = os.path.basename(self.file.name)
        if not self.file_size and self.file:
            self.file_size = self.file.size
        super().save(*args, **kwargs)
    
    def soft_delete(self):
        """Soft delete the upload"""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restore a soft-deleted upload"""
        self.is_deleted = False
        self.deleted_at = None
        self.save()
    
    def is_permanently_deletable(self):
        """Check if upload can be permanently deleted (after 21 days)"""
        if self.deleted_at:
            return timezone.now() > self.deleted_at + timedelta(days=21)
        return False
