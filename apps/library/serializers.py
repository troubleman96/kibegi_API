from rest_framework import serializers

from apps.authentication.serializers import UserSummarySerializer

from .models import LibraryCategory, LibraryItem


class LibraryCategoryReferenceField(serializers.Field):
    def to_representation(self, value):
        if not value:
            return None
        return LibraryCategorySerializer(value, context=self.context).data

    def to_internal_value(self, data):
        if data in (None, ''):
            return None

        queryset = LibraryCategory.objects.filter(is_active=True)

        if isinstance(data, dict):
            slug = data.get('slug')
            if slug:
                category = queryset.filter(slug=slug).first()
                if category:
                    return category
            category_id = data.get('id')
            if category_id:
                category = queryset.filter(pk=category_id).first()
                if category:
                    return category

        if isinstance(data, int) or (isinstance(data, str) and data.isdigit()):
            category = queryset.filter(pk=data).first()
            if category:
                return category

        if isinstance(data, str):
            category = queryset.filter(slug=data).first()
            if category:
                return category

        raise serializers.ValidationError('Select a valid category.')


class LibraryCategorySerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = LibraryCategory
        fields = ['id', 'name', 'slug', 'description', 'is_active', 'item_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'item_count', 'created_at', 'updated_at']

    def get_item_count(self, obj):
        return obj.items.filter(status='public').count()


class LibraryItemListSerializer(serializers.ModelSerializer):
    uploaded_by = UserSummarySerializer(read_only=True)
    category = LibraryCategoryReferenceField(read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = LibraryItem
        fields = [
            'id', 'item_code', 'title', 'description', 'file_type', 'subject', 'course_code',
            'author_name', 'status', 'is_featured', 'view_count', 'download_count', 'file_name',
            'file_url', 'category', 'category_name', 'category_slug', 'uploaded_by', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        if obj.file:
            try:
                return obj.file.url
            except ValueError:
                return None
        return None


class LibraryItemSerializer(serializers.ModelSerializer):
    uploaded_by = UserSummarySerializer(read_only=True)
    category = LibraryCategoryReferenceField()
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = LibraryItem
        fields = [
            'id', 'item_code', 'title', 'description', 'file', 'file_type', 'subject', 'course_code',
            'author_name', 'status', 'is_featured', 'view_count', 'download_count', 'file_name',
            'file_url', 'category', 'category_name', 'category_slug', 'uploaded_by', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'item_code', 'status', 'view_count', 'download_count', 'uploaded_by',
            'category_name', 'category_slug', 'file_name', 'file_url', 'created_at', 'updated_at',
        ]

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        if obj.file:
            try:
                return obj.file.url
            except ValueError:
                return None
        return None

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['uploaded_by'] = request.user
        return super().create(validated_data)
