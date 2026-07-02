from django.urls import path

from .views import RegisterPageView, UserRegistrationAPIView

app_name = 'accounts_app'

urlpatterns = [
    path('register/', RegisterPageView.as_view(), name='register'),
    path('api/register/', UserRegistrationAPIView.as_view(), name='api_register'),
]