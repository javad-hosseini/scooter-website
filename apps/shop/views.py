# apps/shop/views.py

from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


from .models import Product, Category, ProductReview, Wishlist
from .pagination import ProductPagination
from .serializers import (
    ProductListSerializer, ProductDetailSerializer,
    ProductReviewSerializer, ProductReviewCreateSerializer,
    WishlistSerializer, CategorySerializer, CategoryDetailSerializer
)


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


class WishlistToggleAPIView(APIView):
    """API برای افزودن/حذف از علاقه‌مندی‌ها"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        product_id = request.data.get('product_id')
        if not product_id:
            return Response({'error': 'شناسه محصول الزامی است'}, status=status.HTTP_400_BAD_REQUEST)

        product = get_object_or_404(Product, id=product_id, is_published=True)

        wishlist_item = Wishlist.objects.filter(user=request.user, product=product)

        if wishlist_item.exists():
            wishlist_item.delete()
            return Response({'status': 'removed', 'message': 'از علاقه‌مندی‌ها حذف شد.'})
        else:
            Wishlist.objects.create(user=request.user, product=product)
            return Response({'status': 'added', 'message': 'به علاقه‌مندی‌ها اضافه شد.'})


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


