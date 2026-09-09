import pytest
from apps.accounts.models import CustomUser, PasswordResetOTP, Province, City, Address
from django.utils import timezone

@pytest.mark.django_db
class TestCustomUser:
    def test_str_returns_fullname_or_email(self):
        user = CustomUser.objects.create_user(username='testuser', password='pass', email='test@example.com', fullname='John Doe')
        assert str(user) == 'John Doe'
        user.fullname = ''
        user.save()
        assert str(user) == 'test@example.com'

    def test_profile_image_default(self):
        user = CustomUser.objects.create_user(username='imguser', password='pass', email='img@example.com')
        assert user.profile_image.name == 'users/profiles/default-avatar.png'

@pytest.mark.django_db
class TestPasswordResetOTP:
    def test_hash_and_match(self):
        code = '123456'
        hashed = PasswordResetOTP.hash_code(code)
        assert PasswordResetOTP.matches(hashed, code)
        assert not PasswordResetOTP.matches(hashed, '654321')

    def test_is_expired(self, monkeypatch):
        now = timezone.now()
        otp = PasswordResetOTP.objects.create(
            user=CustomUser.objects.create_user(username='u', password='p'),
            code_hash='hash',
            channel='email',
            destination='test',
            expires_at=now
        )
        assert not otp.is_expired()
        monkeypatch.setattr('django.utils.timezone.now', lambda: now + timezone.timedelta(minutes=10))
        assert otp.is_expired()

@pytest.mark.django_db
class TestProvinceCity:
    def test_str(self):
        province = Province.objects.create(name='Tehran')
        city = City.objects.create(name='Tehran', province=province)
        assert str(province) == 'Tehran'
        assert str(city) == 'Tehran (Tehran)'
