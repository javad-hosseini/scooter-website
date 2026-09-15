# apps/shop/utils/coupon_utils.py
"""اعتبارسنجی کد تخفیف.

هم سبد خرید و هم ثبت سفارش از همین‌جا استفاده می‌کنند تا قانون‌ها یک‌جا
تعریف شده باشند و مبلغ نمایش‌داده‌شده با مبلغ پرداختی یکی باشد.
"""

from decimal import Decimal

from apps.shop.models import Coupon


class CouponResult:
    """نتیجه‌ی بررسی یک کد تخفیف.

    یا کوپن معتبر است (`is_valid`) و `discount` مبلغ تخفیف را می‌دهد، یا
    `error` پیام فارسی‌ای دارد که مستقیماً به کاربر نشان داده می‌شود.
    """

    __slots__ = ('coupon', 'discount', 'error')

    def __init__(self, coupon=None, discount=Decimal('0'), error=None):
        self.coupon = coupon
        self.discount = discount
        self.error = error

    @property
    def is_valid(self):
        return self.coupon is not None and self.error is None

    def __repr__(self):  # pragma: no cover - کمک به دیباگ
        return f'<CouponResult coupon={self.coupon} discount={self.discount} error={self.error!r}>'


class CouponManager:
    """بررسی و محاسبه‌ی کد تخفیف"""

    @staticmethod
    def find(code):
        """پیدا کردن کوپن بدون حساسیت به بزرگی/کوچکی حروف و فاصله‌های اضافی."""
        code = (code or '').strip()
        if not code:
            return None
        return Coupon.objects.filter(code__iexact=code).first()

    @classmethod
    def validate(cls, code, user, amount):
        """بررسی کد تخفیف برای یک کاربر و یک مبلغ مشخص.

        Args:
            code: متنی که کاربر وارد کرده است.
            user: کاربر جاری (برای سقف استفاده‌ی هر کاربر).
            amount: مبلغ قابل تخفیف سبد خرید — یعنی جمع کالاها پس از کسر
                تخفیف خودِ محصولات و پیش از مالیات و هزینه‌ی ارسال.

        Returns:
            CouponResult
        """
        if not (code or '').strip():
            return CouponResult(error='کد تخفیف را وارد کنید')

        coupon = cls.find(code)
        if coupon is None:
            return CouponResult(error='کد تخفیف نامعتبر است')

        error = coupon.error_for(user, Decimal(str(amount or 0)))
        if error:
            return CouponResult(coupon=coupon, error=error)

        return CouponResult(coupon=coupon, discount=coupon.discount_for(amount))
