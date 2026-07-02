from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser


class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ["email", "fullname", "mobile", "is_staff", "is_verified"]
    list_filter = ["is_staff", "is_verified", "is_active"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("اطلاعات شخصی", {"fields": ("fullname", "mobile", "username")}),
        (
            "دسترسی‌ها",
            {"fields": ("is_active", "is_staff", "is_superuser", "is_verified")},
        ),
        ("تاریخ‌ها", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "fullname",
                    "mobile",
                    "username",
                    "password1",
                    "password2",
                    "is_verified",
                ),
            },
        ),
    )
    search_fields = ("email", "fullname", "mobile")
    ordering = ("email",)


admin.site.register(CustomUser, CustomUserAdmin)
