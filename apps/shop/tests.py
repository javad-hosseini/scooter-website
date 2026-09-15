from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.shop.models import Order, Transaction, Product, Category, OrderItem
from apps.shop.utils.tax_utils import TaxCalculator
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

    def test_payment_callback_gateway_tampering_rejected(self):
        """Callback with mismatched gateway is rejected with HTTP 403."""
        self.client.login(username='testshopper', password='testpassword123')
        # Order initialized with zarinpal
        trx = Transaction.objects.create(
            order=self.order,
            gateway='zarinpal',
            amount=self.order.total,
            status='pending',
            reference_id='ZARIN-123'
        )
        # Attacker tries to use sandbox callback on a zarinpal transaction
        url = reverse('shop_app:payment_callback', kwargs={'gateway': 'sandbox', 'order_id': self.order.id})
        response = self.client.post(url, data={'status': 'success', 'authority': 'ZARIN-123'})
        self.assertEqual(response.status_code, 403)

    def test_payment_callback_idempotency(self):
        """Already paid order callback does not duplicate processing and redirects safely."""
        self.client.login(username='testshopper', password='testpassword123')
        self.order.payment_status = 'paid'
        self.order.status = 'processing'
        self.order.save()

        url = reverse('shop_app:payment_callback', kwargs={'gateway': 'sandbox', 'order_id': self.order.id})
        response = self.client.post(url, data={'status': 'success'})
        self.assertEqual(response.status_code, 302)

    def test_order_cancel_unpaid_does_not_inflate_stock(self):
        """Canceling an unpaid pending order does not inflate product stock."""
        category = Category.objects.create(name='اسکوتر', slug='scooters')
        product = Product.objects.create(
            name='اسکوتر تستی',
            slug='scooter-test',
            category=category,
            price=Decimal('1000000'),
            stock=5,
            is_available=True,
            is_published=True
        )
        OrderItem.objects.create(
            order=self.order,
            product=product,
            quantity=3,
            price=Decimal('1000000'),
            discount=0
        )
        initial_stock = product.stock

        self.client.login(username='testshopper', password='testpassword123')
        cancel_url = reverse('shop_app:order_cancel', kwargs={'order_number': self.order.order_number})
        response = self.client.post(cancel_url)
        self.assertEqual(response.status_code, 200)

        product.refresh_from_db()
        # Stock should NOT have been increased
        self.assertEqual(product.stock, initial_stock)

    def test_tax_calculator_never_negative(self):
        """TaxCalculator.calculate_total returns at least 0 even with large discount."""
        total = TaxCalculator.calculate_total(
            subtotal=Decimal('10000'),
            discount=Decimal('50000'),
            shipping_cost=Decimal('5000')
        )
        self.assertGreaterEqual(total, Decimal('0'))

    def test_provinces_and_cities_allow_guest(self):
        """Guests can view provinces and cities list without 403."""
        self.client.logout()
        res_prov = self.client.get(reverse('shop_app:api_provinces'))
        self.assertEqual(res_prov.status_code, 200)

        res_city = self.client.get(f"{reverse('shop_app:api_cities')}?province={self.province.id}")
        self.assertEqual(res_city.status_code, 200)


class CKEditor5IntegrationTests(TestCase):
    """Tests confirming CKEditor 5 model field and integration."""

    def test_article_description_is_ckeditor5_field(self):
        """Article model description is an instance of CKEditor5Field."""
        field = Article._meta.get_field('description')
        self.assertIsInstance(field, CKEditor5Field)
        self.assertEqual(field.config_name, 'extends')


class SavedAddressCheckoutTests(TestCase):
    """انتخاب یکی از آدرس‌های ذخیره‌شده در سبد خرید."""

    def setUp(self):
        from apps.accounts.models import Province, City, Address
        from apps.shop.models import Cart, CartItem

        self.user = User.objects.create_user(
            username='savedaddrbuyer',
            email='savedaddr@test.com',
            password='testpassword123',
            fullname='کاربر آدرس',
            mobile='09120000000',
        )
        self.province = Province.objects.create(name='تهران')
        self.city = City.objects.create(province=self.province, name='تهران')
        self.address = Address.objects.create(
            user=self.user,
            recipient_name='کاربر آدرس',
            recipient_phone='09120000000',
            province=self.province,
            city=self.city,
            address='خیابان ولیعصر، پلاک ۱۲',
            postal_code='1234567890',
            plaque='12',
        )

        category = Category.objects.create(name='اسکوتر', slug='scooter-saved-addr')
        self.product = Product.objects.create(
            name='NexGo S1',
            slug='nexgo-s1-saved-addr',
            category=category,
            price=Decimal('1000000'),
            stock=5,
        )
        cart = Cart.objects.create(user=self.user, is_active=True)
        CartItem.objects.create(
            cart=cart,
            product=self.product,
            quantity=1,
            price_snapshot=Decimal('1000000'),
        )
        self.client.force_login(self.user)

    def _payload(self, **overrides):
        data = {
            'first_name': 'کاربر',
            'last_name': 'آدرس',
            'phone': '09120000000',
            'province_id': self.province.id,
            'city_id': self.city.id,
            'postal_code': '1234567890',
            'address': 'خیابان ولیعصر، پلاک ۱۲',
            'payment_method': 'card',
        }
        data.update(overrides)
        return data

    def test_selected_saved_address_is_reused(self):
        """address_id سفارش را به همان رکورد وصل می‌کند و آدرس تکراری نمی‌سازد."""
        from apps.accounts.models import Address

        res = self.client.post(
            reverse('shop_app:checkout_submit'),
            self._payload(address_id=self.address.id),
        )
        self.assertEqual(res.status_code, 201, res.content[:500])
        self.assertEqual(Address.objects.filter(user=self.user).count(), 1)
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.address_id, self.address.id)

    def test_address_of_another_user_is_rejected(self):
        """فرستادن address_id کاربر دیگر باید رد شود."""
        from apps.accounts.models import Address

        other = User.objects.create_user(
            username='otherbuyer',
            email='other@test.com',
            password='testpassword123',
            fullname='کاربر دیگر',
            mobile='09120000001',
        )
        foreign = Address.objects.create(
            user=other,
            recipient_name='کاربر دیگر',
            recipient_phone='09120000001',
            province=self.province,
            city=self.city,
            address='نشانی دیگر',
            postal_code='9999999999',
            plaque='1',
        )
        res = self.client.post(
            reverse('shop_app:checkout_submit'),
            self._payload(address_id=foreign.id),
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_checkout_without_address_id_still_works(self):
        """مسیر قبلی (پر کردن دستی فرم) دست‌نخورده باقی می‌ماند."""
        from apps.accounts.models import Address

        res = self.client.post(
            reverse('shop_app:checkout_submit'),
            self._payload(save_address=True),
        )
        self.assertEqual(res.status_code, 201, res.content[:500])
        self.assertEqual(Address.objects.filter(user=self.user).count(), 1)

    def test_address_list_api_feeds_the_cart_picker(self):
        """لیست آدرس‌ها شناسه‌ی استان/شهر را می‌دهد تا فرم قابل پر شدن باشد."""
        res = self.client.get(reverse('accounts_app:api_addresses'))
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]['province'], self.province.id)
        self.assertEqual(body[0]['city'], self.city.id)

    def test_cart_page_renders_the_address_picker(self):
        res = self.client.get(reverse('shop_app:cart'))
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        self.assertIn('id="saved-addresses"', html)
        self.assertIn('hf_address_id', html)
