from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

User = get_user_model()


class HeaderAuthenticationUITests(TestCase):
    """Tests for the header authentication UI according to requirements:
    - Unauthenticated: Show only Login and Register; hide cart and profile button.
    - Authenticated: Hide Login and Register; show Profile button linking to dashboard,
      displaying profile picture, first name, and last name; show cart button.
    """

    def setUp(self):
        self.client = Client()
        self.home_url = reverse('home_app:index')

    def test_unauthenticated_header_ui(self):
        response = self.client.get(self.home_url)
        self.assertEqual(response.status_code, 200)

        # Login and Register are visible
        self.assertContains(response, 'class="auth-link-login"')
        self.assertContains(response, reverse('accounts_app:login'))
        self.assertContains(response, reverse('accounts_app:register'))

        # Cart and Profile button are hidden
        self.assertNotContains(response, 'id="navCartBtn"')
        self.assertNotContains(response, 'id="authUserBtn"')
        self.assertNotContains(response, 'id="authUser"')

    def test_authenticated_header_ui(self):
        user = User.objects.create_user(
            username='testuser',
            password='Password123!',
            first_name='Ali',
            last_name='Rezaei'
        )
        self.client.force_login(user)

        response = self.client.get(self.home_url)
        self.assertEqual(response.status_code, 200)

        # Login and Register are hidden
        self.assertNotContains(response, 'class="auth-link-login"')
        self.assertNotContains(response, 'id="authGuest"')

        # Cart is visible
        self.assertContains(response, 'id="navCartBtn"')
        self.assertContains(response, reverse('shop_app:cart'))

        # Profile button is visible and links to profile page
        self.assertContains(response, 'id="authUserBtn"')
        self.assertContains(response, reverse('accounts_app:dashboard'))

        # Profile picture, first name, and last name are displayed
        self.assertContains(response, 'auth-user-avatar')
        self.assertContains(response, 'Ali')
        self.assertContains(response, 'Rezaei')

    def test_authenticated_header_ui_with_fullname_sync(self):
        user = User.objects.create_user(
            username='fullnameuser',
            password='Password123!',
            fullname='Sina Moradi'
        )
        self.client.force_login(user)

        response = self.client.get(self.home_url)
        self.assertEqual(response.status_code, 200)

        # Profile button displays first and last name from synced fullname
        self.assertContains(response, 'Sina')
        self.assertContains(response, 'Moradi')

    def test_mobile_drawer_removed_account_buttons(self):
        user = User.objects.create_user(
            username='draweruser',
            password='Password123!',
            first_name='Reza',
            last_name='Ahmadi'
        )
        self.client.force_login(user)

        response = self.client.get(self.home_url)
        self.assertEqual(response.status_code, 200)

        # In drawerAuthUser, the 4 specific links are removed
        # Ensure #orders, #wishlist, #settings links are not in drawer
        content = response.content.decode('utf-8')
        self.assertIn('id="drawerAuthUser"', content)
        drawer_part = content.split('id="drawerAuthUser"')[1].split('</div>')[0]
        self.assertNotIn('#orders', drawer_part)
        self.assertNotIn('#wishlist', drawer_part)
        self.assertNotIn('#settings', drawer_part)

