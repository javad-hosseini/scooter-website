from typing import Dict, Type

from django.conf import settings
from .base import BasePaymentGateway
from .zarinpal import ZarinpalGateway
from .snappay import SnappPayGateway
from .digipay import DigiPayGateway
from .sandbox import SandboxGateway


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
        """
        gateway_name = (gateway_name or '').lower().strip()

        # اگر درگاه ناشناخته باشد یا در حالت تستی باشد
        gateway_class = cls._gateways.get(gateway_name)
        if not gateway_class:
            if settings.DEBUG:
                gateway_class = SandboxGateway
            else:
                gateway_class = ZarinpalGateway

        return gateway_class()
