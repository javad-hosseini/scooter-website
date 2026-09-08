# apps/shop/views.py

from django.db.models import F, Q
from django.db.models.functions import Coalesce
from django.http import HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.functional import cached_property
from django.views.generic import DetailView, ListView, RedirectView
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.seo import schema
from apps.seo.cache import cached_page_class
from apps.seo.seo import SEOMixin
from apps.seo.utils import canonical_url, image_url, meta_description, meta_title

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
        return (
            Wishlist.objects.filter(user=self.request.user)
            .select_related('product', 'product__category')
            .order_by('-created_at')
        )


# ══════════════════════════════════════════════════════════════════════
#  HTML pages
#
#  These used to be bare TemplateViews that rendered an empty shell and let
#  JavaScript fetch the product from the API and write the title, meta tags
#  and JSON-LD into the DOM. That made every product and category page
#  indistinguishable to a crawler that does not execute JS, and unreliable
#  even for one that does. The page data is now resolved server-side and
#  rendered into the initial HTML response; the existing scripts still
#  hydrate the interactive parts on top of it.
# ══════════════════════════════════════════════════════════════════════

#: Parameters that produce a filtered/sorted view of an existing listing.
#: Their presence flips the page to noindex,follow and points the canonical
#: back at the clean URL.
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
        'خرید اسکوتر برقی ولتکس؛ مقایسه قیمت، برد، سرعت و زمان شارژ همه مدل‌ها '
        'با گارانتی ۳ ساله و ارسال سریع به سراسر ایران.'
    )

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
            f'خرید {self.category.name} ولتکس با گارانتی رسمی، قیمت شفاف و ارسال '
            f'سریع. مقایسه مشخصات فنی همه مدل‌های {self.category.name}.',
        )
        context = super().get_context_data(**kwargs)
        context['category'] = self.category
        context['slug'] = self.category.slug
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
