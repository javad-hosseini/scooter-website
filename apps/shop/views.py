# apps/shop/views.py

from datetime import timedelta, datetime
from decimal import Decimal

import jdatetime
from django.db import transaction
from django.db.models import Sum, Q, Count, Avg
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.generic import TemplateView
from rest_framework import generics, serializers
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.permissions import IsAdminUser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import CustomUser
from apps.accounts.models import Province, City
from .models import Category, ProductReview, Wishlist, Cart, CartItem, ProductImage
from .models import Product, Order, OrderItem, Address
from .pagination import ProductPagination
from .serializers import (
    OrderCreateSerializer, CartItemSerializer, OrderListSerializer, AdminProductReviewSerializer
)
from .serializers import (
    ProductListSerializer, ProductDetailSerializer,
    ProductReviewSerializer, WishlistSerializer, CategorySerializer, CategoryDetailSerializer
)
from .utils.inventory_utils import InventoryManager
from .utils.shipping_utils import ShippingCalculator
from .utils.tax_utils import TaxCalculator


# ============================================
# PRODUCT API VIEWS
# ============================================

class ProductListAPIView(generics.ListAPIView):
    """API برای لیست محصولات"""
    permission_classes = [AllowAny]
    serializer_class = ProductListSerializer
    pagination_class = ProductPagination

    def get_queryset(self):
        qs = Product.objects.filter(is_published=True)

        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))

        category = self.request.query_params.get('category', '').strip()
        if category:
            qs = qs.filter(category__slug=category)

        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        if min_price:
            qs = qs.filter(price__gte=min_price)
        if max_price:
            qs = qs.filter(price__lte=max_price)

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


# apps/shop/views.py

# ============================================
# PRODUCT REVIEWS
# ============================================

class ProductReviewListCreateAPIView(generics.ListCreateAPIView):
    """API برای لیست و ایجاد نظرات محصول"""
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = ProductReviewSerializer

    def get_queryset(self):
        slug = self.kwargs.get('slug')
        product = get_object_or_404(Product, slug=slug, is_published=True)
        return product.reviews.filter(status='approved').order_by('-created_at')

    def perform_create(self, serializer):
        slug = self.kwargs.get('slug')
        product = get_object_or_404(Product, slug=slug, is_published=True)

        # چک کردن تکراری نبودن نظر
        if ProductReview.objects.filter(
                product=product,
                user=self.request.user,
                status__in=['pending', 'approved']
        ).exists():
            raise serializers.ValidationError(
                'شما قبلاً برای این محصول نظر ثبت کرده‌اید.'
            )

        serializer.save(
            user=self.request.user,
            product=product,
            status='pending'
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response({
                'status': 'success',
                'message': 'نظر شما با موفقیت ثبت شد و پس از تایید نمایش داده می‌شود.',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED, headers=headers)
        except serializers.ValidationError as e:
            return Response({
                'status': 'error',
                'message': str(e.detail[0]) if isinstance(e.detail, list) else str(e.detail)
            }, status=status.HTTP_400_BAD_REQUEST)


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
            month_num = month_date.month
            month_name = month_names_fa.get(month_num, str(month_num))
            months.append({
                'month': month_name,
                'year': month_date.year,
                'total': 0
            })

        for data in sales_data:
            if data['month']:
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
    permission_classes = [IsAuthenticated]

    def get_cart(self, request):
        """دریافت یا ایجاد سبد خرید فعال کاربر"""
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

        # محاسبه مالیات و هزینه ارسال (با توابع فرضی)
        tax_amount = self._calculate_tax(subtotal)
        shipping_method = request.query_params.get('shipping_method', 'standard')
        shipping_cost = self._calculate_shipping(subtotal, shipping_method)
        final_total = subtotal - discount_total + shipping_cost + tax_amount

        return Response({
            'items': items_data,
            'item_count': item_count,
            'subtotal': int(subtotal),
            'discount_total': int(discount_total),
            'shipping_cost': int(shipping_cost),
            'shipping_methods': self._get_shipping_methods(),
            'selected_shipping_method': shipping_method,
            'applied_coupon': getattr(cart, 'coupon_code', None),
            'coupon_discount': int(getattr(cart, 'coupon_discount', 0)),
            'tax_amount': int(tax_amount),
            'final_total': int(final_total),
            'estimated_delivery': 3,
        })

    def post(self, request):
        """افزودن محصول به سبد خرید"""
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

        return Response({
            'status': 'updated',
            'message': 'تعداد آیتم به‌روزرسانی شد',
            'item': CartItemSerializer(cart_item).data,
        })

    def patch(self, request):
        """به‌روزرسانی آیتم سبد خرید (رنگ یا تعداد)"""
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
        product_id = request.data.get('product_id')

        if not product_id:
            return Response(
                {'error': 'شناسه محصول الزامی است'},
                status=status.HTTP_400_BAD_REQUEST
            )

        cart = self.get_cart(request)

        deleted = CartItem.objects.filter(cart=cart, product_id=product_id).delete()

        if deleted[0] > 0:
            return Response({
                'status': 'removed',
                'message': 'محصول از سبد خرید حذف شد',
            })
        else:
            return Response(
                {'error': 'آیتم در سبد خرید یافت نشد'},
                status=status.HTTP_404_NOT_FOUND
            )

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


class CheckoutPageView(TemplateView):
    """صفحه تسویه حساب و پرداخت"""
    template_name = 'shop/cart.html'

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


class CartApplyCouponAPIView(APIView):
    """اعمال کد تخفیف به سبد خرید"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        coupon_code = request.data.get('coupon_code', '').strip()

        if not coupon_code:
            return Response(
                {'error': 'کد تخفیف را وارد کنید'},
                status=status.HTTP_400_BAD_REQUEST
            )

        cart = Cart.objects.filter(user=request.user, is_active=True).first()
        if not cart or not cart.items.exists():
            return Response(
                {'error': 'سبد خرید خالی است'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # TODO: اعتبارسنجی کوپن
        # از مدل Coupon استفاده کن
        # coupon = get_object_or_404(Coupon, code=coupon_code, is_active=True)

        # مثال:
        # if coupon.is_expired():
        #     return Response({'error': 'کد تخفیف منقضی شده است'})
        # if coupon.usage_limit and coupon.used_count >= coupon.usage_limit:
        #     return Response({'error': 'تعداد استفاده از این کد به پایان رسیده است'})
        # if coupon.min_order_amount and cart.subtotal < coupon.min_order_amount:
        #     return Response({'error': f'حداقل مبلغ برای این کد {coupon.min_order_amount} تومان است'})

        # اعمال کوپن (مثال)
        discount_amount = 50000  # از مدل Coupon بگیر
        cart.coupon_code = coupon_code
        cart.coupon_discount = discount_amount
        cart.save()

        return Response({
            'status': 'applied',
            'message': 'کد تخفیف با موفقیت اعمال شد',
            'coupon_code': coupon_code,
            'discount_amount': discount_amount,
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
                'is_active': data.get('save_address', False)
            }
        )

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
                'discount': product.discount_price or 0,
            })

        # محاسبه مالیات و هزینه ارسال با utils
        tax_amount = TaxCalculator.calculate_tax(subtotal)
        shipping_method = request.query_params.get('shipping_method', 'standard')
        shipping_cost = ShippingCalculator.calculate_shipping(
            subtotal=subtotal,
            method=shipping_method,
            province_id=self._get_user_province_id(user)
        )

        available_shipping_methods = ShippingCalculator.get_available_methods(subtotal)

        # ===== 5. اعمال کوپن =====
        coupon_discount = Decimal('0')
        if cart.coupon_code:
            # TODO: اعتبارسنجی کوپن
            coupon_discount = Decimal(str(cart.coupon_discount))

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
            notes=f"روش پرداخت: {data['payment_method']}"
        )

        # ===== 8. ایجاد آیتم‌های سفارش =====
        for item_data in items_list:
            OrderItem.objects.create(
                order=order,
                product=item_data['product'],
                quantity=item_data['quantity'],
                price=item_data['price'],
                discount=item_data['discount']
            )

        # ===== 9. کاهش موجودی با استفاده از InventoryManager =====
        InventoryManager.deduct_stock(cart.items.all())

        # ===== 10. غیرفعال کردن سبد خرید =====
        cart.is_active = False
        cart.save()

        # ===== 11. اتصال به درگاه پرداخت =====
        # TODO: اتصال به زرین‌پال یا دیگر درگاه‌ها
        payment_url = self._generate_payment_url(order)

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

    def _generate_payment_url(self, order):
        """تولید لینک درگاه پرداخت"""
        # TODO: پیاده‌سازی واقعی
        # مثلاً برای زرین‌پال:
        # from .services.zarinpal import ZarinpalService
        # return ZarinpalService.get_payment_url(order)
        return f'/payment/gateway/{order.id}/'


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

        # فقط سفارش های در انتظار پرداخت قابل لغو هستند
        if order.status not in ['pending', 'processing']:
            return Response(
                {'error': 'این سفارش قابل لغو نیست'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # بازگرداندن موجودی
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
    """صفحه درگاه پرداخت (موقت)"""
    template_name = 'shop/payment_gateway.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_id = self.kwargs.get('order_id')
        context['order'] = get_object_or_404(Order, id=order_id)
        return context

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
            months.append({'month': month_names_fa.get(month_date.month, ''), 'total': 0})
        for d in monthly_data:
            if d['month']:
                name = month_names_fa.get(d['month'].month, '')
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
            month_keys.append((m.year, m.month))

        gw_lookup = {}
        for row in gw_monthly:
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

