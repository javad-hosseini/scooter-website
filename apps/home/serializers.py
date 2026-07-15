# apps/home/serializers.py
from rest_framework import serializers

from .models import Article, Tag, Comment


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['name', 'slug']


class ArticleListSerializer(serializers.ModelSerializer):
    """برای صفحه لیست - سبک، بدون description کامل"""
    author_name = serializers.CharField(source='author.fullname', read_only=True)
    author_profile_image = serializers.SerializerMethodField()
    tags = TagSerializer(many=True, read_only=True)
    cover_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = [
            'title', 'slug', 'excerpt', 'cover_image_url', 'cover_alt_text',
            'time_to_read', 'created_at', 'published_at', 'author_name',
            'author_profile_image', 'tags', 'view_count'
        ]

    def get_author_profile_image(self, obj):
        if obj.author and obj.author.profile_image:
            return obj.author.profile_image.url
        return None

    def get_cover_image_url(self, obj):
        if obj.cover_image:
            return obj.cover_image.url
        # اگر cover_image نداشت، از attachment استفاده کن (اگر عکس بود)
        if obj.attachment and obj.attachment_type == 'image':
            return obj.attachment.url
        return None


class ArticleDetailSerializer(serializers.ModelSerializer):
    """برای صفحه جزئیات - شامل description کامل و اطلاعات نویسنده"""
    author_name = serializers.CharField(source='author.fullname', read_only=True)
    author_bio = serializers.CharField(source='author.bio', read_only=True, default='')
    author_profile_image = serializers.SerializerMethodField()
    author_joined_date = serializers.SerializerMethodField()
    tags = TagSerializer(many=True, read_only=True)
    cover_image_url = serializers.SerializerMethodField()
    related_articles = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    recent_comments = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = [
            'title', 'slug', 'description', 'excerpt', 'cover_image_url', 'cover_alt_text',
            'attachment', 'attachment_type', 'time_to_read', 'created_at', 'updated_at',
            'published_at', 'author_name', 'author_bio', 'author_profile_image',
            'author_joined_date', 'tags', 'meta_description', 'meta_keywords',
            'canonical_url', 'view_count', 'related_articles', 'comments_count',
            'recent_comments'
        ]

    def get_author_profile_image(self, obj):
        if obj.author and obj.author.profile_image:
            return obj.author.profile_image.url
        return None

    def get_author_joined_date(self, obj):
        if obj.author and obj.author.date_joined:
            return obj.author.date_joined.strftime('%B %Y')
        return None

    def get_cover_image_url(self, obj):
        if obj.cover_image:
            return obj.cover_image.url
        # اگر cover_image نداشت، از attachment استفاده کن (اگر عکس بود)
        if obj.attachment and obj.attachment_type == 'image':
            return obj.attachment.url
        return None

    def get_related_articles(self, obj):
        """مقالات مرتبط با همان تگ‌ها (حداکثر ۳ عدد)"""
        # گرفتن تگ‌های مقاله فعلی
        tag_ids = obj.tags.values_list('id', flat=True)

        # پیدا کردن مقالات دیگر با همان تگ‌ها
        related = Article.objects.filter(
            is_published=True,
            tags__id__in=tag_ids
        ).exclude(id=obj.id).distinct()[:3]

        # سریالایز کردن با یک سریالایزر ساده
        return ArticleListSerializer(related, many=True, context=self.context).data

    def get_comments_count(self, obj):
        return obj.comments.filter(is_approved=True).count()

    def get_recent_comments(self, obj):
        """آخرین ۵ نظر تایید شده"""
        comments = obj.comments.filter(is_approved=True, parent__isnull=True)[:5]
        return CommentSerializer(comments, many=True, context=self.context).data


class CommentSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.fullname', read_only=True)
    user_profile_image = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'user', 'user_name', 'user_profile_image', 'content', 'created_at', 'is_approved', 'parent',
                  'replies']
        read_only_fields = ['user', 'created_at', 'is_approved']

    def get_user_profile_image(self, obj):
        if obj.user and obj.user.profile_image:
            return obj.user.profile_image.url
        return None

    def get_replies(self, obj):
        replies = obj.replies.filter(is_approved=True)
        return CommentSerializer(replies, many=True).data


class CommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ['content', 'parent']

    def validate(self, data):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("برای ارسال نظر باید وارد حساب کاربری خود شوید.")
        return data

    def save(self, **kwargs):
        request = self.context.get('request')
        article_id = self.context.get('article_id')

        self.validated_data['user'] = request.user
        self.validated_data['article_id'] = article_id

        return super().save(**kwargs)


# apps/home/serializers.py (افزودن به سریالایزرهای موجود)

from .models import (
    IndexPageSettings, ProductCard,
    Testimonial, Promise, Article
)

# apps/home/serializers.py

from rest_framework import serializers
from .models import CategoryFeature, CategoryImage, CategoryBadge
from apps.shop.models import Category


class CategoryFeatureSerializer(serializers.ModelSerializer):
    color_hex = serializers.SerializerMethodField()

    class Meta:
        model = CategoryFeature
        fields = ['id', 'icon', 'value', 'label', 'color', 'color_hex', 'order']

    def get_color_hex(self, obj):
        return obj.get_color_hex()


class CategoryImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = CategoryImage
        fields = ['id', 'image_url', 'alt_text', 'is_primary', 'order']

    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return None


class CategoryBadgeSerializer(serializers.ModelSerializer):
    color_hex = serializers.SerializerMethodField()

    class Meta:
        model = CategoryBadge
        fields = ['id', 'label', 'badge_text', 'color', 'color_hex', 'order']

    def get_color_hex(self, obj):
        return obj.get_color_hex()


class CategoryListSerializer(serializers.ModelSerializer):
    """سریالایزر برای نمایش دسته‌بندی‌ها در صفحه اصلی"""
    features = CategoryFeatureSerializer(many=True, read_only=True)
    images = CategoryImageSerializer(many=True, read_only=True)
    badges = CategoryBadgeSerializer(many=True, read_only=True)
    primary_image = serializers.SerializerMethodField()
    primary_color = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'icon', 'description',
            'features', 'images', 'badges', 'primary_image',
            'primary_color', 'is_active', 'order'
        ]

    def get_primary_image(self, obj):
        primary = obj.images.filter(is_primary=True).first()
        if primary:
            return CategoryImageSerializer(primary).data
        first = obj.images.first()
        if first:
            return CategoryImageSerializer(first).data
        return None

    def get_primary_color(self, obj):
        # گرفتن رنگ از اولین ویژگی یا اولین نشان
        feature = obj.features.first()
        if feature:
            return feature.get_color_hex()
        badge = obj.badges.first()
        if badge:
            return badge.get_color_hex()
        return '#00f0ff'


class ProductCardSerializer(serializers.ModelSerializer):
    color_hex = serializers.SerializerMethodField()
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    product_description = serializers.CharField(source='product.description', read_only=True)
    product_price = serializers.DecimalField(source='product.final_price', read_only=True, max_digits=15,
                                             decimal_places=0)
    product_cover = serializers.SerializerMethodField()
    product_specs = serializers.SerializerMethodField()

    class Meta:
        model = ProductCard
        fields = [
            'id', 'product', 'product_name', 'product_slug', 'product_description',
            'product_price', 'product_cover', 'product_specs',
            'badge_text', 'color', 'color_hex', 'order'
        ]

    def get_color_hex(self, obj):
        colors = dict(ProductCard.PRODUCT_COLORS)
        return colors.get(obj.color, '#4fd8ff')

    def get_product_cover(self, obj):
        if obj.product and obj.product.cover_image:
            return obj.product.cover_image.url
        return None

    def get_product_specs(self, obj):
        # گرفتن 3 ویژگی اول محصول
        specs = obj.product.specs.all()[:3]
        return [
            {
                'value': spec.value,
                'unit': '',
                'label': spec.label
            } for spec in specs
        ]


# apps/home/serializers.py

class TestimonialSerializer(serializers.ModelSerializer):
    color_start_hex = serializers.SerializerMethodField()
    color_end_hex = serializers.SerializerMethodField()
    initials = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Testimonial
        fields = [
            'id', 'name', 'quote', 'rating', 'initials',
            'color_start_hex', 'color_end_hex', 'avatar_url',
            'is_featured', 'order', 'is_active'
        ]

    def get_color_start_hex(self, obj):
        colors = {
            'neon': '#4fd8ff',
            'orange': '#ff9a3c',
            'green': '#a8e063',
            'neon2': '#8b7bff',
            'neon3': '#ff6cc4',
        }
        return colors.get(obj.avatar_color_start, '#4fd8ff')

    def get_color_end_hex(self, obj):
        colors = {
            'neon': '#4fd8ff',
            'orange': '#ff9a3c',
            'green': '#a8e063',
            'neon2': '#8b7bff',
            'neon3': '#ff6cc4',
        }
        return colors.get(obj.avatar_color_end, '#8b7bff')

    def get_avatar_url(self, obj):
        if obj.avatar_image:
            return obj.avatar_image.url
        return None

    def get_initials(self, obj):
        return obj.get_initials()


class PromiseSerializer(serializers.ModelSerializer):
    color_hex = serializers.SerializerMethodField()
    rgb = serializers.SerializerMethodField()

    class Meta:
        model = Promise
        fields = [
            'id', 'icon_svg', 'label', 'title', 'description',
            'badge_value', 'badge_unit', 'color', 'color_hex', 'rgb',
            'order', 'is_active'
        ]

    def get_color_hex(self, obj):
        colors = dict(Promise.PROMISE_COLORS)
        return colors.get(obj.color, '#4fd8ff')

    def get_rgb(self, obj):
        rgb_map = {
            'neon': '79,216,255',
            'orange': '255,154,60',
            'green': '168,224,99',
            'neon2': '139,123,255',
            'neon3': '255,108,196',
        }
        return rgb_map.get(obj.color, '79,216,255')


class ArticleCardSerializer(serializers.ModelSerializer):
    tags_list = serializers.SerializerMethodField()
    cover_url = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = ['id', 'title', 'slug', 'excerpt', 'cover_url', 'tags_list']

    def get_tags_list(self, obj):
        return [{'name': tag.name, 'slug': tag.slug} for tag in obj.tags.all()[:2]]

    def get_cover_url(self, obj):
        if obj.cover_image:
            return obj.cover_image.url
        return None


class IndexPageSerializer(serializers.ModelSerializer):
    """سریالایزر کامل صفحه اصلی"""
    categories = serializers.SerializerMethodField()
    product_cards = serializers.SerializerMethodField()
    testimonials = serializers.SerializerMethodField()
    promises = serializers.SerializerMethodField()
    recent_articles = serializers.SerializerMethodField()

    class Meta:
        model = IndexPageSettings
        fields = '__all__'

    def get_categories(self, obj):
        """گرفتن دسته‌بندی‌های فعال با ویژگی‌هایشان"""
        from apps.shop.models import Category
        categories = Category.objects.filter(is_active=True, parent__isnull=True).order_by('order')
        result = []
        for cat in categories:
            features = cat.features.all()[:4]
            result.append({
                'id': cat.id,
                'name': cat.name,
                'slug': cat.slug,
                'icon': cat.icon,
                'description': cat.description,
                'features': CategoryFeatureSerializer(features, many=True).data,
                'image': self._get_category_image(cat),
                'color': features.first().color if features.exists() else 'neon',
                'color_hex': features.first().get_color_hex() if features.exists() else '#4fd8ff',
            })
        return result

    def _get_category_image(self, category):
        """گرفتن تصویر برای دسته‌بندی (از اولین محصول یا پیش‌فرض)"""
        product = category.products.filter(is_published=True).first()
        if product and product.cover_image:
            return product.cover_image.url
        return None

    def get_product_cards(self, obj):
        cards = ProductCard.objects.filter(is_active=True).order_by('order')[:6]
        return ProductCardSerializer(cards, many=True).data

    def get_testimonials(self, obj):
        testimonials = Testimonial.objects.filter(is_active=True).order_by('order')
        return TestimonialSerializer(testimonials, many=True).data

    def get_promises(self, obj):
        promises = Promise.objects.filter(is_active=True).order_by('order')
        return PromiseSerializer(promises, many=True).data

    def get_recent_articles(self, obj):
        articles = Article.objects.filter(is_published=True).order_by('-published_at', '-created_at')[:3]
        return ArticleCardSerializer(articles, many=True).data
