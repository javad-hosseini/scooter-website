from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.shop.models import Order, Transaction
from apps.shop.services.payment import (
    PaymentGatewayFactory,
    BasePaymentGateway,
    PaymentRequestResult,
    PaymentVerificationResult,
    SandboxGateway,
    ZarinpalGateway,
    SnappPayGateway,
    DigiPayGateway,
)
from apps.home.models import Article
from django_ckeditor_5.fields import CKEditor5Field

User = get_user_model()


class PaymentGatewayArchitectureTests(TestCase):
    """Unit tests for the Iranian Payment Gateway Architecture and Sandbox."""

    def setUp(self):
        from apps.accounts.models import Province, City, Address
        self.user = User.objects.create_user(
            username='testshopper',
            email='shopper@test.com',
            password='testpassword123',
            fullname='کاربر تستی'
        )
        self.province = Province.objects.create(name='تهران')
        self.city = City.objects.create(province=self.province, name='تهران')
        self.address = Address.objects.create(
            user=self.user,
            recipient_name='کاربر تستی',
            recipient_phone='09121112233',
            province=self.province,
            city=self.city,
            address='خیابان ولیعصر',
            postal_code='1234567890',
            plaque='10'
        )
        self.order = Order.objects.create(
            user=self.user,
            address=self.address,
            subtotal=Decimal('2500000'),
            total=Decimal('2500000'),
            order_number='ORD-TEST-1001',
            tracking_code='TRK-1001',
            status='pending',
            payment_status='pending'
        )

    def test_factory_gateway_registration_and_retrieval(self):
        """Factory properly returns registered gateways and falls back gracefully."""
        sandbox = PaymentGatewayFactory.get_gateway('sandbox')
        self.assertIsInstance(sandbox, SandboxGateway)

        zarinpal = PaymentGatewayFactory.get_gateway('zarinpal')
        self.assertIsInstance(zarinpal, ZarinpalGateway)

        snappay = PaymentGatewayFactory.get_gateway('snappay')
        self.assertIsInstance(snappay, SnappPayGateway)

        digipay = PaymentGatewayFactory.get_gateway('digipay')
        self.assertIsInstance(digipay, DigiPayGateway)

        # Fallback for unknown gateway (resilient architecture)
        unknown = PaymentGatewayFactory.get_gateway('non_existent_gateway')
        self.assertIsInstance(unknown, (SandboxGateway, ZarinpalGateway))

    def test_factory_list_gateways(self):
        """list_gateways() returns the available gateway keys."""
        keys = PaymentGatewayFactory.list_gateways()
        self.assertIn('sandbox', keys)
        self.assertIn('zarinpal', keys)
        self.assertIn('snappay', keys)
        self.assertIn('digipay', keys)

    def test_sandbox_gateway_request_payment(self):
        """Sandbox request payment returns redirect URL and authority."""
        gateway = SandboxGateway()
        result = gateway.request_payment(
            order=self.order,
            callback_url='http://testserver/shop/payment/callback/sandbox/1/'
        )

        self.assertTrue(result.success)
        self.assertIn(f'/shop/payment/gateway/{self.order.id}/', result.redirect_url)
        self.assertTrue(result.authority.startswith('SBX-'))

    def test_sandbox_gateway_verify_payment_success(self):
        """Sandbox verification with success status returns success result."""
        gateway = SandboxGateway()
        req_res = gateway.request_payment(
            order=self.order,
            callback_url='http://testserver/shop/payment/callback/sandbox/1/'
        )

        request_data = {
            'status': 'success',
            'authority': req_res.authority
        }
        ver_res = gateway.verify_payment(self.order, request_data)

        self.assertTrue(ver_res.success)
        self.assertTrue(ver_res.reference_id.startswith('REF-'))
        self.assertEqual(ver_res.amount, self.order.total)

    def test_sandbox_gateway_verify_payment_failed(self):
        """Sandbox verification with failed status returns failure result."""
        gateway = SandboxGateway()
        req_res = gateway.request_payment(
            order=self.order,
            callback_url='http://testserver/shop/payment/callback/sandbox/1/'
        )

        request_data = {
            'status': 'failed',
            'authority': req_res.authority
        }
        ver_res = gateway.verify_payment(self.order, request_data)

        self.assertFalse(ver_res.success)
        self.assertIsNotNone(ver_res.error_message)

    def test_payment_gateway_view_idor_protection(self):
        """Payment gateway view only allows order owner to access."""
        other_user = User.objects.create_user(
            username='intruder',
            email='intruder@test.com',
            password='password123'
        )
        self.client.login(username='intruder', password='password123')
        response = self.client.get(reverse('shop_app:payment_gateway', kwargs={'order_id': self.order.id}))
        self.assertEqual(response.status_code, 404)

        # Owner can access
        self.client.login(username='testshopper', password='testpassword123')
        response = self.client.get(reverse('shop_app:payment_gateway', kwargs={'order_id': self.order.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'درگاه پرداخت شاپرک / Nex Go')

    def test_payment_callback_view_success_flow(self):
        """Successful payment callback marks order paid, updates transaction, and redirects."""
        self.client.login(username='testshopper', password='testpassword123')
        # Create a pending transaction
        trx = Transaction.objects.create(
            order=self.order,
            gateway='sandbox',
            amount=self.order.total,
            status='pending',
            reference_id='SBX-INIT'
        )

        url = reverse('shop_app:payment_callback', kwargs={'gateway': 'sandbox', 'order_id': self.order.id})
        response = self.client.post(url, data={'status': 'success', 'authority': 'SBX-INIT'})

        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'processing')
        self.assertEqual(self.order.payment_status, 'paid')
        self.assertIsNotNone(self.order.paid_at)

        trx.refresh_from_db()
        self.assertEqual(trx.status, 'success')
        self.assertTrue(trx.reference_id.startswith('REF-'))

    def test_payment_callback_view_failure_flow(self):
        """Failed payment callback marks transaction failed and redirects."""
        self.client.login(username='testshopper', password='testpassword123')
        trx = Transaction.objects.create(
            order=self.order,
            gateway='sandbox',
            amount=self.order.total,
            status='pending',
            reference_id='SBX-INIT'
        )

        url = reverse('shop_app:payment_callback', kwargs={'gateway': 'sandbox', 'order_id': self.order.id})
        response = self.client.post(url, data={'status': 'failed', 'authority': 'SBX-INIT'})

        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending')

        trx.refresh_from_db()
        self.assertEqual(trx.status, 'failed')
        self.assertIsNotNone(trx.failure_reason)


class CKEditor5IntegrationTests(TestCase):
    """Tests confirming CKEditor 5 model field and integration."""

    def test_article_description_is_ckeditor5_field(self):
        """Article model description is an instance of CKEditor5Field."""
        field = Article._meta.get_field('description')
        self.assertIsInstance(field, CKEditor5Field)
        self.assertEqual(field.config_name, 'extends')
