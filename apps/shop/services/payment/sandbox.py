import uuid
from decimal import Decimal
from typing import Any, Dict

from django.urls import reverse

from .base import BasePaymentGateway, PaymentRequestResult, PaymentVerificationResult


class SandboxGateway(BasePaymentGateway):
    """
    درگاه شبیه‌ساز تستی (Sandbox) برای محیط توسعه و تست بدون نیاز به اتصال به اینترنت و مرچنت واقعی
    """

    def get_gateway_name(self) -> str:
        return 'sandbox'

    def request_payment(self, order, callback_url: str) -> PaymentRequestResult:
        mock_authority = f"SBX-{uuid.uuid4().hex[:10].upper()}"
        redirect_url = reverse('shop_app:payment_gateway', kwargs={'order_id': order.id})
        return PaymentRequestResult(
            success=True,
            redirect_url=redirect_url,
            authority=mock_authority,
            raw_data={'mock_authority': mock_authority, 'callback_url': callback_url}
        )

    def verify_payment(self, order, request_data: Dict[str, Any]) -> PaymentVerificationResult:
        status_param = str(request_data.get('status', 'success')).lower().strip()
        mock_ref_id = request_data.get('ref_id') or f"REF-{uuid.uuid4().hex[:8].upper()}"
        tracking = request_data.get('authority', f"TRK-{uuid.uuid4().hex[:6].upper()}")
        order_amount = getattr(order, 'total', getattr(order, 'total_price', Decimal('0')))

        if status_param in ['success', 'ok']:
            return PaymentVerificationResult(
                success=True,
                reference_id=mock_ref_id,
                tracking_code=tracking,
                amount=order_amount,
                raw_data={'status': 'simulated_success'}
            )
        else:
            return PaymentVerificationResult(
                success=False,
                error_message="پرداخت در محیط شبیه‌ساز لغو شد یا با خطا مواجه گردید.",
                raw_data={'status': 'simulated_failure'}
            )
