# apps/shop/utils.py

from .models import Cart, CartItem


def get_or_create_cart(request):
    """دریافت یا ایجاد سبد خرید برای کاربر جاری"""

    cart = None

    # 1. اگر کاربر لاگین است
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user, is_active=True).first()
        if not cart:
            cart = Cart.objects.create(user=request.user)

        # 2. اگر سبد مهمان وجود داشت، منتقلش کن به کاربر
        if request.session.get('cart_session_key'):
            guest_cart = Cart.objects.filter(
                session_key=request.session['cart_session_key'],
                is_active=True
            ).first()

            if guest_cart and guest_cart != cart:
                # انتقال آیتم‌های سبد مهمان به سبد کاربر
                for item in guest_cart.items.all():
                    cart_item, created = CartItem.objects.get_or_create(
                        cart=cart,
                        product=item.product,
                        defaults={'quantity': item.quantity}
                    )
                    if not created:
                        cart_item.quantity += item.quantity
                        cart_item.save()
                # غیرفعال کردن سبد مهمان
                guest_cart.is_active = False
                guest_cart.save()

            # پاک کردن session
            del request.session['cart_session_key']

    else:
        # کاربر مهمان
        session_key = request.session.get('cart_session_key')
        if session_key:
            cart = Cart.objects.filter(session_key=session_key, is_active=True).first()

        if not cart:
            # ایجاد سبد جدید برای مهمان
            cart = Cart.objects.create(session_key=request.session.session_key)
            request.session['cart_session_key'] = cart.session_key

    return cart