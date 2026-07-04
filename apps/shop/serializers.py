# apps/shop/serializers.py

from rest_framework import serializers
from .models import (
    Product, Category, ProductSpec, TrustBadge,
    MarketingFeature, StatFeature, ProductImage,
    ProductReview, Wishlist
)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'icon']


class ProductSpecSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSpec
        fields = ['id', 'icon', 'value', 'label']


class TrustBadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrustBadge
        fields = ['id', 'icon', 'label', 'value']


class MarketingFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketingFeature
        fields = ['id', 'icon', 'title', 'description', 'accent']


class StatFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatFeature
        fields = ['id', 'number', 'suffix', 'label']


class ProductImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ['id', 'image_url', 'color_slug', 'color_label', 'color_hex', 'alt_text', 'sort_order', 'is_primary']

    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return None


class ProductReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.fullname', read_only=True)
    user_avatar = serializers.SerializerMethodField()

    class Meta:
        model = ProductReview
        fields = [
            'id', 'user', 'user_name', 'user_avatar', 'rating', 'title',
            'comment', 'status', 'helpful_count', 'is_verified_purchase',
            'created_at'
        ]
        read_only_fields = ['user', 'status', 'helpful_count', 'created_at']

    def get_user_avatar(self, obj):
        if obj.user and obj.user.profile_image:
            return obj.user.profile_image.url
        return None


class ProductReviewCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductReview
        fields = ['rating', 'title', 'comment']

    def validate(self, data):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("برای ثبت نظر باید وارد حساب کاربری خود شوید.")
        return data

    def save(self, **kwargs):
        request = self.context.get('request')
        product_id = self.context.get('product_id')

        self.validated_data['user'] = request.user
        self.validated_data['product_id'] = product_id
        self.validated_data['status'] = 'pending'  # پیش‌فرض: در انتظار تایید

        return super().save(**kwargs)


class ProductListSerializer(serializers.ModelSerializer):
    """برای لیست محصولات (سبک)"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    cover_image_url = serializers.SerializerMethodField()
    average_rating = serializers.FloatField(read_only=True)
    reviews_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'cover_image_url', 'cover_alt_text',
            'price', 'discount_price', 'final_price', 'average_rating',
            'reviews_count', 'is_available', 'is_featured', 'category_name',
            'created_at'
        ]

    def get_cover_image_url(self, obj):
        if obj.cover_image:
            return obj.cover_image.url
        return None


class ProductDetailSerializer(serializers.ModelSerializer):
    """برای جزئیات کامل محصول"""
    category = CategorySerializer(read_only=True)
    specs = ProductSpecSerializer(many=True, read_only=True)
    trust_badges = TrustBadgeSerializer(many=True, read_only=True)
    marketing_features = MarketingFeatureSerializer(many=True, read_only=True)
    stat_features = StatFeatureSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    cover_image_url = serializers.SerializerMethodField()
    average_rating = serializers.FloatField(read_only=True)
    reviews_count = serializers.IntegerField(read_only=True)
    rating_distribution = serializers.DictField(read_only=True)
    is_in_wishlist = serializers.SerializerMethodField()
    # is_verified = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'category', 'tagline', 'description',
            'cover_image_url', 'cover_alt_text', 'price', 'discount_price',
            'final_price', 'stock', 'is_available', 'is_published',
            'is_featured', 'specs', 'trust_badges', 'marketing_features',
            'stat_features', 'images', 'average_rating', 'reviews_count',
            'rating_distribution', 'view_count', 'is_in_wishlist',
            'meta_title', 'meta_description', 'created_at', 'updated_at'
        ]

    def get_cover_image_url(self, obj):
        if obj.cover_image:
            return obj.cover_image.url
        return None

    def get_is_in_wishlist(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Wishlist.objects.filter(user=request.user, product=obj).exists()
        return False


class WishlistSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)

    class Meta:
        model = Wishlist
        fields = ['id', 'product', 'created_at']