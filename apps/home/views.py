# apps/home/views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Prefetch
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from .models import Article, Tag, Comment
from .pagination import ArticlePagination
from .serializers import (
    ArticleListSerializer, ArticleDetailSerializer,
    TagSerializer, CommentSerializer, CommentCreateSerializer
)


class ArticleListAPIView(generics.ListAPIView):
    """API برای لیست مقالات"""
    permission_classes = [AllowAny]
    serializer_class = ArticleListSerializer
    lookup_field = 'slug'
    lookup_url_kwarg = 'slug'
    pagination_class = ArticlePagination

    def get_queryset(self):
        qs = (
            Article.objects
            .filter(is_published=True)
            .select_related('author')
            .prefetch_related('tags')
            .order_by('-published_at', '-created_at')
        )

        # جستجو در عنوان و محتوا
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(description__icontains=search))

        # فیلتر بر اساس تگ
        tag_slug = self.request.query_params.get('tag', '').strip()
        if tag_slug:
            qs = qs.filter(tags__slug=tag_slug)

        return qs.distinct()


class ArticleDetailAPIView(generics.RetrieveAPIView):
    """API برای جزئیات یک مقاله"""
    permission_classes = [AllowAny]
    serializer_class = ArticleDetailSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        return (
            Article.objects
            .filter(is_published=True)
            .select_related('author')
            .prefetch_related(
                'tags',
                Prefetch('comments', queryset=Comment.objects.filter(is_approved=True))
            )
        )

    def retrieve(self, request, *args, **kwargs):
        # افزایش تعداد بازدید
        instance = self.get_object()
        instance.view_count += 1
        instance.save(update_fields=['view_count'])

        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class TagListAPIView(generics.ListAPIView):
    """API برای لیست تگ‌ها"""
    permission_classes = [AllowAny]
    serializer_class = TagSerializer
    pagination_class = None

    def get_queryset(self):
        return Tag.objects.filter(articles__is_published=True).distinct().order_by('name')


class CommentListCreateAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        """گرفتن نظرات یک مقاله"""
        article = get_object_or_404(Article, slug=slug, is_published=True)
        comments = article.comments.filter(is_approved=True, parent__isnull=True)
        serializer = CommentSerializer(comments, many=True)
        return Response(serializer.data)

    def post(self, request, slug):  # این رو حتماً داشته باش
        """ایجاد نظر جدید"""
        article = get_object_or_404(Article, slug=slug, is_published=True)

        # اگه کاربر لاگین نیست
        if not request.user.is_authenticated:
            return Response(
                {'detail': 'برای ارسال نظر باید وارد حساب کاربری خود شوید.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        serializer = CommentCreateSerializer(
            data=request.data,
            context={'request': request, 'article_id': article.id}
        )

        if serializer.is_valid():
            comment = serializer.save()
            return Response(
                CommentSerializer(comment).data,
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ArticleListPageView(TemplateView):
    """صفحه لیست مقالات (برای رندر HTML)"""
    template_name = 'home/articles.html'


class ArticleDetailPageView(TemplateView):
    """صفحه جزئیات مقاله (برای رندر HTML)"""
    template_name = 'home/article_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['slug'] = self.kwargs.get('slug')
        return context


# apps/home/views.py (افزودن به ویوهای موجود)

from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.views.generic import TemplateView
from .models import IndexPageSettings
from .serializers import IndexPageSerializer


class IndexPageAPIView(generics.RetrieveAPIView):
    """API برای دریافت اطلاعات صفحه اصلی"""
    permission_classes = [AllowAny]
    serializer_class = IndexPageSerializer

    def get_object(self):
        # فقط یک رکورد وجود دارد
        return IndexPageSettings.objects.first()


class IndexPageView(TemplateView):
    """صفحه اصلی سایت"""
    template_name = 'home/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


# apps/home/views.py

from rest_framework import generics
from rest_framework.permissions import AllowAny
from django.views.generic import TemplateView
from apps.shop.models import Category
from .serializers import CategoryListSerializer


class CategoryListAPIView(generics.ListAPIView):
    """API برای دریافت لیست دسته‌بندی‌ها"""
    permission_classes = [AllowAny]
    serializer_class = CategoryListSerializer
    pagination_class = None

    def get_queryset(self):
        return Category.objects.filter(
            is_active=True,
            parent__isnull=True
        ).order_by('order', 'name')


class CategoryPageView(TemplateView):
    """صفحه نمایش دسته‌بندی‌ها"""
    template_name = 'home/categories.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


def is_admin_group(user):
    """چک کردن اینکه کاربر در گروه 'admin' هست"""
    return user.is_authenticated and user.groups.filter(name='admin').exists()


class AccessDeniedView(TemplateView):
    """صفحه عدم دسترسی"""
    template_name = 'home/access_denied.html'


@method_decorator(login_required(login_url='/access-denied/'), name='dispatch')
@method_decorator(staff_member_required(login_url='/access-denied/'), name='dispatch')
class AdminDashboardPageView(TemplateView):
    """صفحه داشبورد ادمین"""
    template_name = 'accounts/admin_dashboard.html'
