# apps/shop/urls.py

from django.urls import path, re_path

from apps.accounts.views import CityListAPIView, ProvinceListAPIView
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

    # Admin APIs
    path('api/admin/reviews/', views.AdminProductReviewListAPIView.as_view(), name='api_admin_reviews'),
    path('api/admin/reviews/<int:pk>/moderate/', views.AdminProductReviewModerateAPIView.as_view(),
         name='api_admin_review_moderate'),
    path('api/admin/finance/stats/', views.AdminFinanceStatsAPIView.as_view(), name='api_admin_finance_stats'),
    path('api/admin/transactions/', views.AdminTransactionListAPIView.as_view(), name='api_admin_transactions'),
    path('api/admin/dashboard/stats/', views.AdminDashboardStatsAPIView.as_view(), name='api_admin_dashboard_stats'),

    # Cart & Checkout APIs
    path('api/cart/add/', views.CartAPIView.as_view(), name='cart_add'),
    path('api/cart/', views.CartAPIView.as_view(), name='api_cart'),
    path('api/cart/clear/', views.CartClearAPIView.as_view(), name='api_cart_clear'),
    path('api/cart/apply-coupon/', views.CartApplyCouponAPIView.as_view(), name='api_cart_apply_coupon'),
    path('checkout/submit/', views.CheckoutSubmitAPIView.as_view(), name='checkout_submit'),

    # Location APIs
    path('api/provinces/', ProvinceListAPIView.as_view(), name='api_provinces'),
    path('api/cities/', CityListAPIView.as_view(), name='api_cities'),

    # ⚠️ More specific product routes first.
    re_path(rf'^api/products/{SLUG}/reviews/$', views.ProductReviewListCreateAPIView.as_view(),
            name='api_reviews'),
    re_path(rf'^api/products/{SLUG}/wishlist/$', views.WishlistToggleAPIView.as_view(),
            name='api_product_wishlist_toggle'),
    re_path(rf'^api/products/{SLUG}/$', views.ProductDetailAPIView.as_view(),
            name='api_product_detail'),

    # ===== صفحات HTML =====
    path('cart/', views.CheckoutPageView.as_view(), name='cart'),
    path('payment/gateway/<int:order_id>/', views.PaymentGatewayView.as_view(), name='payment_gateway'),
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
