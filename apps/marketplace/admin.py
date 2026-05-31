from django.contrib import admin

from .models import Category, Listing, ListingOrder


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'slug')
    ordering = ('name',)


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ('listing_code', 'title', 'seller', 'price', 'status', 'quantity', 'sold_quantity', 'created_at')
    list_filter = ('status', 'condition', 'category', 'created_at')
    search_fields = ('listing_code', 'title', 'description', 'seller__full_name', 'seller__email')
    ordering = ('-created_at',)
    readonly_fields = ('listing_code', 'sold_quantity', 'created_at', 'updated_at')


@admin.register(ListingOrder)
class ListingOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'listing', 'buyer', 'seller', 'quantity', 'total_price', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('listing__title', 'buyer__full_name', 'buyer__email', 'seller__full_name', 'seller__email')
    ordering = ('-created_at',)
    readonly_fields = ('id', 'created_at', 'updated_at')
