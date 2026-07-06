# apps/shop/urls.py

from django.urls import path, re_path
from . import views

app_name = 'shop'

urlpatterns = [
    # ===== API =====
    path('api/products/', views.ProductListAPIView.as_view(), name='api_product_list'),
    re_path(r'^api/category/(?P<slug>.+)/$', views.CategoryDetailAPIView.as_view(), name='api_category_detail'),
    re_path(r'^api/product/(?P<slug>.+)/$', views.ProductDetailAPIView.as_view(), name='api_product_detail'),
    path('api/wishlist/toggle/', views.WishlistToggleAPIView.as_view(), name='api_wishlist_toggle'),

    # ⚠️ IMPORTANT: آدرس‌های با جزئیات بیشتر را اول بگذار
    re_path(r'^api/products/(?P<slug>.+)/reviews/$', views.ProductReviewListCreateAPIView.as_view(),
            name='api_reviews'),
    re_path(r'^api/products/(?P<slug>.+)/wishlist/$', views.WishlistToggleAPIView.as_view(),
            name='api_wishlist_toggle'),
    re_path(r'^api/products/(?P<slug>.+)/$', views.ProductDetailAPIView.as_view(), name='api_product_detail'),
    # ← این آخر باشد

    path('api/categories/', views.CategoryListAPIView.as_view(), name='api_categories'),
    path('api/wishlist/', views.WishlistListAPIView.as_view(), name='api_wishlist_list'),
    re_path(r'^category/(?P<slug>.+)/$', views.CategoryPageView.as_view(), name='category_products'),
    re_path(r'^product/(?P<slug>.+)/$', views.ProductPageView.as_view(), name='product_detail'),

    # ===== صفحات HTML =====
    path('', views.ProductListPageView.as_view(), name='product_list'),
    re_path(r'^(?P<slug>.+)/$', views.ProductDetailPageView.as_view(), name='product_detail'),
]