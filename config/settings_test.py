"""Test settings.

The project targets PostgreSQL, but the audit/test environment has no database
server, so tests run on SQLite. Security-relevant behaviour (permissions,
ownership checks, escaping, throttling, headers) is database-agnostic.

DEBUG is forced False so the production security code paths (secure-cookie
flags, HSTS, error handling) are what actually gets exercised. SECURE_SSL_REDIRECT
is the one prod flag left off, because an unconditional 301-to-https makes the
Django test client unusable.
"""

from .settings import *  # noqa: F401,F403

DEBUG = False

ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Deterministic + fast.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# In-memory, per-process, and cleared between tests via a fixture/tearDown where
# throttling matters.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'nexgo-test',
    }
}

# Exercise the prod paths.
SECURE_SSL_REDIRECT = False          # keep the test client usable
SECURE_HSTS_SECONDS = 31536000
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

MEDIA_ROOT = BASE_DIR / 'test-media'  # noqa: F405

# Don't hit the network / compressor during template rendering.
COMPRESS_ENABLED = False
COMPRESS_OFFLINE = False

# Plain static storage in tests: the manifest/brotli pipeline needs a
# collectstatic run we don't want as a test precondition.
STORAGES = {
    **STORAGES,  # noqa: F405
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}
WHITENOISE_AUTOREFRESH = True

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Make DRF throttling assertions deterministic: the scoped rates are what we
# test, so keep them, but the tests that don't care about throttling call
# _reset_throttles().
