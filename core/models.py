from django.db import models
from django.conf import settings


class RequestLog(models.Model):
    """Store HTTP request logs in database"""
    
    METHOD_CHOICES = [
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('PATCH', 'PATCH'),
        ('DELETE', 'DELETE'),
        ('OPTIONS', 'OPTIONS'),
        ('HEAD', 'HEAD'),
    ]
    
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, db_index=True)
    path = models.CharField(max_length=500, db_index=True)
    full_path = models.TextField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='request_logs'
    )
    user_email = models.EmailField(blank=True, null=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    status_code = models.IntegerField(db_index=True)
    response_time_ms = models.FloatField()
    request_body = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp', 'method']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['status_code', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.method} {self.path} - {self.status_code} ({self.user_email or 'anonymous'})"
