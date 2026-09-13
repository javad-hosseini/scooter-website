"""
Management command to seed realistic Scooter Products with Pillow-generated solid images.
Usage:
    python manage.py seed-product --count 100
    python manage.py seed_product --count 200 --clear
"""

import random
import uuid
from decimal import Decimal
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify
from faker import Faker

from apps.shop.models import Category, Product, ProductImage, ProductSpec, TrustBadge
from apps.seeder.data_catalog import (
    BRANDS,
    ELECTRIC_MODEL_NAMES,
    KICK_MODEL_NAMES,
    ACCESSORY_MODEL_NAMES,
    PART_MODEL_NAMES,
    PRODUCT_COLORS,
    TRUST_BADGES,
    get_specs_for_product,
)
from apps.seeder.image_factory import (
    create_product_cover_image,
    create_product_grid_image,
    create_product_gallery_image,
)

fake = Faker('fa_IR')
fake_en = Faker('en_US')


class Command(BaseCommand):
    help = "Seed realistic scooter products with images, specs, gallery variants, and pricing."

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=20,
            help="Number of products to generate (default: 20).",
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help="Delete all existing products and related specs/images before seeding.",
        )
        parser.add_argument(
            '--category',
            type=str,
            default=None,
            help="Optional category slug to assign all generated products to.",
        )
        parser.add_argument(
            '--no-images',
            action='store_true',
            help="Skip image generation for rapid database-only generation.",
        )

    def handle(self, *args, **options):
        count = options['count']
        clear_existing = options['clear']
        target_category_slug = options.get('category')
        no_images = options['no_images']

        self.stdout.write(self.style.MIGRATE_HEADING(f">>> Seeding {count} Scooter Products..."))

        if clear_existing:
            self.stdout.write(self.style.WARNING("Clearing existing products..."))
            ProductImage.objects.all().delete()
            ProductSpec.objects.all().delete()
            TrustBadge.objects.all().delete()
            Product.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("All products and related records cleared."))

        # Ensure categories exist
        categories = list(Category.objects.all())
        if not categories:
            self.stdout.write(self.style.NOTICE("No categories found. Seeding base categories first..."))
            call_command('seed_category')
            categories = list(Category.objects.all())

        if target_category_slug:
            categories = [c for c in categories if c.slug == target_category_slug]
            if not categories:
                self.stderr.write(self.style.ERROR(f"Category with slug '{target_category_slug}' not found."))
                return

        # Prepare pool of predefined templates
        all_templates = (
            [('electric', item) for item in ELECTRIC_MODEL_NAMES] +
            [('kick', item) for item in KICK_MODEL_NAMES] +
            [('accessory', item) for item in ACCESSORY_MODEL_NAMES] +
            [('part', item) for item in PART_MODEL_NAMES]
        )
        random.shuffle(all_templates)

        created_count = 0
        batch_size = 20

        # We process in batches for transaction efficiency and responsiveness
        for i in range(count):
            # Select or synthesize product data
            if i < len(all_templates):
                ptype, (pname_fa, pname_en, base_price, discount_price) = all_templates[i]
            else:
                # Synthesize realistic variations using domain keywords
                ptype = random.choice(['electric', 'kick', 'accessory', 'part'])
                brand = random.choice(BRANDS)
                model_code = f"{fake_en.lexify(text='???').upper()}-{random.randint(100, 999)}"

                if ptype == 'electric':
                    watts = random.choice([350, 500, 800, 1000, 1600, 2000, 2400])
                    pname_en = f"{brand} {model_code} {watts}W Dual Motor"
                    pname_fa = f"اسکوتر برقی {brand} مدل {model_code} توان {watts} وات"
                    base_price = random.randint(25, 95) * 1_000_000
                elif ptype == 'kick':
                    wheel = random.choice([110, 120, 145, 200, 230])
                    pname_en = f"{brand} {model_code} Stunt {wheel}mm"
                    pname_fa = f"اسکوتر مکانیکی {brand} مدل {model_code} چرخ {wheel} میلی‌متر"
                    base_price = random.randint(3, 16) * 1_000_000
                elif ptype == 'accessory':
                    acc_type = random.choice(["کلاه ایمنی", "قفل ضدسرقت", "کیف هاردشل", "چراغ LED", "نگهدارنده موبایل"])
                    acc_en = random.choice(["Helmet", "Lock", "Handlebar Bag", "Light", "Phone Mount"])
                    pname_en = f"{brand} Pro {acc_en} {model_code}"
                    pname_fa = f"{acc_type} تخصصی {brand} مدل {model_code}"
                    base_price = random.randint(500_000, 4_500_000)
                else:
                    part_type = random.choice(["باتری لیتیومی", "لاستیک توپر", "کالیپر ترمز", "کمک‌فنر دوبل", "شارژر هوشمند"])
                    part_en = random.choice(["Battery Pack", "Solid Tire", "Brake Caliper", "Suspension", "Charger"])
                    pname_en = f"{brand} {part_en} OEM {model_code}"
                    pname_fa = f"{part_type} اورجینال {brand} مدل {model_code}"
                    base_price = random.randint(800_000, 18_000_000)

                # 35% chance of random discount
                if random.random() < 0.35:
                    discount_pct = random.choice([5, 8, 10, 12, 15, 20])
                    discount_price = int(base_price * (100 - discount_pct) / 100)
                else:
                    discount_price = None

            # Pick matching category
            if ptype == 'electric':
                matched_cats = [c for c in categories if 'electric' in c.slug]
            elif ptype == 'kick':
                matched_cats = [c for c in categories if 'kick' in c.slug or 'wheel' in c.slug or 'stunt' in c.slug]
            elif ptype == 'accessory':
                matched_cats = [c for c in categories if 'accessor' in c.slug or 'gear' in c.slug or 'protect' in c.slug or 'lock' in c.slug]
            else:
                matched_cats = [c for c in categories if 'part' in c.slug or 'batter' in c.slug or 'tire' in c.slug or 'brake' in c.slug]

            category = random.choice(matched_cats if matched_cats else categories)

            # Generate unique slug
            base_slug = slugify(pname_en, allow_unicode=False)
            unique_suffix = uuid.uuid4().hex[:6]
            slug = f"{base_slug}-{unique_suffix}"

            cost_price = int(Decimal(base_price) * Decimal(random.uniform(0.70, 0.82)))
            stock = random.choice([0, 2, 5, 8, 12, 20, 35, 50])
            is_avail = stock > 0
            is_feat = (i % 7 == 0)

            # Rich description
            tagline = f"تجربه سرعت، قدرت و طراحی مینیمال با {pname_en}"
            description = (
                f"<p>{pname_fa} یکی از پرفروش‌ترین محصولات تخصصی نکس‌گو است که با تکیه بر استانداردهای بین‌المللی، "
                f"بدنه مقاوم و قطعات اورجینال طراحی شده است.</p>"
                f"<h3>ویژگی‌های شاخص:</h3>"
                f"<ul>"
                f"<li>کیفیت ساخت بالا با فریم آلیاژی مقاوم در برابر ضربه و رطوبت</li>"
                f"<li>طراحی ارگونومیک و تاشوی آسان جهت حمل و نقل راحت در فضاهای عمومی</li>"
                f"<li>راندمان انرژی بالا و سواری فوق‌العاده نرم با حداقل استهلاک</li>"
                f"<li>سازگار با کلیه قطعات یدکی و لوازم جانبی استاندارد</li>"
                f"</ul>"
                f"<p>این محصول به همراه گارانتی رسمی سلامت و اصالت فیزیکی نکس‌گو و خدمات پس از فروش عرضه می‌گردد.</p>"
            )

            product = Product(
                name=pname_fa,
                slug=slug,
                category=category,
                tagline=tagline,
                description=description,
                price=Decimal(base_price),
                discount_price=Decimal(discount_price) if discount_price else None,
                cost_price=Decimal(cost_price),
                stock=stock,
                is_available=is_avail,
                restock_expected=True,
                is_published=True,
                is_featured=is_feat,
                brand=random.choice(BRANDS),
                mpn=f"MPN-{uuid.uuid4().hex[:8].upper()}",
                meta_title=f"{pname_fa} | قیمت و خرید آنلاین",
                meta_description=f"خرید آنلاین {pname_fa} با ضمانت اصالت کالا و ارسال سریع به سراسر ایران.",
                view_count=random.randint(15, 1200),
            )

            # Generate Pillow solid-color images
            if not no_images:
                cover_content = create_product_cover_image(pname_en, brand=product.brand)
                product.cover_image.save(f"{slug}-cover.webp", cover_content, save=False)

                grid_content = create_product_grid_image(pname_en, brand=product.brand)
                product.grid_image.save(f"{slug}-grid.webp", grid_content, save=False)

            # Save product (computes SKU and intrinsic dimensions)
            product.save()

            # Product Specifications
            specs = get_specs_for_product(category.slug, is_electric=(ptype == 'electric'))
            for order, (s_icon, s_label, s_val) in enumerate(specs, start=1):
                ProductSpec.objects.create(
                    product=product,
                    icon=s_icon,
                    label=s_label,
                    value=s_val,
                    order=order,
                )

            # Trust Badges
            selected_badges = random.sample(TRUST_BADGES, 2)
            for b_order, (b_icon, b_label, b_val) in enumerate(selected_badges, start=1):
                TrustBadge.objects.create(
                    product=product,
                    icon=b_icon,
                    label=b_label,
                    value=b_val,
                    order=b_order,
                )

            # Gallery Color Variations (2 to 3 colors)
            num_variants = random.choice([2, 3])
            chosen_colors = random.sample(PRODUCT_COLORS, num_variants)
            for order, (c_label, c_slug, c_hex) in enumerate(chosen_colors, start=1):
                p_image = ProductImage(
                    product=product,
                    color_label=c_label,
                    color_slug=c_slug,
                    color_hex=c_hex,
                    alt_text=f"{product.name} - رنگ {c_label}",
                    sort_order=order,
                    is_primary=(order == 1),
                )
                if not no_images:
                    gallery_content = create_product_gallery_image(pname_en, c_label, c_hex)
                    p_image.image.save(f"{slug}-{c_slug}.webp", gallery_content, save=False)
                p_image.save()

            created_count += 1
            if created_count % 10 == 0 or created_count == count:
                self.stdout.write(
                    f"  [{created_count}/{count}] Seeded: {pname_en[:45]}... (SKU: {product.sku})"
                )

        total_products = Product.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"[OK] Successfully seeded {created_count} products! (Total in DB: {total_products})"
            )
        )
