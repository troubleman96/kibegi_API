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
from rest_framework.permissions import IsAdminUser
from apps.core.utils.responses import success_response, error_response

import logging
logger = logging.getLogger('kibegi')
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
        # Lecturers need admin approval before they can use the platform
        if user.user_type == 'lecturer':
            user.is_approved = False
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

        if user.user_type == 'lecturer' and not user.is_approved:
            return error_response(
                message=_('Your lecturer account is pending admin approval. You will be notified once approved.'),
                status_code=status.HTTP_403_FORBIDDEN
            )

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

        # Apply profile data submitted alongside the OTP
        new_type = request.data.get('user_type', '').strip()
        university = request.data.get('university', '').strip()[:255]
        phone_number = request.data.get('phone_number', '').strip()[:20]

        if new_type in ('student', 'lecturer'):
            user.user_type = new_type
        if university:
            user.university = university
        if phone_number:
            user.phone_number = phone_number

        user.is_active = True
        # Lecturers always require approval, regardless of whether this was set at registration
        if user.user_type == 'lecturer':
            user.is_approved = False
        user.save()

        # mark OTP used
        otp.is_used = True
        otp.save()

        # Lecturers await admin approval — return success but no tokens yet
        if user.user_type == 'lecturer' and not user.is_approved:
            return success_response(
                message=_('Email verified. Your lecturer account is pending admin approval. You will be notified once approved.'),
                status_code=status.HTTP_200_OK
            )

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


@extend_schema(tags=['Authentication'])
class GoogleLoginAPIView(APIView):
    """Exchange a Google ID token for Kibegi JWT tokens.

    The frontend completes the Google OAuth2 flow and receives an ID token
    (credential). It posts that credential here; we verify it with Google,
    then find-or-create the matching Kibegi user and return access/refresh
    tokens exactly like the regular login endpoint.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Login or register with Google",
        description=(
            "Post the Google OAuth2 `access_token` or `credential` obtained from "
            "Google Sign-In. Returns JWT tokens and user profile on success."
        ),
        responses={200: UserProfileSerializer},
    )
    def post(self, request):
        token = (
            request.data.get('access_token')
            or request.data.get('credential')
            or request.data.get('id_token')
            or ''
        ).strip()
        if not token:
            return error_response(
                message=_('Google access_token or credential is required.'),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')

        # Verify the token via Google's API and fetch user info.
        try:
            import json as _json
            import urllib.error
            import urllib.parse
            import urllib.request

            if request.data.get('credential') or request.data.get('id_token'):
                tokeninfo_url = (
                    'https://oauth2.googleapis.com/tokeninfo?'
                    + urllib.parse.urlencode({'id_token': token})
                )
                tokeninfo_req = urllib.request.Request(tokeninfo_url)
                with urllib.request.urlopen(tokeninfo_req, timeout=10) as resp:
                    id_info = _json.loads(resp.read().decode())
            else:
                userinfo_req = urllib.request.Request(
                    'https://www.googleapis.com/oauth2/v3/userinfo',
                )
                userinfo_req.add_header('Authorization', f'Bearer {token}')
                with urllib.request.urlopen(userinfo_req, timeout=10) as resp:
                    id_info = _json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            logger.warning('Google userinfo request failed: %s', exc)
            return error_response(
                message=_('Invalid or expired Google access token.'),
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception as exc:
            logger.error('Google userinfo error: %s', exc, exc_info=True)
            return error_response(
                message=_('Could not verify Google token.'),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        email = id_info.get('email', '').lower()
        if not email:
            return error_response(
                message=_('Google account has no email address.'),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not id_info.get('email_verified', False):
            return error_response(
                message=_('Google email address is not verified.'),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if client_id:
            token_audience = id_info.get('aud')
            if token_audience and token_audience != client_id:
                return error_response(
                    message=_('Google token was issued for a different client.'),
                    status_code=status.HTTP_401_UNAUTHORIZED,
                )

        full_name = (id_info.get('name') or
                     (id_info.get('given_name', '') + ' ' + id_info.get('family_name', '')).strip()
                     or email.split('@')[0])

        # Profile fields — only applied when creating a brand-new account.
        # Existing users keep whatever they registered with.
        requested_type = request.data.get('user_type', 'student')
        if requested_type not in ('student', 'lecturer'):
            requested_type = 'student'
        university = request.data.get('university', '').strip()[:255]
        phone_number = request.data.get('phone_number', '').strip()[:20]

        # Find or create the user
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            is_lecturer = requested_type == 'lecturer'
            user = User.objects.create_user(
                email=email,
                full_name=full_name or email.split('@')[0],
                user_type=requested_type,
                password=None,  # no password — Google auth only
            )
            user.is_active = True
            user.is_approved = not is_lecturer  # lecturers need admin approval
            user.university = university
            user.phone_number = phone_number
            user.save(update_fields=['is_active', 'is_approved', 'university', 'phone_number'])
            logger.info('New Google user created: %s (type=%s)', email, requested_type)

        # Block inactive accounts
        if not user.is_active:
            return error_response(
                _('Your account is inactive. Please contact support.'),
                status.HTTP_403_FORBIDDEN,
            )

        # Block unapproved lecturers (covers both Google-registered and email-registered)
        if user.user_type == 'lecturer' and not user.is_approved:
            return error_response(
                _('pending_approval'),
                status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)
        user_serializer = UserProfileSerializer(user, context={'request': request})
        data = {
            'user': user_serializer.data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
        }
        return success_response(data=data, message=_('Google login successful'))


@extend_schema(tags=['Authentication'])
class LecturerApprovalAPIView(APIView):
    """Admin-only endpoint to list pending lecturers and approve or reject them."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary="List pending lecturer accounts",
        description="Returns all lecturer accounts awaiting admin approval.",
        responses={200: UserProfileSerializer(many=True)}
    )
    def get(self, request):
        pending = User.objects.filter(user_type='lecturer', is_active=True, is_approved=False)
        serializer = UserProfileSerializer(pending, many=True, context={'request': request})
        return success_response(data=serializer.data)

    @extend_schema(
        summary="Approve or reject a lecturer",
        description="Approve or reject a lecturer account. Send `{user_id, action}` where action is 'approve' or 'reject'.",
        responses={200: None}
    )
    def post(self, request):
        user_id = request.data.get('user_id')
        action = request.data.get('action')

        if not user_id or action not in ('approve', 'reject'):
            return error_response(
                message=_("Provide user_id and action ('approve' or 'reject')."),
                status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            lecturer = User.objects.get(id=user_id, user_type='lecturer')
        except User.DoesNotExist:
            return error_response(message=_('Lecturer not found'), status_code=status.HTTP_404_NOT_FOUND)

        if action == 'approve':
            lecturer.is_approved = True
            lecturer.save(update_fields=['is_approved'])
            EmailService.send_lecturer_approved(
                email=lecturer.email,
                user_name=lecturer.full_name or lecturer.email.split('@')[0]
            )
            return success_response(message=_('Lecturer approved and notified via email.'))
        else:
            # Reject: deactivate account
            lecturer.is_active = False
            lecturer.save(update_fields=['is_active'])
            EmailService.send_lecturer_rejected(
                email=lecturer.email,
                user_name=lecturer.full_name or lecturer.email.split('@')[0]
            )
            return success_response(message=_('Lecturer rejected and notified via email.'))


class PhoneSendOTPView(APIView):
    """Send a 6-digit OTP to the user's phone number via SMS."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        import random
        import re
        from django.utils import timezone
        from datetime import timedelta
        from apps.core.utils.sms import SendAfricaSmsClient
        from .models import PhoneOTP

        raw_phone = (request.data.get('phone_number') or '').strip()
        if not raw_phone:
            return error_response(_('phone_number is required'), status_code=status.HTTP_400_BAD_REQUEST)

        # Normalise Tanzania number
        digits = re.sub(r'\D', '', raw_phone)
        if digits.startswith('255') and len(digits) == 12:
            phone = f'+{digits}'
        elif digits.startswith('0') and len(digits) == 10:
            phone = f'+255{digits[1:]}'
        elif len(digits) == 9 and digits[0] in '7':
            phone = f'+255{digits}'
        else:
            return error_response(
                _('Invalid Tanzania phone number. Use format 07XXXXXXXX or +255XXXXXXXXX'),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Valid Tanzania mobile prefixes: 071-078
        prefix = phone[4:7]
        if prefix not in {'071', '072', '073', '074', '075', '076', '077', '078', '065', '066', '067', '068', '069'}:
            return error_response(
                _('Invalid Tanzania mobile number prefix.'),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Rate limit: max 3 OTPs per phone per hour
        one_hour_ago = timezone.now() - timedelta(hours=1)
        recent = PhoneOTP.objects.filter(user=request.user, phone=phone, created_at__gte=one_hour_ago).count()
        if recent >= 3:
            return error_response(
                _('Too many OTP requests. Please wait before trying again.'),
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        otp_code = f"{random.SystemRandom().randint(100000, 999999)}"
        expires_at = timezone.now() + timedelta(minutes=PhoneOTP.EXPIRY_MINUTES)

        PhoneOTP.objects.create(
            user=request.user,
            phone=phone,
            otp=otp_code,
            expires_at=expires_at,
        )

        message = f"Your Kibegi verification code is {otp_code}. Valid for {PhoneOTP.EXPIRY_MINUTES} minutes. Do not share it."

        client = SendAfricaSmsClient()
        if not client.is_configured():
            # In dev/staging without API key: log OTP for testing
            import logging
            logging.getLogger('kibegi').warning('SENDAFRICA not configured — OTP %s for %s', otp_code, phone)
            return success_response(message=_('OTP sent (dev mode — check server logs)'), data={'phone': phone})

        try:
            client.send_sms(phone_number=phone, message=message)
        except Exception as exc:
            return error_response(f'Could not send SMS: {exc}', status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

        return success_response(message=_('OTP sent to your phone number'), data={'phone': phone})


class PhoneVerifyOTPView(APIView):
    """Verify OTP and mark phone number as verified on the user's account."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from django.utils import timezone
        from .models import PhoneOTP

        phone = (request.data.get('phone_number') or '').strip()
        code = (request.data.get('otp') or '').strip()

        if not phone or not code:
            return error_response(_('phone_number and otp are required'), status_code=status.HTTP_400_BAD_REQUEST)

        # Find latest OTP for this user+phone
        try:
            otp_obj = PhoneOTP.objects.filter(
                user=request.user,
                phone=phone,
                verified=False,
            ).latest('created_at')
        except PhoneOTP.DoesNotExist:
            return error_response(_('No pending OTP for this number. Please request a new one.'), status_code=status.HTTP_400_BAD_REQUEST)

        if otp_obj.is_expired():
            return error_response(_('OTP has expired. Please request a new one.'), status_code=status.HTTP_400_BAD_REQUEST)

        if otp_obj.attempts >= PhoneOTP.MAX_ATTEMPTS:
            return error_response(_('Too many failed attempts. Please request a new OTP.'), status_code=status.HTTP_400_BAD_REQUEST)

        if otp_obj.otp != code:
            otp_obj.attempts += 1
            otp_obj.save(update_fields=['attempts'])
            remaining = PhoneOTP.MAX_ATTEMPTS - otp_obj.attempts
            return error_response(
                _('Incorrect OTP.') + (f' {remaining} attempt(s) remaining.' if remaining > 0 else ' Please request a new OTP.'),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Mark OTP verified
        otp_obj.verified = True
        otp_obj.save(update_fields=['verified'])

        # Update user
        user = request.user
        user.phone_number = phone
        user.phone_verified = True
        user.save(update_fields=['phone_number', 'phone_verified'])

        return success_response(
            message=_('Phone number verified successfully'),
            data={'phone_number': phone, 'phone_verified': True},
        )
