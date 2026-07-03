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


