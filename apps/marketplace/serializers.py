from decimal import Decimal

from rest_framework import serializers

from apps.authentication.serializers import UserSummarySerializer

from .models import Category, Listing, ListingOrder


class CategorySerializer(serializers.ModelSerializer):
    listing_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'is_active', 'listing_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'listing_count', 'created_at', 'updated_at']

    def get_listing_count(self, obj):
        return obj.listings.count()


class ListingListSerializer(serializers.ModelSerializer):
    seller = UserSummarySerializer(read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    available_quantity = serializers.IntegerField(read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            'id', 'listing_code', 'title', 'price', 'condition', 'status', 'quantity', 'sold_quantity',
            'available_quantity', 'location', 'seller', 'category', 'category_name', 'category_slug',
            'image', 'image_url', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        if obj.image:
            try:
                return obj.image.url
            except ValueError:
                return None
        return None


class ListingSerializer(serializers.ModelSerializer):
    seller = UserSummarySerializer(read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    available_quantity = serializers.IntegerField(read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            'id', 'listing_code', 'title', 'description', 'price', 'quantity', 'sold_quantity',
            'available_quantity', 'condition', 'status', 'image', 'image_url', 'location',
            'category', 'category_name', 'category_slug', 'seller', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'listing_code', 'sold_quantity', 'available_quantity', 'status', 'seller',
            'category_name', 'category_slug', 'image_url', 'created_at', 'updated_at',
        ]

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        if obj.image:
            try:
                return obj.image.url
            except ValueError:
                return None
        return None

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError('Quantity must be at least 1.')
        return value

    def validate_price(self, value):
        if value <= Decimal('0.00'):
            raise serializers.ValidationError('Price must be greater than zero.')
        return value

    def validate(self, attrs):
        quantity = attrs.get('quantity', getattr(self.instance, 'quantity', None))
        sold_quantity = getattr(self.instance, 'sold_quantity', 0)
        if quantity is not None and quantity < sold_quantity:
            raise serializers.ValidationError({'quantity': 'Quantity cannot be lower than the amount already sold.'})
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['seller'] = request.user
        return super().create(validated_data)


class ListingOrderSerializer(serializers.ModelSerializer):
    listing = ListingListSerializer(read_only=True)
    buyer = UserSummarySerializer(read_only=True)
    seller = UserSummarySerializer(read_only=True)

    class Meta:
        model = ListingOrder
        fields = [
            'id', 'listing', 'buyer', 'seller', 'quantity', 'unit_price', 'total_price',
            'status', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class ListingPurchaseSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(required=False, default=1, min_value=1)

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError('Quantity must be at least 1.')
        return value
