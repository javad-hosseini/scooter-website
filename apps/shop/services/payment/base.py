from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Optional


@dataclass
class PaymentRequestResult:
    """نتیجه درخواست اتصال به درگاه پرداخت"""
    success: bool
    redirect_url: str = ''
    authority: str = ''  # یا Token درگاه
    error_message: str = ''
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PaymentVerificationResult:
    """نتیجه اعتبارسنجی تراکنش پس از بازگشت از درگاه"""
    success: bool
    reference_id: str = ''   # شناسه مرجع بانکی (RefID)
    tracking_code: str = ''  # کد رهگیری شاپرک / رسید دیجیتال
    amount: Decimal = Decimal('0')
    error_message: str = ''
    raw_data: Dict[str, Any] = field(default_factory=dict)


class BasePaymentGateway(ABC):
    """کلاس انتزاعی پایه برای تمامی درگاه‌های پرداخت"""

    @abstractmethod
    def get_gateway_name(self) -> str:
        """نام انگلیسی درگاه مطابق با Transaction.GATEWAY_CHOICES"""
        pass

    @abstractmethod
    def request_payment(self, order, callback_url: str) -> PaymentRequestResult:
        """
        ارسال درخواست اولیه به درگاه جهت دریافت توکن و آدرس پرداخت
        :param order: نمونه‌ی سفارش (Order)
        :param callback_url: آدرس بازگشت کاربر پس از پرداخت
        """
        pass

    @abstractmethod
    def verify_payment(self, order, request_data: Dict[str, Any]) -> PaymentVerificationResult:
        """
        اعتبارسنجی تراکنش پس از بازگشت کاربر از درگاه
        :param order: نمونه‌ی سفارش (Order)
        :param request_data: پارامترهای ارسالی درگاه در درخواست بازگشت (GET/POST)
        """
        pass
