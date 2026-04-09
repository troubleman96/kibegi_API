from django.utils.translation import gettext_lazy as _
from django.contrib.auth import authenticate, get_user_model
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
import uuid
import random
from datetime import timedelta

from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    UserProfileSerializer,
    ProfileImageUploadSerializer,
    OTPVerifySerializer,
    ResendOTPSerializer,
    LogoutSerializer,
    ChangePasswordSerializer,
)
from .services import EmailService
from apps.core.utils.responses import success_response, error_response
from apps.core.utils.api_cache import build_cache_key, get_cached_response, cache_response, invalidate_cache_namespaces

User = get_user_model()


@extend_schema(tags=['Authentication'])
class RegisterAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer

    @extend_schema(
        summary="Register a new user",
        description="Register a new user account. An OTP will be sent to the provided email for verification.",
        request=UserRegistrationSerializer,
        responses={201: None}
    )
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # If user with this email already exists and is active, reject
        email = serializer.validated_data.get('email')
        try:
            existing = User.objects.get(email=email)
            if existing.is_active:
                return error_response(message=_('A user with this email already exists.'), status_code=status.HTTP_400_BAD_REQUEST)
            # else: proceed — allow re-sending OTP for inactive user by creating a new OTP below
        except User.DoesNotExist:
            existing = None

        # Create inactive user (must verify OTP to activate)
        user = serializer.save()
        user.is_active = False
        user.save()

        # generate and send OTP for registration verification
        otp_length = int(getattr(settings, 'OTP_LENGTH', 6))
        otp_code = ''.join([str(random.randint(0, 9)) for _ in range(otp_length)])
        expiry_seconds = int(getattr(settings, 'OTP_EXPIRY_SECONDS', 300))
        expires_at = timezone.now() + timedelta(seconds=expiry_seconds)

        from .models import PasswordResetOTP
        # invalidate previous otps for this email
        PasswordResetOTP.objects.filter(email=email, is_used=False).update(is_used=True)

        otp = PasswordResetOTP.objects.create(email=email, code=otp_code, expires_at=expires_at)

        # Send beautiful HTML email with OTP
        expiry_minutes = int(expiry_seconds / 60)
        user_name = user.full_name or email.split('@')[0]
        EmailService.send_registration_otp(
            email=email,
            user_name=user_name,
            otp_code=otp_code,
            expiry_minutes=expiry_minutes
        )

        return success_response(message=_('Registration initiated. Check your email for the verification code.'), status_code=status.HTTP_201_CREATED)


@extend_schema(tags=["Authentication"])
class LoginAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = UserLoginSerializer

    @extend_schema(
        summary="User login",
        description="Authenticate user with email and password. Returns JWT access and refresh tokens.",
        request=UserLoginSerializer,
        responses={200: UserProfileSerializer}
    )
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(email=serializer.validated_data['email'], password=serializer.validated_data['password'])
        if user is None:
            return error_response(message=_('Invalid email or password'), status_code=status.HTTP_401_UNAUTHORIZED)

        refresh = RefreshToken.for_user(user)
        user_serializer = UserProfileSerializer(user, context={'request': request})
        data = {
            'user': user_serializer.data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }
        return success_response(data=data, message=_('Login successful'))


@extend_schema(tags=["Authentication"])
class PasswordResetRequestAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = PasswordResetRequestSerializer

    @extend_schema(
        summary="Request password reset",
        description="Send an OTP code to the user's email for password reset verification.",
        request=PasswordResetRequestSerializer,
        responses={200: None}
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']

        # generate OTP
        otp_length = int(getattr(settings, 'OTP_LENGTH', 6))
        otp_code = ''.join([str(random.randint(0, 9)) for _ in range(otp_length)])
        expiry_seconds = int(getattr(settings, 'OTP_EXPIRY_SECONDS', 300))
        expires_at = timezone.now() + timedelta(seconds=expiry_seconds)

        # mark previous OTPs for this email as used to avoid reuse
        from .models import PasswordResetOTP
        PasswordResetOTP.objects.filter(email=email, is_used=False).update(is_used=True)

        otp = PasswordResetOTP.objects.create(
            email=email,
            code=otp_code,
            expires_at=expires_at,
        )

        # Send beautiful HTML email with OTP
        # Get user name if user exists
        expiry_minutes = int(expiry_seconds / 60)
        try:
            user = User.objects.get(email=email)
            user_name = user.full_name or email.split('@')[0]
        except User.DoesNotExist:
            user_name = email.split('@')[0]
        
        EmailService.send_password_reset_otp(
            email=email,
            user_name=user_name,
            otp_code=otp_code,
            expiry_minutes=expiry_minutes
        )

        return success_response(message=_('Password reset token has been sent to your email'))


@extend_schema(tags=["Authentication"])
class PasswordResetConfirmAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    @extend_schema(
        summary="Confirm password reset",
        description="Reset password using the reset token obtained from OTP verification.",
        request=PasswordResetConfirmSerializer,
        responses={200: None}
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']

        from .models import PasswordResetOTP
        try:
            otp = PasswordResetOTP.objects.get(reset_token=token, is_used=False)
        except PasswordResetOTP.DoesNotExist:
            return error_response(message=_('Invalid or expired token'), status_code=status.HTTP_400_BAD_REQUEST)

        if otp.expires_at < timezone.now():
            return error_response(message=_('Invalid or expired token'), status_code=status.HTTP_400_BAD_REQUEST)

        # set password for user associated with email
        try:
            user = User.objects.get(email=otp.email)
        except User.DoesNotExist:
            return error_response(message=_('User not found'), status_code=status.HTTP_404_NOT_FOUND)

        user.set_password(new_password)
        user.save()

        otp.is_used = True
        otp.save()

        return success_response(message=_('Password has been reset successfully'))


@extend_schema(tags=["Authentication"])
class PasswordResetVerifyAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = OTPVerifySerializer

    @extend_schema(
        summary="Verify password reset OTP",
        description="Verify the OTP code sent to email. Returns a reset token to use in password reset confirmation.",
        responses={200: None}
    )
    def post(self, request):
        from .serializers import OTPVerifySerializer
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        otp_code = serializer.validated_data['otp']

        from .models import PasswordResetOTP
        try:
            otp = PasswordResetOTP.objects.filter(email=email, code=otp_code, is_used=False).order_by('-created_at').first()
        except PasswordResetOTP.DoesNotExist:
            return error_response(message=_('Invalid code'), status_code=status.HTTP_400_BAD_REQUEST)

        if not otp:
            return error_response(message=_('Invalid code'), status_code=status.HTTP_400_BAD_REQUEST)

        if otp.expires_at < timezone.now():
            return error_response(message=_('OTP has expired'), status_code=status.HTTP_400_BAD_REQUEST)

        # mark OTP used and generate a reset token
        reset_token = str(uuid.uuid4())
        otp.reset_token = reset_token
        otp.is_used = False  # still allow using reset_token once
        otp.save()

        return success_response(data={'reset_token': reset_token}, message=_('OTP verified'))


@extend_schema(tags=["Authentication"])
class PasswordResetResendAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = ResendOTPSerializer

    @extend_schema(
        summary="Resend password reset OTP",
        description="Resend OTP code for password reset to the user's email.",
        responses={200: None}
    )
    def post(self, request):
        from .serializers import ResendOTPSerializer
        serializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']

        # create and send a new OTP
        otp_length = int(getattr(settings, 'OTP_LENGTH', 6))
        otp_code = ''.join([str(random.randint(0, 9)) for _ in range(otp_length)])
        expiry_seconds = int(getattr(settings, 'OTP_EXPIRY_SECONDS', 300))
        expires_at = timezone.now() + timedelta(seconds=expiry_seconds)

        from .models import PasswordResetOTP
        # invalidate previous unused otps
        PasswordResetOTP.objects.filter(email=email, is_used=False).update(is_used=True)

        otp = PasswordResetOTP.objects.create(email=email, code=otp_code, expires_at=expires_at)

        # Send beautiful HTML email with OTP
        expiry_minutes = int(expiry_seconds / 60)
        try:
            user = User.objects.get(email=email)
            user_name = user.full_name or email.split('@')[0]
        except User.DoesNotExist:
            user_name = email.split('@')[0]
        
        EmailService.send_resend_otp(
            email=email,
            user_name=user_name,
            otp_code=otp_code,
            expiry_minutes=expiry_minutes,
            purpose="password_reset"
        )

        return success_response(message=_('Password reset code resent'))


@extend_schema(tags=["Authentication"])
class RegisterResendAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = ResendOTPSerializer

    @extend_schema(
        summary="Resend registration OTP",
        description="Resend verification OTP for user registration. Rate limited to 5 attempts per 25 minutes.",
        responses={200: None, 429: None}
    )
    def post(self, request):
        from .serializers import ResendOTPSerializer
        serializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']

        from .models import PasswordResetOTP
        # rate limit: max 5 attempts per 25 minutes for registration purpose
        window_minutes = 25
        max_attempts = 5
        cutoff = timezone.now() - timedelta(minutes=window_minutes)
        recent_count = PasswordResetOTP.objects.filter(email=email, purpose='registration', created_at__gte=cutoff).count()
        if recent_count >= max_attempts:
            return error_response(message=_('Too many resend attempts. Try again later.'), status_code=status.HTTP_429_TOO_MANY_REQUESTS)

        # invalidate previous unused registration otps
        PasswordResetOTP.objects.filter(email=email, purpose='registration', is_used=False).update(is_used=True)

        otp_length = int(getattr(settings, 'OTP_LENGTH', 6))
        otp_code = ''.join([str(random.randint(0, 9)) for _ in range(otp_length)])
        expiry_seconds = int(getattr(settings, 'OTP_EXPIRY_SECONDS', 300))
        expires_at = timezone.now() + timedelta(seconds=expiry_seconds)

        otp = PasswordResetOTP.objects.create(email=email, code=otp_code, expires_at=expires_at, purpose='registration')

        # Send beautiful HTML email with OTP
        expiry_minutes = int(expiry_seconds / 60)
        try:
            user = User.objects.get(email=email)
            user_name = user.full_name or email.split('@')[0]
        except User.DoesNotExist:
            user_name = email.split('@')[0]
        
        EmailService.send_resend_otp(
            email=email,
            user_name=user_name,
            otp_code=otp_code,
            expiry_minutes=expiry_minutes,
            purpose="registration"
        )

        return success_response(message=_('Registration code resent'))


@extend_schema(tags=["Authentication"])
class RegisterVerifyAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = OTPVerifySerializer

    @extend_schema(
        summary="Verify registration OTP",
        description="Verify registration OTP code and activate user account. Returns JWT tokens upon successful verification.",
        responses={200: UserProfileSerializer}
    )
    def post(self, request):
        from .serializers import OTPVerifySerializer
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        otp_code = serializer.validated_data['otp']

        from .models import PasswordResetOTP
        otp = PasswordResetOTP.objects.filter(email=email, code=otp_code, is_used=False).order_by('-created_at').first()
        if not otp:
            return error_response(message=_('Invalid code'), status_code=status.HTTP_400_BAD_REQUEST)

        if otp.expires_at < timezone.now():
            return error_response(message=_('OTP has expired'), status_code=status.HTTP_400_BAD_REQUEST)

        # activate user
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return error_response(message=_('User not found'), status_code=status.HTTP_404_NOT_FOUND)

        user.is_active = True
        user.save()

        # mark OTP used
        otp.is_used = True
        otp.save()

        # issue tokens now that the user is verified
        refresh = RefreshToken.for_user(user)
        user_serializer = UserProfileSerializer(user, context={'request': request})
        data = {
            'user': user_serializer.data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }
        return success_response(data=data, message=_('Registration verified'))


@extend_schema(tags=["Authentication"])
class LogoutAPIView(APIView):
    """Blacklist a refresh token so it can't be used again."""
    permission_classes = [AllowAny]
    serializer_class = LogoutSerializer

    @extend_schema(
        summary="User logout",
        description="Blacklist the refresh token to invalidate it. User will need to login again.",
        responses={200: None}
    )
    def post(self, request):
        from .serializers import LogoutSerializer
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh_token = serializer.validated_data['refresh']
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception as e:
            return error_response(message=_('Invalid token or already blacklisted'), status_code=status.HTTP_400_BAD_REQUEST)

        return success_response(message=_('Successfully logged out'))


@extend_schema(tags=["Authentication"])
class ChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    @extend_schema(
        summary="Change password",
        description="Change user password. Requires current password for verification. User must be authenticated.",
        responses={200: None}
    )
    def post(self, request):
        from .serializers import ChangePasswordSerializer
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        current_password = serializer.validated_data['current_password']
        new_password = serializer.validated_data['new_password']

        if not user.check_password(current_password):
            return error_response(message=_('Current password is incorrect'), status_code=status.HTTP_400_BAD_REQUEST)

        # Set the new password (validate_password was already applied in serializer)
        user.set_password(new_password)
        user.save()
        invalidate_cache_namespaces('profile')

        return success_response(message=_('Password changed successfully'))


@extend_schema(tags=["Authentication"])
class UserProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    @extend_schema(
        summary="Get user profile",
        description="Retrieve the authenticated user's profile information.",
        responses={200: UserProfileSerializer}
    )
    def get(self, request):
        cache_key = build_cache_key(request, 'profile')
        cached_response = get_cached_response(cache_key)
        if cached_response is not None:
            return cached_response
        serializer = UserProfileSerializer(request.user, context={'request': request})
        response = success_response(data=serializer.data)
        return cache_response(cache_key, response, 'profile')

    @extend_schema(
        summary="Update user profile",
        description="Update user profile. Only username (full_name) can be updated, email is read-only.",
        request=UserProfileSerializer,
        responses={200: UserProfileSerializer}
    )
    def put(self, request):
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        invalidate_cache_namespaces('profile')
        return success_response(data=serializer.data, message=_('Profile updated'))

    @extend_schema(
        summary="Partially update user profile",
        description="Partially update user profile fields. Only username (full_name) can be updated.",
        request=UserProfileSerializer,
        responses={200: UserProfileSerializer}
    )
    def patch(self, request):
        # Allow partial updates via PATCH as well as PUT
        return self.put(request)


@extend_schema(tags=["Authentication"])
class ProfileImageUploadAPIView(APIView):
    """
    Upload or update user profile image.
    
    POST: Upload/update profile image
    DELETE: Remove profile image
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ProfileImageUploadSerializer
    
    @extend_schema(
        summary="Upload/Update profile image",
        description="""
Upload or update the authenticated user's profile image.

**Supported Formats:**
- JPEG/JPG
- PNG
- GIF
- WebP

**Constraints:**
- Maximum file size: 5MB
- Minimum dimensions: 50x50 pixels
- Maximum dimensions: 2000x2000 pixels

**Note:** If a profile image already exists, it will be replaced with the new one.
        """,
        request=ProfileImageUploadSerializer,
        responses={200: UserProfileSerializer}
    )
    def post(self, request):
        """Upload or update profile image"""
        serializer = ProfileImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        
        # Delete old profile image if it exists
        if user.profile_image:
            try:
                user.profile_image.delete(save=False)
            except Exception:
                pass  # Ignore errors if file doesn't exist
        
        # Set new profile image
        user.profile_image = serializer.validated_data['profile_image']
        user.save()
        invalidate_cache_namespaces('profile')
        
        # Return updated profile
        profile_serializer = UserProfileSerializer(user, context={'request': request})
        return success_response(
            message=_('Profile image uploaded successfully'),
            data=profile_serializer.data
        )
    
    @extend_schema(
        summary="Remove profile image",
        description="Remove the authenticated user's profile image.",
        responses={200: dict}
    )
    def delete(self, request):
        """Remove profile image"""
        user = request.user
        
        if not user.profile_image:
            return error_response(
                message=_('No profile image to remove'),
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Delete the image file
        try:
            user.profile_image.delete(save=False)
        except Exception:
            pass  # Ignore errors if file doesn't exist
        
        # Clear the field
        user.profile_image = None
        user.save()
        invalidate_cache_namespaces('profile')
        
        return success_response(
            message=_('Profile image removed successfully')
        )
