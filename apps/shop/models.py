# apps/shop/models.py
import uuid

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
        verbose_name="تصویر"
    )
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
        ordering = ['-created_at']

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


class Product(models.Model):
    """مدل اصلی محصول"""
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
        help_text="تصویر اصلی محصول که در هدر نمایش داده می‌شود"
    )
    cover_alt_text = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="متن جایگزین تصویر کاور"
    )

    # قیمت
    price = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        verbose_name="قیمت (تومان)"
    )
    cost_price = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=0,
        verbose_name="قیمت تمام‌شده",
        help_text="هزینه‌ی خرید/تولید محصول — برای محاسبه‌ی سود خالص استفاده می‌شود و به مشتری نمایش داده نمی‌شود"
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

    # وضعیت
    is_published = models.BooleanField(default=True, verbose_name="منتشر شده")
    is_featured = models.BooleanField(default=False, verbose_name="ویژه")

    # متادیتا
    meta_title = models.CharField(
        max_length=60,
        blank=True,
        verbose_name="عنوان متا"
    )
    meta_description = models.CharField(
        max_length=160,
        blank=True,
        verbose_name="توضیحات متا"
    )

    # آمار
    view_count = models.PositiveIntegerField(default=0, verbose_name="تعداد بازدید")

    # زمان
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    stock_out_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="تاریخ اتمام موجودی"
    )

    # ===== سیگنال برای اطلاع‌رسانی اتمام موجودی =====
    def send_stock_alert(self):
        """ارسال هشدار اتمام موجودی به ادمین"""
        if self.stock <= 5 and self.is_available:
            # TODO: ارسال ایمیل یا نوتیفیکیشن به ادمین
            pass

    class Meta:
        verbose_name = "محصول"
        verbose_name_plural = "محصولات"
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('shop:product_detail', kwargs={'slug': self.slug})

    @property
    def reviews_count(self):
        return self.reviews.filter(status='approved').count()

    @property
    def final_price(self):
        """قیمت نهایی با احتساب تخفیف"""
        return self.discount_price if self.discount_price else self.price

    @property
    def profit_margin(self):
        """سود هر واحد از فروش این محصول (با احتساب تخفیف)"""
        return self.final_price - self.cost_price

    @property
    def average_rating(self):
        """میانگین امتیازات تایید شده"""
        approved = self.reviews.filter(status='approved')
        if approved.exists():
            return round(approved.aggregate(models.Avg('rating'))['rating__avg'], 1)
        return 0

    @property
    def reviews_count(self):
        """تعداد نظرات تایید شده"""
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
        ('idpay', 'آی‌دی‌پی'),
        ('nextpay', 'نکست‌پی'),
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