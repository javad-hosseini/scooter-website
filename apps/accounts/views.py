import logging

from django.views.generic import TemplateView
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .serializers import UserRegistrationSerializer

logger = logging.getLogger(__name__)


class UserRegistrationAPIView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors,
                'message': 'اطلاعات وارد شده معتبر نیست'
            }, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        return Response({
            'success': True,
            'message': 'ثبت‌نام با موفقیت انجام شد',
            'user': {
                'id': user.id,
                'email': user.email,
                'fullname': user.fullname,
                'mobile': user.mobile
            }
        }, status=status.HTTP_201_CREATED)


class RegisterPageView(TemplateView):
    template_name = 'accounts/register.html'
