# apps/home/views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db.models import F, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import DetailView, ListView, TemplateView
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.seo import schema
from apps.seo.cache import cached_page_class
from apps.seo.seo import SEOMixin
from apps.seo.utils import canonical_url, image_url, meta_description, meta_title

from .models import Article, Tag, Comment, IndexPageSettings
from .pagination import ArticlePagination
from .serializers import (
    ArticleListSerializer,
    ArticleDetailSerializer,
    TagSerializer,
    CommentSerializer,
    CommentCreateSerializer,
    CategoryListSerializer,
    IndexPageSerializer,
    AdminCommentSerializer,
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
                Prefetch('comments', queryset=Comment.objects.filter(status='approved'))
            )
        )

    def retrieve(self, request, *args, **kwargs):
        # افزایش بازدید — atomic, so concurrent hits are not lost and
        # updated_at is left alone (it feeds sitemap <lastmod>).
        instance = self.get_object()
        Article.objects.filter(pk=instance.pk).update(view_count=F('view_count') + 1)

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
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'comment'

    def get(self, request, slug):
        """گرفتن نظرات یک مقاله"""
        article = get_object_or_404(Article, slug=slug, is_published=True)
        comments = article.comments.filter(status='approved', parent__isnull=True)
        serializer = CommentSerializer(comments, many=True)
        return Response(serializer.data)

    def post(self, request, slug):
        """ایجاد نظر جدید"""
        article = get_object_or_404(Article, slug=slug, is_published=True)

        # اگر کاربر لاگین نیست
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


# ══════════════════════════════════════════════════════════════
#  HTML pages — rendered server-side (see apps/shop/views.py for the
#  rationale; these were the same empty JS-hydrated shells).
# ══════════════════════════════════════════════════════════════

ARTICLES_PER_PAGE = 12


@cached_page_class()
class ArticleListPageView(SEOMixin, ListView):
    """صفحه لیست مقالات (برای رندر HTML)"""
    template_name = 'home/articles.html'
    context_object_name = 'articles'
    paginate_by = ARTICLES_PER_PAGE

    seo_title = 'مجله اسکوتر برقی'
    seo_description = (
        'راهنمای خرید، نگهداری و مقایسه اسکوتر برقی در مجله نکس گو؛ مقالات '
        'تخصصی درباره باتری، برد، سرعت و قوانین تردد اسکوتر برقی.'
    )

    def get_queryset(self):
        qs = (
            Article.objects.filter(is_published=True)
            .select_related('author')
            .prefetch_related('tags')
            .order_by('-published_at', '-created_at')
        )
        tag = self.request.GET.get('tag', '').strip()
        if tag:
            qs = qs.filter(tags__slug=tag).distinct()
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tags'] = Tag.objects.filter(articles__is_published=True).distinct()
        context['active_tag'] = self.request.GET.get('tag', '')
        return context

    def get_breadcrumbs(self, context):
        return [('خانه', '/'), ('مجله', reverse('home_app:articles'))]

    def get_seo(self, context):
        seo = super().get_seo(context)
        page_obj = context.get('page_obj')
        base = canonical_url(self.request, reverse('home_app:articles'))

        # A tag filter is a facet over the same articles: crawlable, but not
        # its own indexable page.
        if self.request.GET.get('tag'):
            seo.robots = 'noindex, follow'
            seo.canonical = base
            return seo

        if page_obj and page_obj.number > 1:
            seo.canonical = f'{base}?page={page_obj.number}'
            seo.title = meta_title(f'{self.seo_title} — صفحه {page_obj.number}')
            seo.description = meta_description(
                f'صفحه {page_obj.number} از مقالات و راهنماهای خرید اسکوتر برقی نکس گو.'
            )
        if page_obj and page_obj.has_previous():
            prev_num = page_obj.previous_page_number()
            seo.prev_url = base if prev_num == 1 else f'{base}?page={prev_num}'
        if page_obj and page_obj.has_next():
            seo.next_url = f'{base}?page={page_obj.next_page_number()}'
        return seo

    def get_json_ld(self, context, seo):
        return [schema.breadcrumbs(seo.breadcrumbs, self.request)]


@cached_page_class()
class ArticleDetailPageView(SEOMixin, DetailView):
    """صفحه جزئیات مقاله (برای رندر HTML)"""
    template_name = 'home/article_detail.html'
    context_object_name = 'article'
    seo_og_type = 'article'

    def get_queryset(self):
        return (
            Article.objects.filter(is_published=True)
            .select_related('author')
            .prefetch_related(
                'tags',
                Prefetch(
                    'comments',
                    queryset=Comment.objects.filter(status='approved')
                    .select_related('user')
                    .order_by('-created_at'),
                ),
            )
        )

    def get_context_data(self, **kwargs):
        article = self.object
        self.seo_title = article.title
        self.seo_description = meta_description(
            article.meta_description, article.excerpt, article.description
        )

        context = super().get_context_data(**kwargs)
        context['slug'] = article.slug
        context['comments'] = list(article.comments.all())
        context['related_articles'] = (
            Article.objects.filter(is_published=True, tags__in=article.tags.all())
            .exclude(pk=article.pk)
            .select_related('author')
            .distinct()[:3]
        )
        return context

    def get_canonical_path(self):
        return self.object.get_absolute_url()

    def get_seo(self, context):
        seo = super().get_seo(context)
        # An explicit canonical_url on the model means the article was
        # syndicated from elsewhere and this copy must not compete with it.
        if self.object.canonical_url:
            seo.canonical = self.object.canonical_url
        seo.image_alt = self.object.cover_alt_text or self.object.title
        seo.published_time = self.object.published_at or self.object.created_at
        seo.modified_time = self.object.updated_at
        return seo

    def get_seo_image(self, context):
        return image_url(self.object.cover_image, self.request)

    def get_breadcrumbs(self, context):
        return [
            ('خانه', '/'),
            ('مجله', reverse('home_app:articles')),
            (self.object.title, self.object.get_absolute_url()),
        ]

    def get_json_ld(self, context, seo):
        return [
            schema.article(self.object, self.request),
            schema.breadcrumbs(seo.breadcrumbs, self.request),
        ]


class IndexPageAPIView(generics.RetrieveAPIView):
    """API برای دریافت اطلاعات صفحه اصلی"""
    permission_classes = [AllowAny]
    serializer_class = IndexPageSerializer

    def get_object(self):
        # فقط یک رکورد وجود دارد
        return IndexPageSettings.objects.first()


@cached_page_class()
class IndexPageView(SEOMixin, TemplateView):
    """صفحه اصلی سایت"""
    template_name = 'home/index.html'

    def get_context_data(self, **kwargs):
        from apps.shop.models import Category, Product

        settings_obj = IndexPageSettings.objects.first()
        if settings_obj:
            self.seo_title = settings_obj.meta_title or ''
            self.seo_description = settings_obj.meta_description or ''

        context = super().get_context_data(**kwargs)
        context['index_settings'] = settings_obj
        context['categories'] = (
            Category.objects.filter(is_active=True, parent__isnull=True)
            .prefetch_related('features')
        )
        context['featured_products'] = (
            Product.objects.for_listing().filter(is_featured=True)[:8]
        )
        context['latest_articles'] = (
            Article.objects.filter(is_published=True)
            .select_related('author')
            .order_by('-published_at', '-created_at')[:3]
        )
        return context

    def get_canonical_path(self):
        return '/'

    def get_seo_image(self, context):
        settings_obj = context.get('index_settings')
        if settings_obj:
            return image_url(settings_obj.hero_image, self.request)
        return ''

    def get_breadcrumbs(self, context):
        # The home page is the root of every trail, so it has no breadcrumb of
        # its own — a one-item BreadcrumbList is ignored anyway.
        return []

    def get_json_ld(self, context, seo):
        return [
            schema.organization(self.request),
            schema.website(self.request),
        ]


class CategoryListAPIView(generics.ListAPIView):
    """API برای دریافت لیست دسته‌بندی‌ها"""
    permission_classes = [AllowAny]
    serializer_class = CategoryListSerializer
    pagination_class = None

    def get_queryset(self):
        from apps.shop.models import Category
        return Category.objects.filter(
            is_active=True,
            parent__isnull=True
        ).order_by('order', 'name')


@cached_page_class()
class CategoryPageView(SEOMixin, TemplateView):
    """صفحه نمایش دسته‌بندی‌ها"""
    template_name = 'home/categories.html'

    seo_title = 'دسته‌بندی اسکوترهای برقی'
    seo_description = 'مشاهده تمام دسته‌بندی‌های اسکوتر برقی نکس گو'

    def get_context_data(self, **kwargs):
        from apps.shop.models import Category
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.filter(
            is_active=True,
            parent__isnull=True
        ).prefetch_related('images', 'badges').order_by('order', 'name')
        return context

    def get_breadcrumbs(self, context):
        return [('خانه', '/'), ('دسته‌بندی‌ها', reverse('home_app:categories'))]

    def get_canonical_path(self):
        return reverse('home_app:categories')

    def get_json_ld(self, context, seo):
        return [schema.breadcrumbs(seo.breadcrumbs, self.request)]


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
    """صفحه درباره ما"""
    template_name = 'home/about_us.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class AdminCommentListAPIView(generics.ListAPIView):
    """لیست همه کامنت‌های مقالات برای ادمین، با فیلتر status"""
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
                status=status.HTTP_400_BAD_REQUEST
            )

        if action == 'approve':
            comment.status = 'approved'
            comment.rejection_reason = ''
        else:
            reason = request.data.get('rejection_reason', '').strip()
            if not reason:
                return Response(
                    {'error': 'برای رد کردن کامنت، وارد کردن دلیل الزامی است'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            comment.status = 'rejected'
            comment.rejection_reason = reason

        comment.save(update_fields=['status', 'rejection_reason', 'updated_at'])

        return Response({
            'status': 'success',
            'message': 'وضعیت کامنت با موفقیت به‌روزرسانی شد',
            'data': AdminCommentSerializer(comment).data
        })


@method_decorator(login_required(login_url='/access-denied/'), name='dispatch')
@method_decorator(staff_member_required(login_url='/access-denied/'), name='dispatch')
class CommentsModerationPageView(TemplateView):
    """صفحه مدیریت کامنت‌ها"""
    template_name = 'accounts/comments_moderation.html'


@method_decorator(login_required(login_url='/access-denied/'), name='dispatch')
@method_decorator(staff_member_required(login_url='/access-denied/'), name='dispatch')
class FinancePageView(TemplateView):
    """صفحه مالی ادمین"""
    template_name = 'accounts/admin-earning.html'