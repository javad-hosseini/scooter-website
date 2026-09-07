# apps/shop/urls.py

from django.urls import path, re_path

from . import views

app_name = 'shop'

# Slugs may contain Persian characters (SlugField(allow_unicode=True)), which
# Django's built-in <slug:...> converter rejects, so they are matched with an
# explicit "one path segment" pattern. The old r'.+' patterns matched slashes
# too, which let a single product be reached at unlimited nested URLs.
SLUG = r'(?P<slug>[^/]+)'

urlpatterns = [
    # ===== API =====
    path('api/products/', views.ProductListAPIView.as_view(), name='api_product_list'),
    path('api/categories/', views.CategoryListAPIView.as_view(), name='api_categories'),
    path('api/wishlist/', views.WishlistListAPIView.as_view(), name='api_wishlist_list'),
    path('api/wishlist/toggle/', views.WishlistToggleAPIView.as_view(), name='api_wishlist_toggle'),
    re_path(rf'^api/category/{SLUG}/$', views.CategoryDetailAPIView.as_view(),
            name='api_category_detail'),

    # ⚠️ More specific routes first.
    re_path(rf'^api/products/{SLUG}/reviews/$', views.ProductReviewListCreateAPIView.as_view(),
            name='api_reviews'),
    re_path(rf'^api/products/{SLUG}/wishlist/$', views.WishlistToggleAPIView.as_view(),
            name='api_product_wishlist_toggle'),
    re_path(rf'^api/products/{SLUG}/$', views.ProductDetailAPIView.as_view(),
            name='api_product_detail'),

    # ===== صفحات HTML =====
    re_path(rf'^category/{SLUG}/$', views.CategoryPageView.as_view(), name='category_products'),
    re_path(rf'^product/{SLUG}/$', views.ProductDetailPageView.as_view(), name='product_detail'),
    path('', views.ProductListPageView.as_view(), name='product_list'),

    # Legacy shape: /shop/<slug>/ used to resolve to a product detail page via
    # a catch-all. Kept as a permanent redirect so any existing links and
    # already-indexed URLs consolidate onto /shop/product/<slug>/ instead of
    # serving the same product on two addresses.
    re_path(rf'^{SLUG}/$', views.LegacyProductRedirectView.as_view(),
            name='legacy_product_detail'),
]
