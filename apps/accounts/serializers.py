# apps/accounts/serializers.py
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError
from rest_framework import serializers

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    password1 = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        min_length=6,
        error_messages={
            'min_length': 'رمز عبور باید حداقل ۶ کاراکتر باشد',
            'required': 'رمز عبور الزامی است'
        }
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        error_messages={'required': 'تکرار رمز عبور الزامی است'}
    )
    agree_terms = serializers.BooleanField(
        write_only=True,
        required=True,
        error_messages={'required': 'برای ادامه باید قوانین و مقررات را بپذیرید'}
    )

    class Meta:
        model = User
        fields = ('fullname', 'username', 'mobile', 'email', 'password1', 'password2', 'agree_terms')
        extra_kwargs = {
            'fullname': {'required': True, 'error_messages': {'required': 'نام کامل الزامی است'}},
            'username': {
                'required': True,
                'validators': [],  # غیرفعال کردن UniqueValidator خودکار
                'error_messages': {'required': 'نام کاربری الزامی است'}
            },
            'mobile': {
                'required': True,
                'validators': [],
                'error_messages': {'required': 'شماره موبایل الزامی است'}
            },
            'email': {
                'required': True,
                'validators': [],
                'error_messages': {'required': 'ایمیل الزامی است'}
            },
        }

    def validate_mobile(self, value):
        if not re.match(r'^09\d{9}$', value):
            raise serializers.ValidationError('شماره موبایل باید با ۰۹ شروع شده و ۱۱ رقم باشد')
        if User.objects.filter(mobile=value).exists():
            raise serializers.ValidationError('این شماره موبایل قبلا ثبت شده است')
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('این ایمیل قبلا ثبت شده است')
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('این نام کاربری قبلا ثبت شده است')
        return value

    def validate(self, data):
        if data.get('password1') != data.get('password2'):
            raise serializers.ValidationError({'password2': 'رمز عبور و تکرار آن یکسان نیستند'})
        return data

    def create(self, validated_data):
        validated_data.pop('password2', None)
        validated_data.pop('agree_terms', None)
        password = validated_data.pop('password1')
        try:
            user = User.objects.create_user(password=password, **validated_data)
        except IntegrityError:
            raise serializers.ValidationError({'non_field_errors': ['خطا در ثبت‌نام، لطفا دوباره تلاش کنید']})
        return user


