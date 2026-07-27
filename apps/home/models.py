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

from apps.shop.models import Category

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

    STATUS_CHOICES = (
        ('pending', 'در انتظار تایید'),
        ('approved', 'تایید شده'),
        ('rejected', 'رد شده'),
    )

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

    # ===== جایگزین is_approved =====
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        verbose_name="وضعیت"
    )
    rejection_reason = models.TextField(
        blank=True,
        verbose_name="دلیل رد شدن",
        help_text="در صورت رد شدن نظر، دلیل آن را وارد کنید"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخرین بروزرسانی")

    class Meta:
        verbose_name = "نظر"
        verbose_name_plural = "نظرات"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['article', 'status', 'parent']),
        ]

    def __str__(self):
        return f"نظر {self.user.fullname} - {self.article.title[:30]}"

    @property
    def is_reply(self):
        return self.parent is not None


# apps/home/models.py (افزودن به مدل‌های موجود)

class IndexPageSettings(models.Model):
    """تنظیمات صفحه اصلی"""

    # ===== SEO =====
    meta_title = models.CharField(
        max_length=60,
        blank=True,
        verbose_name="عنوان متا",
        help_text="عنوان صفحه در نتایج جستجو (حداکثر ۶۰ کاراکتر)"
    )
    meta_description = models.CharField(
        max_length=160,
        blank=True,
        verbose_name="توضیحات متا",
        help_text="توضیحات صفحه در نتایج جستجو (حداکثر ۱۶۰ کاراکتر)"
    )

    # ===== Hero =====
    hero_title_part1 = models.CharField(
        max_length=100,
        default='متفاوت',
        verbose_name="بخش اول عنوان هیرو"
    )
    hero_title_part2 = models.CharField(
        max_length=100,
        default='برقی',
        verbose_name="بخش دوم عنوان هیرو (رنگی)"
    )
    hero_title_part3 = models.CharField(
        max_length=100,
        default='برانید',
        verbose_name="بخش سوم عنوان هیرو"
    )
    hero_tag = models.CharField(
        max_length=200,
        default='آینده جابه‌جایی شهری',
        verbose_name="تگ هیرو"
    )
    hero_description = models.TextField(
        default='اسکوترهای برقی پریمیوم، طراحی‌شده برای کسانی که بیشتر می‌خواهند. ساخته‌شده با دقت، هدایت‌شده با عملکرد.',
        verbose_name="توضیحات هیرو"
    )
    hero_btn_text = models.CharField(
        max_length=100,
        default='مشاهده مجموعه',
        verbose_name="متن دکمه اصلی"
    )
    hero_btn_secondary_text = models.CharField(
        max_length=100,
        default='کاوش مدل‌ها',
        verbose_name="متن دکمه ثانویه"
    )

    # ===== Hero Image =====
    hero_image = models.ImageField(
        upload_to='home/index/hero/',
        verbose_name="تصویر هیرو",
        blank=True,
        null=True,
        help_text="تصویر اصلی هیرو (Desktop)\n📐 ابعاد: 1200 × 800 پیکسل\n📁 فرمت: WebP یا JPEG"
    )
    hero_mobile_image = models.ImageField(
        upload_to='home/index/hero/',
        verbose_name="تصویر هیرو موبایل",
        blank=True,
        null=True,
        help_text="تصویر هیرو برای موبایل\n📐 ابعاد: 600 × 400 پیکسل"
    )
    hero_image_alt = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="متن جایگزین تصویر هیرو"
    )

    # ===== Hero Stats (4 عدد) =====
    hero_stat_1_value = models.CharField(max_length=50, default='85', verbose_name="مقدار آمار ۱")
    hero_stat_1_unit = models.CharField(max_length=20, default='km/h',null=True , blank=True, verbose_name="واحد آمار ۱")
    hero_stat_1_label = models.CharField(max_length=50, default='حداکثر سرعت', verbose_name="برچسب آمار ۱")

    hero_stat_2_value = models.CharField(max_length=50, default='160', verbose_name="مقدار آمار ۲")
    hero_stat_2_unit = models.CharField(max_length=20, default='km', blank=True, verbose_name="واحد آمار ۲")
    hero_stat_2_label = models.CharField(max_length=50, default='برد', verbose_name="برچسب آمار ۲")

    hero_stat_3_value = models.CharField(max_length=50, default='2', verbose_name="مقدار آمار ۳")
    hero_stat_3_unit = models.CharField(max_length=20, default='hr', blank=True, verbose_name="واحد آمار ۳")
    hero_stat_3_label = models.CharField(max_length=50, default='زمان شارژ', verbose_name="برچسب آمار ۳")

    hero_stat_4_value = models.CharField(max_length=50, default='40k', verbose_name="مقدار آمار ۴")
    hero_stat_4_unit = models.CharField(max_length=20, default='+', blank=True, verbose_name="واحد آمار ۴")
    hero_stat_4_label = models.CharField(max_length=50, default='کاربران', verbose_name="برچسب آمار ۴")

    # ===== Best Sellers Section =====
    best_sellers_label = models.CharField(
        max_length=100,
        default='پرفروش‌ترین‌ها',
        verbose_name="برچسب بخش پرفروش‌ها"
    )
    best_sellers_title = models.CharField(
        max_length=200,
        default='برترین انتخاب‌های این فصل',
        verbose_name="عنوان بخش پرفروش‌ها"
    )

    # ===== Testimonials Section =====
    testimonials_label = models.CharField(
        max_length=100,
        default='نظرات',
        verbose_name="برچسب بخش نظرات"
    )
    testimonials_title = models.CharField(
        max_length=200,
        default='کاربران چه می‌گویند',
        verbose_name="عنوان بخش نظرات"
    )
    testimonials_rating = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default=4.9,
        verbose_name="میانگین امتیاز"
    )
    testimonials_count = models.CharField(
        max_length=50,
        default='40k',
        verbose_name="تعداد نظرات"
    )
    testimonials_count_label = models.CharField(
        max_length=100,
        default='کاربران راضی',
        verbose_name="برچسب تعداد نظرات"
    )

    # ===== Guide Section =====
    guide_label = models.CharField(
        max_length=100,
        default='منابع',
        verbose_name="برچسب بخش راهنما"
    )
    guide_title = models.CharField(
        max_length=200,
        default='راهنمای کامل خرید',
        verbose_name="عنوان بخش راهنما"
    )

    # ===== Final Section (Promise) =====
    promise_label = models.CharField(
        max_length=100,
        default='چرا VOLTEX',
        verbose_name="برچسب بخش تعهدات"
    )
    promise_title = models.CharField(
        max_length=200,
        default='تعهد VOLTEX',
        verbose_name="عنوان بخش تعهدات"
    )

    # ===== Final Section (Statement) =====
    statement_eyebrow = models.CharField(
        max_length=200,
        default='سفر شما از اینجا آغاز می‌شود',
        verbose_name="زیر عنوان بیانیه پایانی"
    )
    statement_title = models.CharField(
        max_length=200,
        default='امروز جلوتر برو',
        verbose_name="عنوان بیانیه پایانی"
    )
    statement_title_highlight = models.CharField(
        max_length=100,
        default='جلوتر',
        verbose_name="کلمه برجسته در بیانیه پایانی"
    )
    statement_description = models.TextField(
        default='به بیش از ۴۰,۰۰۰ راکب در سراسر اروپا بپیوندید که Voltex را انتخاب کرده‌اند. اسکوترهای پریمیوم، تحویل در ۲۴ ساعت، با ۳ سال گارانتی.',
        verbose_name="توضیحات بیانیه پایانی"
    )
    statement_btn_text = models.CharField(
        max_length=100,
        default='مشاهده همه مدل‌ها',
        verbose_name="متن دکمه اصلی بیانیه پایانی"
    )
    statement_btn_secondary_text = models.CharField(
        max_length=100,
        default='کاوش مجموعه‌ها',
        verbose_name="متن دکمه ثانویه بیانیه پایانی"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "تنظیمات صفحه اصلی"
        verbose_name_plural = "تنظیمات صفحه اصلی"

    def __str__(self):
        return "تنظیمات صفحه اصلی"

    def save(self, *args, **kwargs):
        # فقط یک رکورد وجود داشته باشد
        if not self.pk and IndexPageSettings.objects.exists():
            raise ValueError("تنها یک رکورد برای تنظیمات صفحه اصلی مجاز است.")
        super().save(*args, **kwargs)


class CategoryFeature(models.Model):
    """ویژگی‌های دسته‌بندی (spec-chip)"""
    CATEGORY_COLORS = [
        ('cyan', '#00f0ff'),
        ('orange', '#f97316'),
        ('red', '#ef4444'),
        ('yellow', '#fbbf24'),
        ('purple', '#a855f7'),
        ('green', '#22c55e'),
    ]

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='features'
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="آیکون",
        help_text="آیکون فونت‌آ‌وسم یا ایموجی"
    )
    value = models.CharField(max_length=100, verbose_name="مقدار")
    unit = models.CharField(max_length=50, null=True, blank=True)
    label = models.CharField(max_length=100, verbose_name="برچسب")
    color = models.CharField(
        max_length=20,
        choices=CATEGORY_COLORS,
        default='cyan',
        verbose_name="رنگ"
    )
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")

    class Meta:
        verbose_name = "ویژگی دسته‌بندی"
        verbose_name_plural = "ویژگی‌های دسته‌بندی"
        ordering = ['order']

    def __str__(self):
        return f"{self.category.name} - {self.label}"

    def get_color_hex(self):
        colors = dict(self.CATEGORY_COLORS)
        return colors.get(self.color, '#00f0ff')


class CategoryImage(models.Model):
    """تصویر دسته‌بندی"""
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(
        upload_to='categories/',
        verbose_name="تصویر"
    )
    alt_text = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="متن جایگزین"
    )
    is_primary = models.BooleanField(
        default=True,
        verbose_name="تصویر اصلی"
    )
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب")

    class Meta:
        verbose_name = "تصویر دسته‌بندی"
        verbose_name_plural = "تصاویر دسته‌بندی"
        ordering = ['order']

    def __str__(self):
        return f"{self.category.name} - {self.order}"


class CategoryBadge(models.Model):
    """نشان دسته‌بندی (cat-pill)"""
    CATEGORY_COLORS = [
        ('cyan', '#00f0ff'),
        ('orange', '#f97316'),
        ('red', '#ef4444'),
        ('yellow', '#fbbf24'),
        ('purple', '#a855f7'),
        ('green', '#22c55e'),
    ]

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='badges'
    )
    label = models.CharField(max_length=100, verbose_name="برچسب")
    badge_text = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="متن نشان"
    )
    color = models.CharField(
        max_length=20,
        choices=CATEGORY_COLORS,
        default='cyan',
        verbose_name="رنگ"
    )
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب")

    class Meta:
        verbose_name = "نشان دسته‌بندی"
        verbose_name_plural = "نشان‌های دسته‌بندی"
        ordering = ['order']

    def __str__(self):
        return f"{self.category.name} - {self.label}"

    def get_color_hex(self):
        colors = dict(self.CATEGORY_COLORS)
        return colors.get(self.color, '#00f0ff')


class ProductCard(models.Model):
    """کارت محصولات در بخش پرفروش‌ها"""
    PRODUCT_COLORS = [
        ('neon', '#4fd8ff'),
        ('orange', '#ff9a3c'),
        ('green', '#a8e063'),
        ('neon2', '#8b7bff'),
        ('neon3', '#ff6cc4'),
    ]

    product = models.ForeignKey(
        'shop.Product',
        on_delete=models.CASCADE,
        related_name='index_cards'
    )
    badge_text = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="متن نشان"
    )
    color = models.CharField(
        max_length=20,
        choices=PRODUCT_COLORS,
        default='neon',
        verbose_name="رنگ تم"
    )
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        verbose_name = "کارت محصول"
        verbose_name_plural = "کارت‌های محصول"
        ordering = ['order']

    def __str__(self):
        return f"{self.product.name}"


class Testimonial(models.Model):
    """نظرات در صفحه اصلی"""
    COLORS = [
        ('neon', '#4fd8ff'),
        ('orange', '#ff9a3c'),
        ('green', '#a8e063'),
        ('neon2', '#8b7bff'),
        ('neon3', '#ff6cc4'),
    ]
    name = models.CharField(max_length=100, verbose_name="نام")
    quote = models.TextField(verbose_name="متن نظر")
    rating = models.PositiveSmallIntegerField(
        default=5,
        choices=[(1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5')],
        verbose_name="امتیاز"
    )
    avatar_color_start = models.CharField(
        max_length=20,
        choices=COLORS,
        default='neon',
        verbose_name="رنگ شروع آواتار"
    )
    avatar_color_end = models.CharField(
        max_length=20,
        choices=COLORS,
        default='neon2',
        verbose_name="رنگ پایان آواتار"
    )

    def get_color_hex(self, color_key):
        colors = dict(self.COLORS)
        return colors.get(color_key, '#4fd8ff')

    avatar_image = models.ImageField(
        upload_to='home/testimonials/avatars/',
        verbose_name="عکس پروفایل",
        blank=True,
        null=True,
        help_text="ابعاد پیشنهادی: 200×200 پیکسل، مربع"
    )

    avatar_initials = models.CharField(
        max_length=5,
        blank=True,
        verbose_name="حروف اول (اگر خالی باشد از نام گرفته می‌شود)"
    )
    is_featured = models.BooleanField(default=False, verbose_name="نظر ویژه")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        verbose_name = "نظر"
        verbose_name_plural = "نظرات صفحه اصلی"
        ordering = ['order']

    def __str__(self):
        return f"{self.name} - {'★' * self.rating}"

    def get_initials(self):
        if self.avatar_initials:
            return self.avatar_initials
        return ''.join([word[0].upper() for word in self.name.split()[:2]])


class Promise(models.Model):
    """تعهدات VOLTEX در بخش پایانی"""
    PROMISE_COLORS = [
        ('neon', '#4fd8ff'),
        ('orange', '#ff9a3c'),
        ('green', '#a8e063'),
        ('neon2', '#8b7bff'),
        ('neon3', '#ff6cc4'),
    ]

    icon_svg = models.TextField(
        blank=True,
        verbose_name="SVG آیکون",
        help_text="کد SVG آیکون"
    )
    label = models.CharField(max_length=50, verbose_name="برچسب")
    title = models.CharField(max_length=100, verbose_name="عنوان")
    description = models.CharField(max_length=200, verbose_name="توضیحات")
    badge_value = models.CharField(max_length=50, verbose_name="مقدار نشان")
    badge_unit = models.CharField(max_length=20, blank=True, verbose_name="واحد نشان")
    color = models.CharField(
        max_length=20,
        choices=PROMISE_COLORS,
        default='neon',
        verbose_name="رنگ"
    )
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        verbose_name = "تعهد"
        verbose_name_plural = "تعهدات"
        ordering = ['order']

    def __str__(self):
        return self.title
