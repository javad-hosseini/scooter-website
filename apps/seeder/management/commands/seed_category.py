"""
Management command to seed realistic Scooter Categories with solid-color banner images.
Usage:
    python manage.py seed-category
    python manage.py seed_category --count 10 --clear
"""

import sys
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify
from faker import Faker

from apps.shop.models import Category
from apps.home.models import CategoryImage, CategoryFeature, CategoryBadge
from apps.seeder.data_catalog import SCOOTER_CATEGORIES
from apps.seeder.image_factory import create_category_image

fake = Faker('en_US')


class Command(BaseCommand):
    help = "Seed scooter categories with Pillow-generated banner images and specifications."

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=0,
            help="Total number of categories to ensure. Defaults to full predefined catalog (approx 20 categories).",
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help="Delete existing categories and related category images/features before seeding.",
        )
        parser.add_argument(
            '--no-images',
            action='store_true',
            help="Skip image generation for ultra-fast seeding.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING(">>> Seeding Scooter Categories..."))

        target_count = options.get('count') or 0
        clear_existing = options.get('clear', False)
        no_images = options.get('no_images', False)

        if clear_existing:
            self.stdout.write(self.style.WARNING("Clearing existing categories..."))
            CategoryImage.objects.all().delete()
            CategoryFeature.objects.all().delete()
            CategoryBadge.objects.all().delete()
            Category.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("All existing categories cleared."))

        created_categories = []
        order_counter = 1

        with transaction.atomic():
            # 1. Seed predefined hierarchy from catalog
            for parent_name, parent_slug, icon, desc, children in SCOOTER_CATEGORIES:
                parent, created = Category.objects.get_or_create(
                    slug=parent_slug,
                    defaults={
                        'name': parent_name,
                        'icon': icon,
                        'description': desc,
                        'order': order_counter,
                        'is_active': True,
                        'meta_title': f"خرید انواع {parent_name} | فروشگاه تخصصی نکس‌گو",
                        'meta_description': desc[:150],
                    }
                )
                order_counter += 1
                created_categories.append(parent)

                # Attach image & badges if new or missing
                if not no_images and not parent.images.exists():
                    img_file = create_category_image(parent_slug.replace('-', ' '), subtitle="PREMIUM CATEGORY")
                    CategoryImage.objects.create(
                        category=parent,
                        image=img_file,
                        alt_text=f"تصویر دسته {parent.name}",
                        is_primary=True,
                        order=1,
                    )

                if not parent.badges.exists():
                    CategoryBadge.objects.create(
                        category=parent,
                        label="اصلی",
                        badge_text="کالکشن ۲۰۲۶",
                        color="cyan",
                        order=1,
                    )

                self.stdout.write(f"  [Parent Category] {parent.slug}")

                # Subcategories
                for sub_name, sub_slug, sub_icon, sub_desc in children:
                    sub, sub_created = Category.objects.get_or_create(
                        slug=sub_slug,
                        defaults={
                            'name': sub_name,
                            'icon': sub_icon,
                            'description': sub_desc,
                            'parent': parent,
                            'order': order_counter,
                            'is_active': True,
                            'meta_title': f"{sub_name} اصل با گارانتی | نکس‌گو",
                            'meta_description': sub_desc[:150],
                        }
                    )
                    order_counter += 1
                    created_categories.append(sub)

                    if not no_images and not sub.images.exists():
                        img_file = create_category_image(sub_slug.replace('-', ' '), subtitle="SUB-CATEGORY")
                        CategoryImage.objects.create(
                            category=sub,
                            image=img_file,
                            alt_text=f"Category image {sub_slug}",
                            is_primary=True,
                            order=1,
                        )

                    if not sub.features.exists():
                        CategoryFeature.objects.create(
                            category=sub,
                            icon="fa-solid fa-check",
                            label="تضمین کیفیت",
                            value="استاندارد جهانی",
                            color="cyan",
                            order=1,
                        )
                    self.stdout.write(f"    +-- [Subcategory] {sub.slug}")

            # 2. If user requested more categories with --count, generate remaining using Faker
            current_total = Category.objects.count()
            if target_count > current_total:
                needed = target_count - current_total
                self.stdout.write(self.style.NOTICE(f"Generating {needed} additional categories with Faker..."))
                parent_pool = list(Category.objects.filter(parent__isnull=True))

                for i in range(needed):
                    eng_word = fake.unique.word().capitalize()
                    sub_name = f"دسته {eng_word} اختصاصی"
                    sub_slug = slugify(f"{eng_word}-custom-{order_counter}", allow_unicode=True)
                    chosen_parent = fake.random_element(parent_pool) if parent_pool else None

                    cat = Category.objects.create(
                        name=sub_name,
                        slug=sub_slug,
                        icon="fa-solid fa-tag",
                        description=f"دسته‌بندی آزمایشی {eng_word} با تجهیزات و مشخصات ویژه.",
                        parent=chosen_parent,
                        order=order_counter,
                        is_active=True,
                        meta_title=f"{sub_name} | فروشگاه نکس‌گو",
                        meta_description=f"خرید انواع محصولات {sub_name} با بهترین قیمت",
                    )
                    order_counter += 1
                    created_categories.append(cat)

                    if not no_images:
                        img_file = create_category_image(eng_word, subtitle="CUSTOM CATEGORY")
                        CategoryImage.objects.create(
                            category=cat,
                            image=img_file,
                            alt_text=f"Category {eng_word}",
                            is_primary=True,
                            order=1,
                        )

        total_now = Category.objects.count()
        self.stdout.write(
            self.style.SUCCESS(f"✓ Category seeding complete! Total active categories: {total_now}")
        )
