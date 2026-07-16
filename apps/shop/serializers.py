# apps/shop/serializers.py

from rest_framework import serializers

from .models import (
    Product, Category, ProductSpec, TrustBadge,
    MarketingFeature, StatFeature, ProductImage,
    ProductReview, Wishlist, OrderItem, Order
)
from ..accounts.serializers import UserProfileSerializer, AddressSerializer


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


# apps/shop/serializers.py

from rest_framework import serializers
from apps.home.models import CategoryFeature
from .models import Category, CategoryHeroProduct, Wishlist


class CategoryFeatureSerializer(serializers.ModelSerializer):
    color_hex = serializers.SerializerMethodField()

    class Meta:
        model = CategoryFeature
        fields = ['color', 'color_hex']

    def get_color_hex(self, obj):
        return obj.get_color_hex()


class CategoryHeroProductSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source='product.id')
    product_name = serializers.CharField(source='product.name')
    product_slug = serializers.CharField(source='product.slug')
    product_price = serializers.DecimalField(source='product.price', max_digits=15, decimal_places=0)
    product_discount_price = serializers.DecimalField(source='product.discount_price', max_digits=15, decimal_places=0,
                                                      allow_null=True)
    product_description = serializers.CharField(source='product.description')
    product_tagline = serializers.CharField(source='product.tagline')
    cover_image_url = serializers.SerializerMethodField()
    cover_alt_text = serializers.CharField(source='product.cover_alt_text')

    class Meta:
        model = CategoryHeroProduct
        fields = [
            'product_id', 'product_name', 'product_slug', 'product_price',
            'product_discount_price', 'product_description', 'product_tagline',
            'cover_image_url', 'cover_alt_text', 'order'
        ]

    def get_cover_image_url(self, obj):
        if obj.product and obj.product.cover_image:
            return obj.product.cover_image.url
        return None


class CategoryDetailSerializer(serializers.ModelSerializer):  # ← این رو اضافه کن
    hero_products = CategoryHeroProductSerializer(many=True, read_only=True)
    color_hex = serializers.SerializerMethodField()
    products = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'icon', 'description', 'color_hex', 'hero_products', 'products']

    def get_color_hex(self, obj):
        feature = CategoryFeature.objects.filter(category=obj).first()
        if feature:
            return feature.get_color_hex()
        return '#4fd8ff'

    def get_products(self, obj):
        products = obj.products.filter(is_published=True, is_available=True)
        return ProductListSerializer(products, many=True, context=self.context).data


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)
    product_image = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'product_slug', 'product_image',
                  'quantity', 'price', 'discount', 'total']

    def get_product_image(self, obj):
        if obj.product and obj.product.cover_image:
            return obj.product.cover_image.url
        return None


class OrderListSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    status_label = serializers.SerializerMethodField()
    payment_label = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'tracking_code', 'status', 'status_label',
            'payment_status', 'payment_label', 'total', 'discount_amount',
            'shipping_cost', 'created_at', 'paid_at', 'delivered_at', 'items'
        ]

    def get_status_label(self, obj):
        labels = {
            'pending': 'در انتظار',
            'processing': 'در حال پردازش',
            'shipping': 'ارسال شده',
            'delivered': 'تحویل‌شده',
            'cancelled': 'لغوشده'
        }
        return labels.get(obj.status, obj.status)

    def get_payment_label(self, obj):
        labels = {
            'pending': 'در انتظار پرداخت',
            'paid': 'پرداخت‌شده',
            'failed': 'ناموفق',
            'refunded': 'بازگشت وجه'
        }
        return labels.get(obj.payment_status, obj.payment_status)


class DashboardSerializer(serializers.Serializer):
    """سریالایزر برای دیتای داشبورد"""
    user = UserProfileSerializer()
    stats = serializers.DictField()
    recent_orders = OrderListSerializer(many=True)
    comments = serializers.ListField()
    wishlist = serializers.ListField()
    addresses = AddressSerializer(many=True)
    notifications = serializers.ListField()


# apps/shop/serializers.py (افزودن)

class AdminOrderSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='user.fullname')
    customer_username = serializers.CharField(source='user.username')
    customer_avatar = serializers.SerializerMethodField()
    products = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'order_number', 'customer_name', 'customer_username',
            'customer_avatar', 'products', 'total', 'status',
            'status_label', 'created_at', 'payment_status'
        ]

    def get_customer_avatar(self, obj):
        if obj.user and obj.user.profile_image:
            return obj.user.profile_image.url
        return None

    def get_products(self, obj):
        return [item.product.name for item in obj.items.all()]

    def get_status_label(self, obj):
        return dict(Order.STATUS_CHOICES).get(obj.status, obj.status)