# apps/shop/urls.py

from django.urls import path, re_path
from . import views
from apps.accounts.views import CityListAPIView, ProvinceListAPIView

app_name = 'shop'

urlpatterns = [
    # ============================================================
    # API
    # ============================================================

    # ===== لیست و دسته‌بندی =====
    path('api/products/', views.ProductListAPIView.as_view(), name='api_product_list'),
    path('api/categories/', views.CategoryListAPIView.as_view(), name='api_categories'),
    re_path(r'^api/category/(?P<slug>.+)/$', views.CategoryDetailAPIView.as_view(), name='api_category_detail'),

    # ===== محصولات (با جزئیات بیشتر اول) =====
    re_path(r'^api/products/(?P<slug>.+)/reviews/$', views.ProductReviewListCreateAPIView.as_view(),
            name='api_reviews'),
    re_path(r'^api/products/(?P<slug>.+)/wishlist/$', views.WishlistToggleAPIView.as_view(),
            name='api_wishlist_toggle_slug'),
    re_path(r'^api/products/(?P<slug>.+)/$', views.ProductDetailAPIView.as_view(), name='api_product_detail'),

    # ===== سبد خرید و پرداخت =====
    path('api/cart/', views.CartAPIView.as_view(), name='api_cart'),
    path('api/wishlist/toggle/', views.WishlistToggleAPIView.as_view(), name='api_wishlist_toggle'),
    path('api/wishlist/', views.WishlistListAPIView.as_view(), name='api_wishlist_list'),

    # ===== ادمین =====
    path('api/admin/dashboard/stats/', views.AdminDashboardStatsAPIView.as_view(), name='api_admin_dashboard_stats'),

    # ===== استان و شهر =====
    path('api/provinces/', ProvinceListAPIView.as_view(), name='api_provinces'),
    path('api/cities/', CityListAPIView.as_view(), name='api_cities'),

    # ============================================================
    # صفحات HTML
    # ============================================================

    # ===== سبد خرید و پرداخت =====
    path('cart/', views.CheckoutPageView.as_view(), name='cart'),
    path('checkout/submit/', views.CheckoutSubmitAPIView.as_view(), name='checkout_submit'),
    path('payment/gateway/<int:order_id>/', views.PaymentGatewayView.as_view(), name='payment_gateway'),

    # ===== محصولات =====
    path('', views.ProductListPageView.as_view(), name='product_list'),
    re_path(r'^category/(?P<slug>.+)/$', views.CategoryPageView.as_view(), name='category_products'),
    re_path(r'^product/(?P<slug>.+)/$', views.ProductPageView.as_view(), name='product_detail'),
]