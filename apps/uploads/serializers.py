from rest_framework import serializers
from .models import Upload
from .services import FileHandler
from apps.authentication.serializers import UserSummarySerializer


class UploadSerializer(serializers.ModelSerializer):
    uploader_name = serializers.CharField(source='uploader.full_name', read_only=True)
    uploader_profile_image = serializers.ImageField(source='uploader.profile_image', read_only=True)
    uploader_profile_image_url = serializers.SerializerMethodField()
    class_name = serializers.CharField(source='class_obj.name', read_only=True)
    file_url = serializers.SerializerMethodField()
    file_type = serializers.CharField(read_only=True)  # Auto-detected, not user input
    file_size = serializers.IntegerField(read_only=True)  # Auto-detected from file, not user input
    file_name = serializers.CharField(required=False, allow_blank=True)  # Optional, auto-detected from file if empty
    
    class Meta:
        model = Upload
        fields = [
            'id', 'file', 'file_name', 'file_type', 'file_size', 'file_code',
            'uploader', 'uploader_name', 'uploader_profile_image', 'uploader_profile_image_url', 'class_obj', 'class_name',
            'is_deleted', 'deleted_at', 'created_at', 'updated_at',
            'file_url'
        ]
        read_only_fields = [
            'id', 'file_code', 'file_type', 'file_size', 'uploader', 'uploader_name', 'uploader_profile_image', 'uploader_profile_image_url',
            'class_name', 'is_deleted', 'deleted_at', 'created_at', 'updated_at',
            'file_url'
        ]
    
    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None

    def get_uploader_profile_image_url(self, obj):
        return UserSummarySerializer(context=self.context).get_profile_image_url(obj.uploader)
    
    def validate_file(self, value):
        """Validate file using FileHandler"""
        FileHandler.validate_file(value)
        return value
    
    def create(self, validated_data):
        """Set uploader from request user"""
        request = self.context.get('request')
        validated_data['uploader'] = request.user
        return super().create(validated_data)


class UploadListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views"""
    uploader_name = serializers.CharField(source='uploader.full_name', read_only=True)
    uploader_profile_image = serializers.ImageField(source='uploader.profile_image', read_only=True)
    uploader_profile_image_url = serializers.SerializerMethodField()
    class_name = serializers.CharField(source='class_obj.name', read_only=True)
    
    class Meta:
        model = Upload
        fields = [
            'id', 'file_name', 'file_type', 'file_size', 'file_code',
            'uploader_name', 'uploader_profile_image', 'uploader_profile_image_url', 'class_name', 'created_at'
        ]

    def get_uploader_profile_image_url(self, obj):
        return UserSummarySerializer(context=self.context).get_profile_image_url(obj.uploader)
