from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.files.images import get_image_dimensions
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password], style={'input_type': 'password'})
    confirm_password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['email', 'full_name', 'user_type', 'password', 'confirm_password']

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({
                "password": _("Password fields didn't match.")
            })
        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password', None)
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, **validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True, style={'input_type': 'password'})


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class OTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True)


class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    new_password = serializers.CharField(write_only=True, required=True, validators=[validate_password], style={'input_type': 'password'})
    confirm_password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({
                'password': "Password fields didn't match."
            })
        return attrs


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password], style={'input_type': 'password'})
    confirm_password = serializers.CharField(required=True, style={'input_type': 'password'})

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({
                "password": _("Password fields didn't match.")
            })
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    # expose `full_name` as `username` in API so clients use `username` key
    username = serializers.CharField(source='full_name')
    profile_image_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        # present username and email to clients; email is read-only
        fields = ['id', 'email', 'username', 'user_type', 'profile_image', 'profile_image_url', 'date_joined']
        read_only_fields = ['id', 'email', 'date_joined', 'profile_image_url']
    
    def get_profile_image_url(self, obj):
        """Get full URL for profile image"""
        request = self.context.get('request')
        if obj.profile_image and request:
            return request.build_absolute_uri(obj.profile_image.url)
        return None


class ProfileImageUploadSerializer(serializers.Serializer):
    """
    Serializer for profile image upload/update.
    
    Validates image file and ensures it's a valid image format.
    """
    profile_image = serializers.ImageField(
        required=True,
        help_text="Profile image file. Supported formats: JPEG, PNG, GIF, WebP. Max size: 5MB."
    )
    
    def validate_profile_image(self, value):
        """
        Validate profile image:
        - Check file size (max 5MB)
        - Check file format
        - Optionally validate dimensions
        """
        # Check file size (5MB max)
        max_size = 5 * 1024 * 1024  # 5MB in bytes
        if value.size > max_size:
            raise serializers.ValidationError(
                "Image file too large. Maximum size is 5MB."
            )
        
        # Check file format
        valid_formats = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
        if value.content_type not in valid_formats:
            raise serializers.ValidationError(
                "Unsupported image format. Please upload a JPEG, PNG, GIF, or WebP image."
            )
        
        # Validate it's actually an image by checking dimensions
        try:
            width, height = get_image_dimensions(value)
            if width is None or height is None:
                raise serializers.ValidationError("Invalid image file.")
            
            # Optional: Check minimum dimensions
            if width < 50 or height < 50:
                raise serializers.ValidationError(
                    "Image dimensions too small. Minimum size is 50x50 pixels."
                )
            
            # Optional: Check maximum dimensions (prevent huge images)
            if width > 2000 or height > 2000:
                raise serializers.ValidationError(
                    "Image dimensions too large. Maximum size is 2000x2000 pixels."
                )
        except Exception as e:
            raise serializers.ValidationError(f"Invalid image file: {str(e)}")
        
        return value
