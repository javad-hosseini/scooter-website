# accounts/models.py

import os
import secrets

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinLengthValidator, RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.text import slugify


#: Mirrors ALLOWED_AVATAR_EXTENSIONS in apps/accounts/views.py. The stored
#: extension decides the Content-Type the web server hands back, so it is
#: pinned to this set rather than taken from the uploaded filename.
ALLOWED_IMAGE_EXTENSIONS = ('jpg', 'jpeg', 'png', 'webp', 'gif')


def user_profile_image_path(instance, filename):
    """مسیر ذخیره عکس پروفایل کاربر"""
    ext = os.path.splitext(filename or '')[1].lstrip('.').lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        ext = 'jpg'
    # استفاده از username برای نام فایل
    stem = slugify(instance.username, allow_unicode=False) or 'user'
    filename = f"{stem}-{timezone.now().strftime('%Y%m%d%H%M%S')}.{ext}"
    return os.path.join('users/profiles/', filename)


#: Display names are echoed next to every comment and review. Escaping at the
#: render sites is the real defence; this keeps markup characters out of the
#: column in the first place so a future unescaped sink cannot be fed from here.
#: Allows Persian/Arabic and Latin letters, digits, spaces and name punctuation.
FULLNAME_VALIDATOR = RegexValidator(
    r"^[\w\s؀-ۿ‌.'\-]+$",
    'نام فقط می‌تواند شامل حروف، عدد، فاصله و نشانه‌های . - باشد',
)


class CustomUser(AbstractUser):
    fullname = models.CharField(
        max_length=100,
        validators=[FULLNAME_VALIDATOR],
        verbose_name="نام کامل",
    )
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
    # The reset-token window runs from verification, not from OTP creation —
    # measuring from created_at silently shortened it by however long the user
    # took to enter the code.
    verified_at = models.DateTimeField(null=True, blank=True)

    MAX_ATTEMPTS = 5
    OTP_LIFETIME_MINUTES = 5
    RESET_TOKEN_LIFETIME_MINUTES = 10

    @staticmethod
    def hash_code(code: str) -> str:
        """Salted HMAC of an OTP or reset token.

        Keyed on SECRET_KEY so the stored digests are not a plain SHA-256 of a
        six-digit number, which is trivially reversible by enumeration if the
        table ever leaks.
        """
        # algorithm='sha256' explicitly: salted_hmac defaults to SHA-1, whose
        # 40-char digest would also silently change the stored width.
        return salted_hmac(
            'accounts.PasswordResetOTP', code, algorithm='sha256'
        ).hexdigest()

    @staticmethod
    def matches(stored: str, candidate: str) -> bool:
        """Constant-time comparison of a stored digest against a candidate."""
        if not stored:
            return False
        return constant_time_compare(stored, PasswordResetOTP.hash_code(candidate))

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