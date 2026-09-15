# apps/shop/views.py

from datetime import timedelta, datetime
from decimal import Decimal

import jdatetime
from django.db import transaction
from django.db.models import F, Q, Count, Avg, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.http import HttpResponsePermanentRedirect, HttpResponseForbidden
import logging
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.views.generic import DetailView, ListView, RedirectView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

logger = logging.getLogger(__name__)

from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import CustomUser, Province, City, Address
from apps.seo import schema
from apps.seo.cache import cached_page_class
from apps.seo.seo import SEOMixin
from apps.seo.utils import canonical_url, image_url, meta_description, meta_title

from .models import (
    Product, Category, ProductReview, Wishlist, Cart, CartItem, ProductImage,
    Order, OrderItem, Transaction, RefundRequest, Coupon
)
from .pagination import ProductPagination
from .serializers import (
    ProductListSerializer, ProductDetailSerializer,
    ProductReviewSerializer, ProductReviewCreateSerializer,
    WishlistSerializer, CategorySerializer, CategoryDetailSerializer,
    OrderCreateSerializer, CartItemSerializer, OrderListSerializer,
    AdminProductReviewSerializer, CartSerializer
)
from django.views import View
from .utils.coupon_utils import CouponManager
from .utils.inventory_utils import InventoryManager, InsufficientStockError
from .utils.shipping_utils import ShippingCalculator
from .utils.tax_utils import TaxCalculator
from .services.payment import PaymentGatewayFactory


# ============================================
# PRODUCT API VIEWS
# ============================================

class ProductListAPIView(generics.ListAPIView):
    """API برای لیست محصولات"""
    permission_classes = [AllowAny]
    serializer_class = ProductListSerializer
    pagination_class = ProductPagination

    def get_queryset(self):
        # for_listing() carries select_related('category') plus the review
        # count/average annotations, so serializing a page of products no
        # longer fires three extra queries per row.
        qs = Product.objects.for_listing().annotate(
            # `final_price` is a Python property and cannot be filtered on in
            # SQL — the previous min_price/max_price filters raised FieldError
            # for every request that used them.
            effective_price=Coalesce('discount_price', 'price')
        )

        # جستجو
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))

        # فیلتر بر اساس دسته‌بندی
        category = self.request.query_params.get('category', '').strip()
        if category:
            qs = qs.filter(category__slug=category)

        # فیلتر بر اساس قیمت
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        if min_price:
            qs = qs.filter(effective_price__gte=min_price)
        if max_price:
            qs = qs.filter(effective_price__lte=max_price)

        # مرتب‌سازی
        sort = self.request.query_params.get('sort', '-created_at')
        valid_sorts = {
            'price': 'effective_price', '-price': '-effective_price',
            'created_at': 'created_at', '-created_at': '-created_at',
            'view_count': 'view_count', '-view_count': '-view_count',
        }
        return qs.order_by(valid_sorts.get(sort, '-created_at'))


class CategoryDetailAPIView(generics.RetrieveAPIView):
    """API برای نمایش یک کتگوری با محصولات و اسلایدر"""
    permission_classes = [AllowAny]
    serializer_class = CategoryDetailSerializer
    lookup_field = 'slug'
    lookup_url_kwarg = 'slug'

    def get_queryset(self):
        return (
            Category.objects.filter(is_active=True)
            .select_related('parent')
            .prefetch_related('hero_products__product', 'products')
        )


class ProductDetailAPIView(generics.RetrieveAPIView):
    """API برای نمایش جزئیات یک محصول"""
    permission_classes = [AllowAny]
    serializer_class = ProductDetailSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        return Product.objects.for_detail()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # F() increments in the database instead of read-modify-write, which
        # both avoids losing concurrent hits and skips re-writing the whole row.
        Product.objects.filter(pk=instance.pk).update(view_count=F('view_count') + 1)

        serializer = self.get_serializer(instance, context={'request': request})
        return Response(serializer.data)


class CategoryListAPIView(generics.ListAPIView):
    """API برای لیست دسته‌بندی‌ها"""
    permission_classes = [AllowAny]
    serializer_class = CategorySerializer
    pagination_class = None

    def get_queryset(self):
        return (
            Category.objects.filter(is_active=True, parent__isnull=True)
            .prefetch_related('children')
        )


class ProductReviewListCreateAPIView(APIView):
    """API برای لیست و ایجاد نظرات محصول"""
    permission_classes = [IsAuthenticatedOrReadOnly]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'review'

    def get(self, request, slug):
        """گرفتن نظرات تایید شده یک محصول"""
        product = get_object_or_404(Product, slug=slug, is_published=True)
        reviews = product.reviews.filter(status='approved').order_by('-created_at')
        serializer = ProductReviewSerializer(reviews, many=True)
        return Response(serializer.data)

    def post(self, request, slug):
        """ایجاد نظر جدید برای محصول"""
        product = get_object_or_404(Product, slug=slug, is_published=True)

        if not request.user.is_authenticated:
            return Response(
                {'detail': 'برای ثبت نظر باید وارد حساب کاربری خود شوید.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # چک کردن اینکه کاربر قبلاً برای این محصول نظر نداده باشد
        existing = ProductReview.objects.filter(
            product=product,
            user=request.user,
            status__in=['pending', 'approved']
        ).exists()
        if existing:
            return Response(
                {'detail': 'شما قبلاً برای این محصول نظر ثبت کرده‌اید.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ProductReviewCreateSerializer(
            data=request.data,
            context={'request': request, 'product_id': product.id}
        )

        if serializer.is_valid():
            review = serializer.save()
            return Response(
                ProductReviewSerializer(review).data,
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class WishlistToggleAPIView(APIView):
    #: Without this the project-wide DEFAULT_PERMISSION_CLASSES (IsAuthenticated)
    #: rejected anonymous callers with a bare 403 {"detail": ...} before post()
    #: ever ran, so the login_required branch below was unreachable and the
    #: client fell through to its generic "خطا در عملیات" message. CartAPIView
    #: opts out the same way so that Add to Cart can return its own 401 payload;
    #: the like button now behaves identically.
    permission_classes = [AllowAny]

    def post(self, request, slug=None):
        if not request.user.is_authenticated:
            referer = request.META.get('HTTP_REFERER', '/shop/')
            login_url = f"{reverse('accounts_app:login')}?next={referer}"
            return Response({
                'status': 'login_required',
                'login_required': True,
                'error': 'برای افزودن به علاقه‌مندی‌ها، لطفاً ابتدا وارد حساب کاربری شوید.',
                'login_url': login_url,
            }, status=status.HTTP_401_UNAUTHORIZED)
        if slug:
            product = get_object_or_404(Product, slug=slug, is_published=True)
        else:
            product_id = request.data.get('product_id')
            if not product_id:
                return Response(
                    {'error': 'شناسه محصول الزامی است'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            product = get_object_or_404(Product, id=product_id, is_published=True)

        wishlist_item = Wishlist.objects.filter(user=request.user, product=product)

        if wishlist_item.exists():
            wishlist_item.delete()
            return Response({
                'status': 'removed',
                'message': 'از علاقه‌مندی‌ها حذف شد.',
                'is_in_wishlist': False
            })
        else:
            Wishlist.objects.create(user=request.user, product=product)
            return Response({
                'status': 'added',
                'message': 'به علاقه‌مندی‌ها اضافه شد.',
                'is_in_wishlist': True
            })


class WishlistListAPIView(generics.ListAPIView):
    """API برای لیست علاقه‌مندی‌های کاربر"""
    permission_classes = [IsAuthenticated]
    serializer_class = WishlistSerializer
    pagination_class = ProductPagination

    def get_queryset(self):
        return (
            Wishlist.objects.filter(user=self.request.user)
            .select_related('product', 'product__category')
            .order_by('-created_at')
        )


# ══════════════════════════════════════════════════════════════════════
#  HTML pages
# ══════════════════════════════════════════════════════════════════════

FACET_PARAMS = {
    'search', 'q', 'sort', 'order', 'color', 'price', 'min_price',
    'max_price', 'filter', 'tag', 'brand', 'availability',
}

PRODUCTS_PER_PAGE = 24


def _is_faceted(request):
    return any(param in request.GET for param in FACET_PARAMS)


@cached_page_class()
class ProductDetailPageView(SEOMixin, DetailView):
    """صفحه جزئیات محصول"""
    template_name = 'shop/product_detail.html'
    context_object_name = 'product'
    seo_og_type = 'product'

    def get_queryset(self):
        return Product.objects.for_detail()

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        # A discontinued product is a dead end: redirect its accumulated link
        # equity to the replacement, or failing that to its category, rather
        # than leaving a live page for something nobody can buy.
        if self.object.is_discontinued:
            if self.object.replacement_product_id:
                target = self.object.replacement_product.get_absolute_url()
            else:
                target = self.object.category.get_absolute_url()
            return HttpResponsePermanentRedirect(target)

        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        product = self.object
        # Attached before super() so the schema builder can read them.
        product.gallery_images = list(product.images.all())
        self.seo_title = product.meta_title or product.name
        self.seo_description = meta_description(
            product.meta_description, product.tagline, product.description
        )

        context = super().get_context_data(**kwargs)
        context['slug'] = product.slug
        context['gallery_images'] = product.gallery_images
        context['reviews'] = self._reviews
        context['specs'] = list(product.specs.all())
        context['trust_badges'] = list(product.trust_badges.all())
        context['marketing_features'] = list(product.marketing_features.all())
        context['stat_features'] = list(product.stat_features.all())
        # Out-of-stock but returning: keep the page indexed and offer a route
        # onward instead of letting it read as a dead product.
        context['related_products'] = (
            Product.objects.for_listing()
            .filter(category_id=product.category_id)
            .exclude(pk=product.pk)[:4]
            if not product.is_in_stock else []
        )
        return context

    @cached_property
    def _reviews(self):
        return list(
            self.object.reviews.filter(status='approved')
            .select_related('user')
            .order_by('-created_at')[:20]
        )

    def get_seo_image(self, context):
        return image_url(self.object.cover_image, self.request)

    def get_breadcrumbs(self, context):
        product = self.object
        trail = [('خانه', '/'), ('محصولات', reverse('shop:product_list'))]
        category = product.category
        if category.parent_id:
            trail.append((category.parent.name, category.parent.get_absolute_url()))
        trail.append((category.name, category.get_absolute_url()))
        trail.append((product.name, product.get_absolute_url()))
        return trail

    def get_json_ld(self, context, seo):
        return [
            schema.product(self.object, self.request, reviews=self._reviews),
            schema.breadcrumbs(seo.breadcrumbs, self.request),
        ]

    def get_seo(self, context):
        seo = super().get_seo(context)
        seo.image_alt = self.object.cover_alt_text or self.object.name
        seo.modified_time = self.object.updated_at
        return seo


class BaseProductListView(SEOMixin, ListView):
    """Shared behaviour for the all-products page and category pages."""

    template_name = 'shop/category_products.html'
    context_object_name = 'products'
    paginate_by = PRODUCTS_PER_PAGE

    def get_queryset(self):
        return Product.objects.for_listing()

    def get_canonical_path(self):
        return self.request.path

    def get_seo(self, context):
        seo = super().get_seo(context)
        page_obj = context.get('page_obj')

        if _is_faceted(self.request):
            # Filtered and sorted permutations are infinite and near-duplicate:
            # keep them out of the index but let crawlers follow through to the
            # products, and fold their signals into the clean listing URL.
            seo.robots = 'noindex, follow'
            seo.canonical = canonical_url(self.request, self.get_canonical_path())
            return seo

        if page_obj and page_obj.number > 1:
            # Each paginated page is a distinct set of products, so it gets a
            # self-referencing canonical and its own title/description rather
            # than canonicalising back to page 1 (which would hide pages 2+
            # from the crawler entirely).
            seo.canonical = self._page_url(page_obj.number)
            seo.title = meta_title(f'{self._base_title} — صفحه {page_obj.number}')
            seo.description = meta_description(
                f'صفحه {page_obj.number} از {self._base_title}. {seo.description}'
            )
        if page_obj and page_obj.has_previous():
            seo.prev_url = self._page_url(page_obj.previous_page_number())
        if page_obj and page_obj.has_next():
            seo.next_url = self._page_url(page_obj.next_page_number())
        return seo

    def _page_url(self, number):
        base = canonical_url(self.request, self.get_canonical_path())
        return base if number == 1 else f'{base}?page={number}'

    @property
    def _base_title(self):
        return self.seo_title

    def get_json_ld(self, context, seo):
        return [
            schema.item_list(context['products'], self.request, name=self._base_title),
            schema.breadcrumbs(seo.breadcrumbs, self.request),
        ]


@cached_page_class()
class ProductListPageView(BaseProductListView):
    """صفحه لیست همه محصولات"""

    seo_title = 'اسکوتر برقی'
    seo_description = (
        'خرید اسکوتر برقی نکس گو؛ مقایسه قیمت، برد، سرعت و زمان شارژ همه مدل‌ها '
        'با گارانتی ۳ ساله و ارسال سریع به سراسر ایران.'
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # رشته خالی به JS می‌گوید این صفحه، لیست کل محصولات است نه یک کتگوری
        context['category_slug'] = ''
        return context

    def get_breadcrumbs(self, context):
        return [('خانه', '/'), ('محصولات', reverse('shop:product_list'))]


@cached_page_class()
class CategoryPageView(BaseProductListView):
    """صفحه نمایش محصولات یک کتگوری"""

    def get(self, request, *args, **kwargs):
        self.category = get_object_or_404(
            Category.objects.select_related('parent'),
            slug=self.kwargs['slug'],
            is_active=True,
        )
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        # Include products of child categories so a parent category page is
        # not an empty listing (a classic soft-404).
        category_ids = [self.category.pk] + list(
            self.category.children.filter(is_active=True).values_list('pk', flat=True)
        )
        return Product.objects.for_listing().filter(category_id__in=category_ids)

    @property
    def _base_title(self):
        return self.category.meta_title or self.category.name

    def get_context_data(self, **kwargs):
        self.seo_title = self._base_title
        self.seo_description = meta_description(
            self.category.meta_description,
            self.category.description,
            f'خرید {self.category.name} نکس گو با گارانتی رسمی، قیمت شفاف و ارسال '
            f'سریع. مقایسه مشخصات فنی همه مدل‌های {self.category.name}.',
        )
        context = super().get_context_data(**kwargs)
        context['category'] = self.category
        context['slug'] = self.category.slug
        context['category_slug'] = self.category.slug
        context['hero_products'] = [
            hp.product
            for hp in self.category.hero_products.select_related('product').all()[:5]
        ]
        return context

    def get_canonical_path(self):
        return self.category.get_absolute_url()

    def get_seo_image(self, context):
        hero = context.get('hero_products')
        if hero:
            return image_url(hero[0].cover_image, self.request)
        products = context.get('products')
        if products:
            return image_url(products[0].cover_image, self.request)
        return ''

    def get_breadcrumbs(self, context):
        trail = [('خانه', '/'), ('محصولات', reverse('shop:product_list'))]
        if self.category.parent_id:
            trail.append((self.category.parent.name, self.category.parent.get_absolute_url()))
        trail.append((self.category.name, self.category.get_absolute_url()))
        return trail


class LegacyProductRedirectView(RedirectView):
    """301 from the old /shop/<slug>/ catch-all onto /shop/product/<slug>/."""

    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        product = get_object_or_404(
            Product.objects.only('slug'), slug=kwargs['slug'], is_published=True
        )
        return product.get_absolute_url()


ProductPageView = ProductDetailPageView



class AdminDashboardStatsAPIView(APIView):
    """API برای دریافت آمار داشبورد ادمین"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        user = request.user

        # ===== تاریخ امروز =====
        today = timezone.now().date()

        # ===== 1. کل محصولات فعال =====
        total_products = Product.objects.filter(is_available=True, is_published=True).count()

        # ===== 2. سفارش‌های امروز =====
        today_orders = Order.objects.filter(created_at__date=today).count()

        # ===== 3. کل مشتریان =====
        total_customers = CustomUser.objects.filter(is_active=True).count()

        # ===== 4. درآمد ماهانه (فقط سفارش‌های پرداخت شده) =====
        first_day_of_month = today.replace(day=1)
        monthly_revenue = Order.objects.filter(
            payment_status='paid',
            created_at__gte=first_day_of_month
        ).aggregate(total=Sum('total'))['total'] or 0

        # تبدیل به میلیون تومان
        monthly_revenue_million = monthly_revenue / 1_000_000

        # ===== 5. روند فروش ماهانه (۱۲ ماه اخیر) =====
        end_date = today
        start_date = today - timedelta(days=365)

        sales_data = Order.objects.filter(
            payment_status='paid',
            created_at__gte=start_date,
            created_at__lte=end_date
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            total=Sum('total')
        ).order_by('month')

        # ایجاد لیست کامل ۱۲ ماه با نام‌های فارسی
        month_names_fa = {
            1: 'فروردین', 2: 'اردیبهشت', 3: 'خرداد', 4: 'تیر',
            5: 'مرداد', 6: 'شهریور', 7: 'مهر', 8: 'آبان',
            9: 'آذر', 10: 'دی', 11: 'بهمن', 12: 'اسفند'
        }

        months = []
        for i in range(11, -1, -1):
            month_date = today - timedelta(days=30 * i)
            try:
                j_date = jdatetime.date.fromgregorian(date=month_date)
                month_num = j_date.month
                year_val = j_date.year
            except Exception:
                month_num = month_date.month
                year_val = month_date.year
            month_name = month_names_fa.get(month_num, str(month_num))
            months.append({
                'month': month_name,
                'year': year_val,
                'total': 0
            })

        for data in sales_data:
            if data['month']:
                try:
                    d_val = data['month'].date() if hasattr(data['month'], 'date') else data['month']
                    month_num = jdatetime.date.fromgregorian(date=d_val).month
                except Exception:
                    month_num = data['month'].month
                month_name = month_names_fa.get(month_num, str(month_num))
                for m in months:
                    if m['month'] == month_name:
                        m['total'] = float(data['total']) / 1_000_000
                        break

        monthly_sales = months

        # ===== 6. ۶ سفارش آخر =====
        recent_orders = Order.objects.select_related(
            'user', 'address'
        ).prefetch_related(
            'items__product'
        ).order_by('-created_at')[:6]

        recent_orders_data = []
        for order in recent_orders:
            products = order.items.all()
            product_names = [item.product.name for item in products]

            recent_orders_data.append({
                'order_number': order.order_number,
                'customer_name': order.user.fullname or order.user.username,
                'customer_username': order.user.username,
                'customer_avatar': order.user.profile_image.url if order.user.profile_image else None,
                'products': product_names,
                'total': float(order.total),
                'status': order.status,
                'status_label': dict(Order.STATUS_CHOICES).get(order.status, order.status),
                'created_at': order.created_at.isoformat(),
                'payment_status': order.payment_status,
            })

        # ===== 7. پرفروش‌ترین محصولات ماه =====
        start_of_month = today.replace(day=1)
        top_products = OrderItem.objects.filter(
            order__payment_status='paid',
            order__created_at__gte=start_of_month
        ).values(
            'product_id', 'product__name', 'product__cover_image'
        ).annotate(
            total_sold=Sum('quantity'),
            total_revenue=Sum('price')
        ).order_by('-total_sold')[:4]

        top_products_data = []
        for item in top_products:
            top_products_data.append({
                'product_id': item['product_id'],
                'name': item['product__name'],
                'cover_image': item['product__cover_image'],
                'total_sold': item['total_sold'] or 0,
                'total_revenue': float(item['total_revenue'] or 0),
            })

        # ===== 8. فعالیت‌های اخیر =====
        recent_activities = []

        if recent_orders:
            for order in recent_orders[:3]:
                recent_activities.append({
                    'icon': 'fa-cart-shopping',
                    'title': 'سفارش جدید دریافت شد',
                    'description': f'سفارش {order.order_number}',
                    'time': self._get_time_ago(order.created_at),
                    'color': 'blue'
                })

        recent_products = Product.objects.filter(is_published=True).order_by('-created_at')[:2]
        for product in recent_products:
            recent_activities.append({
                'icon': 'fa-box',
                'title': 'محصول جدید اضافه شد',
                'description': product.name,
                'time': self._get_time_ago(product.created_at),
                'color': 'purple'
            })

        # ===== 9. اعلان‌ها =====
        notifications = []

        low_stock_products = Product.objects.filter(stock__lt=5, is_available=True)[:3]
        for product in low_stock_products:
            notifications.append({
                'priority_color': '#ef4444',
                'icon': 'fa-triangle-exclamation',
                'icon_color': 'red',
                'title': 'هشدار موجودی انبار',
                'description': f'موجودی «{product.name}» کمتر از ۵ واحد است',
                'time': 'همین حالا'
            })

        for order in recent_orders[:2]:
            notifications.append({
                'priority_color': '#3b82f6',
                'icon': 'fa-cart-shopping',
                'icon_color': 'blue',
                'title': 'سفارش جدید ثبت شد',
                'description': f'سفارش {order.order_number} به ارزش {int(order.total):,} تومان',
                'time': self._get_time_ago(order.created_at)
            })

        # ===== تاریخ امروز به شمسی =====
        try:
            today_jalali = jdatetime.date.fromgregorian(date=today)
            weekdays_fa = {
                'Saturday': 'شنبه', 'Sunday': 'یکشنبه', 'Monday': 'دوشنبه',
                'Tuesday': 'سه‌شنبه', 'Wednesday': 'چهارشنبه', 'Thursday': 'پنجشنبه',
                'Friday': 'جمعه'
            }
            weekday_fa = weekdays_fa.get(today.strftime('%A'), '')

            # روش امن برای گرفتن نام ماه
            month_names_fa_full = {
                1: 'فروردین', 2: 'اردیبهشت', 3: 'خرداد', 4: 'تیر',
                5: 'مرداد', 6: 'شهریور', 7: 'مهر', 8: 'آبان',
                9: 'آذر', 10: 'دی', 11: 'بهمن', 12: 'اسفند'
            }
            month_name = month_names_fa_full.get(today_jalali.month, '')
            today_date = f"{weekday_fa}، {today_jalali.day} {month_name} {today_jalali.year}"
        except:
            # اگر jdatetime نصب نبود، از تاریخ میلادی استفاده کن
            today_date = today.strftime('%A, %B %d, %Y')

        data = {
            'user': {
                'fullname': user.fullname or user.username,
                'profile_image': user.profile_image.url if user.profile_image else None,
                'bio': user.bio or 'مدیر فروشگاه',
                'username': user.username,
            },
            'stats': {
                'total_products': total_products,
                'today_orders': today_orders,
                'total_customers': total_customers,
                'monthly_revenue': round(monthly_revenue_million, 1),
                'trends': {
                    'products_trend': '+8.2',
                    'orders_trend': '+12.4',
                    'customers_trend': '+5.1',
                    'revenue_trend': '-2.3',
                }
            },
            'monthly_sales': monthly_sales,
            'recent_orders': recent_orders_data,
            'top_products': top_products_data,
            'recent_activities': recent_activities,
            'notifications': notifications,
            'today_date': today_date,
        }

        return Response(data)

    def _get_time_ago(self, dt):
        """محاسبه زمان گذشته به فارسی"""
        now = timezone.now()
        diff = now - dt

        seconds = int(diff.total_seconds())

        if seconds < 60:
            return 'لحظاتی پیش'
        elif seconds < 3600:
            minutes = seconds // 60
            return f'{minutes} دقیقه پیش'
        elif seconds < 86400:
            hours = seconds // 3600
            return f'{hours} ساعت پیش'
        elif seconds < 604800:
            days = seconds // 86400
            return f'{days} روز پیش'
        else:
            return dt.strftime('%Y/%m/%d')


class CartAPIView(APIView):
    permission_classes = [AllowAny]

    def get_cart(self, request):
        """دریافت یا ایجاد سبد خرید فعال کاربر"""
        if not request.user.is_authenticated:
            return None
        cart, created = Cart.objects.get_or_create(
            user=request.user,
            defaults={'is_active': True}
        )
        if not cart.is_active:
            cart.is_active = True
            cart.save()
        return cart

    def get(self, request):
        """نمایش سبد خرید"""
        # کاربران مهمان سبد خرید ندارند — پاسخ ایمن بازمی‌گردد
        if not request.user.is_authenticated:
            return self._empty_cart_response()

        cart = self.get_cart(request)

        if not cart.items.exists():
            return self._empty_cart_response()

        items_data = []
        item_count = 0
        subtotal = Decimal('0')
        discount_total = Decimal('0')

        for item in cart.items.select_related('product').all():
            product = item.product
            quantity = item.quantity
            price = Decimal(str(product.price))
            discount_price = Decimal(str(product.discount_price)) if product.discount_price else Decimal('0')

            item_subtotal = price * quantity
            item_discount = (price - discount_price) * quantity if product.discount_price else Decimal('0')

            subtotal += item_subtotal
            discount_total += item_discount
            item_count += quantity

            available_colors = product.images.values('color_slug', 'color_label', 'color_hex').distinct()
            selected_color = self._get_selected_color(request, product.id)

            specs = product.specs.all()[:2]
            short_specs = ' | '.join([f"{s.label}: {s.value}" for s in specs])

            delivery_date = datetime.now() + timedelta(days=3)

            items_data.append({
                'product_id': product.id,
                'product_name': product.name,
                'product_slug': product.slug,
                'product_image': product.cover_image.url if product.cover_image else None,
                'short_specs': short_specs,
                'warranty_months': 12,
                'available_colors': [
                    {
                        'slug': c['color_slug'],
                        'name': c['color_label'],
                        'hex': c['color_hex'],
                        'selected': c['color_slug'] == selected_color.get('slug')
                    }
                    for c in available_colors
                ],
                'selected_color': selected_color,
                'quantity': quantity,
                'original_price': int(price),
                'final_price': int(discount_price) if product.discount_price else int(price),
                'saving_amount': int(price - discount_price) if product.discount_price else 0,
                'estimated_delivery': delivery_date.strftime('%d %B %Y'),
                'item_subtotal': int(item_subtotal),
                'item_discount': int(item_discount),
                'total': int(item_subtotal),
            })

        # کوپن هر بار از نو بررسی و محاسبه می‌شود: مبلغ سبد خرید از وقتی کد
        # اعمال شده تغییر کرده و ممکن است کوپن در این فاصله منقضی یا غیرفعال
        # شده باشد. مقدار ذخیره‌شده روی سبد فقط یک snapshot برای نمایش است.
        coupon_discount, coupon_code = self._sync_cart_coupon(
            cart, request.user, subtotal - discount_total
        )

        # محاسبه مالیات و هزینه ارسال (با توابع فرضی)
        tax_amount = self._calculate_tax(subtotal)
        shipping_method = request.query_params.get('shipping_method', 'standard')
        shipping_cost = self._calculate_shipping(subtotal, shipping_method)
        final_total = subtotal - discount_total - coupon_discount + shipping_cost + tax_amount

        return Response({
            'items': items_data,
            'item_count': item_count,
            'subtotal': int(subtotal),
            'discount_total': int(discount_total),
            'shipping_cost': int(shipping_cost),
            'shipping_methods': self._get_shipping_methods(),
            'selected_shipping_method': shipping_method,
            'applied_coupon': coupon_code,
            'coupon_discount': int(coupon_discount),
            'tax_amount': int(tax_amount),
            'final_total': int(max(Decimal('0'), final_total)),
            'estimated_delivery': 3,
        })

    def post(self, request):
        """افزودن محصول به سبد خرید"""
        if not request.user.is_authenticated:
            referer = request.META.get('HTTP_REFERER', '/shop/')
            login_url = f"{reverse('accounts_app:login')}?next={referer}"
            return Response({
                'status': 'login_required',
                'login_required': True,
                'error': 'برای افزودن محصول به سبد خرید، لطفاً ابتدا وارد حساب کاربری شوید.',
                'login_url': login_url,
            }, status=status.HTTP_401_UNAUTHORIZED)

        product_id = request.data.get('product_id')
        quantity = int(request.data.get('quantity', 1))
        color_slug = request.data.get('color_slug', 'black')

        if not product_id:
            return Response(
                {'error': 'شناسه محصول الزامی است'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            product = Product.objects.get(id=product_id, is_published=True, is_available=True)
        except Product.DoesNotExist:
            return Response(
                {'error': 'محصول یافت نشد یا در دسترس نیست'},
                status=status.HTTP_404_NOT_FOUND
            )

        if product.stock < quantity:
            return Response(
                {'error': f'موجودی کافی نیست. موجودی: {product.stock}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        cart = self.get_cart(request)

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={
                'quantity': quantity,
                'color_slug': color_slug,
                'price_snapshot': product.final_price,
            }
        )

        if not created:
            cart_item.quantity += quantity
            if color_slug:
                cart_item.color_slug = color_slug
            cart_item.save()

        total_items = cart.items.aggregate(Sum('quantity'))['quantity__sum'] or 0

        return Response({
            'status': 'added',
            'message': 'محصول به سبد خرید اضافه شد',
            'item_count': total_items,
        }, status=status.HTTP_201_CREATED)

    def put(self, request):
        """به‌روزرسانی تعداد یک آیتم در سبد خرید"""
        if not request.user.is_authenticated:
            return Response({
                'status': 'login_required',
                'login_required': True,
                'error': 'برای ویرایش سبد خرید، لطفاً ابتدا وارد حساب کاربری شوید.',
                'login_url': reverse('accounts_app:login'),
            }, status=status.HTTP_401_UNAUTHORIZED)

        product_id = request.data.get('product_id')
        quantity = int(request.data.get('quantity', 1))

        if not product_id:
            return Response(
                {'error': 'شناسه محصول الزامی است'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if quantity < 1:
            return self.delete(request)

        cart = self.get_cart(request)

        try:
            cart_item = CartItem.objects.get(cart=cart, product_id=product_id)
        except CartItem.DoesNotExist:
            return Response(
                {'error': 'آیتم در سبد خرید یافت نشد'},
                status=status.HTTP_404_NOT_FOUND
            )

        if cart_item.product.stock < quantity:
            return Response(
                {'error': f'موجودی کافی نیست. موجودی: {cart_item.product.stock}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        cart_item.quantity = quantity
        cart_item.save()

        # Return the full cart so the frontend can update all totals
        return self.get(request)

    def patch(self, request):
        """به‌روزرسانی آیتم سبد خرید (رنگ یا تعداد)"""
        if not request.user.is_authenticated:
            return Response({
                'status': 'login_required',
                'login_required': True,
                'error': 'برای ویرایش سبد خرید، لطفاً ابتدا وارد حساب کاربری شوید.',
                'login_url': reverse('accounts_app:login'),
            }, status=status.HTTP_401_UNAUTHORIZED)

        product_id = request.data.get('product_id')
        color_slug = request.data.get('color_slug')
        quantity = request.data.get('quantity')

        if not product_id:
            return Response(
                {'detail': 'product_id الزامی است'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response(
                {'detail': 'محصول یافت نشد'},
                status=status.HTTP_404_NOT_FOUND
            )

        cart = self.get_cart(request)

        try:
            cart_item = CartItem.objects.get(cart=cart, product=product)
        except CartItem.DoesNotExist:
            return Response(
                {'detail': 'آیتم در سبد خرید یافت نشد'},
                status=status.HTTP_404_NOT_FOUND
            )

        # به‌روزرسانی رنگ
        if color_slug is not None:
            cart_item.color_slug = color_slug

        # به‌روزرسانی تعداد
        if quantity is not None:
            quantity = int(quantity)
            if quantity <= 0:
                cart_item.delete()
            else:
                if cart_item.product.stock < quantity:
                    return Response(
                        {'detail': f'موجودی کافی نیست. موجودی: {cart_item.product.stock}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                cart_item.quantity = quantity
                cart_item.save()

        # ✅ برگرداندن سبد خرید به‌روز شده با متد GET
        return self.get(request)

    def delete(self, request):
        """حذف یک آیتم از سبد خرید"""
        if not request.user.is_authenticated:
            return Response({
                'status': 'login_required',
                'login_required': True,
                'error': 'برای ویرایش سبد خرید، لطفاً ابتدا وارد حساب کاربری شوید.',
                'login_url': reverse('accounts_app:login'),
            }, status=status.HTTP_401_UNAUTHORIZED)

        product_id = request.data.get('product_id')

        if not product_id:
            return Response(
                {'error': 'شناسه محصول الزامی است'},
                status=status.HTTP_400_BAD_REQUEST
            )

        cart = self.get_cart(request)

        CartItem.objects.filter(cart=cart, product_id=product_id).delete()

        response = self.get(request)
        response.data['status'] = 'removed'
        response.data['message'] = 'محصول از سبد خرید حذف شد'
        return response

    # ===== متدهای کمکی =====

    def _empty_cart_response(self):
        """پاسخ برای سبد خالی"""
        return Response({
            'items': [],
            'item_count': 0,
            'subtotal': 0,
            'discount_total': 0,
            'shipping_cost': 0,
            'shipping_methods': self._get_shipping_methods(),
            'selected_shipping_method': 'standard',
            'applied_coupon': None,
            'coupon_discount': 0,
            'tax_amount': 0,
            'final_total': 0,
            'estimated_delivery': 3,
        })

    def _get_selected_color(self, request, product_id):
        """دریافت رنگ انتخاب‌شده برای محصول"""
        color_slug = request.query_params.get(f'color_{product_id}', 'black')

        color = ProductImage.objects.filter(
            product_id=product_id,
            color_slug=color_slug
        ).first()

        if color:
            return {
                'slug': color.color_slug,
                'name': color.color_label,
                'hex': color.color_hex,
            }

        default_color = ProductImage.objects.filter(product_id=product_id).first()
        if default_color:
            return {
                'slug': default_color.color_slug,
                'name': default_color.color_label,
                'hex': default_color.color_hex,
            }

        return {'slug': 'black', 'name': 'مشکی', 'hex': '#1A1A1A'}

    def _calculate_tax(self, subtotal):
        """محاسبه مالیات (مثال: ۹٪)"""
        return subtotal * Decimal('0.09')

    def _calculate_shipping(self, subtotal, method='standard'):
        """محاسبه هزینه ارسال"""
        if method == 'express':
            return Decimal('250000')
        elif method == 'standard':
            return Decimal('150000') if subtotal < Decimal('5000000') else Decimal('0')
        return Decimal('0')

    def _get_shipping_methods(self):
        """دریافت روش‌های ارسال"""
        return [
            {'id': 'standard', 'name': 'ارسال معمولی', 'price': 150000},
            {'id': 'express', 'name': 'ارسال فوری', 'price': 250000},
        ]

    def _get_user_province_id(self, user):
        """دریافت استان کاربر از آخرین آدرس"""
        last_address = user.addresses.filter(is_active=True).first()
        if last_address:
            return last_address.province_id
        return None

    @staticmethod
    def _sync_cart_coupon(cart, user, discountable_amount):
        """کوپن ذخیره‌شده روی سبد را دوباره اعتبارسنجی و محاسبه می‌کند.

        اگر کد دیگر معتبر نباشد (منقضی شده، غیرفعال شده، یا مبلغ سبد زیر حد
        نصاب افتاده) از سبد برداشته می‌شود تا کاربر تخفیفی را نبیند که سر
        پرداخت اعمال نخواهد شد.

        Returns:
            tuple: (مبلغ تخفیف, کد تخفیف یا None)
        """
        if not cart.coupon_code:
            return Decimal('0'), None

        result = CouponManager.validate(cart.coupon_code, user, discountable_amount)
        if not result.is_valid:
            cart.coupon_code = None
            cart.coupon_discount = 0
            cart.save(update_fields=['coupon_code', 'coupon_discount', 'updated_at'])
            return Decimal('0'), None

        if cart.coupon_discount != result.discount:
            cart.coupon_discount = result.discount
            cart.save(update_fields=['coupon_discount', 'updated_at'])
        return result.discount, result.coupon.code


class CheckoutPageView(LoginRequiredMixin, TemplateView):
    """صفحه تسویه حساب و پرداخت"""
    template_name = 'shop/cart.html'
    login_url = 'accounts_app:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['provinces'] = Province.objects.all()
        context['cities'] = City.objects.all()
        return context


class CartClearAPIView(APIView):
    """خالی کردن کامل سبد خرید"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        cart = Cart.objects.filter(user=request.user, is_active=True).first()
        if cart:
            cart.items.all().delete()
            cart.coupon_code = None
            cart.coupon_discount = 0
            cart.save()

        return Response({
            'status': 'cleared',
            'message': 'سبد خرید خالی شد'
        })


def cart_discountable_amount(cart):
    """مبلغی از سبد خرید که کد تخفیف روی آن اعمال می‌شود.

    جمع کالاها پس از کسر تخفیف خودِ محصولات و پیش از مالیات و هزینه‌ی ارسال —
    تا کوپن روی مالیات و کرایه‌ی پست تخفیف ندهد.
    """
    amount = Decimal('0')
    for item in cart.items.select_related('product').all():
        product = item.product
        unit = Decimal(str(product.discount_price or product.price))
        amount += unit * item.quantity
    return amount


class CartApplyCouponAPIView(APIView):
    """اعمال و حذف کد تخفیف روی سبد خرید"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        coupon_code = request.data.get('coupon_code', '') or ''
        coupon_code = coupon_code.strip()

        cart = Cart.objects.filter(user=request.user, is_active=True).first()
        if not cart or not cart.items.exists():
            return Response(
                {'error': 'سبد خرید خالی است'},
                status=status.HTTP_400_BAD_REQUEST
            )

        result = CouponManager.validate(
            coupon_code, request.user, cart_discountable_amount(cart)
        )
        if not result.is_valid:
            return Response({'error': result.error}, status=status.HTTP_400_BAD_REQUEST)

        cart.coupon_code = result.coupon.code
        cart.coupon_discount = result.discount
        cart.save(update_fields=['coupon_code', 'coupon_discount', 'updated_at'])

        return Response({
            'status': 'applied',
            'message': f'کد تخفیف {result.coupon.percentage}٪ اعمال شد',
            'coupon_code': result.coupon.code,
            'percentage': result.coupon.percentage,
            'discount_amount': int(result.discount),
        })

    def delete(self, request):
        """برداشتن کد تخفیف از سبد خرید"""
        cart = Cart.objects.filter(user=request.user, is_active=True).first()
        if cart:
            cart.coupon_code = None
            cart.coupon_discount = 0
            cart.save(update_fields=['coupon_code', 'coupon_discount', 'updated_at'])

        return Response({
            'status': 'removed',
            'message': 'کد تخفیف حذف شد',
        })


# apps/shop/views.py

# ============================================
# CHECKOUT API
# ============================================

class CheckoutSubmitAPIView(APIView):
    """API برای ثبت نهایی سفارش"""
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        user = request.user

        # ===== 1. دریافت سبد خرید کاربر =====
        cart = Cart.objects.filter(user=user, is_active=True).first()
        if not cart or not cart.items.exists():
            return Response(
                {'error': 'سبد خرید شما خالی است'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ===== 2. بررسی موجودی با استفاده از InventoryManager =====
        availability = InventoryManager.check_availability(cart.items.all())
        if not availability['available']:
            return Response({
                'error': 'برخی محصولات موجودی کافی ندارند',
                'details': availability['errors']
            }, status=status.HTTP_400_BAD_REQUEST)

        # ===== 3. پیدا کردن یا ایجاد آدرس =====
        save_address = data.get('save_address', False)

        # اگر کاربر یکی از آدرس‌های ذخیره‌شده‌اش را در سبد خرید انتخاب کرده باشد،
        # همان رکورد استفاده می‌شود. فیلتر روی user انجام می‌شود تا کسی نتواند با
        # فرستادن id دلخواه، سفارش را به آدرس کاربر دیگری وصل کند.
        address = None
        if data.get('address_id'):
            address = Address.objects.filter(
                pk=data['address_id'], user=user
            ).first()
            if address is None:
                return Response(
                    {'error': 'آدرس انتخاب‌شده معتبر نیست'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if address is None:
            province = get_object_or_404(Province, id=data['province_id'])
            city = get_object_or_404(City, id=data['city_id'])
            full_name = f"{data['first_name']} {data['last_name']}"

            address, created = Address.objects.get_or_create(
                user=user,
                recipient_name=full_name,
                recipient_phone=data['phone'],
                province=province,
                city=city,
                address=data['address'],
                postal_code=data['postal_code'],
                defaults={
                    'is_active': save_address
                }
            )

            # is_active همان «ذخیره‌شده» است و در لیست آدرس‌های کاربر نمایش داده
            # می‌شود. defaults فقط هنگام ساخت اعمال می‌شود، پس اگر آدرس از قبل
            # به شکل ذخیره‌نشده وجود داشت و کاربر این بار تیک ذخیره را زده،
            # اینجا فعالش می‌کنیم.
            if not created and save_address and not address.is_active:
                address.is_active = True
                address.save(update_fields=['is_active', 'updated_at'])

        # ===== 4. محاسبه قیمت‌ها با استفاده از utils =====
        subtotal = Decimal('0')
        discount_total = Decimal('0')
        items_list = []

        for item in cart.items.select_related('product').all():
            product = item.product
            quantity = item.quantity
            unit_price = item.price_snapshot
            unit_discount = Decimal('0')

            if product.discount_price:
                unit_discount = Decimal(str(product.price)) - Decimal(str(product.discount_price))

            subtotal += unit_price * quantity
            discount_total += unit_discount * quantity

            items_list.append({
                'product': product,
                'quantity': quantity,
                'price': product.price,
                'discount': unit_discount,
            })

        # محاسبه مالیات و هزینه ارسال با utils
        tax_amount = TaxCalculator.calculate_tax(subtotal)
        shipping_method = request.query_params.get('shipping_method', 'standard')
        # _get_user_province_id() lives on CartAPIView, not here, so this call
        # raised AttributeError and every checkout 500'd before reaching the
        # gateway. The order's own address is the right province anyway — the
        # helper guessed from the user's first saved address, which is not
        # necessarily where this order ships.
        shipping_cost = ShippingCalculator.calculate_shipping(
            subtotal=subtotal,
            method=shipping_method,
            province_id=address.province_id
        )

        available_shipping_methods = ShippingCalculator.get_available_methods(subtotal)

        # ===== 5. اعمال کوپن =====
        # کد تخفیف دوباره از صفر اعتبارسنجی می‌شود. مقدار ذخیره‌شده روی سبد
        # خرید فقط برای نمایش است و نباید مبنای مبلغ پرداختی باشد: بین اعمال
        # کد تا ثبت سفارش، سبد تغییر می‌کند و کوپن ممکن است منقضی یا پر شده
        # باشد. اگر کد معتبر نمانده باشد سفارش رد می‌شود تا کاربر مبلغی را
        # پرداخت نکند که با چیزی که دیده فرق دارد.
        coupon = None
        coupon_discount = Decimal('0')
        if cart.coupon_code:
            coupon_result = CouponManager.validate(
                cart.coupon_code, user, cart_discountable_amount(cart)
            )
            if not coupon_result.is_valid:
                return Response(
                    {'error': f'کد تخفیف قابل استفاده نیست: {coupon_result.error}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            coupon = coupon_result.coupon
            coupon_discount = coupon_result.discount

        # ===== 6. محاسبه مبلغ نهایی =====
        total = TaxCalculator.calculate_total(
            subtotal=subtotal,
            discount=discount_total + coupon_discount,
            shipping_cost=shipping_cost
        )

        # ===== 7. ایجاد سفارش =====
        order = Order.objects.create(
            user=user,
            address=address,
            subtotal=subtotal,
            discount_amount=discount_total + coupon_discount,
            shipping_cost=shipping_cost,
            tax_amount=tax_amount,
            total=total,
            status='pending',
            payment_status='pending',
            shipping_method=shipping_method,
            coupon=coupon,
            coupon_code=coupon.code if coupon else '',
            coupon_discount=coupon_discount,
            notes=f"روش پرداخت: {data['payment_method']}"
        )

        # ===== 7.۱ ثبت مصرف کوپن =====
        # F() به‌جای used_count + 1 در پایتون، تا دو سفارش هم‌زمان یک شمارنده
        # را روی هم ننویسند و سقف استفاده قابل دور زدن نباشد.
        if coupon:
            Coupon.objects.filter(pk=coupon.pk).update(used_count=F('used_count') + 1)
            # کد مصرف شد؛ روی سبد خرید نماند تا به سفارش بعدی سرایت نکند.
            cart.coupon_code = None
            cart.coupon_discount = 0
            cart.save(update_fields=['coupon_code', 'coupon_discount', 'updated_at'])

        # ===== 8. ایجاد آیتم‌های سفارش =====
        for item_data in items_list:
            OrderItem.objects.create(
                order=order,
                product=item_data['product'],
                quantity=item_data['quantity'],
                price=item_data['price'],
                discount=item_data['discount']
            )

        # ===== 9. ایجاد تراکنش و اتصال به درگاه پرداخت =====
        gateway_name = data.get('payment_method') or data.get('gateway') or 'sandbox'
        gateway = PaymentGatewayFactory.get_gateway(gateway_name)

        trx = Transaction.objects.create(
            order=order,
            gateway=gateway.get_gateway_name(),
            amount=order.total,
            status='pending'
        )

        callback_url = request.build_absolute_uri(
            reverse('shop_app:payment_callback', kwargs={'gateway': gateway.get_gateway_name(), 'order_id': order.id})
        )
        payment_result = gateway.request_payment(order, callback_url=callback_url)

        if payment_result.success:
            trx.reference_id = payment_result.authority
            trx.save(update_fields=['reference_id'])
            payment_url = payment_result.redirect_url
        else:
            fallback_gateway = PaymentGatewayFactory.get_gateway('sandbox')
            fallback_result = fallback_gateway.request_payment(order, callback_url=callback_url)
            payment_url = fallback_result.redirect_url

        return Response({
            'status': 'success',
            'order_id': order.id,
            'order_number': order.order_number,
            'redirect_url': payment_url,
            'message': 'سفارش با موفقیت ثبت شد و در حال انتقال به درگاه پرداخت هستید.',
            'order': {
                'id': order.id,
                'order_number': order.order_number,
                'total': int(total),
                'status': order.status,
            }
        }, status=status.HTTP_201_CREATED)


# ============================================
# ORDER HISTORY & DETAILS
# ============================================

class OrderListAPIView(generics.ListAPIView):
    """API برای لیست سفارش‌های کاربر"""
    permission_classes = [IsAuthenticated]
    serializer_class = OrderListSerializer
    pagination_class = ProductPagination

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).order_by('-created_at')


class OrderDetailAPIView(generics.RetrieveAPIView):
    """API برای جزئیات یک سفارش"""
    permission_classes = [IsAuthenticated]
    serializer_class = OrderListSerializer
    lookup_field = 'order_number'

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)


class OrderCancelAPIView(APIView):
    """API برای لغو سفارش"""
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, order_number):
        order = get_object_or_404(Order, order_number=order_number, user=request.user)

        # فقط سفارش های در انتظار پرداخت و در حال پردازش قابل لغو هستند
        if order.status not in ['pending', 'processing']:
            return Response(
                {'error': 'این سفارش قابل لغو نیست'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # بازگرداندن موجودی فقط در صورتی که سفارش قبلاً پرداخت شده و موجودی کسر شده باشد
        if order.payment_status == 'paid':
            InventoryManager.restore_stock(order.items.all())

        # لغو سفارش
        order.status = 'cancelled'
        order.save()

        return Response({
            'status': 'cancelled',
            'message': 'سفارش با موفقیت لغو شد',
            'order_number': order.order_number
        })


class PaymentGatewayView(TemplateView):
    """صفحه درگاه پرداخت تستی (Sandbox)"""
    template_name = 'shop/payment_gateway.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_id = self.kwargs.get('order_id')
        if self.request.user.is_authenticated:
            context['order'] = get_object_or_404(Order, id=order_id, user=self.request.user)
        else:
            context['order'] = get_object_or_404(Order, id=order_id)
        return context


class PaymentCallbackView(View):
    """
    رسیدگی به بازگشت کاربر از درگاه‌های پرداخت (زرین‌پال، اسنپ‌پی، دیجی‌پی، تستی)
    """

    def get(self, request, gateway, order_id):
        return self._handle_callback(request, gateway, order_id)

    def post(self, request, gateway, order_id):
        return self._handle_callback(request, gateway, order_id)

    @transaction.atomic
    def _handle_callback(self, request, gateway_name, order_id):
        order = get_object_or_404(Order, id=order_id)
        trx = Transaction.objects.filter(order=order).order_by('-created_at').first()

        # بررسی Idempotency: اگر سفارش از قبل پرداخت شده، فرآیند را تکرار نکن
        if order.payment_status == 'paid':
            return redirect(f"{reverse('accounts_app:dashboard')}?payment=success&order={order.order_number}")

        # بررسی تطابق درگاه کال‌بک با درگاه تراکنش ثبت‌شده (جلوگیری از درگاه تستی جعلی)
        if trx and trx.gateway != gateway_name:
            logger.warning(
                f"Gateway tampering attempt for order {order_id}: expected {trx.gateway}, got {gateway_name}"
            )
            return HttpResponseForbidden("عدم تطابق درگاه پرداخت با تراکنش ثبت‌شده.")

        gateway = PaymentGatewayFactory.get_gateway(gateway_name)
        request_params = {**request.GET.dict(), **request.POST.dict()}

        verification = gateway.verify_payment(order, request_params)

        if verification.success:
            order.status = 'processing'
            order.payment_status = 'paid'
            order.paid_at = timezone.now()
            order.save(update_fields=['status', 'payment_status', 'paid_at', 'updated_at'])

            if trx:
                trx.status = 'success'
                trx.reference_id = verification.reference_id or trx.reference_id
                trx.paid_at = timezone.now()
                trx.save(update_fields=['status', 'reference_id', 'paid_at'])

            # کسر قطعی موجودی انبار پس از پرداخت موفقیت‌آمیز
            # select_for_update در inventory_utils از race-condition جلوگیری می‌کند
            try:
                InventoryManager.deduct_stock(order.items.all())
            except InsufficientStockError as exc:
                # موجودی در فاصله checkout تا callback تمام شده (edge-case)
                # سفارش را به حالت تعلیق در می‌آوریم تا ادمین بررسی کند
                order.status = 'on_hold'
                order.notes = (order.notes or '') + f' | موجودی ناکافی: {exc}'
                order.save(update_fields=['status', 'notes', 'updated_at'])
                return redirect(
                    f"{reverse('accounts_app:dashboard')}?payment=stock_error&order={order.order_number}"
                )

            # غیرفعال‌سازی سبد خرید فعلی
            Cart.objects.filter(user=order.user, is_active=True).update(is_active=False)

            return redirect(f"{reverse('accounts_app:dashboard')}?payment=success&order={order.order_number}")
        else:
            if trx:
                trx.status = 'failed'
                trx.failure_reason = verification.error_message
                trx.save(update_fields=['status', 'failure_reason'])

            return redirect(f"{reverse('accounts_app:dashboard')}?payment=failed&order={order.order_number}")


class AdminProductReviewListAPIView(generics.ListAPIView):
    """لیست همه‌ی نظرات محصولات برای ادمین، با فیلتر status"""
    permission_classes = [IsAdminUser]
    serializer_class = AdminProductReviewSerializer
    pagination_class = ProductPagination

    def get_queryset(self):
        qs = ProductReview.objects.select_related('user', 'product').order_by('-created_at')
        status_param = self.request.query_params.get('status', '').strip()
        if status_param in dict(ProductReview.STATUS_CHOICES):
            qs = qs.filter(status=status_param)
        return qs


class AdminProductReviewModerateAPIView(APIView):
    """تایید یا رد نظر محصول"""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        review = get_object_or_404(ProductReview, pk=pk)
        action = request.data.get('action')

        if action not in ['approve', 'reject']:
            return Response(
                {'error': "مقدار action باید 'approve' یا 'reject' باشد"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if action == 'approve':
            review.status = 'approved'
            review.rejection_reason = ''
        else:
            reason = request.data.get('rejection_reason', '').strip()
            if not reason:
                return Response(
                    {'error': 'برای رد کردن نظر، وارد کردن دلیل الزامی است'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            review.status = 'rejected'
            review.rejection_reason = reason

        review.save(update_fields=['status', 'rejection_reason', 'updated_at'])

        return Response({
            'status': 'success',
            'message': 'وضعیت نظر با موفقیت به‌روزرسانی شد',
            'data': AdminProductReviewSerializer(review).data
        })

from .models import Transaction, RefundRequest
from .serializers import AdminTransactionSerializer
from django.db.models.functions import TruncDate


class AdminTransactionListAPIView(generics.ListAPIView):
    """لیست تراکنش‌ها برای پنل مالی ادمین، با فیلتر بازه/درگاه/وضعیت/مبلغ"""
    permission_classes = [IsAdminUser]
    serializer_class = AdminTransactionSerializer
    pagination_class = ProductPagination

    def get_queryset(self):
        qs = Transaction.objects.select_related('order', 'order__user').order_by('-created_at')

        days = self.request.query_params.get('days')
        if days:
            try:
                since = timezone.now() - timedelta(days=int(days))
                qs = qs.filter(created_at__gte=since)
            except ValueError:
                pass

        gateway = self.request.query_params.get('gateway', '').strip()
        if gateway in dict(Transaction.GATEWAY_CHOICES):
            qs = qs.filter(gateway=gateway)

        status_param = self.request.query_params.get('status', '').strip()
        if status_param in dict(Transaction.STATUS_CHOICES):
            qs = qs.filter(status=status_param)

        min_amount = self.request.query_params.get('min_amount')
        max_amount = self.request.query_params.get('max_amount')
        if min_amount:
            qs = qs.filter(amount__gte=min_amount)
        if max_amount:
            qs = qs.filter(amount__lte=max_amount)

        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(transaction_id__icontains=search) |
                Q(order__order_number__icontains=search) |
                Q(order__user__fullname__icontains=search)
            )

        return qs


class AdminFinanceStatsAPIView(APIView):
    """آمار و نمودارهای صفحه مدیریت مالی"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        today = timezone.now().date()
        first_day_of_month = today.replace(day=1)

        successful_tx = Transaction.objects.filter(status='success')

        # ===== ۱. کارت‌های آماری اصلی =====
        total_revenue = successful_tx.aggregate(total=Sum('amount'))['total'] or 0
        today_revenue = successful_tx.filter(created_at__date=today).aggregate(
            total=Sum('amount'))['total'] or 0
        month_revenue = successful_tx.filter(created_at__gte=first_day_of_month).aggregate(
            total=Sum('amount'))['total'] or 0
        pending_settlement = successful_tx.filter(settled_at__isnull=True).aggregate(
            total=Sum('amount'))['total'] or 0

        successful_count = successful_tx.count()
        failed_count = Transaction.objects.filter(status='failed').count()
        refund_count = RefundRequest.objects.filter(status='pending').count()

        # ===== ۲. سود خالص (بر اساس OrderItem های سفارش‌های پرداخت‌شده) =====
        paid_items = OrderItem.objects.filter(
            order__payment_status='paid',
            order__created_at__gte=first_day_of_month
        ).select_related('product')

        month_cost = sum(
            (item.product.cost_price or 0) * item.quantity for item in paid_items
        )
        net_profit = month_revenue - month_cost
        profit_margin = round((net_profit / month_revenue * 100), 1) if month_revenue else 0

        # ===== ۳. روند درآمد ماهانه (۱۲ ماه اخیر) =====
        start_date = today - timedelta(days=365)
        monthly_data = successful_tx.filter(
            created_at__date__gte=start_date
        ).annotate(month=TruncMonth('created_at')).values('month').annotate(
            total=Sum('amount')
        ).order_by('month')

        month_names_fa = {
            1: 'فروردین', 2: 'اردیبهشت', 3: 'خرداد', 4: 'تیر',
            5: 'مرداد', 6: 'شهریور', 7: 'مهر', 8: 'آبان',
            9: 'آذر', 10: 'دی', 11: 'بهمن', 12: 'اسفند'
        }
        months = []
        for i in range(11, -1, -1):
            month_date = today - timedelta(days=30 * i)
            try:
                j_m = jdatetime.date.fromgregorian(date=month_date).month
            except Exception:
                j_m = month_date.month
            months.append({'month': month_names_fa.get(j_m, ''), 'total': 0})
        for d in monthly_data:
            if d['month']:
                try:
                    d_date = d['month'].date() if hasattr(d['month'], 'date') else d['month']
                    j_m = jdatetime.date.fromgregorian(date=d_date).month
                except Exception:
                    j_m = d['month'].month
                name = month_names_fa.get(j_m, '')
                for m in months:
                    if m['month'] == name:
                        m['total'] = float(d['total']) / 1_000_000
                        break

        # ===== ۴. منابع درآمد به تفکیک درگاه =====
        gateway_data = successful_tx.filter(
            created_at__gte=first_day_of_month
        ).values('gateway').annotate(total=Sum('amount')).order_by('-total')
        gateway_labels = dict(Transaction.GATEWAY_CHOICES)
        revenue_sources = [
            {'label': gateway_labels.get(g['gateway'], g['gateway']), 'value': float(g['total'])}
            for g in gateway_data
        ]

        # ===== ۵. فروش روزانه (۳۰ روز اخیر) =====
        last_30_start = today - timedelta(days=29)
        daily_data = successful_tx.filter(
            created_at__date__gte=last_30_start
        ).annotate(day=TruncDate('created_at')).values('day').annotate(
            total=Sum('amount')
        ).order_by('day')
        daily_map = {d['day']: float(d['total']) for d in daily_data}
        daily_sales = [
            {
                'date': (last_30_start + timedelta(days=i)).strftime('%m/%d'),
                'total': daily_map.get(last_30_start + timedelta(days=i), 0) / 1_000_000
            }
            for i in range(30)
        ]

        # ===== ۶. مقایسه درگاه‌ها ماه به ماه (۶ ماه اخیر) =====
        six_months_start = today - timedelta(days=180)
        gw_monthly = successful_tx.filter(
            created_at__date__gte=six_months_start
        ).annotate(month=TruncMonth('created_at')).values('month', 'gateway').annotate(
            total=Sum('amount')
        ).order_by('month')

        gw_compare = {code: [] for code, _ in Transaction.GATEWAY_CHOICES}
        month_keys = []
        for i in range(5, -1, -1):
            m = today - timedelta(days=30 * i)
            try:
                jm = jdatetime.date.fromgregorian(date=m)
                month_keys.append((jm.year, jm.month))
            except Exception:
                month_keys.append((m.year, m.month))

        gw_lookup = {}
        for row in gw_monthly:
            d_date = row['month'].date() if hasattr(row['month'], 'date') else row['month']
            try:
                jm = jdatetime.date.fromgregorian(date=d_date)
                key = (jm.year, jm.month, row['gateway'])
            except Exception:
                key = (row['month'].year, row['month'].month, row['gateway'])
            gw_lookup[key] = float(row['total']) / 1_000_000

        for code, _ in Transaction.GATEWAY_CHOICES:
            gw_compare[code] = [
                gw_lookup.get((y, m, code), 0) for (y, m) in month_keys
            ]

        # ===== ۷. تفکیک به ازای هر درگاه (کل تاریخچه) =====
        gateway_totals = Transaction.objects.values('gateway').annotate(
            total_count=Count('id'),
            success_count=Count('id', filter=Q(status='success')),
            revenue=Sum('amount', filter=Q(status='success')),
        )
        gateway_breakdown = []
        for row in gateway_totals:
            total = row['total_count'] or 0
            success = row['success_count'] or 0
            gateway_breakdown.append({
                'code': row['gateway'],
                'label': gateway_labels.get(row['gateway'], row['gateway']),
                'total_count': total,
                'success_count': success,
                'revenue': float(row['revenue'] or 0),
                'success_rate': round((success / total * 100), 1) if total else 0,
            })

        # ===== ۸. میانگین ارزش سفارش =====
        avg_order_value = Order.objects.filter(payment_status='paid').aggregate(
            avg=Avg('total'))['avg'] or 0

        return Response({
            'stats': {
                'total_revenue': float(total_revenue),
                'today_revenue': float(today_revenue),
                'month_revenue': float(month_revenue),
                'pending_settlement': float(pending_settlement),
                'successful_count': successful_count,
                'failed_count': failed_count,
                'refund_requests_count': refund_count,
                'net_profit': float(net_profit),
                'profit_margin': profit_margin,
                'avg_order_value': float(avg_order_value),
            },
            'monthly_revenue': months,
            'revenue_sources': revenue_sources,
            'daily_sales': daily_sales,
            'gateway_compare': {
                'months': [month_names_fa.get(m, '') for (_, m) in month_keys],
                'series': gw_compare,
            },
            'gateway_breakdown': gateway_breakdown,
        })

