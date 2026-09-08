from django.urls import path

from . import views

app_name = 'seo'

urlpatterns = [
    path('about/', views.AboutPageView.as_view(), name='about'),
    path('contact/', views.ContactPageView.as_view(), name='contact'),
]
