import logging
import secrets
from datetime import timedelta

from django.contrib.auth import login as django_login
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.views.generic import TemplateView
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from django.contrib.auth import update_session_auth_hash
from rest_framework.permissions import IsAuthenticated

from .models import PasswordResetOTP
from .serializers import UserLoginSerializer, UserRegistrationSerializer, PasswordResetRequestSerializer, User, \
    PasswordResetVerifySerializer, PasswordResetConfirmSerializer, ChangePasswordSerializer

logger = logging.getLogger(__name__)


class UserRegistrationAPIView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors,
                'message': 'اطلاعات وارد شده معتبر نیست'
            }, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        return Response({
            'success': True,
            'message': 'ثبت‌نام با موفقیت انجام شد',
            'user': {
                'id': user.id,
                'email': user.email,
                'fullname': user.fullname,
                'mobile': user.mobile
            }
        }, status=status.HTTP_201_CREATED)


class RegisterPageView(TemplateView):
    template_name = 'accounts/register.html'


class UserLoginAPIView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = UserLoginSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors,
                'message': 'ورود ناموفق بود'
            }, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data['user']
        django_login(request, user)  # session رو می‌سازه، session-fixation رو هم خودش هندل می‌کنه

        logger.info(f"User logged in: {user.username} (id={user.id})")

        return Response({
            'success': True,
            'message': 'با موفقیت وارد شدید',
            'user': {
                'id': user.id,
                'username': user.username,
                'fullname': user.fullname,
                'mobile': user.mobile
            }
        }, status=status.HTTP_200_OK)


class LoginPageView(TemplateView):
    template_name = 'accounts/login.html'


class PasswordResetRequestAPIView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = PasswordResetRequestSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset_request'

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data['identifier']
        channel = serializer.validated_data['channel']

        user = User.objects.filter(
            Q(email=identifier) | Q(mobile=identifier)
        ).first()

        # همیشه پیام یکسان — چه کاربر پیدا شد چه نه
        generic_response = Response({
            'success': True,
            'message': 'در صورت معتبر بودن حساب، کد تایید ارسال شد'
        }, status=status.HTTP_200_OK)

        if not user:
            return generic_response

        code = PasswordResetOTP.generate_code()
        PasswordResetOTP.objects.create(
            user=user,
            code_hash=PasswordResetOTP.hash_code(code),
            channel=channel,
            destination=identifier,
            expires_at=timezone.now() + timedelta(minutes=PasswordResetOTP.OTP_LIFETIME_MINUTES)
        )

        # TODO: گام بعد - وصل کردن به سرویس واقعی SMS/Email
        # send_otp(channel=channel, destination=identifier, code=code)
        logger.info(f"OTP generated for user_id={user.id} via {channel}")

        return generic_response


class PasswordResetVerifyAPIView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = PasswordResetVerifySerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset_verify'

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data['identifier']
        code = serializer.validated_data['code']

        user = User.objects.filter(Q(email=identifier) | Q(mobile=identifier)).first()
        generic_error = Response({
            'success': False,
            'errors': {'code': ['کد وارد شده نامعتبر یا منقضی شده است']},
            'message': 'تایید ناموفق بود'
        }, status=status.HTTP_400_BAD_REQUEST)

        if not user:
            return generic_error

        otp = PasswordResetOTP.objects.filter(
            user=user, is_used=False
        ).order_by('-created_at').first()

        if not otp or otp.is_expired() or otp.is_locked():
            return generic_error

        if otp.code_hash != PasswordResetOTP.hash_code(code):
            otp.attempts = models.F('attempts') + 1
            otp.save(update_fields=['attempts'])
            return generic_error

        # کد درسته → یکبار مصرفش کن، reset_token بده
        raw_token = secrets.token_urlsafe(32)
        otp.reset_token = PasswordResetOTP.hash_code(raw_token)  # هش شده ذخیره میشه
        otp.is_used = True
        otp.save(update_fields=['reset_token', 'is_used'])

        return Response({
            'success': True,
            'message': 'کد تایید شد',
            'reset_token': raw_token,  # فقط همینجا خام برمی‌گرده به کلاینت
            'expires_in': PasswordResetOTP.RESET_TOKEN_LIFETIME_MINUTES * 60
        }, status=status.HTTP_200_OK)


class PasswordResetConfirmAPIView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = PasswordResetConfirmSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset_confirm'

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_token = serializer.validated_data['reset_token']
        token_hash = PasswordResetOTP.hash_code(raw_token)

        otp = PasswordResetOTP.objects.filter(
            reset_token=token_hash,
            is_used=True  # باید از مرحله verify اومده باشه
        ).order_by('-created_at').first()

        generic_error = Response({
            'success': False,
            'errors': {'reset_token': ['توکن نامعتبر یا منقضی شده است']},
            'message': 'بازنشانی رمز عبور ناموفق بود'
        }, status=status.HTTP_400_BAD_REQUEST)

        if not otp:
            return generic_error

        token_expiry = otp.created_at + timedelta(minutes=PasswordResetOTP.RESET_TOKEN_LIFETIME_MINUTES)
        if timezone.now() > token_expiry:
            return generic_error

        user = otp.user
        user.set_password(serializer.validated_data['new_password1'])
        user.save(update_fields=['password'])

        # مهم: توکن رو بلافاصله بعد از مصرف باطل کن تا reuse نشه
        otp.reset_token = None
        otp.save(update_fields=['reset_token'])

        logger.info(f"Password reset completed for user_id={user.id}")

        return Response({
            'success': True,
            'message': 'رمز عبور با موفقیت تغییر کرد'
        }, status=status.HTTP_200_OK)

class PasswordResetPageView(TemplateView):
    template_name = 'accounts/forgot-password.html'





class ChangePasswordAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'change_password'

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors,
                'message': 'تغییر رمز عبور ناموفق بود'
            }, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        user.set_password(serializer.validated_data['new_password1'])
        user.save(update_fields=['password'])

        # حیاتی: بدون این خط، session کاربر بعد از تغییر پسورد invalid می‌شه
        # و باید دوباره لاگین کنه. مهم‌تر: این خط session hash رو rotate می‌کنه
        # که یعنی هر session token دیگه‌ای (مثلاً session دزدیده‌شده) بلافاصله invalid می‌شه
        update_session_auth_hash(request, user)

        logger.info(f"Password changed for user_id={user.id}")

        return Response({
            'success': True,
            'message': 'رمز عبور با موفقیت تغییر کرد'
        }, status=status.HTTP_200_OK)