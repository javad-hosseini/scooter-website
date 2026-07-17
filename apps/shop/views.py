# apps/shop/views.py

from datetime import timedelta

from django.db import transaction
from django.db.models import Sum, Q
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.generic import TemplateView
from rest_framework import generics
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.permissions import IsAdminUser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import CustomUser
from .models import Category, ProductReview, Wishlist
from .models import Product, Order, OrderItem, Address
from .pagination import ProductPagination
from .serializers import (
    CartSerializer, OrderCreateSerializer, CartItemSerializer
)
from .serializers import (
    ProductListSerializer, ProductDetailSerializer,
    ProductReviewSerializer, ProductReviewCreateSerializer,
    WishlistSerializer, CategorySerializer, CategoryDetailSerializer
)

from apps.accounts.models import  Province, City

class ProductListAPIView(generics.ListAPIView):
    """API برای لیست محصولات"""
    permission_classes = [AllowAny]
    serializer_class = ProductListSerializer
    pagination_class = ProductPagination

    def get_queryset(self):
        qs = Product.objects.filter(is_published=True)

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
            qs = qs.filter(final_price__gte=min_price)
        if max_price:
            qs = qs.filter(final_price__lte=max_price)

        # مرتب‌سازی
        sort = self.request.query_params.get('sort', '-created_at')
        valid_sorts = ['price', '-price', 'created_at', '-created_at', 'view_count', '-view_count']
        if sort in valid_sorts:
            qs = qs.order_by(sort)

        return qs


class CategoryDetailAPIView(generics.RetrieveAPIView):
    """API برای نمایش یک کتگوری با محصولات و اسلایدر"""
    permission_classes = [AllowAny]
    serializer_class = CategoryDetailSerializer
    lookup_field = 'slug'
    lookup_url_kwarg = 'slug'

    def get_queryset(self):
        return Category.objects.filter(is_active=True)


class ProductDetailAPIView(generics.RetrieveAPIView):
    """API برای نمایش جزئیات یک محصول"""
    permission_classes = [AllowAny]
    serializer_class = ProductDetailSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        return Product.objects.filter(is_published=True)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.view_count += 1
        instance.save(update_fields=['view_count'])

        serializer = self.get_serializer(instance, context={'request': request})
        return Response(serializer.data)


class CategoryListAPIView(generics.ListAPIView):
    """API برای لیست دسته‌بندی‌ها"""
    permission_classes = [AllowAny]
    serializer_class = CategorySerializer
    pagination_class = None

    def get_queryset(self):
        return Category.objects.filter(is_active=True, parent__isnull=True)


class ProductReviewListCreateAPIView(APIView):
    """API برای لیست و ایجاد نظرات محصول"""
    permission_classes = [IsAuthenticatedOrReadOnly]

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


# apps/shop/views.py

class WishlistToggleAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug=None):  # ← slug رو اضافه کن
        # اگر slug از URL اومده
        if slug:
            product = get_object_or_404(Product, slug=slug, is_published=True)
        else:
            # اگر product_id از body اومده
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
        return Wishlist.objects.filter(user=self.request.user).order_by('-created_at')


class ProductListPageView(TemplateView):
    """صفحه لیست محصولات"""
    template_name = 'shop/category_products.html'


class ProductDetailPageView(TemplateView):
    """صفحه جزئیات محصول"""
    template_name = 'shop/product_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['slug'] = self.kwargs.get('slug')
        return context


class CategoryPageView(TemplateView):
    """صفحه نمایش محصولات یک کتگوری"""
    template_name = 'shop/category_products.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['slug'] = self.kwargs.get('slug')
        return context


class ProductPageView(TemplateView):
    """صفحه نمایش یک محصول"""
    template_name = 'shop/product_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['slug'] = self.kwargs.get('slug')
        return context


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
        today_orders = Order.objects.filter(
            created_at__date=today
        ).count()

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
        monthly_sales = []
        end_date = today
        start_date = today - timedelta(days=365)

        # گرفتن داده‌های ماهانه
        sales_data = Order.objects.filter(
            payment_status='paid',
            created_at__gte=start_date,
            created_at__lte=end_date
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            total=Sum('total')
        ).order_by('month')

        # ایجاد لیست کامل ۱۲ ماه
        months = []
        for i in range(11, -1, -1):
            month_date = today - timedelta(days=30 * i)
            months.append({
                'month': month_date.strftime('%B'),
                'year': month_date.year,
                'total': 0
            })

        # پر کردن داده‌ها
        for data in sales_data:
            if data['month']:
                month_name = data['month'].strftime('%B')
                for m in months:
                    if m['month'] == month_name:
                        m['total'] = data['total'] / 1_000_000  # تبدیل به میلیون
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
            # گرفتن محصولات
            products = order.items.all()
            product_names = [item.product.name for item in products]

            recent_orders_data.append({
                'order_number': order.order_number,
                'customer_name': order.user.fullname or order.user.username,
                'customer_username': order.user.username,
                'customer_avatar': order.user.profile_image.url if order.user.profile_image else None,
                'products': product_names,
                'total': order.total,
                'status': order.status,
                'status_label': dict(Order.STATUS_CHOICES).get(order.status, order.status),
                'created_at': order.created_at,
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
                'total_sold': item['total_sold'],
                'total_revenue': item['total_revenue'] or 0,
            })

        # ===== 8. فعالیت‌های اخیر (برای TODO) =====
        # این بخش فعلاً با داده‌های نمونه پر می‌شود
        recent_activities = [
            {
                'icon': 'fa-cart-shopping',
                'title': 'سفارش جدید دریافت شد',
                'description': f'سفارش #{recent_orders[0].order_number if recent_orders else "N/A"}',
                'time': '۲ دقیقه پیش',
                'color': 'blue'
            },
            # ... بقیه فعالیت‌ها
        ]

        # ===== 9. اعلان‌ها (برای TODO) =====
        notifications = [
            {
                'priority_color': 'red',
                'icon': 'fa-triangle-exclamation',
                'icon_color': 'red',
                'title': 'هشدار موجودی انبار',
                'description': 'موجودی «اسکوتر فلش پرو» کمتر از ۵ واحد است',
                'time': '۲ دقیقه پیش'
            },
            # ... بقیه اعلان‌ها
        ]

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
                    'products_trend': '+8.2%',
                    'orders_trend': '+12.4%',
                    'customers_trend': '+5.1%',
                    'revenue_trend': '-2.3%',
                }
            },
            'monthly_sales': monthly_sales,
            'recent_orders': recent_orders_data,
            'top_products': top_products_data,
            'recent_activities': recent_activities,
            'notifications': notifications,
            'today_date': today.strftime('%A، %d %B %Y'),
        }

        return Response(data)


# apps/shop/views.py (افزودن به ویوهای موجود)


# apps/shop/views.py

# apps/shop/views.py

class CartAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        product = Product.objects.filter(is_published=True, is_available=True).first()
        if not product:
            return Response({
                'items': [],
                'item_count': 0,
                'subtotal': 0,
                'discount_total': 0,
                'shipping_cost': 'رایگان',
                'applied_coupon': None,
                'tax_amount': 0,
                'final_total': 0,
            })

        quantity = 2
        from decimal import Decimal

        # ساخت آیتم با دیکشنری
        items = [{
            'product': product,
            'quantity': quantity,
            'selected_color': {'slug': 'black', 'name': 'مشکی', 'hex': '#1A1A1A'},
        }]

        # محاسبات
        price = Decimal(str(product.price))
        discount_price = Decimal(str(product.discount_price)) if product.discount_price else Decimal('0')

        subtotal = price * Decimal(str(quantity))
        discount = discount_price * Decimal(str(quantity)) if discount_price else Decimal('0')
        final_total = subtotal - discount
        tax = (subtotal * Decimal('0.09')).quantize(Decimal('0'))

        # سریالایز کردن آیتم‌ها
        serialized_items = CartItemSerializer(items, many=True).data

        data = {
            'items': serialized_items,
            'item_count': quantity,
            'subtotal': int(subtotal),
            'discount_total': int(discount),
            'shipping_cost': 'رایگان',
            'applied_coupon': None,
            'tax_amount': int(tax),
            'final_total': int(final_total + tax),
        }

        return Response(data)

class CheckoutPageView(TemplateView):
    """صفحه تسویه حساب و پرداخت"""
    template_name = 'shop/cart.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['provinces'] = Province.objects.all()
        context['cities'] = City.objects.all()
        return context


class CheckoutSubmitAPIView(APIView):
    """API برای ثبت نهایی سفارش و هدایت به درگاه پرداخت"""
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        user = request.user

        # ===== 1. پیدا کردن یا ایجاد آدرس =====
        province = get_object_or_404(Province, id=data['province_id'])
        city = get_object_or_404(City, id=data['city_id'])

        # آدرس کامل
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
                'is_active': data.get('save_address', False)
            }
        )

        # ===== 2. محاسبه قیمت‌ها =====
        # TODO: گرفتن آیتم‌های سبد خرید از session
        # فعلاً با دیتای نمونه
        product = Product.objects.filter(is_published=True, is_available=True).first()
        if not product:
            return Response(
                {'error': 'هیچ محصولی در سبد خرید وجود ندارد'},
                status=status.HTTP_400_BAD_REQUEST
            )

        quantity = 2  # از session گرفته شود
        unit_price = product.final_price
        subtotal = unit_price * quantity
        discount = 0  # از session گرفته شود
        shipping_cost = 0  # از session گرفته شود
        tax = int(subtotal * 0.09)  # ۹% مالیات
        total = subtotal - discount + shipping_cost + tax

        # ===== 3. ایجاد سفارش =====
        order = Order.objects.create(
            user=user,
            address=address,
            subtotal=subtotal,
            discount_amount=discount,
            shipping_cost=shipping_cost,
            total=total,
            status='pending',
            payment_status='pending',
            notes=f"روش پرداخت: {data['payment_method']}"
        )

        # ===== 4. ایجاد آیتم‌های سفارش =====
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            price=product.price,
            discount=product.discount_price or 0
        )

        # ===== 5. TODO: اتصال به درگاه پرداخت =====
        # اینجا باید به درگاه پرداخت متصل شود
        # و user را به صفحه پرداخت هدایت کند
        # فعلاً یک پاسخ موفق برمی‌گردانیم

        return Response({
            'status': 'success',
            'order_id': order.id,
            'order_number': order.order_number,
            'redirect_url': f'/payment/gateway/{order.id}/',  # TODO: آدرس درگاه پرداخت
            'message': 'سفارش با موفقیت ثبت شد و در حال انتقال به درگاه پرداخت هستید.'
        })


class PaymentGatewayView(TemplateView):
    """صفحه درگاه پرداخت (موقت)"""
    template_name = 'shop/payment_gateway.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_id = self.kwargs.get('order_id')
        context['order'] = get_object_or_404(Order, id=order_id)
        return context
