import logging
import secrets
from datetime import timedelta

from django.contrib.auth import login as django_login
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
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


# class LoginPageView(TemplateView):
#     template_name = 'accounts/login.html'
#
#     def post(self, request, *args, **kwargs):
#         form = AuthenticationForm(request, data=request.POST)
#         if form.is_valid():
#             user = form.get_user()
#             login(request, user)
#
#
#             if user.is_staff:
#                 return redirect('home_app:admin_dashboard')
#             return redirect('home_app:index')
#
#         return self.render_to_response({'form': form})

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

        if otp.code_hash != PasswordResetOTP.hash_code(code):
            otp.attempts = models.F('attempts') + 1
            otp.save(update_fields=['attempts'])
            return generic_error

        # کد درسته → یکبار مصرفش کن، reset_token بده
        raw_token = secrets.token_urlsafe(32)
        otp.reset_token = PasswordResetOTP.hash_code(raw_token)  # هش شده ذخیره میشه
        otp.is_used = True
        otp.save(update_fields=['reset_token', 'is_used'])

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

        token_expiry = otp.created_at + timedelta(minutes=PasswordResetOTP.RESET_TOKEN_LIFETIME_MINUTES)
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


# apps/accounts/views.py

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

        # نظرات مقالات (QuerySet) - اینجا نباید count() بزنی
        article_comments_qs = Comment.objects.filter(user=user, is_approved=True)  # ← بدون count()
        article_comments_count = article_comments_qs.count()  # ← تعداد رو اینجا بگیر

        stats = {
            'total_orders': total_orders,
            'delivered_orders': delivered_orders,
            'pending_orders': pending_orders,
            'approved_comments': approved_product_comments + article_comments_count,  # ← از عدد استفاده کن
            'pending_comments': pending_product_comments,
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

        # نظرات مقالات - از QuerySet استفاده کن
        for comment in article_comments_qs.select_related('article').order_by('-created_at'):  # ← حالا درسته
            comments_data.append({
                'type': 'article',
                'article_title': comment.article.title,
                'article_slug': comment.article.slug,
                'article_image': comment.article.cover_image.url if comment.article.cover_image else None,
                'date': comment.created_at,
                'rating': None,
                'text': comment.content,
                'status': 'approved' if comment.is_approved else 'pending',
                'reject_reason': None,
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
        notifications = [
            {'icon': 'truck', 'title': 'سفارش شما ارسال شد',
             'desc': 'سفارش شما تحویل پست شد', 'time': '۲ ساعت پیش', 'unread': True},
        ]

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

class UserProfileUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        user = request.user

        # ===== ۱. اول عکس رو ذخیره کن =====
        if 'avatar' in request.FILES:
            user.profile_image = request.FILES['avatar']
            user.save(update_fields=['profile_image'])

        # ===== ۲. بعد بقیه فیلدها رو با serializer بروزرسانی کن =====
        # اما profile_image رو نادیده بگیر
        serializer = UserUpdateSerializer(
            user,
            data=request.data,
            partial=True,
            context={'request': request}
        )

        if serializer.is_valid():
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
    permission_classes = [IsAuthenticated]
    serializer_class = ProvinceSerializer
    queryset = Province.objects.all()


class CityListAPIView(generics.ListAPIView):
    """API برای لیست شهرهای یک استان"""
    permission_classes = [IsAuthenticated]
    serializer_class = CitySerializer

    def get_queryset(self):
        province_id = self.request.query_params.get('province')
        if province_id:
            return City.objects.filter(province_id=province_id)
        return City.objects.none()


@method_decorator(login_required(login_url='/accounts/login/'), name='dispatch')
class DashboardPageView(TemplateView):
    """صفحه داشبورد کاربر"""
    template_name = 'accounts/user_dashboard.html'