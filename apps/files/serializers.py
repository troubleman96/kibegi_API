from rest_framework import serializers
from apps.uploads.models import Upload
from apps.sharing.models import SharedFile
from django.contrib.auth import get_user_model

User = get_user_model()


class FileOwnerSerializer(serializers.ModelSerializer):
    """Serializer for file owner/uploader info"""
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'user_type']


class UnifiedFileSerializer(serializers.Serializer):
    """Unified serializer for files from both uploads and sharing"""
    id = serializers.UUIDField()
    file_code = serializers.CharField()
    file_name = serializers.CharField()
    file_size = serializers.IntegerField()
    file_type = serializers.CharField()
    file_url = serializers.SerializerMethodField()
    source = serializers.CharField()  # 'upload' or 'shared'
    owner = FileOwnerSerializer()
    uploaded_at = serializers.DateTimeField()
    is_deleted = serializers.BooleanField()
    deleted_at = serializers.DateTimeField(allow_null=True)
    
    # Sharing-specific fields (null for uploads)
    shared_by = serializers.SerializerMethodField()
    shared_at = serializers.DateTimeField(allow_null=True, required=False)
    accepted = serializers.BooleanField(required=False, allow_null=True)
    
    def get_file_url(self, obj):
        file_obj = obj.get('file') if isinstance(obj, dict) else getattr(obj, 'file', None)
        if file_obj:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(file_obj.url)
        return None
    
    def get_shared_by(self, obj):
        shared_by = obj.get('shared_by') if isinstance(obj, dict) else getattr(obj, 'shared_by', None)
        if shared_by:
            return FileOwnerSerializer(shared_by).data
        return None


class DeletedFileSerializer(serializers.Serializer):
    """Serializer for deleted files from both uploads and sharing"""
    id = serializers.UUIDField()
    file_code = serializers.CharField()
    file_name = serializers.CharField()
    file_size = serializers.IntegerField()
    file_type = serializers.CharField()
    source = serializers.CharField()  # 'upload' or 'shared'
    owner = FileOwnerSerializer()
    deleted_at = serializers.DateTimeField()
    days_until_permanent_deletion = serializers.IntegerField()
    
    # Sharing-specific
    shared_by = serializers.SerializerMethodField()
    was_accepted = serializers.BooleanField(required=False, allow_null=True)
    
    def get_shared_by(self, obj):
        shared_by = obj.get('shared_by') if isinstance(obj, dict) else getattr(obj, 'shared_by', None)
        if shared_by:
            return FileOwnerSerializer(shared_by).data
        return None
