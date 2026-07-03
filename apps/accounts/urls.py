from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from .views import RegisterPageView, UserRegistrationAPIView, LoginPageView, UserLoginAPIView, \
    PasswordResetRequestAPIView, PasswordResetConfirmAPIView, PasswordResetVerifyAPIView, PasswordResetPageView, \
    ChangePasswordAPIView

app_name = 'accounts_app'

urlpatterns = [
    path('register/', RegisterPageView.as_view(), name='register'),
    path('api/register/', UserRegistrationAPIView.as_view(), name='api_register'),
    path('login/', LoginPageView.as_view(), name='login'),
    path('api/login/', UserLoginAPIView.as_view(), name='api_login'),
    path('api/password-reset/request/', PasswordResetRequestAPIView.as_view(), name='api_password_reset_request'),
    path('api/password-reset/verify/', PasswordResetVerifyAPIView.as_view(), name='api_password_reset_verify'),
    path('api/password-reset/confirm/', PasswordResetConfirmAPIView.as_view(), name='api_password_reset_confirm'),
    path('password-reset/', PasswordResetPageView.as_view(), name='password_reset'),  # صفحه‌ی HTML سه‌مرحله‌ای
    path('api/change-password/', ChangePasswordAPIView.as_view(), name='api_change_password'),
]
