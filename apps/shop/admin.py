# apps/shop/admin.py

from django.contrib import admin
from django.db import models
from django.db.models import Count, Avg
from django.utils.html import format_html

from .models import (
    Product, Category, ProductSpec, TrustBadge,
    MarketingFeature, StatFeature, ProductImage,
    ProductReview, Wishlist
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
