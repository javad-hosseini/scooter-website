import json
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
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


class CouponTests(TestCase):
    """کد تخفیف درصدی: تعریف در ادمین، اعمال در سبد خرید، و ثبت سفارش."""

    def setUp(self):
        from apps.accounts.models import Province, City, Address
        from apps.shop.models import Cart, CartItem

        self.user = User.objects.create_user(
            username='couponbuyer',
            email='couponbuyer@test.com',
            password='testpassword123',
            fullname='خریدار کوپن',
            mobile='09150000000',
        )
        self.province = Province.objects.create(name='تهران')
        self.city = City.objects.create(province=self.province, name='تهران')
        self.address = Address.objects.create(
            user=self.user,
            recipient_name='خریدار کوپن',
            recipient_phone='09150000000',
            province=self.province,
            city=self.city,
            address='خیابان آزادی',
            postal_code='1234567890',
            plaque='5',
        )

        category = Category.objects.create(name='اسکوتر', slug='scooter-coupon')
        # قیمت گرد است تا ۱۰٪ آن دقیقاً محاسبه‌شدنی باشد.
        self.product = Product.objects.create(
            name='NexGo C1',
            slug='nexgo-c1-coupon',
            category=category,
            price=Decimal('10000000'),
            stock=50,
        )
        self.cart = Cart.objects.create(user=self.user, is_active=True)
        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            quantity=1,
            price_snapshot=Decimal('10000000'),
        )
        self.client.force_login(self.user)

    # ---------- کمک‌کننده‌ها ----------

    def _coupon(self, **kwargs):
        from apps.shop.models import Coupon
        defaults = {'code': 'VOLT10', 'percentage': 10}
        defaults.update(kwargs)
        return Coupon.objects.create(**defaults)

    def _apply(self, code):
        return self.client.post(
            reverse('shop_app:api_cart_apply_coupon'),
            data=json.dumps({'coupon_code': code}),
            content_type='application/json',
        )

    def _cart(self):
        return self.client.get(reverse('shop_app:api_cart')).json()

    def _refill_cart(self):
        """سبد را برای سفارش بعدی آماده می‌کند.

        ثبت سفارش در این پروژه سبد خرید را خالی نمی‌کند، پس آیتم معمولاً هنوز
        هست؛ این متد فقط مطمئن می‌شود یک عدد از محصول در سبد وجود دارد.
        """
        from apps.shop.models import CartItem

        CartItem.objects.update_or_create(
            cart=self.cart,
            product=self.product,
            defaults={'quantity': 1, 'price_snapshot': Decimal('10000000')},
        )

    def _checkout(self):
        return self.client.post(reverse('shop_app:checkout_submit'), {
            'first_name': 'خریدار',
            'last_name': 'کوپن',
            'phone': '09150000000',
            'province_id': self.province.id,
            'city_id': self.city.id,
            'postal_code': '1234567890',
            'address': 'خیابان آزادی',
            'payment_method': 'card',
        })

    # ---------- مدل ----------

    def test_code_is_normalised_to_uppercase(self):
        """کد یکتاست، پس باید یک شکل ذخیره شود تا volt10 و VOLT10 یکی باشند."""
        coupon = self._coupon(code='  volt10  ')
        self.assertEqual(coupon.code, 'VOLT10')

    def test_percentage_is_calculated_on_the_given_amount(self):
        coupon = self._coupon(percentage=15)
        self.assertEqual(coupon.discount_for(Decimal('2000000')), Decimal('300000'))

    def test_max_discount_amount_caps_the_percentage(self):
        coupon = self._coupon(percentage=50, max_discount_amount=Decimal('500000'))
        self.assertEqual(coupon.discount_for(Decimal('10000000')), Decimal('500000'))

    def test_discount_never_exceeds_the_amount(self):
        coupon = self._coupon(percentage=100)
        self.assertEqual(coupon.discount_for(Decimal('1000')), Decimal('1000'))

    # ---------- اعمال در سبد خرید ----------

    def test_valid_coupon_applies_and_reduces_cart_total(self):
        self._coupon(percentage=10)
        before = self._cart()

        res = self._apply('VOLT10')
        self.assertEqual(res.status_code, 200, res.content[:300])
        self.assertEqual(res.json()['discount_amount'], 1000000)

        after = self._cart()
        self.assertEqual(after['applied_coupon'], 'VOLT10')
        self.assertEqual(after['coupon_discount'], 1000000)
        self.assertEqual(before['final_total'] - after['final_total'], 1000000)

    def test_coupon_lookup_is_case_insensitive(self):
        self._coupon(code='VOLT10')
        res = self._apply('volt10')
        self.assertEqual(res.status_code, 200, res.content[:300])
        self.assertEqual(res.json()['coupon_code'], 'VOLT10')

    def test_unknown_code_is_rejected(self):
        res = self._apply('DOES-NOT-EXIST')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['error'], 'کد تخفیف نامعتبر است')
        self.assertEqual(self._cart()['coupon_discount'], 0)

    def test_inactive_code_is_rejected(self):
        self._coupon(is_active=False)
        res = self._apply('VOLT10')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['error'], 'این کد تخفیف فعال نیست')

    def test_expired_code_is_rejected(self):
        self._coupon(valid_until=timezone.now() - timedelta(days=1))
        res = self._apply('VOLT10')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['error'], 'این کد تخفیف منقضی شده است')

    def test_code_that_has_not_started_is_rejected(self):
        self._coupon(valid_from=timezone.now() + timedelta(days=1))
        res = self._apply('VOLT10')
        self.assertEqual(res.status_code, 400)
        self.assertIn('هنوز نرسیده', res.json()['error'])

    def test_exhausted_code_is_rejected(self):
        coupon = self._coupon(usage_limit=2)
        coupon.used_count = 2
        coupon.save()
        res = self._apply('VOLT10')
        self.assertEqual(res.status_code, 400)
        self.assertIn('ظرفیت', res.json()['error'])

    def test_min_order_amount_is_enforced(self):
        self._coupon(min_order_amount=Decimal('20000000'))
        res = self._apply('VOLT10')
        self.assertEqual(res.status_code, 400)
        self.assertIn('حداقل مبلغ', res.json()['error'])

    def test_coupon_can_be_removed(self):
        self._coupon()
        self._apply('VOLT10')
        res = self.client.delete(reverse('shop_app:api_cart_apply_coupon'))
        self.assertEqual(res.status_code, 200)
        cart = self._cart()
        self.assertIsNone(cart['applied_coupon'])
        self.assertEqual(cart['coupon_discount'], 0)

    def test_discount_follows_the_cart_when_quantity_changes(self):
        """تخفیف با هر بار خواندن سبد از نو حساب می‌شود، نه از مقدار ذخیره‌شده."""
        from apps.shop.models import CartItem

        self._coupon(percentage=10)
        self._apply('VOLT10')
        self.assertEqual(self._cart()['coupon_discount'], 1000000)

        item = CartItem.objects.get(cart=self.cart)
        item.quantity = 2
        item.save()

        self.assertEqual(self._cart()['coupon_discount'], 2000000)

    def test_coupon_is_dropped_when_it_becomes_invalid(self):
        """کدی که بعد از اعمال منقضی شود نباید در سبد نمایش داده شود."""
        from apps.shop.models import Coupon

        coupon = self._coupon()
        self._apply('VOLT10')
        self.assertEqual(self._cart()['coupon_discount'], 1000000)

        Coupon.objects.filter(pk=coupon.pk).update(
            valid_until=timezone.now() - timedelta(minutes=1)
        )

        cart = self._cart()
        self.assertIsNone(cart['applied_coupon'])
        self.assertEqual(cart['coupon_discount'], 0)
        self.cart.refresh_from_db()
        self.assertIsNone(self.cart.coupon_code)

    # ---------- ثبت سفارش ----------

    def test_order_total_includes_the_coupon_discount(self):
        self._coupon(percentage=10)

        control = self._checkout()
        self.assertEqual(control.status_code, 201, control.content[:300])
        control_total = Order.objects.get(
            order_number=control.json()['order_number']
        ).total

        self._refill_cart()
        self._apply('VOLT10')
        res = self._checkout()
        self.assertEqual(res.status_code, 201, res.content[:300])

        order = Order.objects.get(order_number=res.json()['order_number'])
        self.assertEqual(order.coupon_code, 'VOLT10')
        self.assertEqual(order.coupon_discount, Decimal('1000000'))
        self.assertEqual(control_total - order.total, Decimal('1000000'))

    def test_used_count_increases_after_checkout(self):
        coupon = self._coupon()
        self._apply('VOLT10')
        self._checkout()
        coupon.refresh_from_db()
        self.assertEqual(coupon.used_count, 1)

    def test_coupon_does_not_survive_into_the_next_order(self):
        """کد مصرف‌شده نباید روی سبد بماند و به سفارش بعدی سرایت کند."""
        self._coupon()
        self._apply('VOLT10')
        self._checkout()

        self.cart.refresh_from_db()
        self.assertIsNone(self.cart.coupon_code)
        self.assertEqual(self.cart.coupon_discount, 0)

        self._refill_cart()
        res = self._checkout()
        order = Order.objects.get(order_number=res.json()['order_number'])
        self.assertEqual(order.coupon_discount, Decimal('0'))

    def test_per_user_limit_blocks_a_second_use(self):
        self._coupon(usage_limit_per_user=1)
        self._apply('VOLT10')
        self._checkout()

        self._refill_cart()
        res = self._apply('VOLT10')
        self.assertEqual(res.status_code, 400)
        self.assertIn('قبلاً', res.json()['error'])

    def test_checkout_rejects_a_code_that_expired_after_it_was_applied(self):
        """مبلغ پرداختی از روی مقدار ذخیره‌شده‌ی سبد ساخته نمی‌شود."""
        from apps.shop.models import Coupon

        coupon = self._coupon()
        self._apply('VOLT10')
        # کوپن را مستقیم در دیتابیس منقضی می‌کنیم و سبد را دست نمی‌زنیم،
        # پس cart.coupon_discount هنوز مقدار قدیمی را دارد.
        Coupon.objects.filter(pk=coupon.pk).update(is_active=False)

        res = self._checkout()
        self.assertEqual(res.status_code, 400)
        self.assertIn('کد تخفیف', res.json()['error'])
        self.assertEqual(Order.objects.count(), 0)

    def test_a_made_up_code_no_longer_grants_a_discount(self):
        """رگرسیون: قبلاً هر رشته‌ای ۵۰٬۰۰۰ تومان تخفیف می‌گرفت."""
        res = self._apply('I-JUST-MADE-THIS-UP')
        self.assertEqual(res.status_code, 400)

        checkout = self._checkout()
        order = Order.objects.get(order_number=checkout.json()['order_number'])
        self.assertEqual(order.coupon_discount, Decimal('0'))
        self.assertEqual(order.discount_amount, Decimal('0'))

    # ---------- پنل ادمین ----------

    def test_admin_can_create_a_coupon(self):
        """ادمین باید بتواند کد و درصدش را از پنل تعریف کند."""
        from apps.shop.models import Coupon

        admin_user = User.objects.create_superuser(
            username='couponadmin',
            email='couponadmin@test.com',
            password='testpassword123',
            fullname='مدیر',
            mobile='09150000009',
        )
        self.client.force_login(admin_user)

        add_url = reverse('admin:shop_coupon_add')
        self.assertEqual(self.client.get(add_url).status_code, 200)

        res = self.client.post(add_url, {
            'code': 'ADMIN20',
            'percentage': '20',
            'min_order_amount': '0',
            'is_active': 'on',
        })
        self.assertEqual(res.status_code, 302, res.content[:500])
        coupon = Coupon.objects.get(code='ADMIN20')
        self.assertEqual(coupon.percentage, 20)

        # و همان کد بلافاصله در سبد خرید کار می‌کند.
        self.client.force_login(self.user)
        apply_res = self._apply('ADMIN20')
        self.assertEqual(apply_res.status_code, 200, apply_res.content[:300])
        self.assertEqual(apply_res.json()['discount_amount'], 2000000)

    def test_admin_changelist_renders(self):
        self._coupon()
        admin_user = User.objects.create_superuser(
            username='couponadmin2',
            email='couponadmin2@test.com',
            password='testpassword123',
            fullname='مدیر ۲',
            mobile='09150000008',
        )
        self.client.force_login(admin_user)
        res = self.client.get(reverse('admin:shop_coupon_changelist'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'VOLT10')
