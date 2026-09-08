"""Excessive data exposure and mass-assignment on the public/authenticated API."""

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from ._helpers import (
    make_user, make_product, make_article, make_comment, make_review,
    reset_throttles,
)


@override_settings(SECURE_SSL_REDIRECT=False)
class PublicCommentSerializerTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        reset_throttles()
        self.article = make_article()
        self.author = make_user(username='commenter')
        make_comment(article=self.article, user=self.author, approved=True)

    def test_public_comment_feed_does_not_leak_internal_user_id(self):
        resp = self.client.get(
            reverse('home_app:api_comments', args=[self.article.slug])
        )
        self.assertEqual(resp.status_code, 200)
        row = resp.json()[0]
        self.assertIn('user_name', row)
        self.assertNotIn(
            'user', row,
            'raw user PK is exposed on the public comment feed -> user enumeration',
        )

    def test_public_comment_feed_does_not_leak_moderation_flag(self):
        resp = self.client.get(
            reverse('home_app:api_comments', args=[self.article.slug])
        )
        row = resp.json()[0]
        self.assertNotIn('is_approved', row)


@override_settings(SECURE_SSL_REDIRECT=False)
class PublicReviewSerializerTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        reset_throttles()
        self.product = make_product()
        make_review(product=self.product, status='approved')

    def test_public_review_feed_does_not_leak_internal_user_id(self):
        resp = self.client.get(
            reverse('shop:api_reviews', args=[self.product.slug])
        )
        self.assertEqual(resp.status_code, 200)
        row = resp.json()[0]
        self.assertIn('user_name', row)
        self.assertNotIn('user', row, 'raw user PK exposed on public review feed')

    def test_public_review_feed_does_not_leak_moderation_status(self):
        resp = self.client.get(
            reverse('shop:api_reviews', args=[self.product.slug])
        )
        row = resp.json()[0]
        self.assertNotIn('status', row)


@override_settings(SECURE_SSL_REDIRECT=False)
class ProductDetailExposureTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        reset_throttles()
        self.product = make_product(stock=7, view_count=999)

    def test_exact_stock_count_is_not_published(self):
        resp = self.client.get(
            reverse('shop:api_product_detail', args=[self.product.slug])
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertNotIn(
            'stock', body,
            'exact inventory count is commercial signal and should not be public',
        )
        # a boolean availability flag is fine
        self.assertIn('is_available', body)

    def test_review_create_cannot_force_approved_status(self):
        user = make_user()
        self.client.force_authenticate(user)
        resp = self.client.post(
            reverse('shop:api_reviews', args=[self.product.slug]),
            {'rating': 5, 'title': 'x', 'comment': 'y', 'status': 'approved'},
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        from apps.shop.models import ProductReview
        self.assertEqual(ProductReview.objects.get().status, 'pending')

    def test_comment_create_cannot_force_approved_flag(self):
        user = make_user()
        self.client.force_authenticate(user)
        article = make_article()
        resp = self.client.post(
            reverse('home_app:api_comments', args=[article.slug]),
            {'content': 'hello', 'is_approved': True},
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        from apps.home.models import Comment
        self.assertFalse(Comment.objects.get().is_approved)


@override_settings(SECURE_SSL_REDIRECT=False)
class ProfileUpdateMassAssignmentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        reset_throttles()
        self.user = make_user(password='Current-Pw-1')
        self.url = reverse('accounts_app:api_profile_update')

    def test_cannot_escalate_privileges_through_profile_update(self):
        self.client.force_authenticate(self.user)
        resp = self.client.put(
            self.url,
            {
                'full_name': 'رضا',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
                'is_verified': True,
            },
            format='json',
        )
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
        self.assertFalse(self.user.is_verified)

    def test_changing_email_requires_current_password(self):
        """A stolen session must not convert straight to account takeover."""
        self.client.force_authenticate(self.user)
        resp = self.client.put(
            self.url, {'email': 'attacker@evil.test'}, format='json'
        )
        self.assertEqual(
            resp.status_code, 400,
            'email changed with no re-authentication -> takeover via password reset',
        )
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.email, 'attacker@evil.test')

    def test_email_change_succeeds_with_current_password(self):
        self.client.force_authenticate(self.user)
        resp = self.client.put(
            self.url,
            {'email': 'new@example.test', 'current_password': 'Current-Pw-1'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'new@example.test')

    def test_non_identity_fields_do_not_require_password(self):
        self.client.force_authenticate(self.user)
        resp = self.client.put(self.url, {'bio': 'سلام'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.user.refresh_from_db()
        self.assertEqual(self.user.bio, 'سلام')
