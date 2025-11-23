from rest_framework import serializers
from .models import SharedFile
from uploads.serializers import UploadSerializer
from authentication.models import User


class ShareFileSerializer(serializers.Serializer):
    """
    Serializer for creating a new file share.
    
    Fields:
    - file_code: The code of the file to share
    - shared_with_id: UUID of user to share with
    - message: Optional message to recipient
    """
    file_code = serializers.CharField(
        max_length=8,
        help_text="Unique code of the file to share"
    )
    shared_with_id = serializers.IntegerField(
        help_text="ID of the user to share with"
    )
    message = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        help_text="Optional message to the recipient"
    )
    
    def validate_file_code(self, value):
        """Validate that file exists and user can share it"""
        from uploads.models import Upload
        
        try:
            upload = Upload.objects.get(
                file_code=value.upper(),
                is_deleted=False
            )
            self.context['upload'] = upload
            return value.upper()
        except Upload.DoesNotExist:
            raise serializers.ValidationError("File not found or has been deleted")
    
    def validate_shared_with_id(self, value):
        """Validate that user exists"""
        try:
            user = User.objects.get(id=value)
            self.context['shared_with'] = user
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")
    
    def validate(self, data):
        """Cross-field validation"""
        request = self.context.get('request')
        upload = self.context.get('upload')
        shared_with = self.context.get('shared_with')
        
        # Check if user is trying to share with themselves
        if request.user == shared_with:
            raise serializers.ValidationError("Cannot share file with yourself")
        
        # Check if user has permission to share
        from .services import SharingService
        if not SharingService.can_share_file(request.user, upload):
            raise serializers.ValidationError("You don't have permission to share this file")
        
        # Check if recipient can receive the share
        if not SharingService.can_receive_share(shared_with, upload):
            raise serializers.ValidationError(
                "Recipient must be a member of the class to receive this file"
            )
        
        # Check if share already exists
        if SharingService.share_exists(upload, shared_with):
            raise serializers.ValidationError("File already shared with this user")
        
        return data


class BulkShareSerializer(serializers.Serializer):
    """
    Serializer for sharing a file with multiple users at once.
    
    Fields:
    - file_code: The code of the file to share
    - user_ids: List of user IDs to share with
    - message: Optional message
    """
    file_code = serializers.CharField(max_length=8)
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=50,  # Limit to 50 users per request
        help_text="List of user IDs to share with (max 50)"
    )
    message = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True
    )
    
    def validate_file_code(self, value):
        """Validate file exists"""
        from uploads.models import Upload
        
        try:
            upload = Upload.objects.get(
                file_code=value.upper(),
                is_deleted=False
            )
            self.context['upload'] = upload
            return value.upper()
        except Upload.DoesNotExist:
            raise serializers.ValidationError("File not found")


class SharedFileSerializer(serializers.ModelSerializer):
    """
    Serializer for SharedFile model with full details.
    
    Includes nested serializers for upload, sharer, and recipient.
    """
    # Nested upload details
    upload = UploadSerializer(read_only=True)
    
    # Sharer details
    shared_by_name = serializers.CharField(
        source='shared_by.full_name',
        read_only=True
    )
    shared_by_email = serializers.CharField(
        source='shared_by.email',
        read_only=True
    )
    
    # Recipient details
    shared_with_name = serializers.CharField(
        source='shared_with.full_name',
        read_only=True
    )
    shared_with_email = serializers.CharField(
        source='shared_with.email',
        read_only=True
    )
    
    # Computed fields
    can_access = serializers.SerializerMethodField()
    
    class Meta:
        model = SharedFile
        fields = [
            'id', 'upload', 'status', 'message',
            'shared_by', 'shared_by_name', 'shared_by_email',
            'shared_with', 'shared_with_name', 'shared_with_email',
            'shared_at', 'accepted_at', 'rejected_at',
            'can_access'
        ]
        read_only_fields = [
            'id', 'shared_by', 'shared_at',
            'accepted_at', 'rejected_at'
        ]
    
    def get_can_access(self, obj):
        """Check if recipient can access the file"""
        return obj.can_access_file


class SharedFileListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for list views.
    Shows essential share information without full nested data.
    """
    file_name = serializers.CharField(source='upload.file_name', read_only=True)
    file_type = serializers.CharField(source='upload.file_type', read_only=True)
    file_code = serializers.CharField(source='upload.file_code', read_only=True)
    shared_by_name = serializers.CharField(source='shared_by.full_name', read_only=True)
    shared_with_name = serializers.CharField(source='shared_with.full_name', read_only=True)
    
    class Meta:
        model = SharedFile
        fields = [
            'id', 'file_name', 'file_type', 'file_code',
            'shared_by_name', 'shared_with_name',
            'status', 'message', 'shared_at'
        ]


class AcceptRejectSerializer(serializers.Serializer):
    """
    Serializer for accepting or rejecting share requests.
    No additional fields needed - just the action.
    """
    pass

