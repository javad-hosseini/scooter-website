# provinces_and_cities/reset_data.py

import os
import sys
import django

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.accounts.models import Province, City

# حذف همه
Province.objects.all().delete()
City.objects.all().delete()

print("🗑️ همه استان‌ها و شهرها حذف شدند")