# apps/accounts/serializers.py
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import serializers

from apps.accounts.models import Province, City, Address

User = get_user_model()


#: Django's own password-validator messages are translated by LocaleMiddleware,
#: which follows the browser's Accept-Language. On a Persian-only site that
#: means an English-locale browser gets English validation text back. Mapping
#: by the validator's stable `code` gives one clear Persian sentence regardless
#: of the request locale, and says what to do rather than only what is wrong.
PASSWORD_ERROR_MESSAGES = {
    'password_too_short': 'رمز عبور باید حداقل ۸ کاراکتر باشد.',
    'password_too_common': 'این رمز عبور بسیار رایج است. ترکیبی از حروف، عدد و نماد انتخاب کنید.',
    'password_entirely_numeric': 'رمز عبور نمی‌تواند فقط عدد باشد. حداقل یک حرف اضافه کنید.',
    'password_too_similar': 'رمز عبور نباید شبیه نام کاربری، ایمیل یا نام شما باشد.',
}

#: Fallback when a validator raises without a code we recognise.
PASSWORD_ERROR_FALLBACK = 'رمز عبور انتخاب‌شده معتبر نیست. رمز قوی‌تری انتخاب کنید.'


def localized_password_errors(error):
    """Translate a Django password ValidationError into Persian messages."""
    messages = []
    for item in getattr(error, 'error_list', []) or []:
        code = getattr(item, 'code', None)
        if code in PASSWORD_ERROR_MESSAGES:
            messages.append(PASSWORD_ERROR_MESSAGES[code])
        else:
            # Unknown validator (e.g. a custom one): keep its own message,
            # which is authored rather than machine-generated.
            messages.extend(item.messages or [PASSWORD_ERROR_FALLBACK])
    return messages or [PASSWORD_ERROR_FALLBACK]


class UserRegistrationSerializer(serializers.ModelSerializer):
    password1 = serializers.CharField(
        write_only=True,
        required=True,
        min_length=8,
        error_messages={
            'min_length': 'رمز عبور باید حداقل ۸ کاراکتر باشد',
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

    def validate_agree_terms(self, value):
        # ``required=True`` only forces the key to be present — ``False`` is
        # still a valid boolean, so an explicit check is needed to refuse it.
        if not value:
            raise serializers.ValidationError('برای ادامه باید قوانین و مقررات را بپذیرید')
        return value

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
        if data["password1"] != data["password2"]:
            raise serializers.ValidationError({
                "password2": "رمز عبور و تکرار آن یکسان نیستند"
            })

        try:
            validate_password(data["password1"])
        except DjangoValidationError as e:
            messages = []

            translations = {
                "This password is too common.": "این رمز عبور بیش از حد رایج است.",
                "This password is entirely numeric.": "رمز عبور نباید فقط شامل عدد باشد.",
                "This password is too short. It must contain at least 8 characters.":
                    "رمز عبور باید حداقل ۸ کاراکتر باشد.",
            }

            for msg in e.messages:
                messages.append(translations.get(msg, msg))

            raise serializers.ValidationError({
                "password1": messages
            })

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


# login

from django.contrib.auth import authenticate


class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField(
        required=True,
        error_messages={'required': 'نام کاربری یا شماره موبایل الزامی است'}
    )
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'},
        error_messages={'required': 'رمز عبور الزامی است'}
    )

    def validate(self, data):
        request = self.context.get('request')
        user = authenticate(
            request=request,
            username=data.get('username'),
            password=data.get('password')
        )

        if not user:
            # پیام عمومی و یکسان برای هر دو حالت (کاربر نیست / پسورد غلط)
            raise serializers.ValidationError({
                'non_field_errors': ['نام کاربری/شماره موبایل یا رمز عبور اشتباه است']
            })

        if not user.is_active:
            raise serializers.ValidationError({
                'non_field_errors': ['این حساب کاربری غیرفعال شده است']
            })

        data['user'] = user
        return data


# apps/accounts/serializers.py (اضافه به فایل موجود)

class PasswordResetRequestSerializer(serializers.Serializer):
    identifier = serializers.CharField(
        required=True,
        error_messages={'required': 'ایمیل یا شماره موبایل الزامی است'}
    )
    # کاربر انتخاب می‌کنه از کدوم کانال کد بگیره
    channel = serializers.ChoiceField(choices=['email', 'sms'], required=True)


class PasswordResetVerifySerializer(serializers.Serializer):
    identifier = serializers.CharField(required=True)
    code = serializers.CharField(required=True, min_length=6, max_length=6)


class PasswordResetConfirmSerializer(serializers.Serializer):
    reset_token = serializers.CharField(required=True)
    new_password1 = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    new_password2 = serializers.CharField(write_only=True, required=True)

    def validate(self, data):
        if data['new_password1'] != data['new_password2']:
            raise serializers.ValidationError({'new_password2': 'رمز عبور و تکرار آن یکسان نیستند'})
        return data


# apps/accounts/serializers.py (اضافه به فایل موجود)

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(
        required=True,
        write_only=True,
        error_messages={'required': 'رمز عبور فعلی الزامی است'}
    )
    new_password1 = serializers.CharField(
        required=True,
        write_only=True,
        # validate_password is run in validate() instead, where the user is
        # available for the similarity check and the messages get localised.
        error_messages={'required': 'رمز عبور جدید الزامی است'}
    )
    new_password2 = serializers.CharField(
        required=True,
        write_only=True,
        error_messages={'required': 'تکرار رمز عبور جدید الزامی است'}
    )

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('رمز عبور فعلی اشتباه است')
        return value

    def validate_new_password1(self, value):
        # Field-level rather than inside validate(): DRF skips validate()
        # entirely once any field fails, so running the strength check here
        # means a weak new password and a wrong current password are both
        # reported in the same response instead of one at a time.
        try:
            validate_password(value, user=self.context['request'].user)
        except DjangoValidationError as e:
            raise serializers.ValidationError(localized_password_errors(e))
        return value

    def validate(self, data):
        if data['new_password1'] != data['new_password2']:
            raise serializers.ValidationError({'new_password2': 'رمز عبور و تکرار آن یکسان نیستند'})

        if data['old_password'] == data['new_password1']:
            raise serializers.ValidationError({'new_password1': 'رمز عبور جدید نباید با رمز عبور فعلی یکسان باشد'})

        return data


class UserProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='fullname')
    avatar = serializers.SerializerMethodField()
    membership_date = serializers.SerializerMethodField()
    orders_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'full_name', 'email', 'mobile', 'bio',
            'avatar', 'profile_image', 'national_code', 'birth_date',
            'gender', 'is_verified', 'membership_date', 'orders_count'
        ]

    def get_avatar(self, obj):
        if obj.profile_image:
            return obj.profile_image.url
        return '/static/img/avatar-placeholder.png'

    def get_membership_date(self, obj):
        if obj.date_joined:
            # تبدیل به تاریخ شمسی
            return obj.date_joined.strftime('%B %Y')
        return None

    def get_orders_count(self, obj):
        return obj.orders.count()


class UserUpdateSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='fullname', required=False)
    profile_image = serializers.ImageField(required=False)
    current_password = serializers.CharField(write_only=True, required=False)

    #: Changing any of these is an identity change: on its own a stolen session
    #: could be converted straight into account takeover (e.g. via a password
    #: reset to the attacker's address), so re-authentication is required.
    IDENTITY_FIELDS = ('email', 'username', 'mobile')

    class Meta:
        model = User
        fields = ['full_name', 'username', 'email', 'mobile', 'national_code',
                  'birth_date', 'gender', 'bio', 'profile_image', 'current_password']

    def validate_mobile(self, value):
        import re
        if not re.match(r'^09\d{9}$', value):
            raise serializers.ValidationError('شماره موبایل معتبر نیست')
        return value

    def validate(self, attrs):
        user = self.instance
        changing_identity = user is not None and any(
            field in attrs and attrs[field] != getattr(user, field)
            for field in self.IDENTITY_FIELDS
        )
        if changing_identity:
            current = attrs.get('current_password')
            if not current or not user.check_password(current):
                raise serializers.ValidationError({
                    'current_password': 'برای تغییر ایمیل، نام کاربری یا شماره موبایل باید رمز عبور فعلی را وارد کنید'
                })
        return attrs


class ProvinceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Province
        fields = ['id', 'name']


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ['id', 'name', 'province']


class AddressSerializer(serializers.ModelSerializer):
    province_name = serializers.CharField(source='province.name', read_only=True)
    city_name = serializers.CharField(source='city.name', read_only=True)

    class Meta:
        model = Address
        fields = [
            'id', 'recipient_name', 'recipient_phone', 'province', 'province_name',
            'city', 'city_name', 'address', 'postal_code', 'plaque',
            'unit', 'floor', 'description', 'is_active', 'created_at'
        ]
        read_only_fields = ['user', 'created_at']