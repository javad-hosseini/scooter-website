# apps/shop/utils/shipping_utils.py

from django.conf import settings
from decimal import Decimal


class ShippingCalculator:
    """محاسبه‌گر هزینه ارسال"""

    # تعریف روش‌های ارسال
    SHIPPING_METHODS = {
        'express': {
            'name': 'پیک موتوری (فوری)',
            'base_cost': 35_000,
            'free_threshold': 700_000,
            'estimated_days': 1,
        },
        'standard': {
            'name': 'پست پیشتاز',
            'base_cost': 25_000,
            'free_threshold': 500_000,
            'estimated_days': 3,
        },
        'economy': {
            'name': 'پست سفارشی',
            'base_cost': 15_000,
            'free_threshold': 300_000,
            'estimated_days': 5,
        },
    }

    @classmethod
    def calculate_shipping(cls, subtotal, method='standard', province_id=None):
        """
        محاسبه هزینه ارسال

        Args:
            subtotal: مبلغ کل سبد
            method: نوع ارسال (express, standard, economy)
            province_id: شناسه استان (برای محاسبه هزینه بر اساس منطقه)
        """
        method_config = cls.SHIPPING_METHODS.get(method, cls.SHIPPING_METHODS['standard'])

        # هزینه پایه
        base_cost = method_config['base_cost']
        free_threshold = method_config['free_threshold']

        # تخفیف بر اساس استان (مثلاً تهران ارزان‌تر)
        location_discount = cls._get_location_discount(province_id)

        # محاسبه نهایی
        if subtotal >= free_threshold:
            return 0  # رایگان

        cost = base_cost - location_discount
        return max(0, cost)  # هزینه نمی‌تونه منفی بشه

    @classmethod
    def _get_location_discount(cls, province_id):
        """تخفیف بر اساس استان (مثلاً تهران)"""
        if not province_id:
            return 0

        # تهران ارزان‌تر (مثلاً ۵,۰۰۰ تومان)
        if province_id in [1, 2]:  # فرض کنیم تهران و البرز
            return 5_000
        return 0

    @classmethod
    def get_estimated_delivery(cls, method='standard'):
        """دریافت زمان تقریبی تحویل"""
        method_config = cls.SHIPPING_METHODS.get(method, cls.SHIPPING_METHODS['standard'])
        return method_config['estimated_days']

    @classmethod
    def get_available_methods(cls, subtotal):
        """دریافت روش‌های ارسال موجود بر اساس مبلغ"""
        available = []
        for key, method in cls.SHIPPING_METHODS.items():
            free = subtotal >= method['free_threshold']
            available.append({
                'id': key,
                'name': method['name'],
                'cost': 0 if free else method['base_cost'],
                'is_free': free,
                'estimated_days': method['estimated_days'],
            })
        return available