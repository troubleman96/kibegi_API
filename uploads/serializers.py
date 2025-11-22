from rest_framework import serializers
from .models import Upload
from .services import FileHandler


class UploadSerializer(serializers.ModelSerializer):
    uploader_name = serializers.CharField(source='uploader.full_name', read_only=True)
    class_name = serializers.CharField(source='class_obj.name', read_only=True)
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Upload
        fields = [
            'id', 'file', 'file_name', 'file_size', 'file_code',
            'uploader', 'uploader_name', 'class_obj', 'class_name',
            'is_deleted', 'deleted_at', 'created_at', 'updated_at',
            'file_url'
        ]
        read_only_fields = [
            'id', 'file_code', 'uploader', 'uploader_name',
            'is_deleted', 'deleted_at', 'created_at', 'updated_at',
            'file_url'
        ]
    
    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None
    
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
    class_name = serializers.CharField(source='class_obj.name', read_only=True)
    
    class Meta:
        model = Upload
        fields = [
            'id', 'file_name', 'file_size', 'file_code',
            'uploader_name', 'class_name', 'created_at'
        ]
