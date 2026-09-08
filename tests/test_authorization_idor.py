"""Object-level and function-level access control.

Horizontal escalation (user A reaching user B's data) and vertical escalation
(a normal user reaching staff/admin surface).
"""

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Address, Province, City
from ._helpers import make_user, make_staff, make_product, reset_throttles


@override_settings(SECURE_SSL_REDIRECT=False)
class AddressOwnershipTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        reset_throttles()
        self.alice = make_user()
        self.bob = make_user()
        self.province = Province.objects.create(name='تهران')
        self.city = City.objects.create(province=self.province, name='تهران')
        self.bob_address = Address.objects.create(
            user=self.bob,
            recipient_name='باب',
            recipient_phone='09120000000',
            province=self.province,
            city=self.city,
            address='خیابان تست',
            postal_code='1234567890',
            plaque='1',
        )

    def test_address_list_is_scoped_to_the_caller(self):
        self.client.force_authenticate(self.alice)
        resp = self.client.get(reverse('accounts_app:api_addresses'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])  # Bob's address must not appear

    def test_user_cannot_delete_another_users_address(self):
        self.client.force_authenticate(self.alice)
        resp = self.client.delete(
            reverse('accounts_app:api_address_delete', args=[self.bob_address.pk])
        )
        self.assertEqual(resp.status_code, 404)
        self.bob_address.refresh_from_db()
        self.assertTrue(self.bob_address.is_active)

    def test_owner_can_delete_their_own_address(self):
        self.client.force_authenticate(self.bob)
        resp = self.client.delete(
            reverse('accounts_app:api_address_delete', args=[self.bob_address.pk])
        )
        self.assertEqual(resp.status_code, 200)
        self.bob_address.refresh_from_db()
        self.assertFalse(self.bob_address.is_active)

    def test_new_address_is_bound_to_caller_even_if_user_id_is_forced(self):
        self.client.force_authenticate(self.alice)
        resp = self.client.post(
            reverse('accounts_app:api_addresses'),
            {
                'user': self.bob.id,  # attempted override
                'recipient_name': 'آلیس',
                'recipient_phone': '09120000001',
                'province': self.province.id,
                'city': self.city.id,
                'address': 'جای دیگر',
                'postal_code': '1234509876',
                'plaque': '9',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(Address.objects.get(id=resp.json()['id']).user_id, self.alice.id)


@override_settings(SECURE_SSL_REDIRECT=False)
class DashboardOwnershipTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        reset_throttles()
        self.alice = make_user()
        self.bob = make_user()

    def test_dashboard_requires_authentication(self):
        resp = self.client.get(reverse('accounts_app:api_dashboard'))
        self.assertIn(resp.status_code, (401, 403))

    def test_dashboard_returns_only_callers_data(self):
        self.client.force_authenticate(self.alice)
        resp = self.client.get(reverse('accounts_app:api_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['user']['username'], self.alice.username)


@override_settings(SECURE_SSL_REDIRECT=False)
class WishlistOwnershipTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        reset_throttles()
        self.alice = make_user()
        self.bob = make_user()
        self.product = make_product()

    def test_wishlist_list_is_scoped_to_caller(self):
        from apps.shop.models import Wishlist
        Wishlist.objects.create(user=self.bob, product=self.product)
        self.client.force_authenticate(self.alice)
        resp = self.client.get(reverse('shop:api_wishlist_list'))
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        results = body['results'] if isinstance(body, dict) else body
        self.assertEqual(results, [])

    def test_wishlist_toggle_requires_auth(self):
        resp = self.client.post(
            reverse('shop:api_wishlist_toggle'), {'product_id': self.product.id}, format='json'
        )
        self.assertIn(resp.status_code, (401, 403))


@override_settings(SECURE_SSL_REDIRECT=False)
class VerticalEscalationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        reset_throttles()
        self.user = make_user()

    def test_admin_index_denied_to_anonymous_and_normal_users(self):
        self.assertEqual(self.client.get('/admin/').status_code, 302)  # -> login
        self.client.force_login(self.user)
        resp = self.client.get('/admin/', follow=True)
        # non-staff hitting admin gets bounced to the admin login, never the index
        self.assertNotContains(resp, 'id="user-tools"', status_code=200)

    def test_openapi_schema_is_staff_only(self):
        for name in ('schema', 'swagger-ui', 'redoc'):
            resp = self.client.get(reverse(name))
            self.assertIn(
                resp.status_code, (401, 403),
                f'{name} exposed to anonymous callers (status {resp.status_code})',
            )

    def test_openapi_schema_denied_to_normal_user(self):
        self.client.force_authenticate(self.user)
        resp = self.client.get(reverse('schema'))
        self.assertIn(resp.status_code, (401, 403))

    def test_staff_can_reach_openapi_schema(self):
        staff = make_staff()
        self.client.force_authenticate(staff)
        resp = self.client.get(reverse('schema'))
        self.assertEqual(resp.status_code, 200)

    def test_normal_user_cannot_reach_django_admin_model_pages(self):
        self.client.force_login(self.user)
        for path in ('/admin/accounts/customuser/', '/admin/shop/product/', '/admin/home/comment/'):
            resp = self.client.get(path)
            self.assertIn(resp.status_code, (302, 403), f'{path} -> {resp.status_code}')
