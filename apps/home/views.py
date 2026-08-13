# apps/home/views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Prefetch
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from rest_framework import generics
from rest_framework import status as http_status
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
                Prefetch(
                    'comments',
                    queryset=Comment.objects.filter(
                        status='approved', parent__isnull=True
                    ).select_related('user')
                )
            )
        )

    def retrieve(self, request, *args, **kwargs):
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
        """گرفتن نظرات تایید شده‌ی یک مقاله"""
        article = get_object_or_404(Article, slug=slug, is_published=True)
        comments = article.comments.filter(
            status='approved', parent__isnull=True
        ).select_related('user')
        serializer = CommentSerializer(comments, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request, slug):
        """ایجاد نظر جدید (با وضعیت pending)"""
        article = get_object_or_404(Article, slug=slug, is_published=True)

        if not request.user.is_authenticated:
            return Response(
                {'detail': 'برای ارسال نظر باید وارد حساب کاربری خود شوید.'},
                status=http_status.HTTP_401_UNAUTHORIZED
            )

        serializer = CommentCreateSerializer(
            data=request.data,
            context={'request': request, 'article_id': article.id}
        )

        if serializer.is_valid():
            comment = serializer.save()
            return Response(
                {
                    'comment': CommentSerializer(comment, context={'request': request}).data,
                    'message': 'نظر شما با موفقیت ثبت شد و پس از تایید توسط ادمین نمایش داده خواهد شد.'
                },
                status=http_status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)


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

from rest_framework import generics
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


class AboutUsPageView(TemplateView):
    template_name = 'home/about_us.html'


from rest_framework.permissions import IsAdminUser
from .serializers import AdminCommentSerializer  # اگه بالای فایل import گروهی داری، همونجا اضافه کن


class AdminCommentListAPIView(generics.ListAPIView):
    """لیست همه‌ی کامنت‌های مقالات برای ادمین، با فیلتر status"""
    permission_classes = [IsAdminUser]
    serializer_class = AdminCommentSerializer

    def get_queryset(self):
        qs = Comment.objects.select_related('user', 'article').order_by('-created_at')
        status_param = self.request.query_params.get('status', '').strip()
        if status_param in dict(Comment.STATUS_CHOICES):
            qs = qs.filter(status=status_param)
        return qs


class AdminCommentModerateAPIView(APIView):
    """تایید یا رد کامنت مقاله"""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        comment = get_object_or_404(Comment, pk=pk)
        action = request.data.get('action')

        if action not in ['approve', 'reject']:
            return Response(
                {'error': "مقدار action باید 'approve' یا 'reject' باشد"},
                status=http_status.HTTP_400_BAD_REQUEST
            )

        if action == 'approve':
            comment.status = 'approved'
            comment.rejection_reason = ''
        else:
            reason = request.data.get('rejection_reason', '').strip()
            if not reason:
                return Response(
                    {'error': 'برای رد کردن کامنت، وارد کردن دلیل الزامی است'},
                    status=http_status.HTTP_400_BAD_REQUEST
                )
            comment.status = 'rejected'
            comment.rejection_reason = reason

        comment.save(update_fields=['status', 'rejection_reason', 'updated_at'])

        return Response({
            'status': 'success',
            'message': 'وضعیت کامنت با موفقیت به‌روزرسانی شد',
            'data': AdminCommentSerializer(comment).data
        })

# apps/home/views.py
@method_decorator(login_required(login_url='/access-denied/'), name='dispatch')
@method_decorator(staff_member_required(login_url='/access-denied/'), name='dispatch')
class CommentsModerationPageView(TemplateView):
    template_name = 'accounts/comments_moderation.html'


@method_decorator(login_required(login_url='/access-denied/'), name='dispatch')
@method_decorator(staff_member_required(login_url='/access-denied/'), name='dispatch')
class FinancePageView(TemplateView):
    template_name = 'accounts/admin-earning.html'