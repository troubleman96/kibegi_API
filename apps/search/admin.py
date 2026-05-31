from django.contrib import admin
from .models import SearchHistory


@admin.register(SearchHistory)
class SearchHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'query', 'result_count', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__email', 'user__full_name', 'query')
    readonly_fields = ('user', 'query', 'result_count', 'categories_searched', 'created_at')
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False
