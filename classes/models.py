import uuid
from django.db import models
from django.conf import settings
from core.utils.code_generator import generate_unique_code


class Class(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    class_code = models.CharField(max_length=6, unique=True, editable=False, db_index=True)
    is_public = models.BooleanField(default=False)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_classes'
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='Membership',
        related_name='joined_classes'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Classes"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.class_code})"
    
    def save(self, *args, **kwargs):
        if not self.class_code:
            self.class_code = generate_unique_code(Class, 'class_code', 6)
        super().save(*args, **kwargs)


class Membership(models.Model):
    ROLE_CHOICES = [
        ('lecturer', 'Lecturer'),
        ('student', 'Student'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    class_obj = models.ForeignKey('Class', on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'class_obj']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.class_obj.name} ({self.role})"