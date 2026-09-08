# accounts/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import CustomUser, PasswordResetOTP, Province, City, Address


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = [
        'profile_image_thumbnail', 'fullname', 'email', 'mobile', 
        'is_verified', 'is_staff', 'is_active', 'articles_count', 'comments_count'
    ]
    list_filter = ['is_verified', 'is_staff', 'is_active', 'is_superuser', 'created_at']
    search_fields = ['fullname', 'email', 'mobile', 'username']
    ordering = ['-date_joined']
    list_per_page = 25
    actions = ['verify_users', 'unverify_users']

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (_("اطلاعات شخصی"), {
            "fields": ("fullname", "email", "mobile", "bio", "profile_image", "profile_image_preview")
        }),
        (_("دسترسی‌ها"), {
            "fields": ("is_active", "is_staff", "is_superuser", "is_verified", "groups", "user_permissions")
        }),
        (_("تاریخ‌ها"), {"fields": ("last_login", "date_joined", "created_at")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username", "fullname", "email", "mobile", 
                    "password1", "password2", "is_verified"
                ),
            },
        ),
    )

    readonly_fields = ['profile_image_preview', 'created_at', 'date_joined', 'last_login']

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('articles', 'article_comments')

    # ===== پیش‌نمایش عکس پروفایل =====
    def profile_image_thumbnail(self, obj):
        """پیش‌نمایش کوچک در لیست"""
        if obj.profile_image:
            return format_html(
                '<img src="{}" style="width:36px;height:36px;border-radius:50%;object-fit:cover;border:2px solid #4fd8ff;" />',
                obj.profile_image.url
            )
        return format_html(
            '<div style="width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,#4fd8ff,#8b7bff);display:flex;align-items:center;justify-content:center;color:#fff;font-size:14px;font-weight:bold;">{}</div>',
            obj.fullname[0] if obj.fullname else obj.username[0].upper()
        )
    profile_image_thumbnail.short_description = 'تصویر'

    def profile_image_preview(self, obj):
        """پیش‌نمایش بزرگ در صفحه ویرایش"""
        if obj.profile_image:
            return format_html(
                '<img src="{}" style="max-height:200px;max-width:200px;border-radius:50%;object-fit:cover;border:3px solid #4fd8ff;" />',
                obj.profile_image.url
            )
        return 'تصویری آپلود نشده'
    profile_image_preview.short_description = 'پیش‌نمایش عکس'

    # ===== آمار =====
    def articles_count(self, obj):
        """تعداد مقالات نوشته شده"""
        count = obj.articles.filter(is_published=True).count()
        return format_html(
            '<span style="color:#4fd8ff;font-weight:bold;">{}</span>',
            count
        )
    articles_count.short_description = 'مقالات'

    def comments_count(self, obj):
        """تعداد نظرات ثبت شده"""
        count = obj.article_comments.filter(is_approved=True).count()
        return format_html(
            '<span style="color:#8b7bff;font-weight:bold;">{}</span>',
            count
        )
    comments_count.short_description = 'نظرات'

    # ===== اکشن‌ها =====
    @admin.action(description='تایید کاربران انتخاب‌شده')
    def verify_users(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} کاربر تایید شد')

    @admin.action(description='لغو تایید کاربران انتخاب‌شده')
    def unverify_users(self, request, queryset):
        updated = queryset.update(is_verified=False)
        self.message_user(request, f'{updated} کاربر از تایید خارج شد')


@admin.register(PasswordResetOTP)
class PasswordResetOTPAdmin(admin.ModelAdmin):
    list_display = [
        'user_display', 'channel', 'destination', 'is_used', 
        'is_expired_display', 'attempts', 'created_at'
    ]
    list_filter = ['channel', 'is_used', 'created_at', 'expires_at']
    search_fields = ['user__fullname', 'user__email', 'destination', 'reset_token']
    readonly_fields = ['code_hash', 'created_at', 'expires_at', 'reset_token']
    list_per_page = 25

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

    def user_display(self, obj):
        return obj.user.fullname or obj.user.email
    user_display.short_description = 'کاربر'

    def is_expired_display(self, obj):
        if obj.is_expired():
            return format_html('<span style="color:#ef4444;">✅ منقضی شده</span>')
        return format_html('<span style="color:#22c55e;">✓ معتبر</span>')
    is_expired_display.short_description = 'وضعیت انقضا'

    def has_add_permission(self, request):
        """اجازه ایجاد OTP از ادمین رو غیرفعال کن"""
        return False

    def has_delete_permission(self, request, obj=None):
        """اجازه حذف OTP رو غیرفعال کن"""
        return False

@admin.register(Province)
class ProvinceAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ['name', 'province']
    list_filter = ['province']
    search_fields = ['name']


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ['user', 'recipient_name', 'province', 'city', 'is_active', 'created_at']
    list_filter = ['province', 'city', 'is_active']
    search_fields = ['user__fullname', 'recipient_name', 'address', 'postal_code']
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 25

    fieldsets = (
        ('اطلاعات گیرنده', {
            'fields': ('user', 'recipient_name', 'recipient_phone')
        }),
        ('آدرس', {
            'fields': ('province', 'city', 'address', 'postal_code', 'plaque', 'unit', 'floor')
        }),
        ('وضعیت', {
            'fields': ('is_active',)
        }),
        ('توضیحات', {
            'fields': ('description',)
        }),
        ('تاریخ', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )