# apps/shop/admin.py

from django.contrib import admin
from django.db import models
from django.db.models import Count, Avg
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    Product, Category, ProductSpec, TrustBadge,
    MarketingFeature, StatFeature, ProductImage,
    ProductReview, Wishlist, CategoryHeroProduct, OrderItem, Order
)
from .actions import (
    export_selected_orders_to_pdf,
    export_selected_orders_to_excel,
)


class ProductSpecInline(admin.TabularInline):
    model = ProductSpec
    extra = 1
    fields = ['icon', 'value', 'label', 'order']
    ordering = ['order']


class TrustBadgeInline(admin.TabularInline):
    model = TrustBadge
    extra = 1
    fields = ['icon', 'label', 'value', 'order']
    ordering = ['order']


class MarketingFeatureInline(admin.TabularInline):
    model = MarketingFeature
    extra = 1
    fields = ['icon', 'title', 'description', 'accent', 'order']
    ordering = ['order']


class StatFeatureInline(admin.TabularInline):
    model = StatFeature
    extra = 1
    fields = ['number', 'suffix', 'label', 'order']
    ordering = ['order']


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ['image', 'color_slug', 'color_label', 'color_hex', 'alt_text', 'sort_order', 'is_primary']
    ordering = ['sort_order']


class ProductReviewInline(admin.TabularInline):
    model = ProductReview
    extra = 0
    fields = ['user', 'rating', 'title', 'comment_preview', 'status', 'created_at']
    readonly_fields = ['user', 'comment_preview', 'created_at']
    ordering = ['-created_at']

    def comment_preview(self, obj):
        return obj.comment[:50] + '...' if len(obj.comment) > 50 else obj.comment

    comment_preview.short_description = 'متن نظر'


class CategoryHeroProductInline(admin.TabularInline):
    model = CategoryHeroProduct
    extra = 1
    fields = ['product', 'order']
    ordering = ['order']
    autocomplete_fields = ['product']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'icon', 'product_count', 'is_active', 'order']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['order', 'name']

    def product_count(self, obj):
        return obj.products.filter(is_published=True).count()

    product_count.short_description = 'تعداد محصولات'
    inlines = [CategoryHeroProductInline]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'cover_image_thumbnail', 'name', 'category', 'price_display',
        'stock_status', 'is_available', 'is_published', 'is_featured',
        'average_rating_display', 'reviews_count_display', 'view_count'
    ]
    list_filter = ['category', 'is_published', 'is_available', 'is_featured', 'created_at']
    search_fields = ['name', 'slug', 'description']
    prepopulated_fields = {'slug': ('name',)}
    list_per_page = 25
    date_hierarchy = 'created_at'
    readonly_fields = ['view_count', 'created_at', 'updated_at', 'cover_image_preview']

    inlines = [
        ProductSpecInline,
        TrustBadgeInline,
        MarketingFeatureInline,
        StatFeatureInline,
        ProductImageInline,
        ProductReviewInline
    ]

    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('name', 'slug', 'category', 'cover_image', 'cover_image_preview', 'cover_alt_text')
        }),
        ('محتوای محصول', {
            'fields': ('tagline', 'description')
        }),
        ('قیمت و موجودی', {
            'fields': ('price', 'discount_price', 'stock', 'is_available')
        }),
        ('وضعیت', {
            'fields': ('is_published', 'is_featured')
        }),
        ('متادیتا', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',)
        }),
        ('آمار', {
            'fields': ('view_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def reviews_count_display(self, obj):
        return obj.total_reviews

    reviews_count_display.short_description = 'تعداد نظرات'
    reviews_count_display.admin_order_field = 'total_reviews'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('category').annotate(
            avg_rating=Avg('reviews__rating', filter=models.Q(reviews__status='approved')),
            total_reviews=Count('reviews', filter=models.Q(reviews__status='approved'))
        )

    def cover_image_thumbnail(self, obj):
        if obj.cover_image:
            return format_html(
                '<img src="{}" style="height:50px;width:50px;object-fit:cover;border-radius:6px;" />',
                obj.cover_image.url
            )
        return '—'

    cover_image_thumbnail.short_description = 'تصویر'

    def cover_image_preview(self, obj):
        if obj.cover_image:
            return format_html(
                '<img src="{}" style="max-height:200px;max-width:200px;border-radius:8px;object-fit:cover;" />',
                obj.cover_image.url
            )
        return 'تصویری آپلود نشده'

    cover_image_preview.short_description = 'پیش‌نمایش تصویر'

    def price_display(self, obj):
        if obj.discount_price:
            return format_html(
                '<span style="color:#C9A84C;font-weight:bold;">{} تومان</span> '
                '<span style="color:rgba(255,255,255,0.3);text-decoration:line-through;">{} تومان</span>',
                obj.final_price,
                obj.price
            )
        return f"{obj.price:,} تومان"

    price_display.short_description = 'قیمت'

    def stock_status(self, obj):
        if obj.stock > 10:
            color = '#22c55e'
            status_text = 'موجود'
        elif obj.stock > 0:
            color = '#eab308'
            status_text = f'{obj.stock} عدد باقی'
        else:
            color = '#ef4444'
            status_text = 'ناموجود'
        return format_html('<span style="color:{};">{}</span>', color, status_text)

    stock_status.short_description = 'وضعیت موجودی'

    def average_rating_display(self, obj):
        if obj.avg_rating:
            stars = '★' * round(obj.avg_rating) + '☆' * (5 - round(obj.avg_rating))
            return format_html(
                '<span style="color:#C9A84C;">{} ({})</span>',
                stars,
                str(round(obj.avg_rating, 1))
            )
        return 'بدون نظر'

    average_rating_display.short_description = 'امتیاز'

    actions = ['make_published', 'make_unpublished', 'make_featured', 'make_unfeatured']

    @admin.action(description='انتشار محصولات انتخاب‌شده')
    def make_published(self, request, queryset):
        updated = queryset.update(is_published=True)
        self.message_user(request, f'{updated} محصول منتشر شد')

    @admin.action(description='لغو انتشار محصولات انتخاب‌شده')
    def make_unpublished(self, request, queryset):
        updated = queryset.update(is_published=False)
        self.message_user(request, f'{updated} محصول از انتشار خارج شد')

    @admin.action(description='ویژه کردن محصولات انتخاب‌شده')
    def make_featured(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} محصول ویژه شد')

    @admin.action(description='لغو ویژه بودن محصولات انتخاب‌شده')
    def make_unfeatured(self, request, queryset):
        updated = queryset.update(is_featured=False)
        self.message_user(request, f'{updated} محصول از ویژه بودن خارج شد')


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'product_name', 'rating_stars', 'title', 'status_badge',
        'helpful_count', 'created_at'
    ]
    list_filter = ['status', 'rating', 'created_at']
    search_fields = ['user__fullname', 'user__email', 'title', 'comment', 'product__name']
    list_per_page = 25
    readonly_fields = ['created_at', 'updated_at', 'user', 'product']
    actions = ['approve_reviews', 'reject_reviews']

    fieldsets = (
        ('اطلاعات نظر', {
            'fields': ('product', 'user', 'rating')
        }),
        ('محتوا', {
            'fields': ('title', 'comment')
        }),
        ('وضعیت', {
            'fields': ('status', 'rejection_reason')
        }),
        ('آمار', {
            'fields': ('helpful_count', 'is_verified_purchase', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'product')

    def product_name(self, obj):
        return obj.product.name

    product_name.short_description = 'محصول'

    def rating_stars(self, obj):
        return '★' * obj.rating + '☆' * (5 - obj.rating)

    rating_stars.short_description = 'امتیاز'

    def status_badge(self, obj):
        colors = {
            'pending': '#eab308',
            'approved': '#22c55e',
            'rejected': '#ef4444'
        }
        labels = {
            'pending': 'در انتظار تایید',
            'approved': 'تایید شده',
            'rejected': 'رد شده'
        }
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>',
            colors[obj.status],
            labels[obj.status]
        )

    status_badge.short_description = 'وضعیت'

    @admin.action(description='تایید نظرات انتخاب‌شده')
    def approve_reviews(self, request, queryset):
        updated = queryset.update(status='approved')
        self.message_user(request, f'{updated} نظر تایید شد')

    @admin.action(description='رد کردن نظرات انتخاب‌شده')
    def reject_reviews(self, request, queryset):
        # برای رد کردن نیاز به دلیل داریم، بنابراین یک فرم می‌خواهیم
        # ساده‌ترین راه: یک action جداگانه با فرم
        if 'apply' in request.POST:
            reason = request.POST.get('rejection_reason', '')
            if not reason:
                self.message_user(request, 'لطفاً دلیل رد کردن را وارد کنید.', level='ERROR')
                return
            updated = queryset.update(status='rejected', rejection_reason=reason)
            self.message_user(request, f'{updated} نظر رد شد.')
        else:
            # نمایش یک فرم ساده برای وارد کردن دلیل
            from django.shortcuts import render
            return render(request, 'admin/reject_reviews.html', {
                'queryset': queryset,
                'action': 'reject_reviews'
            })

    reject_reviews.short_description = 'رد کردن نظرات انتخاب‌شده'


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__fullname', 'user__email', 'product__name']
    readonly_fields = ['created_at']


# ============================================================
# ORDER ITEM INLINE (برای اضافه کردن محصولات به سفارش)
# ============================================================

class OrderItemInline(admin.TabularInline):
    """Inline برای اضافه کردن محصولات به سفارش"""
    model = OrderItem
    extra = 1
    fields = ['product', 'quantity', 'price', 'discount', 'total_display']
    readonly_fields = ['total_display']
    autocomplete_fields = ['product']
    ordering = ['id']

    def total_display(self, obj):
        if obj.id:
            return format_html(
                '<span style="color:var(--gold);font-weight:bold;">{} تومان</span>',
                obj.total
            )
        return '-'

    total_display.short_description = 'جمع آیتم'


# ============================================================
# 🆕 ORDER ADMIN (برای ثبت سفارش دستی)
# ============================================================

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'order_number', 'user_display', 'total_display', 'status_badge',
        'payment_status_badge', 'created_at', 'order_actions'
    ]
    list_filter = ['status', 'payment_status', 'created_at']
    search_fields = ['order_number', 'tracking_code', 'user__fullname', 'user__email']
    readonly_fields = ['order_number', 'tracking_code', 'created_at', 'updated_at', 'total_display']
    list_per_page = 25
    date_hierarchy = 'created_at'
    inlines = [OrderItemInline]
    actions = [
        'mark_as_pending',
        'mark_as_processing',
        'mark_as_shipping',
        'mark_as_delivered',
        'mark_as_cancelled',
        # ===== اضافه کردن اکشن‌های جدید =====
        export_selected_orders_to_pdf,
        export_selected_orders_to_excel,
    ]
    fieldsets = (
        ('اطلاعات سفارش', {
            'fields': ('order_number', 'tracking_code', 'user', 'address')
        }),
        ('وضعیت', {
            'fields': ('status', 'payment_status')
        }),
        ('قیمت‌ها', {
            'fields': ('subtotal', 'discount_amount', 'shipping_cost', 'total_display')
        }),
        ('زمان', {
            'fields': ('paid_at', 'delivered_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        ('یادداشت', {
            'fields': ('notes',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'address')

    def save_model(self, request, obj, form, change):
        # محاسبه خودکار total
        if not obj.total:
            obj.total = obj.subtotal - obj.discount_amount + obj.shipping_cost
        super().save_model(request, obj, form, change)

    def user_display(self, obj):
        return obj.user.fullname or obj.user.username

    user_display.short_description = 'کاربر'

    def total_display(self, obj):
        if obj.total is None:
            return "۰ تومان"
        return f"{int(obj.total):,} تومان"

    total_display.short_description = 'مبلغ نهایی'

    def status_badge(self, obj):
        colors = {
            'pending': '#eab308',
            'processing': '#3b82f6',
            'shipping': '#22d3ee',
            'delivered': '#22c55e',
            'cancelled': '#ef4444'
        }
        labels = {
            'pending': 'در انتظار پرداخت',
            'processing': 'در حال پردازش',
            'shipping': 'ارسال شده',
            'delivered': 'تحویل داده شده',
            'cancelled': 'لغو شده'
        }
        return format_html(
            '<span style="background:{};color:white;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:600;">{}</span>',
            colors.get(obj.status, '#6b7280'),
            labels.get(obj.status, obj.status)
        )

    status_badge.short_description = 'وضعیت سفارش'

    def payment_status_badge(self, obj):
        colors = {
            'pending': '#eab308',
            'paid': '#22c55e',
            'failed': '#ef4444',
            'refunded': '#6b7280'
        }
        labels = {
            'pending': 'در انتظار پرداخت',
            'paid': 'پرداخت شده',
            'failed': 'ناموفق',
            'refunded': 'بازگشت وجه'
        }
        return format_html(
            '<span style="background:{};color:white;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:600;">{}</span>',
            colors.get(obj.payment_status, '#6b7280'),
            labels.get(obj.payment_status, obj.payment_status)
        )

    payment_status_badge.short_description = 'وضعیت پرداخت'

    def order_actions(self, obj):
        """دکمه‌های عملیات سریع روی سفارش"""
        buttons = []
        actions = {
            'pending': ('در انتظار پرداخت', 'processing'),
            'processing': ('در حال پردازش', 'shipping'),
            'shipping': ('ارسال شده', 'delivered'),
            'delivered': ('تحویل داده شده', None),
            'cancelled': ('لغو شده', None),
        }

        current_label, next_status = actions.get(obj.status, (obj.status, None))

        if next_status:
            status_labels = {
                'pending': 'تغییر به در حال پردازش',
                'processing': 'تغییر به ارسال شده',
                'shipping': 'تغییر به تحویل داده شده',
            }
            btn_text = status_labels.get(obj.status, f'تغییر وضعیت')
            url = reverse('admin:shop_order_change', args=[obj.id])
            buttons.append(
                format_html(
                    '<a href="{}" style="background:var(--blue);color:white;padding:4px 10px;border-radius:6px;text-decoration:none;font-size:11px;">{}</a>',
                    url,
                    btn_text
                )
            )

        return format_html(' '.join(buttons))

    order_actions.short_description = 'عملیات'

    # ===== اکشن‌های گروهی =====
    @admin.action(description='تغییر وضعیت به در انتظار پرداخت')
    def mark_as_pending(self, request, queryset):
        updated = queryset.update(status='pending')
        self.message_user(request, f'{updated} سفارش به وضعیت در انتظار پرداخت تغییر یافت')

    @admin.action(description='تغییر وضعیت به در حال پردازش')
    def mark_as_processing(self, request, queryset):
        updated = queryset.update(status='processing')
        self.message_user(request, f'{updated} سفارش به وضعیت در حال پردازش تغییر یافت')

    @admin.action(description='تغییر وضعیت به ارسال شده')
    def mark_as_shipping(self, request, queryset):
        updated = queryset.update(status='shipping')
        self.message_user(request, f'{updated} سفارش به وضعیت ارسال شده تغییر یافت')

    @admin.action(description='تغییر وضعیت به تحویل داده شده')
    def mark_as_delivered(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='delivered', delivered_at=timezone.now())
        self.message_user(request, f'{updated} سفارش به وضعیت تحویل داده شده تغییر یافت')

    @admin.action(description='تغییر وضعیت به لغو شده')
    def mark_as_cancelled(self, request, queryset):
        updated = queryset.update(status='cancelled')
        self.message_user(request, f'{updated} سفارش لغو شد')


# ============================================================
# 🆕 ORDER ITEM ADMIN (برای مدیریت جداگانه آیتم‌ها)
# ============================================================

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order_display', 'product_display', 'quantity', 'price_display', 'total_display']
    list_filter = ['order__status', 'order__payment_status']
    search_fields = ['order__order_number', 'product__name', 'order__user__fullname']
    autocomplete_fields = ['order', 'product']
    list_per_page = 25
    readonly_fields = ['price', 'discount', 'total_display']

    def order_display(self, obj):
        return obj.order.order_number
    order_display.short_description = 'شماره سفارش'

    def product_display(self, obj):
        return obj.product.name
    product_display.short_description = 'محصول'

    def price_display(self, obj):
        return f"{obj.price:,} تومان"
    price_display.short_description = 'قیمت واحد'

    def total_display(self, obj):
        formatted_total = f"{obj.total:,}"
        return format_html(
            '<span style="color:var(--gold);font-weight:bold;">{} تومان</span>',
            formatted_total
        )
    total_display.short_description = 'جمع'