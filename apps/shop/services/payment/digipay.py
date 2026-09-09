import logging
from decimal import Decimal
from typing import Any, Dict

import requests
from django.conf import settings
from decouple import config

from .base import BasePaymentGateway, PaymentRequestResult, PaymentVerificationResult

logger = logging.getLogger(__name__)


class DigiPayGateway(BasePaymentGateway):
    """
    پیاده‌سازی سرویس درگاه پرداخت و کیف‌پول دیجی‌پی (DigiPay)
    """

    def __init__(self):
        self.base_url = config('DIGIPAY_BASE_URL', default='https://api.mydigipay.com')
        self.client_id = config('DIGIPAY_CLIENT_ID', default='')
        self.client_secret = config('DIGIPAY_CLIENT_SECRET', default='')

    def get_gateway_name(self) -> str:
        return 'digipay'

    def request_payment(self, order, callback_url: str) -> PaymentRequestResult:
        if not self.client_id or not self.client_secret:
            logger.warning("DigiPay credentials not configured. Please set DIGIPAY_* env vars.")
            return PaymentRequestResult(
                success=False,
                error_message="درگاه دیجی‌پی در حال حاضر پیکربندی نشده است."
            )

        try:
            url = f"{self.base_url}/digipay/api/tickets/business"
            # تبدیل به ریال
            amount_in_rial = int(order.total * 10)

            payload = {
                "amount": amount_in_rial,
                "callbackUrl": callback_url,
                "providerId": str(order.order_number),
                "cellNumber": getattr(order.user, 'mobile', '') or getattr(order.address, 'recipient_phone', ''),
            }

            headers = {
                "Content-Type": "application/json",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }

            response = requests.post(url, json=payload, headers=headers, timeout=15)
            data = response.json()

            ticket = data.get('ticket')
            redirect_url = data.get('redirectUrl')

            if response.status_code == 200 and ticket:
                return PaymentRequestResult(
                    success=True,
                    redirect_url=redirect_url or f"https://mydigipay.com/payment?ticket={ticket}",
                    authority=ticket,
                    raw_data=data
                )
            else:
                msg = data.get('result', {}).get('message', 'خطا در دریافت تیکت پرداخت دیجی‌پی')
                return PaymentRequestResult(success=False, error_message=msg, raw_data=data)

        except Exception as e:
            logger.exception(f"Exception connecting to DigiPay: {e}")
            return PaymentRequestResult(success=False, error_message=f"خطا در ارتباط با دیجی‌پی: {str(e)}")

    def verify_payment(self, order, request_data: Dict[str, Any]) -> PaymentVerificationResult:
        tracking_code = request_data.get('trackingCode') or request_data.get('tracking_code')
        type_str = request_data.get('type')

        if not tracking_code:
            return PaymentVerificationResult(
                success=False,
                error_message="کد رهگیری دیجی‌پی در بازگشت یافت نشد."
            )

        try:
            url = f"{self.base_url}/digipay/api/purchases/verify"
            payload = {"trackingCode": tracking_code}
            headers = {
                "Content-Type": "application/json",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }

            response = requests.post(url, json=payload, headers=headers, timeout=15)
            data = response.json()

            if response.status_code == 200 and data.get('result', {}).get('status') == 0:
                ref_id = str(data.get('trackingCode', tracking_code))
                return PaymentVerificationResult(
                    success=True,
                    reference_id=ref_id,
                    tracking_code=str(tracking_code),
                    amount=order.total,
                    raw_data=data
                )
            else:
                msg = data.get('result', {}).get('message', 'تراکنش دیجی‌پی تایید نشد.')
                return PaymentVerificationResult(success=False, error_message=msg, raw_data=data)

        except Exception as e:
            logger.exception(f"Exception verifying DigiPay: {e}")
            return PaymentVerificationResult(success=False, error_message=f"خطا در تایید دیجی‌پی: {str(e)}")
