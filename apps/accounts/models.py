from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    fullname = models.CharField(max_length=100, verbose_name="نام کامل")
    mobile = models.CharField(max_length=11, unique=True, verbose_name="شماره موبایل")
    email = models.EmailField(unique=True, verbose_name="ایمیل")
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

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
        return self.email

    class Meta:
        verbose_name = "کاربر"
        verbose_name_plural = "کاربران"
