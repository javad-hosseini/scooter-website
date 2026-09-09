# apps/shop/models.py
import uuid

from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
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

    # موجودی
    stock = models.PositiveIntegerField(default=0, verbose_name="موجودی")
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
        default='VOLTEX',
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
            self.cover_alt_text = f'{self.name} — اسکوتر برقی {self.brand or "ولتکس"}'
        super().save(*args, **kwargs)
        if not self.sku:
            # Needs the PK, so it has to happen after the first insert.
            type(self).objects.filter(pk=self.pk).update(sku=f'VLX-{self.pk:05d}')
            self.sku = f'VLX-{self.pk:05d}'

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