# home/models.py

import time
import uuid

from ckeditor.fields import RichTextField
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone as django_timezone
from django.utils.text import slugify

ALLOWED_ATTACHMENT_EXTENSIONS = ['png', 'jpg', 'jpeg', 'webp', 'mp4', 'mp3', 'pdf']
MAX_ATTACHMENT_SIZE_MB = 25


def validate_attachment_size(file):
    limit_bytes = MAX_ATTACHMENT_SIZE_MB * 1024 * 1024
    if file.size > limit_bytes:
        raise ValidationError(f'حجم فایل نباید بیشتر از {MAX_ATTACHMENT_SIZE_MB} مگابایت باشد')


def validate_attachment_content(file):
    """
    چک واقعی محتوای فایل با magic bytes، نه فقط اعتماد به پسوند/content-type.
    Content-Type از کلاینت میاد و به‌راحتی spoof میشه؛ این تابع فایل رو واقعاً می‌خونه.
    """
    import filetype  # pip install filetype --break-system-packages

    file.seek(0)
    kind = filetype.guess(file.read(261))  # فقط header اول فایل کافیه
    file.seek(0)  # مهم: pointer رو برگردون، وگرنه save بعدی فایل خالی ذخیره می‌کنه

    if kind is None:
        raise ValidationError('نوع فایل قابل تشخیص نیست یا فایل خراب است')

    allowed_mimes = {
        'image/png', 'image/jpeg', 'image/webp',
        'video/mp4', 'audio/mpeg', 'application/pdf',
    }
    if kind.mime not in allowed_mimes:
        raise ValidationError(f'نوع فایل مجاز نیست: {kind.mime}')


def article_attachment_upload_path(instance, filename):
    # اسم فایل رو خودمون می‌سازیم، نه از ورودی کاربر - جلوی path traversal رو می‌گیره
    ext = filename.rsplit('.', 1)[-1].lower()
    return f'articles/{instance.created_at.year if instance.created_at and hasattr(instance.created_at, "year") else "misc"}/{uuid.uuid4().hex}.{ext}'


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True, allow_unicode=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)


class Article(models.Model):
    # ========== فیلدهای اصلی ==========
    title = models.CharField(max_length=255, verbose_name="عنوان مقاله")
    slug = models.SlugField(max_length=280, unique=True, allow_unicode=True, db_index=True, verbose_name="اسلاگ")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='articles',
        verbose_name="نویسنده"
    )
    tags = models.ManyToManyField(Tag, related_name='articles', blank=True, verbose_name="برچسب‌ها")

    # ========== محتوا ==========
    description = RichTextField(verbose_name="محتوا")

    # ========== خلاصه مقاله (برای meta description) ==========
    excerpt = models.TextField(
        max_length=300,
        verbose_name="خلاصه",
        blank=True,
        help_text="خلاصه‌ای از مقاله که در کارت‌ها و متا دیسکریپشن نمایش داده می‌شود. اگر خالی باشد، از ۱۵۰ کاراکتر اول description استفاده می‌شود."
    )

    # ========== تصویر شاخص (کاور) ==========
    cover_image = models.ImageField(
        upload_to='home/articles/',
        verbose_name="تصویر کاور",
        blank=True,
        null=True,
        help_text="تصویر اصلی مقاله که در هدر و کارت‌ها نمایش داده می‌شود.\n📐 ابعاد: 1200 × 630 پیکسل (نسبت 1.91:1)\n📁 فرمت: WebP (بهترین) یا JPEG\n📦 حجم: حداکثر 200 کیلوبایت\n🖥️ رزولوشن: 72 DPI (مناسب برای وب)"
    )
    cover_alt_text = models.CharField(
        max_length=200,
        verbose_name="متن جایگزین تصویر",
        blank=True,
        help_text="برای سئو و دسترسی‌پذیری"
    )

    # ========== فایل پیوست (برای ویدیو/صوت/PDF) ==========
    attachment = models.FileField(
        upload_to=article_attachment_upload_path,
        validators=[
            FileExtensionValidator(allowed_extensions=ALLOWED_ATTACHMENT_EXTENSIONS),
            validate_attachment_size,
            validate_attachment_content,
        ],
        blank=True,
        null=True,
        help_text='فرمت‌های مجاز: png, jpg, webp, mp4, mp3, pdf — حداکثر ۲۵ مگابایت'
    )

    # ========== زمان مطالعه ==========
    time_to_read = models.PositiveSmallIntegerField(
        verbose_name="زمان مطالعه (دقیقه)",
        blank=True,
        null=True,
        help_text="اگر خالی باشد، به‌طور خودکار از روی محتوا محاسبه می‌شود"
    )

    # ========== متادیتا برای سئو ==========
    meta_description = models.CharField(
        max_length=160,
        verbose_name="متا دیسکریپشن",
        blank=True,
        help_text="اگر خالی باشد، از excerpt استفاده می‌شود"
    )
    meta_keywords = models.CharField(
        max_length=200,
        verbose_name="کلمات کلیدی",
        blank=True,
        help_text="با کاما جدا کنید"
    )
    canonical_url = models.URLField(
        verbose_name="لینک کنونیکال",
        blank=True,
        help_text="اگر خالی باشد، لینک خود مقاله استفاده می‌شود"
    )

    # ========== وضعیت و زمان‌بندی ==========
    is_published = models.BooleanField(default=True, db_index=True, verbose_name="منتشر شده")
    published_at = models.DateTimeField(
        verbose_name="زمان انتشار",
        blank=True,
        null=True,
        help_text="اگر خالی باشد و is_published=True باشد، زمان ایجاد استفاده می‌شود"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخرین بروزرسانی")

    # ========== آمار ==========
    view_count = models.PositiveIntegerField(default=0, verbose_name="تعداد بازدید")

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at', 'is_published']),
            models.Index(fields=['slug']),
            models.Index(fields=['is_published', '-published_at']),
        ]
        verbose_name = "مقاله"
        verbose_name_plural = "مقالات"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # ===== تولید اسلاگ =====
        if not self.slug:
            self.slug = slugify(self.title, allow_unicode=True)
            if not self.slug:
                self.slug = f"article-{int(time.time())}"

        # ===== تنظیم زمان انتشار =====
        if self.is_published and not self.published_at:
            self.published_at = django_timezone.now()

        # ===== تولید خلاصه اگر خالی باشد =====
        if not self.excerpt and self.description:
            # حذف تگ‌های HTML از description
            from django.utils.html import strip_tags
            plain_text = strip_tags(self.description)
            self.excerpt = plain_text[:297] + '...' if len(plain_text) > 300 else plain_text

        # ===== تولید متا دیسکریپشن اگر خالی باشد =====
        if not self.meta_description and self.excerpt:
            self.meta_description = self.excerpt[:155]

        # ===== محاسبه زمان مطالعه =====
        if not self.time_to_read and self.description:
            from django.utils.html import strip_tags
            plain_text = strip_tags(self.description)
            word_count = len(plain_text.strip().split())
            # حدود ۲۰۰ کلمه در دقیقه
            self.time_to_read = max(1, round(word_count / 200))

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('home:article_detail', kwargs={'slug': self.slug})

    @property
    def attachment_type(self):
        """برای frontend که بدونه با <img>، <video> یا <audio> رندر کنه"""
        if not self.attachment:
            return None
        ext = self.attachment.name.rsplit('.', 1)[-1].lower() if self.attachment else ''
        if ext in ('png', 'jpg', 'jpeg', 'webp'):
            return 'image'
        elif ext == 'mp4':
            return 'video'
        elif ext == 'mp3':
            return 'audio'
        elif ext == 'pdf':
            return 'pdf'
        return 'unknown'

    @property
    def og_image(self):
        """برای Open Graph از تصویر کاور استفاده می‌شود"""
        if self.cover_image:
            return self.cover_image.url
        return None


# home/models.py (ادامه)

class Comment(models.Model):
    """نظرات مقالات"""
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name="مقاله"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='article_comments',
        verbose_name="کاربر"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies',
        verbose_name="پاسخ به"
    )
    content = models.TextField(verbose_name="متن نظر")
    is_approved = models.BooleanField(default=True, verbose_name="تایید شده")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخرین بروزرسانی")

    class Meta:
        verbose_name = "نظر"
        verbose_name_plural = "نظرات"
        ordering = ['-created_at']

    def __str__(self):
        return f"نظر {self.user.fullname} - {self.article.title[:30]}"

    @property
    def is_reply(self):
        return self.parent is not None
