from django.contrib import admin
from django.utils.html import format_html
from django.contrib.auth import get_user_model

from .models import Article, Tag, Comment

User = get_user_model()


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'article_count']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}

    def article_count(self, obj):
        return obj.articles.count()

    article_count.short_description = 'تعداد مقالات'


class CommentInline(admin.TabularInline):
    """نمایش نظرات در صفحه مقاله"""
    model = Comment
    extra = 0
    fields = ['user', 'content_preview', 'is_approved', 'created_at']
    readonly_fields = ['user', 'content_preview', 'created_at']
    can_delete = True
    show_change_link = True

    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content

    content_preview.short_description = 'متن نظر'


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'author', 'cover_image_preview', 'attachment_preview',
        'tag_list', 'time_to_read', 'comments_count', 'view_count',
        'is_published', 'created_at'
    ]
    list_filter = ['is_published', 'tags', 'author', 'created_at']
    search_fields = ['title', 'description', 'author__username', 'author__fullname']
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ['tags']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at', 'attachment_preview_large', 'cover_image_preview_large']
    list_per_page = 25
    actions = ['make_published', 'make_unpublished']
    inlines = [CommentInline]

    fieldsets = (
        ('محتوای اصلی', {
            'fields': ('title', 'slug', 'author', 'tags', 'description', 'excerpt')
        }),
        ('تصویر کاور', {
            'fields': ('cover_image', 'cover_alt_text', 'cover_image_preview_large')
        }),
        ('فایل پیوست', {
            'fields': ('attachment', 'attachment_preview_large')
        }),
        ('متادیتا و سئو', {
            'fields': ('meta_description', 'meta_keywords', 'canonical_url')
        }),
        ('زمان و انتشار', {
            'fields': ('time_to_read', 'is_published', 'published_at', 'created_at', 'updated_at')
        }),
        ('آمار', {
            'fields': ('view_count',),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('author').prefetch_related('tags')

    def tag_list(self, obj):
        return ', '.join(t.name for t in obj.tags.all())

    tag_list.short_description = 'تگ‌ها'

    def comments_count(self, obj):
        count = obj.comments.filter(is_approved=True).count()
        return format_html('<span style="color:var(--neon);">{}</span>', count)

    comments_count.short_description = 'نظرات'

    # ===== تصویر شاخص =====
    def cover_image_preview(self, obj):
        """پیش‌نمایش کوچک تصویر شاخص در لیست"""
        if obj.cover_image:
            return format_html('<img src="{}" style="height:36px;width:36px;border-radius:6px;object-fit:cover;" />',
                               obj.cover_image.url)
        return '—'

    cover_image_preview.short_description = 'کاور'

    def cover_image_preview_large(self, obj):
        """پیش‌نمایش بزرگ تصویر شاخص در صفحه ویرایش"""
        if obj.cover_image:
            return format_html(
                '<img src="{}" style="max-height:250px;max-width:100%;border-radius:10px;border:1px solid #e2e8f0;" />',
                obj.cover_image.url
            )
        return 'تصویری آپلود نشده'

    cover_image_preview_large.short_description = 'پیش‌نمایش کاور'

    # ===== فایل پیوست =====
    def attachment_preview(self, obj):
        """پیش‌نمایش کوچک در لیست"""
        if not obj.attachment:
            return '—'
        if obj.attachment_type == 'image':
            return format_html('<img src="{}" style="height:36px;border-radius:6px;" />', obj.attachment.url)
        icons = {'video': '🎬', 'audio': '🎵', 'pdf': '📄'}
        return icons.get(obj.attachment_type, '📎')

    attachment_preview.short_description = 'فایل'

    def attachment_preview_large(self, obj):
        """پیش‌نمایش بزرگ در صفحه ویرایش"""
        if not obj.attachment:
            return 'فایلی آپلود نشده'
        url = obj.attachment.url
        if obj.attachment_type == 'image':
            return format_html('<img src="{}" style="max-height:220px;border-radius:10px;" />', url)
        elif obj.attachment_type == 'video':
            return format_html('<video src="{}" controls style="max-height:220px;border-radius:10px;"></video>', url)
        elif obj.attachment_type == 'audio':
            return format_html('<audio src="{}" controls></audio>', url)
        elif obj.attachment_type == 'pdf':
            return format_html('<a href="{}" target="_blank" style="color:var(--neon);">📄 مشاهده PDF</a>', url)
        return 'نوع فایل ناشناخته'

    attachment_preview_large.short_description = 'پیش‌نمایش فایل'

    @admin.action(description='انتشار مقالات انتخاب‌شده')
    def make_published(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(is_published=True, published_at=timezone.now())
        self.message_user(request, f'{updated} مقاله منتشر شد')

    @admin.action(description='لغو انتشار مقالات انتخاب‌شده')
    def make_unpublished(self, request, queryset):
        updated = queryset.update(is_published=False)
        self.message_user(request, f'{updated} مقاله از حالت انتشار خارج شد')


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = [
        'user_display', 'article_title', 'content_preview',
        'is_approved', 'is_reply', 'created_at'
    ]
    list_filter = ['is_approved', 'created_at', 'article']
    search_fields = ['content', 'user__fullname', 'user__username', 'article__title']
    readonly_fields = ['user', 'article', 'created_at', 'updated_at', 'parent']
    list_per_page = 25
    actions = ['approve_comments', 'unapprove_comments']

    fieldsets = (
        ('اطلاعات نظر', {
            'fields': ('article', 'user', 'parent')
        }),
        ('متن نظر', {
            'fields': ('content',)
        }),
        ('وضعیت', {
            'fields': ('is_approved', 'created_at', 'updated_at')
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'article', 'parent')

    def user_display(self, obj):
        if obj.user.profile_image:
            return format_html(
                '<img src="{}" style="height:24px;width:24px;border-radius:50%;object-fit:cover;margin-left:6px;" /> {}',
                obj.user.profile_image.url,
                obj.user.fullname or obj.user.username
            )
        return obj.user.fullname or obj.user.username

    user_display.short_description = 'کاربر'

    def article_title(self, obj):
        return format_html(
            '<a href="/admin/home/article/{}/change/" style="color:var(--neon);">{}</a>',
            obj.article.id,
            obj.article.title[:30] + '...' if len(obj.article.title) > 30 else obj.article.title
        )

    article_title.short_description = 'مقاله'

    def content_preview(self, obj):
        return obj.content[:60] + '...' if len(obj.content) > 60 else obj.content

    content_preview.short_description = 'متن نظر'

    def is_reply(self, obj):
        return '✅' if obj.parent else '—'

    is_reply.short_description = 'پاسخ'

    @admin.action(description='تایید نظرات انتخاب‌شده')
    def approve_comments(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f'{updated} نظر تایید شد')

    @admin.action(description='لغو تایید نظرات انتخاب‌شده')
    def unapprove_comments(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f'{updated} نظر از تایید خارج شد')