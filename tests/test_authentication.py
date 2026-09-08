"""Authentication surface: registration, login, password change, session handling."""

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from ._helpers import make_user, reset_throttles


@override_settings(SECURE_SSL_REDIRECT=False)
class RegistrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        reset_throttles()
        self.url = reverse('accounts_app:api_register')

    def _payload(self, **over):
        data = dict(
            fullname='رضا تستی',
            username='newuser',
            mobile='09121234567',
            email='newuser@example.test',
            password1='Str0ng-Passw0rd!',
            password2='Str0ng-Passw0rd!',
            agree_terms=True,
        )
        data.update(over)
        return data

    def test_valid_registration_creates_user(self):
        resp = self.client.post(self.url, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        from django.contrib.auth import get_user_model
        self.assertTrue(get_user_model().objects.filter(username='newuser').exists())

    def test_registration_rejects_html_in_fullname(self):
        """fullname is echoed next to every comment/review — markup must be refused."""
        resp = self.client.post(
            self.url,
            self._payload(fullname='<img src=x onerror=alert(1)>'),
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('fullname', resp.json().get('errors', {}))

    def test_registration_cannot_set_privileged_flags(self):
        """Mass-assignment guard: is_staff / is_superuser / is_active are not writable."""
        resp = self.client.post(
            self.url,
            self._payload(is_staff=True, is_superuser=True, is_active=False),
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.get(username='newuser')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_active)

    def test_registration_enforces_password_confirmation(self):
        resp = self.client.post(
            self.url, self._payload(password2='different'), format='json'
        )
        self.assertEqual(resp.status_code, 400)

    def test_registration_rejects_weak_password(self):
        resp = self.client.post(
            self.url,
            self._payload(password1='12345678', password2='12345678'),
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_registration_requires_terms_acceptance(self):
        resp = self.client.post(
            self.url, self._payload(agree_terms=False), format='json'
        )
        self.assertEqual(resp.status_code, 400)


@override_settings(SECURE_SSL_REDIRECT=False)
class LoginTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        reset_throttles()
        self.user = make_user(username='alice', password='Alice-Str0ng-1')
        self.url = reverse('accounts_app:api_login')

    def test_login_succeeds_with_username(self):
        resp = self.client.post(
            self.url, {'username': 'alice', 'password': 'Alice-Str0ng-1'}, format='json'
        )
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_login_succeeds_with_mobile(self):
        resp = self.client.post(
            self.url,
            {'username': self.user.mobile, 'password': 'Alice-Str0ng-1'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_wrong_password_and_unknown_user_are_indistinguishable(self):
        wrong_pw = self.client.post(
            self.url, {'username': 'alice', 'password': 'nope'}, format='json'
        )
        reset_throttles()
        no_user = self.client.post(
            self.url, {'username': 'ghost', 'password': 'nope'}, format='json'
        )
        self.assertEqual(wrong_pw.status_code, 400)
        self.assertEqual(no_user.status_code, 400)
        self.assertEqual(wrong_pw.json()['errors'], no_user.json()['errors'])

    def test_inactive_account_cannot_log_in(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        resp = self.client.post(
            self.url, {'username': 'alice', 'password': 'Alice-Str0ng-1'}, format='json'
        )
        self.assertEqual(resp.status_code, 400)

    def test_login_is_rate_limited(self):
        reset_throttles()
        codes = []
        for _ in range(9):
            r = self.client.post(
                self.url, {'username': 'alice', 'password': 'bad'}, format='json'
            )
            codes.append(r.status_code)
        self.assertIn(429, codes, f'no 429 in {codes} — login brute-force is unthrottled')


@override_settings(SECURE_SSL_REDIRECT=False)
class PasswordChangeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        reset_throttles()
        self.user = make_user(password='Old-Passw0rd-1')
        self.url = reverse('accounts_app:api_change_password')

    def test_requires_authentication(self):
        resp = self.client.post(self.url, {}, format='json')
        self.assertIn(resp.status_code, (401, 403))

    def test_requires_correct_current_password(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(
            self.url,
            {
                'old_password': 'WRONG',
                'new_password1': 'Brand-New-Pw-9',
                'new_password2': 'Brand-New-Pw-9',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Old-Passw0rd-1'))

    def test_successful_change_keeps_current_session_valid(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            self.url,
            {
                'old_password': 'Old-Passw0rd-1',
                'new_password1': 'Brand-New-Pw-9',
                'new_password2': 'Brand-New-Pw-9',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        # session hash was rotated in-place -> still authenticated
        who = self.client.get(reverse('accounts_app:api_dashboard'))
        self.assertEqual(who.status_code, 200)
