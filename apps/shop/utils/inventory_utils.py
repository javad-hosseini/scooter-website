# apps/shop/utils/inventory_utils.py
from django.db import transaction

from apps.shop.models import Product


class InsufficientStockError(Exception):
    """موجودی انبار برای ثبت سفارش کافی نیست."""

    def __init__(self, product_name, available):
        self.product_name = product_name
        self.available = available
        super().__init__(
            f"موجودی کافی نیست — {product_name}: {available} عدد موجود"
        )


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
        """
        کاهش قطعی موجودی آیتم‌ها با قفل ردیف (select_for_update).

        باید درون یک تراکنش اتمیک فراخوانده شود (PaymentCallbackView
        از @transaction.atomic استفاده می‌کند).

        Raises:
            InsufficientStockError: اگر موجودی واقعی (پس از قفل) کافی نباشد.
        """
        for item in items:
            # قفل ردیف محصول در سطح DB تا از race-condition جلوگیری شود
            product = Product.objects.select_for_update().get(pk=item.product_id)

            if product.stock < item.quantity:
                raise InsufficientStockError(product.name, product.stock)

            product.stock -= item.quantity

            if product.stock <= 0:
                product.is_available = False

            product.save(update_fields=['stock', 'is_available', 'updated_at'])

            # ارسال هشدار اگر موجودی کم است
            if hasattr(product, 'send_stock_alert') and product.stock <= 5:
                product.send_stock_alert()

    @classmethod
    @transaction.atomic
    def restore_stock(cls, items):
        """بازگرداندن موجودی (در صورت لغو سفارش)"""
        for item in items:
            product = Product.objects.select_for_update().get(pk=item.product_id)
            product.stock += item.quantity

            if not product.is_available and product.stock > 0:
                product.is_available = True

            product.save(update_fields=['stock', 'is_available', 'updated_at'])
