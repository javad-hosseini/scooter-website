import logging
import os
import secrets
from datetime import timedelta

import filetype
from PIL import Image

from django.contrib.auth import login as django_login, logout as django_logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views import View
from django.views.generic import TemplateView
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import PasswordResetOTP, Province, City, Address
from .serializers import UserLoginSerializer, UserRegistrationSerializer, PasswordResetRequestSerializer, User, \
    PasswordResetVerifySerializer, PasswordResetConfirmSerializer, ChangePasswordSerializer, ProvinceSerializer, \
    AddressSerializer, UserProfileSerializer, UserUpdateSerializer, CitySerializer
from ..home.models import Comment
from ..shop.models import ProductReview
from ..shop.serializers import OrderListSerializer

logger = logging.getLogger(__name__)


class UserRegistrationAPIView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'register'

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors,
                'message': 'اطلاعات وارد شده معتبر نیست'
            }, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        return Response({
            'success': True,
            'message': 'ثبت‌نام با موفقیت انجام شد',
            'user': {
                'id': user.id,
                'email': user.email,
                'fullname': user.fullname,
                'mobile': user.mobile
            }
        }, status=status.HTTP_201_CREATED)


class RegisterPageView(TemplateView):
    template_name = 'accounts/register.html'


class UserLoginAPIView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = UserLoginSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors,
                'message': 'ورود ناموفق بود'
            }, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data['user']
        django_login(request, user)  # session رو می‌سازه، session-fixation رو هم خودش هندل می‌کنه

        logger.info(f"User logged in: {user.username} (id={user.id})")

        return Response({
            'success': True,
            'message': 'با موفقیت وارد شدید',
            'user': {
                'id': user.id,
                'username': user.username,
                'fullname': user.fullname,
                'mobile': user.mobile
            }
        }, status=status.HTTP_200_OK)


class LoginPageView(TemplateView):
    template_name = 'accounts/login.html'


class PasswordResetRequestAPIView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = PasswordResetRequestSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset_request'

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data['identifier']
        channel = serializer.validated_data['channel']

        user = User.objects.filter(
            Q(email=identifier) | Q(mobile=identifier)
        ).first()

        # همیشه پیام یکسان — چه کاربر پیدا شد چه نه
        generic_response = Response({
            'success': True,
            'message': 'در صورت معتبر بودن حساب، کد تایید ارسال شد'
        }, status=status.HTTP_200_OK)

        if not user:
            return generic_response

        code = PasswordResetOTP.generate_code()
        PasswordResetOTP.objects.create(
            user=user,
            code_hash=PasswordResetOTP.hash_code(code),
            channel=channel,
            destination=identifier,
            expires_at=timezone.now() + timedelta(minutes=PasswordResetOTP.OTP_LIFETIME_MINUTES)
        )

        # TODO: گام بعد - وصل کردن به سرویس واقعی SMS/Email
        # send_otp(channel=channel, destination=identifier, code=code)
        logger.info(f"OTP generated for user_id={user.id} via {channel}")

        return generic_response


class PasswordResetVerifyAPIView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = PasswordResetVerifySerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset_verify'

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data['identifier']
        code = serializer.validated_data['code']

        user = User.objects.filter(Q(email=identifier) | Q(mobile=identifier)).first()
        generic_error = Response({
            'success': False,
            'errors': {'code': ['کد وارد شده نامعتبر یا منقضی شده است']},
            'message': 'تایید ناموفق بود'
        }, status=status.HTTP_400_BAD_REQUEST)

        if not user:
            return generic_error

        otp = PasswordResetOTP.objects.filter(
            user=user, is_used=False
        ).order_by('-created_at').first()

        if not otp or otp.is_expired() or otp.is_locked():
            return generic_error

        if not PasswordResetOTP.matches(otp.code_hash, code):
            otp.attempts = models.F('attempts') + 1
            otp.save(update_fields=['attempts'])
            return generic_error

        # کد درسته → یکبار مصرفش کن، reset_token بده
        raw_token = secrets.token_urlsafe(32)
        otp.reset_token = PasswordResetOTP.hash_code(raw_token)  # هش شده ذخیره میشه
        otp.is_used = True
        otp.verified_at = timezone.now()
        otp.save(update_fields=['reset_token', 'is_used', 'verified_at'])

        return Response({
            'success': True,
            'message': 'کد تایید شد',
            'reset_token': raw_token,  # فقط همینجا خام برمی‌گرده به کلاینت
            'expires_in': PasswordResetOTP.RESET_TOKEN_LIFETIME_MINUTES * 60
        }, status=status.HTTP_200_OK)


class PasswordResetConfirmAPIView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = PasswordResetConfirmSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset_confirm'

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw_token = serializer.validated_data['reset_token']
        token_hash = PasswordResetOTP.hash_code(raw_token)

        otp = PasswordResetOTP.objects.filter(
            reset_token=token_hash,
            is_used=True  # باید از مرحله verify اومده باشه
        ).order_by('-created_at').first()

        generic_error = Response({
            'success': False,
            'errors': {'reset_token': ['توکن نامعتبر یا منقضی شده است']},
            'message': 'بازنشانی رمز عبور ناموفق بود'
        }, status=status.HTTP_400_BAD_REQUEST)

        if not otp:
            return generic_error

        # From verified_at, not created_at: the latter charged the user for
        # however long they took to type the code.
        issued_at = otp.verified_at or otp.created_at
        token_expiry = issued_at + timedelta(minutes=PasswordResetOTP.RESET_TOKEN_LIFETIME_MINUTES)
        if timezone.now() > token_expiry:
            return generic_error

        user = otp.user
        user.set_password(serializer.validated_data['new_password1'])
        user.save(update_fields=['password'])

        # مهم: توکن رو بلافاصله بعد از مصرف باطل کن تا reuse نشه
        otp.reset_token = None
        otp.save(update_fields=['reset_token'])

        logger.info(f"Password reset completed for user_id={user.id}")

        return Response({
            'success': True,
            'message': 'رمز عبور با موفقیت تغییر کرد'
        }, status=status.HTTP_200_OK)


class PasswordResetPageView(TemplateView):
    template_name = 'accounts/forgot-password.html'


class ChangePasswordAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'change_password'

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors,
                'message': 'تغییر رمز عبور ناموفق بود'
            }, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        user.set_password(serializer.validated_data['new_password1'])
        user.save(update_fields=['password'])

        # حیاتی: بدون این خط، session کاربر بعد از تغییر پسورد invalid می‌شه
        # و باید دوباره لاگین کنه. مهم‌تر: این خط session hash رو rotate می‌کنه
        # که یعنی هر session token دیگه‌ای (مثلاً session دزدیده‌شده) بلافاصله invalid می‌شه
        update_session_auth_hash(request, user)

        logger.info(f"Password changed for user_id={user.id}")

        return Response({
            'success': True,
            'message': 'رمز عبور با موفقیت تغییر کرد'
        }, status=status.HTTP_200_OK)


# ══════════════════════════════════════════════════════════════════════
#  Dashboard notifications
#
#  There is no Notification model, and the previous implementation shipped a
#  single hard-coded entry ("سفارش شما ارسال شد") that every user saw whether
#  or not they had ever placed an order. Notifications are derived from the
#  user's own records instead — the same approach the admin dashboard already
#  uses in apps/shop/views.py — so no schema change is needed.
#
#  Read state is kept as a timestamp in the session rather than a new model:
#  anything that happened at or before that moment counts as read.
# ══════════════════════════════════════════════════════════════════════

NOTIFICATIONS_READ_AT_SESSION_KEY = 'notifications_read_at'

#: Notifications older than this are not worth surfacing on the dashboard.
NOTIFICATION_MAX_AGE_DAYS = 60
NOTIFICATION_LIMIT = 20


def get_notifications_read_at(request):
    """The moment the user last marked their notifications read, or None."""
    raw = request.session.get(NOTIFICATIONS_READ_AT_SESSION_KEY)
    if not raw:
        return None
    parsed = parse_datetime(raw)
    if parsed is None:
        return None
    return parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)


def humanize_since(dt):
    """Relative Persian time, matching the admin dashboard's wording."""
    seconds = int((timezone.now() - dt).total_seconds())
    if seconds < 60:
        return 'لحظاتی پیش'
    if seconds < 3600:
        return f'{seconds // 60} دقیقه پیش'
    if seconds < 86400:
        return f'{seconds // 3600} ساعت پیش'
    if seconds < 604800:
        return f'{seconds // 86400} روز پیش'
    return f'{seconds // 604800} هفته پیش'


#: Wording and icon per order status. `delivered` and `shipping` are the two
#: the customer actually wants to hear about; the rest are still useful.
ORDER_STATUS_NOTIFICATIONS = {
    'pending': ('clock', 'سفارش در انتظار پرداخت', 'سفارش {number} هنوز پرداخت نشده است'),
    'processing': ('box', 'سفارش در حال پردازش', 'سفارش {number} در حال آماده‌سازی است'),
    'shipping': ('truck', 'سفارش شما ارسال شد', 'سفارش {number} تحویل پست شد'),
    'delivered': ('check', 'سفارش تحویل داده شد', 'سفارش {number} با موفقیت تحویل شما شد'),
    'cancelled': ('x', 'سفارش لغو شد', 'سفارش {number} لغو شده است'),
}


def build_user_notifications(user, orders_qs, product_comments_qs,
                             article_comments_qs, read_at=None):
    """Derive the user's notification feed from their own records."""
    cutoff = timezone.now() - timedelta(days=NOTIFICATION_MAX_AGE_DAYS)
    events = []

    def add(when, icon, title, desc):
        if when is None or when < cutoff:
            return
        events.append({'when': when, 'icon': icon, 'title': title, 'desc': desc})

    # ── سفارش‌ها ──
    for order in orders_qs.filter(updated_at__gte=cutoff).order_by('-updated_at')[:NOTIFICATION_LIMIT]:
        icon, title, desc = ORDER_STATUS_NOTIFICATIONS.get(
            order.status, ('box', 'به‌روزرسانی سفارش', 'وضعیت سفارش {number} تغییر کرد')
        )
        # delivered_at / paid_at are more accurate than updated_at when set.
        when = order.delivered_at if order.status == 'delivered' and order.delivered_at else order.updated_at
        add(when, icon, title, desc.format(number=order.order_number))

    # ── نتیجه بررسی نظرات محصول ──
    for review in product_comments_qs.filter(
        updated_at__gte=cutoff, status__in=('approved', 'rejected')
    ).select_related('product').order_by('-updated_at')[:NOTIFICATION_LIMIT]:
        if review.status == 'approved':
            add(review.updated_at, 'check', 'نظر شما تایید شد',
                f'نظر شما درباره «{review.product.name}» منتشر شد')
        else:
            reason = review.rejection_reason or 'مطابق قوانین سایت نبود'
            add(review.updated_at, 'x', 'نظر شما تایید نشد',
                f'نظر شما درباره «{review.product.name}» رد شد: {reason}')

    # ── نتیجه بررسی نظرات مقاله ──
    for comment in article_comments_qs.filter(
        updated_at__gte=cutoff, status__in=('approved', 'rejected')
    ).select_related('article').order_by('-updated_at')[:NOTIFICATION_LIMIT]:
        when = comment.updated_at
        if comment.status == 'approved':
            add(when, 'check', 'دیدگاه شما تایید شد',
                f'دیدگاه شما در «{comment.article.title}» منتشر شد')
        else:
            reason = comment.rejection_reason or 'مطابق قوانین سایت نبود'
            add(when, 'x', 'دیدگاه شما تایید نشد',
                f'دیدگاه شما در «{comment.article.title}» رد شد: {reason}')

    events.sort(key=lambda item: item['when'], reverse=True)

    return [
        {
            'icon': event['icon'],
            'title': event['title'],
            'desc': event['desc'],
            'time': humanize_since(event['when']),
            'timestamp': event['when'].isoformat(),
            'unread': read_at is None or event['when'] > read_at,
        }
        for event in events[:NOTIFICATION_LIMIT]
    ]


class NotificationsMarkReadAPIView(APIView):
    """Mark every current notification as read for this session."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        now = timezone.now()
        request.session[NOTIFICATIONS_READ_AT_SESSION_KEY] = now.isoformat()
        request.session.modified = True
        return Response({'success': True, 'read_at': now.isoformat()})


class DashboardDataAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # ===== دریافت سفارشات =====
        orders_qs = user.orders.all()

        # ===== آمار =====
        total_orders = orders_qs.count()
        delivered_orders = orders_qs.filter(status='delivered').count()
        pending_orders = orders_qs.filter(status__in=['pending', 'processing']).count()

        # نظرات محصولات (QuerySet)
        product_comments_qs = ProductReview.objects.filter(user=user)
        approved_product_comments = product_comments_qs.filter(status='approved').count()
        pending_product_comments = product_comments_qs.filter(status='pending').count()

        # نظرات مقالات - همه‌ی وضعیت‌ها (approved/pending/rejected)
        article_comments_qs = Comment.objects.filter(user=user)
        approved_article_comments = article_comments_qs.filter(status='approved').count()
        pending_article_comments = article_comments_qs.filter(status='pending').count()

        stats = {
            'total_orders': total_orders,
            'delivered_orders': delivered_orders,
            'pending_orders': pending_orders,
            'approved_comments': approved_product_comments + approved_article_comments,
            'pending_comments': pending_product_comments + pending_article_comments,
            'wishlist_count': user.wishlist.count(),
        }

        # ===== آخرین سفارشات =====
        recent_orders = orders_qs.select_related('address').prefetch_related('items__product')[:5]
        recent_orders_data = OrderListSerializer(recent_orders, many=True).data

        # ===== نظرات کاربر (برای نمایش در بخش نظرات) =====
        comments_data = []

        # نظرات محصولات
        for comment in product_comments_qs.select_related('product').order_by('-created_at'):
            comments_data.append({
                'type': 'product',
                'product_name': comment.product.name,
                'product_slug': comment.product.slug,
                'product_image': comment.product.cover_image.url if comment.product.cover_image else None,
                'date': comment.created_at,
                'rating': comment.rating,
                'text': comment.comment,
                'status': comment.status,
                'reject_reason': comment.rejection_reason if comment.status == 'rejected' else None,
                'title': comment.title,
            })

        # نظرات مقالات
        for comment in article_comments_qs.select_related('article').order_by('-created_at'):
            comments_data.append({
                'type': 'article',
                'article_title': comment.article.title,
                'article_slug': comment.article.slug,
                'article_image': comment.article.cover_image.url if comment.article.cover_image else None,
                'date': comment.created_at,
                'rating': None,
                'text': comment.content,
                'status': comment.status,
                'reject_reason': comment.rejection_reason if comment.status == 'rejected' else None,
                'title': None,
            })

        # مرتب‌سازی نظرات بر اساس تاریخ
        comments_data.sort(key=lambda x: x['date'], reverse=True)

        # ===== علاقه‌مندی‌ها =====
        wishlist_data = []
        for item in user.wishlist.select_related('product').all():
            product = item.product
            wishlist_data.append({
                'id': item.id,
                'product_id': product.id,
                'product_name': product.name,
                'product_slug': product.slug,
                'product_image': product.cover_image.url if product.cover_image else None,
                'price': product.price,
                'discount_price': product.discount_price,
                'final_price': product.final_price,
                'in_stock': product.is_available and product.stock > 0,
            })

        # ===== آدرس‌ها =====
        addresses = user.addresses.filter(is_active=True).select_related('province', 'city')
        addresses_data = AddressSerializer(addresses, many=True).data

        # ===== اعلان‌ها =====
        notifications = build_user_notifications(
            user,
            orders_qs=orders_qs,
            product_comments_qs=product_comments_qs,
            article_comments_qs=article_comments_qs,
            read_at=get_notifications_read_at(request),
        )

        # ===== کاربر =====
        user_data = UserProfileSerializer(user).data

        data = {
            'user': user_data,
            'stats': stats,
            'recent_orders': recent_orders_data,
            'comments': comments_data[:20],
            'wishlist': wishlist_data,
            'addresses': addresses_data,
            'notifications': notifications,
        }

        return Response(data)


# apps/accounts/views.py

#: Avatars are served back from our own origin and embedded in comment and
#: review markup, so an .svg or .html "image" is a stored-XSS delivery vector.
#: Extension, declared type and sniffed magic bytes all have to agree.
ALLOWED_AVATAR_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'gif'}
ALLOWED_AVATAR_MIME_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
MAX_AVATAR_BYTES = 3 * 1024 * 1024  # 3 MB


def validate_avatar(uploaded):
    """Return an error message for a rejected avatar, or None if it passes."""
    if uploaded.size > MAX_AVATAR_BYTES:
        return 'حجم عکس نباید بیشتر از ۳ مگابایت باشد'

    ext = os.path.splitext(uploaded.name or '')[1].lstrip('.').lower()
    if ext not in ALLOWED_AVATAR_EXTENSIONS:
        return 'فرمت عکس مجاز نیست (فقط JPG، PNG، WebP یا GIF)'

    # content_type is client-supplied; checked so an obvious mismatch is
    # rejected early, but the magic-byte check below is what actually decides.
    if uploaded.content_type and uploaded.content_type not in ALLOWED_AVATAR_MIME_TYPES:
        return 'فرمت عکس مجاز نیست (فقط JPG، PNG، WebP یا GIF)'

    head = uploaded.read(261)
    uploaded.seek(0)
    kind = filetype.guess(head)
    if kind is None or kind.mime not in ALLOWED_AVATAR_MIME_TYPES:
        return 'فایل ارسالی یک تصویر معتبر نیست'

    # Last gate: Pillow has to be able to parse it as an actual image. This is
    # the check Model.save() skips.
    try:
        image = Image.open(uploaded)
        image.verify()
    except Exception:
        return 'فایل ارسالی یک تصویر معتبر نیست'
    finally:
        uploaded.seek(0)

    return None


class UserProfileUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'profile_update'

    def put(self, request):
        user = request.user

        # ===== ۱. اعتبارسنجی عکس =====
        # Assigning request.FILES straight onto the model field skipped every
        # check: Model.save() does not run full_clean(), so ImageField's
        # Pillow verification never fired, the extension came from the client
        # verbatim, and there was no size ceiling. Validate first, and only
        # persist once the rest of the payload has validated too.
        avatar = request.FILES.get('avatar')
        if avatar is not None:
            error = validate_avatar(avatar)
            if error:
                return Response(
                    {'avatar': [error]}, status=status.HTTP_400_BAD_REQUEST
                )

        # ===== ۲. بعد بقیه فیلدها رو با serializer بروزرسانی کن =====
        # اما profile_image رو نادیده بگیر
        serializer = UserUpdateSerializer(
            user,
            data=request.data,
            partial=True,
            context={'request': request}
        )

        if serializer.is_valid():
            if avatar is not None:
                user.profile_image = avatar
            # فقط فیلدهایی که میخوای رو جداگانه ست کن
            allowed_fields = ['fullname', 'username', 'email', 'mobile',
                              'national_code', 'birth_date', 'gender', 'bio']

            for field in allowed_fields:
                if field in serializer.validated_data:
                    setattr(user, field, serializer.validated_data[field])

            user.save()

            return Response(UserProfileSerializer(user).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AddressListCreateAPIView(APIView):
    """API برای لیست و ایجاد آدرس"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        addresses = request.user.addresses.filter(is_active=True).select_related('province', 'city')
        serializer = AddressSerializer(addresses, many=True)
        return Response(serializer.data)

    def post(self, request):
        data = request.data.copy()
        data['user'] = request.user.id
        serializer = AddressSerializer(data=data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AddressDeleteAPIView(APIView):
    """API برای حذف آدرس"""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        address = get_object_or_404(Address, pk=pk, user=request.user)
        address.is_active = False
        address.save()
        return Response({'message': 'آدرس با موفقیت حذف شد'})


class ProvinceListAPIView(generics.ListAPIView):
    """API برای لیست استان‌ها"""
    permission_classes = [AllowAny]
    serializer_class = ProvinceSerializer
    queryset = Province.objects.all()


class CityListAPIView(generics.ListAPIView):
    """API برای لیست شهرهای یک استان"""
    permission_classes = [AllowAny]
    serializer_class = CitySerializer

    def get_queryset(self):
        province_id = self.request.query_params.get('province')
        if province_id:
            return City.objects.filter(province_id=province_id)
        return City.objects.none()


class UserLogoutView(View):
    """خروج کاربر و ابطال کامل نشست (پشتیبانی از هر دو متد GET و POST)"""
    def dispatch(self, request, *args, **kwargs):
        django_logout(request)
        request.session.flush()
        return redirect('accounts_app:login')


class DashboardPageView(LoginRequiredMixin, TemplateView):
    """صفحه داشبورد کاربر"""
    template_name = 'accounts/user_dashboard.html'
    login_url = 'accounts_app:login'


class RulesView(TemplateView):
    """صفحه قوانین و مقررات"""
    template_name = 'accounts/rules.html'
