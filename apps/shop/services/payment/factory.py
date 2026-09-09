import sys
from typing import Dict, Type

from django.conf import settings
from .base import BasePaymentGateway
from .zarinpal import ZarinpalGateway
from .snappay import SnappPayGateway
from .digipay import DigiPayGateway
from .sandbox import SandboxGateway


def _is_sandbox_allowed() -> bool:
    """درگاه تستی فقط در حالت DEBUG یا در زمان اجرای تست‌های خودکار مجاز است"""
    return bool(settings.DEBUG or ('test' in sys.argv) or getattr(settings, 'TESTING', False))


class PaymentGatewayFactory:
    """
    کارخانه ساخت و مدیریت نمونه‌های درگاه پرداخت (Factory Pattern)
    """

    _gateways: Dict[str, Type[BasePaymentGateway]] = {
        'zarinpal': ZarinpalGateway,
        'snappay': SnappPayGateway,
        'digipay': DigiPayGateway,
        'sandbox': SandboxGateway,
    }

    @classmethod
    def get_gateway(cls, gateway_name: str = '') -> BasePaymentGateway:
        """
        دریافت نمونه‌ی درگاه متناسب با نام ورودی
        اگر نام درگاه مشخص نباشد یا در محیط توسعه (DEBUG) باشیم و درگاه تستی خواسته شود، هندل می‌کند.
        در محیط غیر DEBUG (پروداکشن)، درگاه Sandbox مجاز نیست و به درگاه پیش‌فرض هدایت می‌شود.
        """
        gateway_name = (gateway_name or '').lower().strip()
        sandbox_allowed = _is_sandbox_allowed()

        if gateway_name == 'sandbox' and not sandbox_allowed:
            gateway_name = 'zarinpal'

        # اگر درگاه ناشناخته باشد یا در حالت تستی باشد
        gateway_class = cls._gateways.get(gateway_name)
        if not gateway_class or (gateway_class == SandboxGateway and not sandbox_allowed):
            if sandbox_allowed:
                gateway_class = SandboxGateway
            else:
                gateway_class = ZarinpalGateway

        return gateway_class()

    @classmethod
    def list_gateways(cls) -> list[str]:
        """لیست نام تمام درگاه‌های پشتیبانی‌شده"""
        return list(cls._gateways.keys())

    @classmethod
    def register_gateway(cls, name: str, gateway_class: Type[BasePaymentGateway]) -> None:
        """امکان ثبت درگاه جدید به صورت پویا (Pluggable)"""
        cls._gateways[name.lower().strip()] = gateway_class
