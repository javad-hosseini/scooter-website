# apps/shop/utils/tax_utils.py

from django.conf import settings
from decimal import Decimal


class TaxCalculator:
    """محاسبه‌گر مالیات و هزینه‌ها"""

    @staticmethod
    def get_tax_rate():
        """دریافت نرخ مالیات از تنظیمات"""
        return Decimal(str(getattr(settings, 'TAX_RATE', 0.09)))

    @staticmethod
    def calculate_tax(amount):
        """محاسبه مالیات یک مبلغ"""
        return (amount * TaxCalculator.get_tax_rate()).quantize(Decimal('0'))

    @staticmethod
    def get_shipping_cost(subtotal):
        """محاسبه هزینه ارسال بر اساس مبلغ سبد"""
        threshold = getattr(settings, 'FREE_SHIPPING_THRESHOLD', 500_000)
        cost = getattr(settings, 'SHIPPING_COST', 25_000)
        return 0 if subtotal >= threshold else cost

    @staticmethod
    def calculate_total(subtotal, discount=0, shipping_cost=0):
        """
        محاسبه مبلغ نهایی

        Args:
            subtotal: مبلغ کل قبل از تخفیف
            discount: مبلغ تخفیف (اختیاری)
            shipping_cost: هزینه ارسال (اختیاری)
        """
        tax = TaxCalculator.calculate_tax(subtotal)
        return subtotal - discount + shipping_cost + tax