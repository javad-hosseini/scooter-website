# accounts/models.py

import hashlib
import secrets
import os

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


def user_profile_image_path(instance, filename):
    """مسیر ذخیره عکس پروفایل کاربر"""
    ext = filename.split('.')[-1]
    # استفاده از username برای نام فایل
    filename = f"{slugify(instance.username)}-{timezone.now().strftime('%Y%m%d%H%M%S')}.{ext}"
    return os.path.join('users/profiles/', filename)


class CustomUser(AbstractUser):
    fullname = models.CharField(max_length=100, verbose_name="نام کامل")
    mobile = models.CharField(max_length=11, unique=True, verbose_name="شماره موبایل")
    email = models.EmailField(unique=True, verbose_name="ایمیل")
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # ========== فیلد جدید برای عکس پروفایل ==========
    profile_image = models.ImageField(
        upload_to=user_profile_image_path,
        verbose_name="عکس پروفایل",
        blank=True,
        null=True,
        default='users/profiles/default-avatar.png'
    )

    bio = models.TextField(
        verbose_name="بیوگرافی",
        blank=True,
        null=True,
        help_text="توضیحات درباره نویسنده برای نمایش در انتهای مقاله"
    )

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='customuser_set',
        blank=True,
        verbose_name='groups',
        help_text='The groups this user belongs to.'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='customuser_set',
        blank=True,
        verbose_name='user permissions',
        help_text='Specific permissions for this user.'
    )

    USERNAME_FIELD = 'username'

    def __str__(self):
        return self.fullname or self.email

    class Meta:
        verbose_name = "کاربر"
        verbose_name_plural = "کاربران"


class PasswordResetOTP(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reset_otps')
    code_hash = models.CharField(max_length=64)  # هش SHA-256 کد، نه خود کد
    channel = models.CharField(max_length=10, choices=[('email', 'Email'), ('sms', 'SMS')])
    destination = models.CharField(max_length=255)  # ایمیل یا موبایلی که کد بهش رفته
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)
    reset_token = models.CharField(max_length=64, null=True, blank=True, unique=True)  # بعد از verify موفق ست میشه

    MAX_ATTEMPTS = 5
    OTP_LIFETIME_MINUTES = 5
    RESET_TOKEN_LIFETIME_MINUTES = 10

    @staticmethod
    def hash_code(code: str) -> str:
        return hashlib.sha256(code.encode()).hexdigest()

    @classmethod
    def generate_code(cls) -> str:
        # secrets نه random — چون این یک security token هست، نه شبیه‌سازی
        return f"{secrets.randbelow(1000000):06d}"

    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    def is_locked(self) -> bool:
        return self.attempts >= self.MAX_ATTEMPTS