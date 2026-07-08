# provinces_and_cities/import_data.py (نسخه کامل)

import os
import sys
import json
import django
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.accounts.models import Province, City


def import_provinces():
    file_path = os.path.join(os.path.dirname(__file__), 'provinces.json')

    if not os.path.exists(file_path):
        print(f"❌ فایل {file_path} پیدا نشد!")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    created_count = 0
    existing_count = 0

    for item in data:
        name = item.get('provinceName')
        if not name:
            continue

        province, created = Province.objects.get_or_create(name=name)
        if created:
            created_count += 1
            print(f"✅ استان {name} ایجاد شد")
        else:
            existing_count += 1

    print(f"📊 {created_count} استان جدید / {existing_count} استان موجود")
    return created_count


def import_cities():
    file_path = os.path.join(os.path.dirname(__file__), 'provinces_cities.json')

    if not os.path.exists(file_path):
        print(f"❌ فایل {file_path} پیدا نشد!")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # گروه‌بندی شهرها بر اساس استان
    cities_by_province = defaultdict(list)
    for item in data:
        province_name = item.get('provinceName')
        city_name = item.get('cityName')
        if province_name and city_name:
            cities_by_province[province_name].append(city_name)

    created_count = 0
    existing_count = 0
    skipped_provinces = []

    for province_name, city_names in cities_by_province.items():
        try:
            province = Province.objects.get(name=province_name)
        except Province.DoesNotExist:
            skipped_provinces.append(province_name)
            print(f"⚠️ استان {province_name} وجود ندارد - {len(city_names)} شهر رد شد")
            continue

        for city_name in set(city_names):  # حذف تکراری‌ها
            city, created = City.objects.get_or_create(
                province=province,
                name=city_name
            )
            if created:
                created_count += 1
                print(f"✅ شهر {city_name} ({province_name}) ایجاد شد")
            else:
                existing_count += 1

    if skipped_provinces:
        print(f"\n⚠️ استان‌های بدون شهر: {', '.join(skipped_provinces)}")

    print(f"📊 {created_count} شهر جدید / {existing_count} شهر موجود")
    return created_count


def main():
    print("=" * 60)
    print("🚀 شروع ایمپورت استان‌ها و شهرهای ایران")
    print("=" * 60)

    print("\n📌 مرحله ۱: ایمپورت استان‌ها...")
    import_provinces()

    print("\n📌 مرحله ۲: ایمپورت شهرها...")
    import_cities()

    print("\n" + "=" * 60)
    print("🎉 ایمپورت با موفقیت انجام شد!")
    print("=" * 60)


if __name__ == '__main__':
    main()