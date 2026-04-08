from rest_framework import serializers
from django.db.models import Count
from .models import Class, Membership
from apps.authentication.models import User


# ============================================================================
# Upload Serializers for Class Context
# ============================================================================

class ClassUploadSerializer(serializers.Serializer):
    """
    Lightweight serializer for uploads displayed within a class context.
    Shows essential upload information without exposing sensitive data.
    """
    id = serializers.UUIDField(read_only=True)
    file_name = serializers.CharField(read_only=True)
    file_type = serializers.CharField(read_only=True)
    file_size = serializers.IntegerField(read_only=True)
    file_code = serializers.CharField(read_only=True)
    uploader_id = serializers.UUIDField(source='uploader.id', read_only=True)
    uploader_name = serializers.CharField(source='uploader.full_name', read_only=True)
    uploader_type = serializers.CharField(source='uploader.user_type', read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class UploaderStatsSerializer(serializers.Serializer):
    """
    Serializer for uploader statistics within a class.
    Shows how many uploads each member has contributed.
    """
    uploader_id = serializers.UUIDField(read_only=True)
    uploader_name = serializers.CharField(read_only=True)
    uploader_type = serializers.CharField(read_only=True)  # 'lecturer' or 'student'
    upload_count = serializers.IntegerField(read_only=True)
    is_active_contributor = serializers.BooleanField(read_only=True)  # True if uploaded more than 2 files


class UploadsSummarySerializer(serializers.Serializer):
    """
    Serializer for uploads summary statistics.
    Provides overview of all uploads in a class.
    """
    total_uploads = serializers.IntegerField(read_only=True)
    uploads_by_type = serializers.DictField(read_only=True)  # {'document': 5, 'image': 3, ...}
    total_size_bytes = serializers.IntegerField(read_only=True)
    total_size_mb = serializers.FloatField(read_only=True)
    lecturers_with_uploads = serializers.IntegerField(read_only=True)
    active_contributors = serializers.IntegerField(read_only=True)  # Users with > 2 uploads


# ============================================================================
# Membership Serializers
# ============================================================================

class MembershipSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = Membership
        fields = ['id', 'user', 'user_name', 'user_email', 'role', 'joined_at']
        read_only_fields = ['id', 'joined_at']


class ClassSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source='creator.full_name', read_only=True)
    creator_type = serializers.CharField(source='creator.user_type', read_only=True)
    member_count = serializers.SerializerMethodField()
    is_member = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()
    
    class Meta:
        model = Class
        fields = [
            'id', 'name', 'description', 'class_code', 'is_public', 'is_verified',
            'creator', 'creator_name', 'creator_type', 'member_count', 'is_member',
            'user_role', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'class_code', 'is_verified', 'creator', 'created_at', 'updated_at']
    
    def get_member_count(self, obj):
        # Use annotation if available, otherwise count
        if hasattr(obj, 'total_members'):
            return obj.total_members
        return obj.members.count()
    
    def get_is_member(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.members.filter(id=request.user.id).exists()
        return False
    
    def get_user_role(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            membership = obj.memberships.filter(user=request.user).first()
            return membership.role if membership else None
        return None
    
    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['creator'] = request.user
        
        # Auto-set is_verified based on creator's user_type
        # Lecturers create verified classes, students create study groups
        validated_data['is_verified'] = request.user.user_type == 'lecturer'
        
        class_obj = super().create(validated_data)
        
        # Add creator as member with role matching their user_type
        # Lecturers get 'lecturer' role, students get 'student' role
        creator_role = 'lecturer' if request.user.user_type == 'lecturer' else 'student'
        Membership.objects.create(
            user=request.user,
            class_obj=class_obj,
            role=creator_role
        )
        
        return class_obj


class ClassListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views"""
    creator_name = serializers.CharField(source='creator.full_name', read_only=True)
    creator_type = serializers.CharField(source='creator.user_type', read_only=True)
    member_count = serializers.IntegerField(source='total_members', read_only=True)
    
    class Meta:
        model = Class
        fields = ['id', 'name', 'class_code', 'is_public', 'is_verified', 'creator_name', 'creator_type', 'member_count', 'created_at']


# ============================================================================
# Class Detail Serializer with Uploads Information
# ============================================================================

class ClassDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for class detail view.
    
    Includes:
    - All class information
    - Upload statistics and summary
    - Recent uploads list
    - Uploader statistics (who uploaded what)
    - Active contributors (members with > 2 uploads)
    
    This serializer provides rich data for UI to display:
    - Class overview with member counts
    - Upload activity and statistics
    - Quick access to recent files
    """
    # Basic class info
    creator_name = serializers.CharField(source='creator.full_name', read_only=True)
    creator_type = serializers.CharField(source='creator.user_type', read_only=True)
    member_count = serializers.SerializerMethodField()
    is_member = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()
    
    # Upload information - NEW FIELDS
    uploads_summary = serializers.SerializerMethodField()
    recent_uploads = serializers.SerializerMethodField()
    uploader_stats = serializers.SerializerMethodField()
    
    class Meta:
        model = Class
        fields = [
            # Basic info
            'id', 'name', 'description', 'class_code', 'is_public', 'is_verified',
            'creator', 'creator_name', 'creator_type', 'member_count', 'is_member',
            'user_role', 'created_at', 'updated_at',
            # Upload info - NEW
            'uploads_summary', 'recent_uploads', 'uploader_stats'
        ]
        read_only_fields = ['id', 'class_code', 'is_verified', 'creator', 'created_at', 'updated_at']
    
    def get_member_count(self, obj):
        """Get total member count for the class"""
        if hasattr(obj, 'total_members'):
            return obj.total_members
        return obj.members.count()
    
    def get_is_member(self, obj):
        """Check if current user is a member of this class"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.members.filter(id=request.user.id).exists()
        return False
    
    def get_user_role(self, obj):
        """Get current user's role in this class"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            membership = obj.memberships.filter(user=request.user).first()
            return membership.role if membership else None
        return None
    
    def get_uploads_summary(self, obj):
        """
        Get summary statistics of all uploads in this class.
        
        Returns:
            dict: Contains total_uploads, uploads_by_type, total_size_bytes,
                  total_size_mb, lecturers_with_uploads, active_contributors
        """
        from apps.uploads.models import Upload
        from django.db.models import Sum
        
        # Get all non-deleted uploads for this class
        uploads = Upload.objects.filter(class_obj=obj, is_deleted=False)
        
        # Count by file type
        type_counts = uploads.values('file_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        uploads_by_type = {item['file_type']: item['count'] for item in type_counts}
        
        # Total size
        total_size = uploads.aggregate(total=Sum('file_size'))['total'] or 0
        
        # Count lecturers with uploads
        lecturers_with_uploads = uploads.filter(
            uploader__user_type='lecturer'
        ).values('uploader').distinct().count()
        
        # Count active contributors (users with more than 2 uploads)
        active_contributors = uploads.values('uploader').annotate(
            upload_count=Count('id')
        ).filter(upload_count__gt=2).count()
        
        return {
            'total_uploads': uploads.count(),
            'uploads_by_type': uploads_by_type,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2) if total_size else 0,
            'lecturers_with_uploads': lecturers_with_uploads,
            'active_contributors': active_contributors
        }
    
    def get_recent_uploads(self, obj):
        """
        Get the 10 most recent uploads in this class.
        
        Returns:
            list: Recent uploads with file info and uploader details
        """
        from apps.uploads.models import Upload
        
        # Get recent non-deleted uploads
        recent = Upload.objects.filter(
            class_obj=obj, 
            is_deleted=False
        ).select_related('uploader').order_by('-created_at')[:10]
        
        return ClassUploadSerializer(recent, many=True).data
    
    def get_uploader_stats(self, obj):
        """
        Get statistics for each uploader in this class.
        
        Shows:
        - Each member who has uploaded files
        - Their upload count
        - Whether they're an active contributor (> 2 uploads)
        - Their user type (lecturer/student)
        
        This helps students see which lecturers are actively sharing materials.
        
        Returns:
            list: Uploader statistics sorted by upload count (descending)
        """
        from apps.uploads.models import Upload
        
        # Get upload counts per uploader
        uploader_data = Upload.objects.filter(
            class_obj=obj,
            is_deleted=False
        ).values(
            'uploader__id',
            'uploader__full_name',
            'uploader__user_type'
        ).annotate(
            upload_count=Count('id')
        ).order_by('-upload_count')
        
        stats = []
        for item in uploader_data:
            stats.append({
                'uploader_id': item['uploader__id'],
                'uploader_name': item['uploader__full_name'],
                'uploader_type': item['uploader__user_type'],
                'upload_count': item['upload_count'],
                'is_active_contributor': item['upload_count'] > 2  # More than 2 uploads = active
            })
        
        return stats


class JoinClassSerializer(serializers.Serializer):
    """Serializer for joining a class"""
    class_code = serializers.CharField(max_length=6)
    
    def validate_class_code(self, value):
        try:
            class_obj = Class.objects.get(class_code=value.upper())
            self.context['class_obj'] = class_obj
            return value.upper()
        except Class.DoesNotExist:
            raise serializers.ValidationError("Invalid class code")


class MemberSerializer(serializers.ModelSerializer):
    """Serializer for displaying class members"""
    role = serializers.SerializerMethodField()
    joined_at = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'user_type', 'role', 'joined_at']
    
    def get_role(self, obj):
        class_obj = self.context.get('class_obj')
        if class_obj:
            membership = class_obj.memberships.filter(user=obj).first()
            return membership.role if membership else None
        return None
    
    def get_joined_at(self, obj):
        class_obj = self.context.get('class_obj')
        if class_obj:
            membership = class_obj.memberships.filter(user=obj).first()
            return membership.joined_at if membership else None
        return None
