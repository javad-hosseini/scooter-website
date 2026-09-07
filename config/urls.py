"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps import views as sitemap_views
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

from apps.seo import views as seo_views
from apps.seo.cache import versioned_cache_page
from apps.seo.sitemaps import SITEMAPS

# Errors are rendered by our own templates so a missing page returns a real
# 404 with usable navigation instead of a dead end (or, worse, a soft 404).
handler404 = 'apps.seo.views.page_not_found'
handler500 = 'apps.seo.views.server_error'

# Sitemaps are relatively expensive to build, so they are cached for a day —
# but under a version namespace that any product/article save bumps, so a new
# page still shows up in the sitemap immediately.
sitemap_cache = versioned_cache_page(60 * 60 * 24)

urlpatterns = [
    path('', include('apps.home.urls', namespace='home_app')),

    # ===== Crawling & indexation =====
    path('robots.txt', seo_views.robots_txt, name='robots_txt'),
    path(
        'sitemap.xml',
        sitemap_cache(sitemap_views.index),
        {'sitemaps': SITEMAPS, 'sitemap_url_name': 'sitemap-section'},
        name='sitemap-index',
    ),
    path(
        'sitemap-<section>.xml',
        sitemap_cache(sitemap_views.sitemap),
        {'sitemaps': SITEMAPS},
        name='sitemap-section',
    ),

    # ===== Static content pages =====
    path('', include('apps.seo.urls', namespace='seo')),

    # 📄 schema (خروجی خام OpenAPI JSON)
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),

    # 📘 Swagger UI (همون /docs شبیه FastAPI)
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),

    # 📚 ReDoc UI (یه UI تمیزتر و مستنداتی)
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    path("i18n/", include("django.conf.urls.i18n")),
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls', namespace='accounts_app')),
    path('shop/', include('apps.shop.urls', namespace='shop_app')),
]

# ===== 301 redirects for legacy / mistyped paths =====
# Several templates linked to /products/, /blog/, /models/ and /register/,
# none of which ever resolved — every one of those links was a 404 bleeding
# crawl budget and internal link equity. They now redirect permanently to the
# canonical page instead of being silently removed, so any external link or
# already-indexed URL is consolidated rather than dropped.
_LEGACY_REDIRECTS = [
    ('products/', '/shop/'),
    ('models/', '/shop/'),
    ('collection/', '/shop/'),
    ('blog/', '/articles/'),
    ('guide/', '/articles/'),
    ('register/', '/accounts/register/'),
    ('login/', '/accounts/login/'),
    ('dashboard/', '/accounts/dashboard/'),
]
urlpatterns += [
    path(source, RedirectView.as_view(url=target, permanent=True))
    for source, target in _LEGACY_REDIRECTS
]
urlpatterns += [
    re_path(
        r'^product/(?P<slug>[^/]+)/$',
        RedirectView.as_view(pattern_name='shop_app:product_detail', permanent=True),
    ),
    re_path(
        r'^category/(?P<slug>[^/]+)/$',
        RedirectView.as_view(pattern_name='shop_app:category_products', permanent=True),
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
