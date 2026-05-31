from django.conf import settings
from django.db import models


class SearchHistory(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='search_history',
    )
    query = models.CharField(max_length=200)
    result_count = models.IntegerField(default=0)
    categories_searched = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]
        verbose_name = 'Search History'
        verbose_name_plural = 'Search Histories'

    def __str__(self):
        return f'{self.user.email}: "{self.query}" ({self.result_count} results)'
