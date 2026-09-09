import pytest
from django.test import RequestFactory

@pytest.fixture
def request_factory():
    return RequestFactory()

def test_dummy_middleware_process_request(request_factory):
    # Example: test a generic middleware that does nothing
    try:
        from apps.core.middleware import ExampleMiddleware
    except ImportError:
        pytest.skip("ExampleMiddleware not defined in apps.core.middleware")
    request = request_factory.get('/')
    middleware = ExampleMiddleware(lambda r: None)
    # If middleware defines process_request, call it
    if hasattr(middleware, 'process_request'):
        response = middleware.process_request(request)
        assert response is None
    else:
        pytest.skip("process_request not implemented")
