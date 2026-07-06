from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, re_path

from . import views
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

    # ===== صفحه اصلی =====
    path('', views.IndexPageView.as_view(), name='index'),
    path('api/index/', views.IndexPageAPIView.as_view(), name='api_index'),

    # ===== صفحات مقالات (موجود) =====
    path('articles/', views.ArticleListPageView.as_view(), name='articles'),
    re_path(r'^articles/(?P<slug>.+)/$', views.ArticleDetailPageView.as_view(), name='article_detail'),

    # ===== API =====
    # ✅ IMPORTANT: URLهای با جزئیات بیشتر را اول قرار بده
    re_path(r'^api/articles/(?P<slug>.+)/comments/$', CommentListCreateAPIView.as_view(), name='api_comments'),
    re_path(r'^api/articles/(?P<slug>.+)/$', ArticleDetailAPIView.as_view(), name='api_article_detail'),
    path('api/articles/', ArticleListAPIView.as_view(), name='api_articles'),
    path('api/tags/', TagListAPIView.as_view(), name='api_tags'),


    # ===== API مقالات (موجود) =====
    path('api/articles/', views.ArticleListAPIView.as_view(), name='api_articles'),
    re_path(r'^api/articles/(?P<slug>.+)/$', views.ArticleDetailAPIView.as_view(), name='api_article_detail'),
    path('api/tags/', views.TagListAPIView.as_view(), name='api_tags'),
    re_path(r'^api/articles/(?P<slug>.+)/comments/$', views.CommentListCreateAPIView.as_view(), name='api_comments'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
