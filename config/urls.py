"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.http import JsonResponse
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

def cache_debug_view(request):
    return JsonResponse({"test": "no headers set manually"})

urlpatterns = [
    path('', include('apps.home.urls', namespace='home_app')),
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
    path('cache-debug-test/', cache_debug_view),
    path('api/shop/', include('apps.shop.urls')),
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls', namespace='accounts_app')),
    path('shop/', include('apps.shop.urls', namespace='shop_app')),
    path('social-auth/', include('allauth.urls')),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
