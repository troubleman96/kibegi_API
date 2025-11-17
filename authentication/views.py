from django.utils.translation import gettext_lazy as _
from django.contrib.auth import authenticate, get_user_model
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
import uuid
import random
from datetime import timedelta

from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    UserProfileSerializer,
)
from utils.response import success_response, error_response

User = get_user_model()


class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

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

        subject = _('Your Kibegi registration code')
        message = _('Your registration verification code is: {code}. It will expire in {mins} minutes.').format(code=otp_code, mins=int(expiry_seconds / 60))
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
        try:
            if from_email:
                send_mail(subject, message, from_email, [email])
        except Exception:
            pass

        return success_response(message=_('Registration initiated. Check your email for the verification code.'), status_code=status.HTTP_201_CREATED)


class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(email=serializer.validated_data['email'], password=serializer.validated_data['password'])
        if user is None:
            return error_response(message=_('Invalid email or password'), status_code=status.HTTP_401_UNAUTHORIZED)

        refresh = RefreshToken.for_user(user)
        data = {
            'user': UserProfileSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }
        return success_response(data=data, message=_('Login successful'))


class PasswordResetRequestAPIView(APIView):
    permission_classes = [AllowAny]

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

        # attempt to send email; fail silently but log in response if needed
        subject = _('Your Kibegi password reset code')
        message = _(
            'Your password reset code is: {code}. It will expire in {mins} minutes.'
        ).format(code=otp_code, mins=int(expiry_seconds / 60))
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
        try:
            if from_email:
                send_mail(subject, message, from_email, [email])
        except Exception:
            # don't expose email errors directly; return generic message
            pass

        return success_response(message=_('Password reset link has been sent to your email'))


class PasswordResetConfirmAPIView(APIView):
    permission_classes = [AllowAny]

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


class PasswordResetVerifyAPIView(APIView):
    permission_classes = [AllowAny]

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


class PasswordResetResendAPIView(APIView):
    permission_classes = [AllowAny]

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

        subject = _('Your Kibegi password reset code')
        message = _(
            'Your password reset code is: {code}. It will expire in {mins} minutes.'
        ).format(code=otp_code, mins=int(expiry_seconds / 60))
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
        try:
            if from_email:
                send_mail(subject, message, from_email, [email])
        except Exception:
            pass

        return success_response(message=_('Password reset code resent'))


class RegisterResendAPIView(APIView):
    permission_classes = [AllowAny]

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

        subject = _('Your Kibegi registration code')
        message = _('Your registration verification code is: {code}. It will expire in {mins} minutes.').format(code=otp_code, mins=int(expiry_seconds / 60))
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
        try:
            if from_email:
                send_mail(subject, message, from_email, [email])
        except Exception:
            pass

        return success_response(message=_('Registration code resent'))


class RegisterVerifyAPIView(APIView):
    permission_classes = [AllowAny]

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
        data = {
            'user': UserProfileSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }
        return success_response(data=data, message=_('Registration verified'))


class UserProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return success_response(data=serializer.data)

    def put(self, request):
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(data=serializer.data, message=_('Profile updated'))
