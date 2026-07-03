from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, re_path

from .views import (
    ArticleListAPIView,
    ArticleDetailAPIView,
    ArticleListPageView,
    ArticleDetailPageView,
    TagListAPIView,
    CommentListCreateAPIView
)

app_name = 'home_app'

urlpatterns = [
    # ===== صفحات HTML =====
    path('articles/', ArticleListPageView.as_view(), name='articles'),
    re_path(r'^articles/(?P<slug>.+)/$', ArticleDetailPageView.as_view(), name='article_detail'),

    # ===== API =====
    # ✅ IMPORTANT: URLهای با جزئیات بیشتر را اول قرار بده
    re_path(r'^api/articles/(?P<slug>.+)/comments/$', CommentListCreateAPIView.as_view(), name='api_comments'),
    re_path(r'^api/articles/(?P<slug>.+)/$', ArticleDetailAPIView.as_view(), name='api_article_detail'),
    path('api/articles/', ArticleListAPIView.as_view(), name='api_articles'),
    path('api/tags/', TagListAPIView.as_view(), name='api_tags'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)