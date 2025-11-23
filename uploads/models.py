import uuid
import os
import mimetypes
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from core.utils.code_generator import generate_unique_code


def upload_file_path(instance, filename):
    """Generate upload path for files"""
    return f'uploads/{instance.uploader.id}/{filename}'


class Upload(models.Model):
    FILE_TYPE_CHOICES = [
        ('document', 'Document'),
        ('image', 'Image'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('archive', 'Archive'),
        ('spreadsheet', 'Spreadsheet'),
        ('presentation', 'Presentation'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to=upload_file_path)
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, default='other')
    file_size = models.BigIntegerField()
    file_code = models.CharField(max_length=8, unique=True, editable=False, db_index=True)
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploads'
    )
    # Foreign key to classes app - REQUIRED
    class_obj = models.ForeignKey(
        'classes.Class',  # String reference to avoid circular import
        on_delete=models.CASCADE,
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
    
    def detect_file_type(self):
        """Automatically detect file type based on extension and MIME type"""
        if not self.file:
            return 'other'
        
        # Get file extension
        filename = self.file.name
        ext = os.path.splitext(filename)[1][1:].lower()
        
        # Get MIME type
        mime_type, _ = mimetypes.guess_type(filename)
        
        # Document types
        if ext in ['pdf', 'doc', 'docx', 'txt', 'rtf', 'odt'] or (mime_type and 'text' in mime_type and ext not in ['csv']):
            return 'document'
        
        # Spreadsheet types
        if ext in ['xls', 'xlsx', 'csv', 'ods'] or (mime_type and 'spreadsheet' in mime_type):
            return 'spreadsheet'
        
        # Presentation types
        if ext in ['ppt', 'pptx', 'odp', 'key'] or (mime_type and 'presentation' in mime_type):
            return 'presentation'
        
        # Image types
        if ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp', 'ico'] or (mime_type and 'image' in mime_type):
            return 'image'
        
        # Video types
        if ext in ['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm', 'm4v'] or (mime_type and 'video' in mime_type):
            return 'video'
        
        # Audio types
        if ext in ['mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac', 'wma'] or (mime_type and 'audio' in mime_type):
            return 'audio'
        
        # Archive types
        if ext in ['zip', 'rar', 'tar', 'gz', '7z', 'bz2', 'xz']:
            return 'archive'
        
        return 'other'
    
    def save(self, *args, **kwargs):
        if not self.file_code:
            self.file_code = generate_unique_code(Upload, 'file_code', 8)
        if not self.file_name and self.file:
            self.file_name = os.path.basename(self.file.name)
        if not self.file_size and self.file:
            self.file_size = self.file.size
        # Auto-detect file type if not set or is 'other'
        if self.file and (not self.file_type or self.file_type == 'other'):
            self.file_type = self.detect_file_type()
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
