from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import LogoutView
from django.urls import path, re_path
from . import views

from .views import RegisterPageView, UserRegistrationAPIView, LoginPageView, UserLoginAPIView, \
    PasswordResetRequestAPIView, PasswordResetConfirmAPIView, PasswordResetVerifyAPIView, PasswordResetPageView, \
    ChangePasswordAPIView
from ..shop.views import WishlistToggleAPIView

app_name = 'accounts_app'

urlpatterns = [
    path('dashboard/', views.DashboardPageView.as_view(), name='dashboard'),
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),
    path('register/', RegisterPageView.as_view(), name='register'),
    path('api/register/', UserRegistrationAPIView.as_view(), name='api_register'),
    path('login/', LoginPageView.as_view(), name='login'),
    path('api/login/', UserLoginAPIView.as_view(), name='api_login'),
    path('api/password-reset/request/', PasswordResetRequestAPIView.as_view(), name='api_password_reset_request'),
    path('api/password-reset/verify/', PasswordResetVerifyAPIView.as_view(), name='api_password_reset_verify'),
    path('api/password-reset/confirm/', PasswordResetConfirmAPIView.as_view(), name='api_password_reset_confirm'),
    path('password-reset/', PasswordResetPageView.as_view(), name='password_reset'),  # صفحه‌ی HTML سه‌مرحله‌ای
    path('api/change-password/', ChangePasswordAPIView.as_view(), name='api_change_password'),
    # ===== API =====
    path('api/dashboard/', views.DashboardDataAPIView.as_view(), name='api_dashboard'),
    path('api/profile/update/', views.UserProfileUpdateAPIView.as_view(), name='api_profile_update'),
    path('api/password/change/', views.ChangePasswordAPIView.as_view(), name='api_password_change'),
    re_path(r'^api/products/(?P<slug>.+)/wishlist/$', WishlistToggleAPIView.as_view(), name='api_wishlist_toggle'),
    path('api/wishlist/toggle/', WishlistToggleAPIView.as_view(), name='api_wishlist_toggle_id'),

    path('api/addresses/', views.AddressListCreateAPIView.as_view(), name='api_addresses'),
    path('api/addresses/<int:pk>/delete/', views.AddressDeleteAPIView.as_view(), name='api_address_delete'),

    path('api/provinces/', views.ProvinceListAPIView.as_view(), name='api_provinces'),
    path('api/cities/', views.CityListAPIView.as_view(), name='api_cities'),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
