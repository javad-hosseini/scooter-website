# Test Suite Overview

This document provides a high‑level summary of the automated test suites added to the **Scooter Website** project and a quick cheat‑sheet for common development commands.

---
## What Is Tested?

| App | Test File | Focus Area |
|-----|-----------|------------|
| **accounts** | `apps/accounts/tests/test_models.py` | Model behaviours:
- `CustomUser.__str__` returns `fullname` when set, otherwise the email.
- Default profile image path.
- `PasswordResetOTP` hashing, matching and expiration logic.
- `Province` and `City` string representations. |
| **core** | `apps/core/tests/test_middleware.py` | Basic middleware execution (example `ExampleMiddleware`). The test gracefully skips if the middleware does not exist. |
| **global fixtures** | `tests/conftest.py` | Provides a reusable `client` fixture for Django tests. |

These tests are written with **pytest** and use the `pytest‑django` plugin, allowing database access with the `@pytest.mark.django_db` marker.

---
## How to Run the Tests

```bash
# Install test dependencies (if not already in requirements-dev.txt)
pip install pytest pytest-django

# Run all tests (quiet mode)
pytest -q

# Run a specific app's tests
pytest apps/accounts
pytest apps/core

# Generate an HTML coverage report (requires pytest-cov)
pytest --cov=. --cov-report=html
```

---
## Cheat‑Sheet for Common Commands

| Task | Command |
|------|----------|
| **Start development server** | `python manage.py runserver` |
| **Apply migrations** | `python manage.py migrate` |
| **Create a new migration** | `python manage.py makemigrations <app_name>` |
| **Run test suite** | `pytest -q` |
| **Run tests with coverage** | `pytest --cov=. --cov-report=term-missing` |
| **Open Django shell** | `python manage.py shell` |
| **Create superuser** | `python manage.py createsuperuser` |
| **Collect static files** | `python manage.py collectstatic` |
| **Generate test skeletons (custom command)** | `python manage.py generate_tests` *(see `tools/unit_test_generator.py`)* |

Feel free to extend this document as new tests are added or new utilities are created.
