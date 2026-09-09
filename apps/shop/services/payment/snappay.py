import logging
from decimal import Decimal
from typing import Any, Dict

import requests
from django.conf import settings
from decouple import config

from .base import BasePaymentGateway, PaymentRequestResult, PaymentVerificationResult

logger = logging.getLogger(__name__)


class SnappPayGateway(BasePaymentGateway):
    """
    پیاده‌سازی سرویس پرداخت اقساطی / اعتباری اسنپ‌پی (SnappPay BNPL)
    """

    def __init__(self):
        self.base_url = config('SNAPPAY_BASE_URL', default='https://staging-api.snapppay.ir')
        self.client_id = config('SNAPPAY_CLIENT_ID', default='')
        self.client_secret = config('SNAPPAY_CLIENT_SECRET', default='')
        self.username = config('SNAPPAY_USERNAME', default='')
        self.password = config('SNAPPAY_PASSWORD', default='')

    def get_gateway_name(self) -> str:
        return 'snappay'

    def _get_auth_token(self) -> str:
        """دریافت توکن دسترسی از اسنپ‌پی"""
        url = f"{self.base_url}/api/online/v1/oauth/token"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "grant_type": "password",
            "scope": "online-merchant",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "username": self.username,
            "password": self.password
        }
        response = requests.post(url, data=data, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json().get('access_token', '')
        raise ValueError(f"Failed to obtain SnappPay token: {response.text}")

    def request_payment(self, order, callback_url: str) -> PaymentRequestResult:
        # اگر تنظیمات ست نشده باشد، لاگ می‌اندازد و نتیجه تمیز می‌دهد
        if not self.client_id or not self.client_secret:
            logger.warning("SnappPay credentials not configured. Please set SNAPPAY_* env vars.")
            return PaymentRequestResult(
                success=False,
                error_message="درگاه اسنپ‌پی در حال حاضر پیکربندی نشده است."
            )

        try:
            token = self._get_auth_token()
            url = f"{self.base_url}/api/online/payment/v1/token"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            # تبدیل مبالغ به ریال
            amount_in_rial = int(order.total * 10)
            items = []
            for item in order.items.all():
                items.append({
                    "id": str(item.product.id),
                    "name": item.product.name,
                    "count": item.quantity,
                    "amount": int(item.price * 10),
                    "category": item.product.category.name if item.product.category else "General"
                })

            payload = {
                "amount": amount_in_rial,
                "paymentMethodTypeDto": "INSTALLMENT",
                "returnUrl": callback_url,
                "userMobile": getattr(order.user, 'mobile', '') or getattr(order.address, 'recipient_phone', ''),
                "cartId": str(order.order_number),
                "products": items
            }

            response = requests.post(url, json=payload, headers=headers, timeout=15)
            data = response.json()

            if response.status_code == 200 and data.get('successful'):
                payment_token = data.get('response', {}).get('paymentToken')
                redirect_url = data.get('response', {}).get('paymentPageUrl')
                return PaymentRequestResult(
                    success=True,
                    redirect_url=redirect_url,
                    authority=payment_token,
                    raw_data=data
                )
            else:
                error_msg = data.get('error', {}).get('message', 'خطا در ثبت سفارش در اسنپ‌پی')
                return PaymentRequestResult(success=False, error_message=error_msg, raw_data=data)

        except Exception as e:
            logger.exception(f"Exception connecting to SnappPay: {e}")
            return PaymentRequestResult(success=False, error_message=f"خطا در ارتباط با اسنپ‌پی: {str(e)}")

    def verify_payment(self, order, request_data: Dict[str, Any]) -> PaymentVerificationResult:
        payment_token = request_data.get('paymentToken') or request_data.get('transactionId')
        state = request_data.get('state')

        if state != 'OK' or not payment_token:
            return PaymentVerificationResult(
                success=False,
                error_message="پرداخت اسنپ‌پی تایید نشد یا توسط کاربر لغو گردید."
            )

        try:
            token = self._get_auth_token()
            verify_url = f"{self.base_url}/api/online/payment/v1/verify"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            payload = {"paymentToken": payment_token}

            response = requests.post(verify_url, json=payload, headers=headers, timeout=15)
            data = response.json()

            if response.status_code == 200 and data.get('successful'):
                # پس از Verify باید Settle نیز صدا زده شود تا پول واریز گردد
                settle_url = f"{self.base_url}/api/online/payment/v1/settle"
                requests.post(settle_url, json=payload, headers=headers, timeout=10)

                transaction_id = str(data.get('response', {}).get('transactionId', payment_token))
                return PaymentVerificationResult(
                    success=True,
                    reference_id=transaction_id,
                    tracking_code=payment_token,
                    amount=order.total,
                    raw_data=data
                )
            else:
                msg = data.get('error', {}).get('message', 'تراکنش اسنپ‌پی اعتبارسنجی نشد')
                return PaymentVerificationResult(success=False, error_message=msg, raw_data=data)

        except Exception as e:
            logger.exception(f"Exception verifying SnappPay: {e}")
            return PaymentVerificationResult(success=False, error_message=f"خطا در تایید اسنپ‌پی: {str(e)}")
