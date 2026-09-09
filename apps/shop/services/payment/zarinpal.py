import logging
from decimal import Decimal
from typing import Any, Dict

import requests
from django.conf import settings
from decouple import config

from .base import BasePaymentGateway, PaymentRequestResult, PaymentVerificationResult

logger = logging.getLogger(__name__)


class ZarinpalGateway(BasePaymentGateway):
    """
    پیاده‌سازی اتصال به درگاه پرداخت زرین‌پال (نسخه REST v4)
    """

    def __init__(self):
        self.merchant_id = config('ZARINPAL_MERCHANT_ID', default='00000000-0000-0000-0000-000000000000')
        self.sandbox = config('ZARINPAL_SANDBOX', default=True, cast=bool)

        if self.sandbox:
            self.request_url = 'https://sandbox.zarinpal.com/pg/v4/payment/request.json'
            self.verify_url = 'https://sandbox.zarinpal.com/pg/v4/payment/verify.json'
            self.start_pay_url = 'https://sandbox.zarinpal.com/pg/StartPay/'
        else:
            self.request_url = 'https://payment.zarinpal.com/pg/v4/payment/request.json'
            self.verify_url = 'https://payment.zarinpal.com/pg/v4/payment/verify.json'
            self.start_pay_url = 'https://payment.zarinpal.com/pg/StartPay/'

    def get_gateway_name(self) -> str:
        return 'zarinpal'

    def request_payment(self, order, callback_url: str) -> PaymentRequestResult:
        # زرین‌پال به ریال دریافت می‌کند (قیمت سایت به تومان است: x10)
        amount_in_rial = int(order.total * 10)
        description = f"پرداخت سفارش {order.order_number} در سایت Nex Go"

        payload = {
            "merchant_id": self.merchant_id,
            "amount": amount_in_rial,
            "callback_url": callback_url,
            "description": description,
            "metadata": {
                "mobile": getattr(order.user, 'mobile', '') or getattr(order.address, 'recipient_phone', ''),
                "email": getattr(order.user, 'email', ''),
                "order_id": str(order.id),
            }
        }

        try:
            response = requests.post(self.request_url, json=payload, timeout=15)
            data = response.json()

            if response.status_code == 200 and data.get('data', {}).get('code') == 100:
                authority = data['data']['authority']
                redirect_url = f"{self.start_pay_url}{authority}"
                return PaymentRequestResult(
                    success=True,
                    redirect_url=redirect_url,
                    authority=authority,
                    raw_data=data
                )
            else:
                message = data.get('errors', {}).get('message', 'خطا در برقراری ارتباط با زرین‌پال')
                logger.error(f"Zarinpal request failed for order {order.id}: {data}")
                return PaymentRequestResult(success=False, error_message=message, raw_data=data)

        except Exception as e:
            logger.exception(f"Exception connecting to Zarinpal: {e}")
            return PaymentRequestResult(success=False, error_message=f"خطای ارتباط با درگاه: {str(e)}")

    def verify_payment(self, order, request_data: Dict[str, Any]) -> PaymentVerificationResult:
        authority = request_data.get('Authority')
        status = request_data.get('Status')

        if status != 'OK' or not authority:
            return PaymentVerificationResult(
                success=False,
                error_message="پرداخت توسط کاربر لغو شد یا ناموفق بود."
            )

        amount_in_rial = int(order.total * 10)
        payload = {
            "merchant_id": self.merchant_id,
            "amount": amount_in_rial,
            "authority": authority
        }

        try:
            response = requests.post(self.verify_url, json=payload, timeout=15)
            data = response.json()

            code = data.get('data', {}).get('code')
            if response.status_code == 200 and code in [100, 101]:
                ref_id = str(data['data'].get('ref_id', ''))
                return PaymentVerificationResult(
                    success=True,
                    reference_id=ref_id,
                    tracking_code=authority,
                    amount=order.total,
                    raw_data=data
                )
            else:
                message = data.get('errors', {}).get('message', 'تراکنش تایید نشد')
                return PaymentVerificationResult(success=False, error_message=message, raw_data=data)

        except Exception as e:
            logger.exception(f"Exception verifying Zarinpal payment: {e}")
            return PaymentVerificationResult(success=False, error_message=f"خطا در وریفای پرداخت: {str(e)}")
