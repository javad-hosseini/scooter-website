from django.urls import path, re_path

from . import views

app_name = 'home_app'

# Article slugs allow unicode, so they cannot use <slug:...>. Restricting the
# pattern to a single path segment stops one article resolving at an unbounded
# number of nested URLs.
SLUG = r'(?P<slug>[^/]+)'

urlpatterns = [
    # ===== صفحه اصلی =====
    path('', views.IndexPageView.as_view(), name='index'),

    # ===== صفحات HTML مقالات =====
    path('articles/', views.ArticleListPageView.as_view(), name='articles'),
    re_path(rf'^articles/{SLUG}/$', views.ArticleDetailPageView.as_view(),
            name='article_detail'),

    # ===== API =====
    path('api/index/', views.IndexPageAPIView.as_view(), name='api_index'),
    path('api/articles/', views.ArticleListAPIView.as_view(), name='api_articles'),
    path('api/tags/', views.TagListAPIView.as_view(), name='api_tags'),
    # ✅ More specific routes first.
    re_path(rf'^api/articles/{SLUG}/comments/$', views.CommentListCreateAPIView.as_view(),
            name='api_comments'),
    re_path(rf'^api/articles/{SLUG}/$', views.ArticleDetailAPIView.as_view(),
            name='api_article_detail'),
]
