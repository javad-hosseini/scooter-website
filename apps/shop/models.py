# apps/shop/models.py
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import CustomUser, Address

User = get_user_model()


class Category(models.Model):
    """دسته‌بندی محصولات"""
    name = models.CharField(max_length=100, verbose_name="نام دسته‌بندی")
    slug = models.SlugField(max_length=120, unique=True, verbose_name="اسلاگ")
    icon = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="آیکون",
        help_text="آیکون فونت‌آ‌وسم یا ایموجی"
    )
    description = models.TextField(blank=True, verbose_name="توضیحات")
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="دسته‌بندی والد"
    )
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    # ===== SEO =====
    meta_title = models.CharField(
        max_length=60,
        blank=True,
        verbose_name="عنوان متا",
        help_text="حداکثر ۶۰ کاراکتر. اگر خالی باشد از نام دسته‌بندی ساخته می‌شود."
    )
    meta_description = models.CharField(
        max_length=160,
        blank=True,
        verbose_name="توضیحات متا",
        help_text="حداکثر ۱۶۰ کاراکتر. اگر خالی باشد از توضیحات دسته‌بندی ساخته می‌شود."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "دسته‌بندی"
        verbose_name_plural = "دسته‌بندی‌ها"
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('shop:category_products', kwargs={'slug': self.slug})


class ProductSpec(models.Model):
    """ویژگی‌های محصول (برای بخش hero-specs)"""
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='specs'
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="آیکون",
        help_text="آیکون فونت‌آ‌وسم یا ایموجی"
    )
    value = models.CharField(max_length=100, verbose_name="مقدار")
    label = models.CharField(max_length=100, verbose_name="برچسب")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")

    class Meta:
        verbose_name = "ویژگی محصول"
        verbose_name_plural = "ویژگی‌های محصول"
        ordering = ['order']

    def __str__(self):
        return f"{self.label}: {self.value}"


class TrustBadge(models.Model):
    """نشان‌های اعتماد (بخش trust-row)"""
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='trust_badges'
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="آیکون",
        help_text="آیکون فونت‌آ‌وسم یا ایموجی"
    )
    label = models.CharField(max_length=100, verbose_name="برچسب")
    value = models.CharField(max_length=100, blank=True, verbose_name="مقدار")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")

    class Meta:
        verbose_name = "نشان اعتماد"
        verbose_name_plural = "نشان‌های اعتماد"
        ordering = ['order']

    def __str__(self):
        return self.label


class MarketingFeature(models.Model):
    """ویژگی‌های بازاریابی (بخش marketing)"""
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='marketing_features'
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="آیکون",
        help_text="آیکون فونت‌آ‌وسم یا ایموجی"
    )
    title = models.CharField(max_length=200, verbose_name="عنوان")
    description = models.TextField(verbose_name="توضیحات")
    accent = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="آیکون پس‌زمینه"
    )
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")

    class Meta:
        verbose_name = "ویژگی بازاریابی"
        verbose_name_plural = "ویژگی‌های بازاریابی"
        ordering = ['order']

    def __str__(self):
        return self.title


class StatFeature(models.Model):
    """آمارهای محصول (بخش stats-row)"""
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='stat_features'
    )
    number = models.CharField(max_length=50, verbose_name="عدد/مقدار")
    suffix = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="پسوند",
        help_text="مثلاً: +, km, W, سال"
    )
    label = models.CharField(max_length=100, verbose_name="برچسب")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")

    class Meta:
        verbose_name = "آمار محصول"
        verbose_name_plural = "آمارهای محصول"
        ordering = ['order']

    def __str__(self):
        return self.label


class ProductImage(models.Model):
    """تصاویر محصول با رنگ‌بندی"""
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(
        upload_to='products/gallery/',
        verbose_name="تصویر",
        width_field='image_width',
        height_field='image_height',
    )
    # Cached intrinsic dimensions. Without them the template cannot emit
    # width/height attributes without opening every file with Pillow on each
    # render, and missing attributes are the main source of layout shift.
    image_width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    image_height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    color_slug = models.SlugField(
        max_length=50,
        verbose_name="اسلاگ رنگ",
        help_text="مثلاً: red, white, black, blue"
    )
    color_label = models.CharField(
        max_length=50,
        verbose_name="نام رنگ",
        help_text="مثلاً: قرمز, سفید, مشکی, آبی"
    )
    color_hex = models.CharField(
        max_length=7,
        verbose_name="کد رنگ (Hex)",
        help_text="مثلاً: #D6483C",
        default='#FFFFFF'
    )
    alt_text = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="متن جایگزین"
    )
    sort_order = models.PositiveIntegerField(default=0, verbose_name="ترتیب")
    is_primary = models.BooleanField(default=False, verbose_name="تصویر اصلی")

    class Meta:
        verbose_name = "تصویر محصول"
        verbose_name_plural = "تصاویر محصول"
        ordering = ['sort_order']

    def __str__(self):
        return f"{self.product.name} - {self.color_label}"


class ProductReview(models.Model):
    """نظرات محصولات"""
    STATUS_CHOICES = (
        ('pending', 'در انتظار تایید'),
        ('approved', 'تایید شده'),
        ('rejected', 'رد شده'),
    )

    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='product_reviews'
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="امتیاز"
    )
    title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="عنوان نظر"
    )
    comment = models.TextField(verbose_name="متن نظر")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="وضعیت"
    )
    rejection_reason = models.TextField(
        blank=True,
        verbose_name="دلیل رد شدن",
        help_text="در صورت رد شدن نظر، دلیل آن را وارد کنید"
    )
    helpful_count = models.PositiveIntegerField(default=0, verbose_name="تعداد مفید بودن")
    is_verified_purchase = models.BooleanField(default=False, verbose_name="خرید تایید شده")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "نظر محصول"
        verbose_name_plural = "نظرات محصولات"
        ordering  = ['-created_at']

    def __str__(self):
        return f"{self.user.fullname} - {self.product.name} ({self.rating}★)"


class Wishlist(models.Model):
    """لیست علاقه‌مندی‌ها"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='wishlist'
    )
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='wishlisted_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "علاقه‌مندی"
        verbose_name_plural = "علاقه‌مندی‌ها"
        unique_together = ['user', 'product']

    def __str__(self):
        return f"{self.user.fullname} - {self.product.name}"


class ProductQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True)

    def with_ratings(self):
        """Annotate approved-review count/average in one pass.

        Product cards show a star rating, so without this every card on a
        listing page triggers its own COUNT and AVG — the single biggest
        contributor to slow TTFB on category pages.
        """
        approved = models.Q(reviews__status='approved')
        return self.annotate(
            approved_review_count=models.Count(
                'reviews', filter=approved, distinct=True
            ),
            approved_review_average=models.Avg('reviews__rating', filter=approved),
        )

    def for_listing(self):
        """Everything a product card renders, with no N+1 left behind."""
        return (
            self.published()
            .filter(is_discontinued=False)
            .select_related('category')
            .with_ratings()
            # Explicit and total. annotate() drops the model's default
            # ordering, and an unordered queryset makes pagination
            # non-deterministic — the same product can appear on page 1 and
            # page 2, or on neither, across two crawls of the same listing.
            .order_by('-is_featured', '-created_at', 'pk')
        )

    def for_detail(self):
        return (
            self.published()
            .select_related('category', 'category__parent')
            .prefetch_related('specs', 'trust_badges', 'marketing_features',
                              'stat_features', 'images')
            .with_ratings()
        )


class Product(models.Model):
    """مدل اصلی محصول"""
    objects = ProductQuerySet.as_manager()

    # اطلاعات پایه
    name = models.CharField(max_length=255, verbose_name="نام محصول")
    slug = models.SlugField(max_length=280, unique=True, allow_unicode=True, verbose_name="اسلاگ")
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
        verbose_name="دسته‌بندی"
    )

    # محتوا
    tagline = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="شعار",
        help_text="یک عبارت کوتاه برای نمایش در هدر"
    )
    description = models.TextField(verbose_name="توضیحات")

    # تصویر اصلی (کاور)
    cover_image = models.ImageField(
        upload_to='products/covers/',
        verbose_name="تصویر کاور",
        help_text="تصویر اصلی محصول که در هدر نمایش داده می‌شود",
        width_field='cover_image_width',
        height_field='cover_image_height',
    )
    cover_image_width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    cover_image_height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    cover_alt_text = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="متن جایگزین تصویر کاور",
        help_text="برای سئوی تصویر و دسترسی‌پذیری. اگر خالی باشد از نام محصول ساخته می‌شود."
    )
    grid_image = models.ImageField(
        upload_to='products/grid/',
        blank=True,
        null=True,
        verbose_name="تصویر گرید",
        help_text="تصویری که در کارت محصول داخل صفحه‌ی دسته‌بندی نمایش داده می‌شود. اگر خالی بماند، از تصویر کاور استفاده می‌شود."
    )

    # قیمت
    price = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        verbose_name="قیمت (تومان)"
    )
    discount_price = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        blank=True,
        null=True,
        verbose_name="قیمت با تخفیف"
    )
    cost_price = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=0,
        verbose_name="قیمت تمام‌شده",
        help_text="هزینه‌ی خرید/تولید محصول — برای محاسبه‌ی سود خالص استفاده می‌شود و به مشتری نمایش داده نمی‌شود"
    )

    # موجودی
    stock = models.PositiveIntegerField(default=0, verbose_name="موجودی")
    stock_out_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="تاریخ اتمام موجودی"
    )
    is_available = models.BooleanField(default=True, verbose_name="موجود")
    restock_expected = models.BooleanField(
        default=True,
        verbose_name="به‌زودی شارژ می‌شود",
        help_text="اگر تیک بخورد، صفحه‌ی محصول ناموجود زنده و ایندکس‌شده می‌ماند."
    )
    is_discontinued = models.BooleanField(
        default=False,
        verbose_name="تولید متوقف شده",
        help_text=(
            "محصولی که دیگر تولید/فروخته نمی‌شود. صفحه با ریدایرکت ۳۰۱ به محصول "
            "جایگزین یا به دسته‌بندی والد منتقل می‌شود تا ارزش لینک‌ها از بین نرود."
        )
    )
    replacement_product = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replaces',
        verbose_name="محصول جایگزین",
        help_text="مقصد ریدایرکت ۳۰۱ برای محصول متوقف‌شده. اگر خالی باشد به دسته‌بندی می‌رود."
    )

    # وضعیت
    is_published = models.BooleanField(default=True, verbose_name="منتشر شده")
    is_featured = models.BooleanField(default=False, verbose_name="ویژه")

    # شناسه‌های کالا (برای Product schema و گوگل شاپینگ)
    sku = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        verbose_name="کد کالا (SKU)",
        help_text="اگر خالی باشد به‌صورت خودکار ساخته می‌شود."
    )
    brand = models.CharField(
        max_length=100,
        blank=True,
        default='NeX Go',
        verbose_name="برند"
    )
    mpn = models.CharField(
        max_length=64,
        blank=True,
        verbose_name="شماره قطعه سازنده (MPN)"
    )

    # متادیتا
    meta_title = models.CharField(
        max_length=60,
        blank=True,
        verbose_name="عنوان متا",
        help_text="حداکثر ۶۰ کاراکتر. اگر خالی باشد از نام محصول ساخته می‌شود."
    )
    meta_description = models.CharField(
        max_length=160,
        blank=True,
        verbose_name="توضیحات متا",
        help_text="حداکثر ۱۶۰ کاراکتر. اگر خالی باشد از توضیحات محصول ساخته می‌شود."
    )

    # آمار
    view_count = models.PositiveIntegerField(default=0, verbose_name="تعداد بازدید")

    # زمان
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "محصول"
        verbose_name_plural = "محصولات"
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        if not self.cover_alt_text:
            # Never ship an empty alt on the product's primary image.
            self.cover_alt_text = f'{self.name} — اسکوتر برقی {self.brand or "نکس گو"}'
        super().save(*args, **kwargs)
        if not self.sku:
            # Needs the PK, so it has to happen after the first insert.
            type(self).objects.filter(pk=self.pk).update(sku=f'NXG-{self.pk:05d}')
            self.sku = f'NXG-{self.pk:05d}'

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('shop:product_detail', kwargs={'slug': self.slug})

    @property
    def seo_title(self):
        return self.meta_title or self.name

    @property
    def is_in_stock(self):
        return self.is_available and self.stock > 0 and not self.is_discontinued

    @property
    def final_price(self):
        """قیمت نهایی با احتساب تخفیف"""
        return self.discount_price if self.discount_price else self.price

    @property
    def formatted_price(self):
        """قیمت اصلی با جداکننده سه رقمی"""
        return f"{int(self.price):,}" if self.price is not None else "0"

    @property
    def formatted_final_price(self):
        """قیمت نهایی با جداکننده سه رقمی"""
        return f"{int(self.final_price):,}" if self.final_price is not None else "0"

    @property
    def formatted_discount_price(self):
        """قیمت با تخفیف با جداکننده سه رقمی"""
        return f"{int(self.discount_price):,}" if self.discount_price is not None else ""

    @property
    def average_rating(self):
        """میانگین امتیازات تایید شده

        Uses the ``approved_review_average`` annotation added by
        ``Product.objects.with_ratings()`` when it is present. Without it a
        listing page would fire two extra queries per product.
        """
        annotated = getattr(self, 'approved_review_average', None)
        if annotated is not None:
            return round(annotated, 1) if annotated else 0
        result = self.reviews.filter(status='approved').aggregate(
            avg=models.Avg('rating')
        )['avg']
        return round(result, 1) if result else 0

    @property
    def reviews_count(self):
        """تعداد نظرات تایید شده"""
        annotated = getattr(self, 'approved_review_count', None)
        if annotated is not None:
            return annotated
        return self.reviews.filter(status='approved').count()

    @property
    def rating_distribution(self):
        """توزیع امتیازات"""
        distribution = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
        approved = self.reviews.filter(status='approved')
        if approved.exists():
            for rating in range(1, 6):
                distribution[rating] = approved.filter(rating=rating).count()
        return distribution

    def profit_margin(self):
        """حاشیه سود = (قیمت فروش - قیمت خرید) / قیمت فروش"""
        if self.price and self.cost_price:
            return round(((self.price - self.cost_price) / self.price) * 100, 1)
        return 0

    def send_stock_alert(self):
        """ارسال هشدار به ادمین وقتی موجودی کمه"""
        if self.stock <= 2:
            print(f"هشدار: موجودی {self.name} کم است ({self.stock} عدد)")


# apps/shop/models.py

class CategoryHeroProduct(models.Model):
    """محصولات نمایش داده شده در هیرو اسلایدر هر کتگوری"""
    category = models.ForeignKey(
        'Category',
        on_delete=models.CASCADE,
        related_name='hero_products'
    )
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='hero_slides'
    )
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")

    class Meta:
        verbose_name = "محصول اسلایدر"
        verbose_name_plural = "محصولات اسلایدر"
        ordering = ['order']
        unique_together = ['category', 'product']

    def __str__(self):
        return f"{self.category.name} - {self.product.name}"


class Coupon(models.Model):
    """کد تخفیف درصدی که مدیر از پنل ادمین تعریف می‌کند.

    اعتبارسنجی در دو نقطه انجام می‌شود: وقتی کاربر کد را در سبد خرید وارد
    می‌کند و دوباره موقع ثبت سفارش. دلیل تکرار این است که مبلغ سبد خرید و
    وضعیت کوپن بین این دو لحظه تغییر می‌کند و مقدار ذخیره‌شده روی سبد خرید
    نباید به‌تنهایی مبنای مبلغ پرداختی باشد.
    """

    code = models.CharField(
        max_length=32,
        unique=True,
        verbose_name="کد تخفیف",
        help_text="کاربر همین کد را در سبد خرید وارد می‌کند. بزرگی و کوچکی حروف مهم نیست."
    )
    percentage = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name="درصد تخفیف",
        help_text="عددی بین ۱ تا ۱۰۰"
    )
    max_discount_amount = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        null=True,
        blank=True,
        verbose_name="سقف مبلغ تخفیف",
        help_text="بیشترین تخفیفی که این کد می‌دهد (تومان). خالی یعنی بدون سقف."
    )
    min_order_amount = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=0,
        verbose_name="حداقل مبلغ سبد خرید",
        help_text="اگر مبلغ سبد خرید کمتر از این باشد کد پذیرفته نمی‌شود. صفر یعنی بدون محدودیت."
    )
    valid_from = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="شروع اعتبار",
        help_text="خالی یعنی از همین حالا معتبر است."
    )
    valid_until = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="پایان اعتبار",
        help_text="خالی یعنی تاریخ انقضا ندارد."
    )
    usage_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="سقف کل دفعات استفاده",
        help_text="مجموع دفعاتی که همه‌ی کاربران می‌توانند از این کد استفاده کنند. خالی یعنی نامحدود."
    )
    usage_limit_per_user = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="سقف استفاده برای هر کاربر",
        help_text="مثلاً ۱ یعنی هر کاربر فقط یک‌بار. خالی یعنی نامحدود."
    )
    used_count = models.PositiveIntegerField(
        default=0,
        editable=False,
        verbose_name="دفعات استفاده‌شده"
    )
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "کد تخفیف"
        verbose_name_plural = "کدهای تخفیف"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} ({self.percentage}%)"

    def save(self, *args, **kwargs):
        # کد یکتاست، پس باید یک شکل استاندارد داشته باشد؛ وگرنه «volt10» و
        # «VOLT10» دو ردیف جدا می‌شوند و کاربر بسته به شکل تایپش نتیجه‌ی
        # متفاوتی می‌گیرد.
        self.code = (self.code or '').strip().upper()
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return bool(self.valid_until and timezone.now() > self.valid_until)

    @property
    def has_started(self):
        return not self.valid_from or timezone.now() >= self.valid_from

    @property
    def is_exhausted(self):
        return bool(self.usage_limit is not None and self.used_count >= self.usage_limit)

    @property
    def remaining_uses(self):
        if self.usage_limit is None:
            return None
        return max(0, self.usage_limit - self.used_count)

    def times_used_by(self, user):
        """چند سفارش ثبت‌شده‌ی این کاربر با این کد بوده است."""
        if user is None or not getattr(user, 'is_authenticated', False):
            return 0
        return self.orders.filter(user=user).count()

    def error_for(self, user, amount):
        """اگر کد برای این کاربر و این مبلغ قابل استفاده نیست، پیام خطا را برمی‌گرداند."""
        if not self.is_active:
            return 'این کد تخفیف فعال نیست'
        if not self.has_started:
            return 'زمان استفاده از این کد تخفیف هنوز نرسیده است'
        if self.is_expired:
            return 'این کد تخفیف منقضی شده است'
        if self.is_exhausted:
            return 'ظرفیت استفاده از این کد تخفیف تمام شده است'
        if self.usage_limit_per_user is not None and self.times_used_by(user) >= self.usage_limit_per_user:
            return 'شما قبلاً از این کد تخفیف استفاده کرده‌اید'
        if self.min_order_amount and amount < self.min_order_amount:
            return f'حداقل مبلغ سبد خرید برای این کد {int(self.min_order_amount):,} تومان است'
        return None

    def discount_for(self, amount):
        """مبلغ تخفیف این کد روی مبلغ داده‌شده.

        سقف کوپن و خودِ مبلغ سبد خرید هر دو اعمال می‌شوند تا تخفیف هیچ‌وقت از
        مبلغ قابل پرداخت بیشتر نشود و جمع نهایی منفی نگردد.
        """
        amount = Decimal(str(amount or 0))
        if amount <= 0:
            return Decimal('0')
        discount = (amount * Decimal(self.percentage) / Decimal('100')).quantize(Decimal('1'))
        if self.max_discount_amount is not None:
            discount = min(discount, Decimal(str(self.max_discount_amount)))
        return min(discount, amount)


class Order(models.Model):
    """مدل سفارشات"""
    STATUS_CHOICES = [
        ('pending', 'در انتظار پرداخت'),
        ('processing', 'در حال پردازش'),
        ('shipping', 'ارسال شده'),
        ('delivered', 'تحویل داده شده'),
        ('cancelled', 'لغو شده'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'در انتظار پرداخت'),
        ('paid', 'پرداخت شده'),
        ('failed', 'ناموفق'),
        ('refunded', 'بازگشت وجه'),
    ]

    SHIPPING_METHOD_CHOICES = [
        ('standard', 'ارسال معمولی'),
        ('express', 'ارسال فوری'),
    ]

    # اطلاعات اصلی
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='orders',
        verbose_name="کاربر"
    )
    order_number = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        verbose_name="شماره سفارش"
    )
    tracking_code = models.CharField(
        max_length=20,
        blank=True,
        unique=True,
        verbose_name="کد پیگیری"
    )

    # آدرس
    address = models.ForeignKey(
        Address,
        on_delete=models.PROTECT,
        related_name='orders',
        verbose_name="آدرس ارسال"
    )

    # کد تخفیف استفاده‌شده — برای گزارش‌گیری ادمین و شمردن سقف استفاده‌ی هر کاربر.
    coupon = models.ForeignKey(
        'Coupon',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
        verbose_name="کد تخفیف"
    )
    coupon_code = models.CharField(
        max_length=32,
        blank=True,
        verbose_name="کد تخفیف واردشده",
        help_text="متن کد در لحظه‌ی ثبت سفارش؛ اگر بعداً کوپن حذف شود این باقی می‌ماند."
    )
    coupon_discount = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=0,
        verbose_name="تخفیف کد تخفیف"
    )

    # وضعیت
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="وضعیت سفارش"
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending',
        verbose_name="وضعیت پرداخت"
    )

    # قیمت‌ها
    subtotal = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        verbose_name="جمع کل"
    )
    discount_amount = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=0,
        verbose_name="تخفیف"
    )
    shipping_cost = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=0,
        verbose_name="هزینه ارسال"
    )
    shipping_method = models.CharField(
        max_length=20,
        choices=SHIPPING_METHOD_CHOICES,
        default='standard',
        verbose_name="روش ارسال"
    )
    tax_amount = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=0,
        verbose_name="مالیات"
    )
    total = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        verbose_name="مبلغ نهایی"
    )

    # زمان
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ پرداخت")
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ تحویل")

    # اطلاعات اضافی
    notes = models.TextField(blank=True, verbose_name="یادداشت")

    @property
    def formatted_total(self):
        return f"{int(self.total):,}" if self.total is not None else "0"

    @property
    def formatted_subtotal(self):
        return f"{int(self.subtotal):,}" if self.subtotal is not None else "0"

    @property
    def formatted_discount(self):
        return f"{int(self.discount_amount):,}" if self.discount_amount is not None else "0"

    class Meta:
        verbose_name = "سفارش"
        verbose_name_plural = "سفارش‌ها"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order_number} - {self.user.fullname}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            # تولید شماره سفارش یکتا
            self.order_number = f"VX-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        if not self.tracking_code:
            # تولید کد پیگیری یکتا
            self.tracking_code = f"IR-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)


class OrderItem(models.Model):
    """آیتم‌های هر سفارش"""
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="سفارش"
    )
    product = models.ForeignKey(
        'Product',
        on_delete=models.PROTECT,
        related_name='order_items',
        verbose_name="محصول"
    )
    quantity = models.PositiveIntegerField(default=1, verbose_name="تعداد")
    price = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        verbose_name="قیمت واحد هنگام خرید"
    )
    discount = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=0,
        verbose_name="تخفیف واحد"
    )

    class Meta:
        verbose_name = "آیتم سفارش"
        verbose_name_plural = "آیتم‌های سفارش"

    def __str__(self):
        return f"{self.product.name} x{self.quantity}"

    @property
    def total(self):
        return (self.price - self.discount) * self.quantity


# apps/shop/models.py

class Cart(models.Model):
    """سبد خرید کاربر (اعم از مهمان یا لاگین‌شده)"""

    # ===== شناسه =====
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cart',
        verbose_name="کاربر"
    )
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="کلید نشست"
    )

    # ===== وضعیت =====
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    # ===== کوپن/تخفیف =====
    coupon_code = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="کد تخفیف"
    )
    coupon_discount = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        default=0,
        verbose_name="تخفیف کوپن"
    )

    # ===== زمان =====
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "سبد خرید"
        verbose_name_plural = "سبدهای خرید"
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_key', 'is_active']),
        ]

    def __str__(self):
        if self.user:
            return f"سبد {self.user.fullname}"
        return f"سبد مهمان ({self.session_key})"

    @property
    def item_count(self):
        """تعداد کل آیتم‌های سبد خرید"""
        return self.items.aggregate(Sum('quantity'))['quantity__sum'] or 0

    @property
    def total_items(self):
        """تعداد کل آیتم‌ها"""
        return self.items.aggregate(
            total=models.Sum('quantity')
        )['total'] or 0

    @property
    def subtotal(self):
        """جمع کل بدون تخفیف"""
        total = 0
        for item in self.items.all():
            total += item.product.price * item.quantity
        return total

    @property
    def total(self):
        """مبلغ نهایی با تخفیف"""
        return self.subtotal - self.coupon_discount

    @property
    def has_items(self):
        return self.items.exists()


class CartItem(models.Model):
    """آیتم‌های سبد خرید"""

    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="سبد خرید"
    )
    product = models.ForeignKey(
        'Product',
        on_delete=models.PROTECT,
        related_name='cart_items',
        verbose_name="محصول"
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="تعداد"
    )

    color_slug = models.CharField(
        max_length=50,
        blank=True,
        default='',
        verbose_name="رنگ"
    )

    # ===== اطلاعات محصول در زمان اضافه شدن (برای ثبات قیمت) =====
    price_snapshot = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        verbose_name="قیمت لحظه اضافه شدن"
    )

    # ===== اضافه کردن این فیلد =====
    selected_color = models.CharField(
        max_length=50,
        default='black',
        verbose_name="رنگ انتخاب‌شده"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "آیتم سبد خرید"
        verbose_name_plural = "آیتم‌های سبد خرید"
        unique_together = ['cart', 'product']  # هر محصول فقط یک بار در سبد

    def __str__(self):
        return f"{self.product.name} x{self.quantity}"

    @property
    def total(self):
        return self.price_snapshot * self.quantity

    def save(self, *args, **kwargs):
        """ذخیره قیمت لحظه‌ای در اولین بار ایجاد"""
        if not self.pk and not self.price_snapshot:
            self.price_snapshot = self.product.final_price  # قیمت با تخفیف
        super().save(*args, **kwargs)


class Transaction(models.Model):
    """تراکنش‌های پرداخت مرتبط با یک سفارش (هر تلاش پرداخت یک رکورد)"""

    GATEWAY_CHOICES = [
        ('zarinpal', 'زرین‌پال'),
        ('snappay', 'اسنپ‌پی (اقساطی BNPL)'),
        ('digipay', 'دیجی‌پی'),
        ('idpay', 'آی‌دی‌پی'),
        ('nextpay', 'نکست‌پی'),
        ('sandbox', 'درگاه تستی (Sandbox)'),
        ('bank', 'بانکی'),
    ]

    STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('success', 'موفق'),
        ('failed', 'ناموفق'),
    ]

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='transactions',
        verbose_name="سفارش"
    )
    transaction_id = models.CharField(
        max_length=30,
        unique=True,
        editable=False,
        verbose_name="شناسه تراکنش"
    )
    gateway = models.CharField(
        max_length=20,
        choices=GATEWAY_CHOICES,
        verbose_name="درگاه پرداخت"
    )
    reference_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="کد رهگیری درگاه",
        help_text="Authority/RefID که خودِ درگاه برمی‌گرداند"
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        verbose_name="مبلغ"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="وضعیت"
    )
    failure_reason = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="دلیل ناموفق بودن"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد")
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان پرداخت")
    settled_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان تسویه")

    class Meta:
        verbose_name = "تراکنش"
        verbose_name_plural = "تراکنش‌ها"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order', 'status']),
            models.Index(fields=['gateway', 'status']),
        ]

    def __str__(self):
        return f"{self.transaction_id} - {self.get_gateway_display()} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            self.transaction_id = f"TRX-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)


class RefundRequest(models.Model):
    """درخواست بازگشت وجه برای یک سفارش"""

    STATUS_CHOICES = [
        ('pending', 'در انتظار بررسی'),
        ('approved', 'تایید شده'),
        ('rejected', 'رد شده'),
        ('completed', 'بازگشت انجام شد'),
    ]

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='refund_requests',
        verbose_name="سفارش"
    )
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refund_requests',
        verbose_name="تراکنش مرتبط"
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        verbose_name="مبلغ درخواستی"
    )
    reason = models.TextField(verbose_name="دلیل درخواست کاربر")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="وضعیت"
    )
    admin_note = models.TextField(
        blank=True,
        verbose_name="یادداشت ادمین",
        help_text="در صورت رد شدن، دلیل رد شدن اینجا ثبت می‌شود"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان درخواست")
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان تصمیم‌گیری")

    class Meta:
        verbose_name = "درخواست بازگشت وجه"
        verbose_name_plural = "درخواست‌های بازگشت وجه"
        ordering = ['-created_at']

    def __str__(self):
        return f"بازگشت وجه سفارش {self.order.order_number} - {self.get_status_display()}"