"""Shared builders and utilities for the security test suite.

No factory_boy dependency — plain helper functions keep the suite runnable with
just Django + DRF, which is all the project ships.
"""

from __future__ import annotations

import io
import itertools

from django.contrib.auth import get_user_model
from django.core.cache import cache

from apps.home.models import Article, Comment
from apps.shop.models import Category, Product, ProductReview

User = get_user_model()

_counter = itertools.count(1)


def reset_throttles():
    """DRF throttling is cache-backed; clear it so unrelated tests don't trip it."""
    cache.clear()


def make_user(**kwargs):
    n = next(_counter)
    defaults = dict(
        username=f'user{n}',
        email=f'user{n}@example.test',
        password='Str0ng-pw-{}'.format(n),
        fullname=f'کاربر {n}',
        mobile=f'0912000{n:04d}',
    )
    defaults.update(kwargs)
    password = defaults.pop('password')
    user = User(**defaults)
    user.set_password(password)
    user.save()
    user.raw_password = password
    return user


def make_staff(**kwargs):
    kwargs.setdefault('is_staff', True)
    return make_user(**kwargs)


def make_superuser(**kwargs):
    kwargs.setdefault('is_staff', True)
    kwargs.setdefault('is_superuser', True)
    return make_user(**kwargs)


def make_category(**kwargs):
    n = next(_counter)
    defaults = dict(name=f'دسته {n}', slug=f'cat-{n}')
    defaults.update(kwargs)
    return Category.objects.create(**defaults)


def make_product(*, category=None, **kwargs):
    n = next(_counter)
    category = category or make_category()
    defaults = dict(
        name=f'اسکوتر {n}',
        slug=f'scooter-{n}',
        category=category,
        description='توضیحات آزمایشی محصول برای تست امنیت.',
        price=10_000_000,
        stock=5,
    )
    defaults.update(kwargs)
    return Product.objects.create(**defaults)


def make_article(*, author=None, **kwargs):
    n = next(_counter)
    author = author or make_user()
    defaults = dict(
        title=f'مقاله {n}',
        slug=f'article-{n}',
        author=author,
        description='<p>محتوای آزمایشی مقاله.</p>',
    )
    defaults.update(kwargs)
    return Article.objects.create(**defaults)


def make_comment(*, article=None, user=None, approved=True, **kwargs):
    article = article or make_article()
    user = user or make_user()
    defaults = dict(article=article, user=user, content='یک نظر آزمایشی', is_approved=approved)
    defaults.update(kwargs)
    return Comment.objects.create(**defaults)


def make_review(*, product=None, user=None, status='approved', **kwargs):
    product = product or make_product()
    user = user or make_user()
    defaults = dict(product=product, user=user, rating=5, comment='نظر آزمایشی', status=status)
    defaults.update(kwargs)
    return ProductReview.objects.create(**defaults)


def tiny_png(name='avatar.png'):
    """A real 1x1 PNG as an uploadable file object."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    data = bytes.fromhex(
        '89504e470d0a1a0a0000000d49484452000000010000000108020000009077'
        '53de0000000c49444154789c6360000002000100025d4db2f30000000049454e44ae426082'
    )
    return SimpleUploadedFile(name, data, content_type='image/png')
