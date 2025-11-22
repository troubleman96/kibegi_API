from rest_framework import serializers
from .models import Class, Membership
from authentication.models import User


class MembershipSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = Membership
        fields = ['id', 'user', 'user_name', 'user_email', 'role', 'joined_at']
        read_only_fields = ['id', 'joined_at']


class ClassSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source='creator.full_name', read_only=True)
    member_count = serializers.SerializerMethodField()
    is_member = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()
    
    class Meta:
        model = Class
        fields = [
            'id', 'name', 'description', 'class_code', 'is_public',
            'creator', 'creator_name', 'member_count', 'is_member',
            'user_role', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'class_code', 'creator', 'created_at', 'updated_at']
    
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
        class_obj = super().create(validated_data)
        
        # Automatically add creator as a member with lecturer role
        Membership.objects.create(
            user=request.user,
            class_obj=class_obj,
            role='lecturer'
        )
        
        return class_obj


class ClassListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views"""
    creator_name = serializers.CharField(source='creator.full_name', read_only=True)
    member_count = serializers.IntegerField(source='total_members', read_only=True)
    
    class Meta:
        model = Class
        fields = ['id', 'name', 'class_code', 'is_public', 'creator_name', 'member_count', 'created_at']


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
