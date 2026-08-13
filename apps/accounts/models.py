# accounts/models.py

import hashlib
import os
import secrets

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinLengthValidator, RegexValidator
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
    mobile = models.CharField(max_length=11, unique=True, blank=True, null=True, verbose_name="شماره موبایل")
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

    national_code = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        validators=[MinLengthValidator(10)],
        verbose_name="کد ملی"
    )
    birth_date = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name="تاریخ تولد"
    )
    gender = models.CharField(
        max_length=10,
        choices=[
            ('male', 'مرد'),
            ('female', 'زن'),
            ('none', 'ترجیح می‌دهم نگویم')
        ],
        default='none',
        verbose_name="جنسیت"
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


class Province(models.Model):
    """استان"""
    name = models.CharField(max_length=100, unique=True, verbose_name="نام استان")

    class Meta:
        verbose_name = "استان"
        verbose_name_plural = "استان‌ها"
        ordering = ['name']

    def __str__(self):
        return self.name


class City(models.Model):
    """شهر"""
    province = models.ForeignKey(
        Province,
        on_delete=models.CASCADE,
        related_name='cities',
        verbose_name="استان"
    )
    name = models.CharField(max_length=100, verbose_name="نام شهر")

    class Meta:
        verbose_name = "شهر"
        verbose_name_plural = "شهرها"
        ordering = ['name']
        unique_together = ['province', 'name']

    def __str__(self):
        return f"{self.name} ({self.province.name})"


class Address(models.Model):
    """آدرس کاربر"""
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='addresses',
        verbose_name="کاربر"
    )
    recipient_name = models.CharField(max_length=100, verbose_name="نام گیرنده")
    recipient_phone = models.CharField(
        max_length=11,
        validators=[RegexValidator(r'^09\d{9}$', 'شماره موبایل معتبر نیست')],
        verbose_name="شماره موبایل گیرنده"
    )
    province = models.ForeignKey(
        Province,
        on_delete=models.PROTECT,
        verbose_name="استان"
    )
    city = models.ForeignKey(
        City,
        on_delete=models.PROTECT,
        verbose_name="شهر"
    )
    address = models.TextField(verbose_name="آدرس کامل")
    postal_code = models.CharField(
        max_length=10,
        validators=[MinLengthValidator(10)],
        verbose_name="کد پستی"
    )
    plaque = models.CharField(max_length=20, verbose_name="پلاک")
    unit = models.CharField(max_length=20, blank=True, verbose_name="واحد")
    floor = models.CharField(max_length=20, blank=True, verbose_name="طبقه")
    description = models.TextField(blank=True, verbose_name="توضیحات اضافی")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "آدرس"
        verbose_name_plural = "آدرس‌ها"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.recipient_name} - {self.city.name}"