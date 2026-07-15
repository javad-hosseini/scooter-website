from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils.html import format_html

# from apps.shop.models import Category
from .models import Article, Tag, Comment
from .models import CategoryImage, CategoryBadge

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


# apps/home/admin.py (افزودن به ادمین موجود)

from django.contrib import admin
from .models import (
    IndexPageSettings, CategoryFeature, ProductCard,
    Testimonial, Promise
)


@admin.register(IndexPageSettings)
class IndexPageSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('SEO', {
            'fields': ('meta_title', 'meta_description')
        }),
        ('بخش هیرو', {
            'fields': (
                'hero_title_part1', 'hero_title_part2', 'hero_title_part3',
                'hero_tag', 'hero_description', 'hero_btn_text', 'hero_btn_secondary_text',
                'hero_image', 'hero_mobile_image', 'hero_image_alt'
            )
        }),
        ('آمارهای هیرو', {
            'fields': (
                'hero_stat_1_value', 'hero_stat_1_unit', 'hero_stat_1_label',
                'hero_stat_2_value', 'hero_stat_2_unit', 'hero_stat_2_label',
                'hero_stat_3_value', 'hero_stat_3_unit', 'hero_stat_3_label',
                'hero_stat_4_value', 'hero_stat_4_unit', 'hero_stat_4_label',
            )
        }),
        ('بخش پرفروش‌ها', {
            'fields': ('best_sellers_label', 'best_sellers_title')
        }),
        ('بخش نظرات', {
            'fields': (
                'testimonials_label', 'testimonials_title',
                'testimonials_rating', 'testimonials_count',
                'testimonials_count_label'
            )
        }),
        ('بخش راهنما', {
            'fields': ('guide_label', 'guide_title')
        }),
        ('بخش تعهدات', {
            'fields': ('promise_label', 'promise_title')
        }),
        ('بیانیه پایانی', {
            'fields': (
                'statement_eyebrow', 'statement_title',
                'statement_title_highlight', 'statement_description',
                'statement_btn_text', 'statement_btn_secondary_text'
            )
        }),
        ('فوتر', {
            'fields': ('footer_tagline', 'footer_copyright')
        }),
    )

    def has_add_permission(self, request):
        # فقط یک رکورد مجاز است
        if IndexPageSettings.objects.exists():
            return False
        return True

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CategoryFeature)
class CategoryFeatureAdmin(admin.ModelAdmin):
    list_display = ['category', 'label', 'value', 'color', 'order']
    list_filter = ['category', 'color']
    list_editable = ['order']
    ordering = ['category', 'order']


@admin.register(ProductCard)
class ProductCardAdmin(admin.ModelAdmin):
    list_display = ['product', 'badge_text', 'color', 'order', 'is_active']
    list_filter = ['color', 'is_active']
    list_editable = ['order', 'is_active']
    search_fields = ['product__name']
    ordering = ['order']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "product":
            kwargs["queryset"] = db_field.remote_field.model.objects.filter(is_published=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ['name', 'avatar_preview', 'rating', 'is_featured', 'order', 'is_active']
    list_filter = ['rating', 'is_featured', 'is_active']
    list_editable = ['order', 'is_active']
    search_fields = ['name', 'quote']
    ordering = ['order']

    def avatar_preview(self, obj):
        if obj.avatar_image:
            return format_html(
                '<img src="{}" style="width:40px;height:40px;border-radius:50%;object-fit:cover;" />',
                obj.avatar_image.url
            )
        return '—'

    avatar_preview.short_description = 'عکس'


@admin.register(Promise)
class PromiseAdmin(admin.ModelAdmin):
    list_display = ['title', 'label', 'badge_value', 'color', 'order', 'is_active']
    list_filter = ['color', 'is_active']
    list_editable = ['order', 'is_active']
    ordering = ['order']


# apps/home/admin.py


class CategoryFeatureInline(admin.TabularInline):
    model = CategoryFeature
    extra = 1
    fields = ['icon', 'value', 'label', 'color', 'order']
    ordering = ['order']


class CategoryImageInline(admin.TabularInline):
    model = CategoryImage
    extra = 1
    fields = ['image', 'alt_text', 'is_primary', 'order']
    ordering = ['order']


class CategoryBadgeInline(admin.TabularInline):
    model = CategoryBadge
    extra = 1
    fields = ['label', 'badge_text', 'color', 'order']
    ordering = ['order']


# @admin.register(Category)
# class CategoryAdmin(admin.ModelAdmin):
#     list_display = ['name', 'slug', 'icon', 'is_active', 'order', 'feature_count']
#     list_filter = ['is_active']
#     search_fields = ['name', 'slug', 'description']
#     prepopulated_fields = {'slug': ('name',)}
#     list_editable = ['order', 'is_active']
#     inlines = [CategoryFeatureInline, CategoryImageInline, CategoryBadgeInline]
#
#     fieldsets = (
#         ('اطلاعات اصلی', {
#             'fields': ('name', 'slug', 'icon', 'description')
#         }),
#         ('والد', {
#             'fields': ('parent',)
#         }),
#         ('وضعیت', {
#             'fields': ('is_active', 'order')
#         }),
#         ('تاریخ', {
#             'fields': ('created_at', 'updated_at'),
#             'classes': ('collapse',)
#         }),
#     )
#
#     readonly_fields = ['created_at', 'updated_at']
#
#     def feature_count(self, obj):
#         return obj.features.count()
#
#     feature_count.short_description = 'تعداد ویژگی‌ها'
