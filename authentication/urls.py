from django.urls import path
from .views import (
    RegisterAPIView,
    LoginAPIView,
    PasswordResetRequestAPIView,
    PasswordResetConfirmAPIView,
    UserProfileAPIView,
    ProfileImageUploadAPIView,
    PasswordResetVerifyAPIView,
    PasswordResetResendAPIView,
    RegisterVerifyAPIView,
    RegisterResendAPIView,
    LogoutAPIView,
    ChangePasswordAPIView,
)
from rest_framework_simplejwt.views import TokenRefreshView

app_name = 'authentication'

urlpatterns = [
    path('register/', RegisterAPIView.as_view(), name='register'),
    path('register/verify/', RegisterVerifyAPIView.as_view(), name='register_verify'),
    path('register/resend/', RegisterResendAPIView.as_view(), name='register_resend'),
    path('login/', LoginAPIView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutAPIView.as_view(), name='logout'),
    path('password-reset/', PasswordResetRequestAPIView.as_view(), name='password_reset'),
    path('password-reset/verify/', PasswordResetVerifyAPIView.as_view(), name='password_reset_verify'),
    path('password-reset/resend/', PasswordResetResendAPIView.as_view(), name='password_reset_resend'),
    path('password-reset-confirm/', PasswordResetConfirmAPIView.as_view(), name='password_reset_confirm'),
    path('change-password/', ChangePasswordAPIView.as_view(), name='change_password'),
    path('profile/', UserProfileAPIView.as_view(), name='profile'),
    path('profile/image/', ProfileImageUploadAPIView.as_view(), name='profile_image'),
]
