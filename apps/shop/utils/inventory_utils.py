# apps/shop/utils/inventory_utils.py
from datetime import timezone

from django.db import transaction


class InventoryManager:
    """مدیریت موجودی انبار"""

    @classmethod
    def check_availability(cls, items):
        """
        بررسی موجودی آیتم‌ها قبل از ثبت سفارش

        Returns:
            dict: {'available': True/False, 'errors': []}
        """
        errors = []
        for item in items:
            if item.product.stock < item.quantity:
                errors.append({
                    'product': item.product.name,
                    'available': item.product.stock,
                    'requested': item.quantity,
                })

        return {
            'available': len(errors) == 0,
            'errors': errors,
        }

    @classmethod
    @transaction.atomic
    def deduct_stock(cls, items):
        """کاهش موجودی آیتم‌ها"""
        for item in items:
            product = item.product
            product.stock -= item.quantity

            if product.stock <= 0:
                product.is_available = False
                product.stock_out_at = timezone.now()

            product.save()

            # ارسال هشدار اگر موجودی کم است
            if product.stock <= 5:
                product.send_stock_alert()

    @classmethod
    @transaction.atomic
    def restore_stock(cls, items):
        """بازگرداندن موجودی (در صورت لغو سفارش)"""
        for item in items:
            product = item.product
            product.stock += item.quantity

            if not product.is_available and product.stock > 0:
                product.is_available = True
                product.stock_out_at = None

            product.save()
