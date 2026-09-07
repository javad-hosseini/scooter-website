"""One-off backfill for rows that predate the SEO fields.

``width_field``/``height_field`` are only populated when a file is saved, so
existing images have NULL dimensions and templates would fall back to nominal
sizes. Same for SKUs and image alt text. Run once after migrating:

    python manage.py backfill_seo_data
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.home.models import Article, IndexPageSettings
from apps.shop.models import Product, ProductImage


class Command(BaseCommand):
    help = 'پر کردن ابعاد تصاویر، SKU و متن جایگزین برای رکوردهای قدیمی'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='فقط گزارش بده، چیزی ذخیره نکن',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        stats = {}

        stats['product_images'] = self._fill_dimensions(
            ProductImage.objects.filter(image_width__isnull=True),
            [('image', 'image_width', 'image_height')],
            dry_run,
        )
        stats['product_covers'] = self._fill_dimensions(
            Product.objects.filter(cover_image_width__isnull=True),
            [('cover_image', 'cover_image_width', 'cover_image_height')],
            dry_run,
        )
        stats['articles'] = self._fill_dimensions(
            Article.objects.filter(cover_image_width__isnull=True).exclude(cover_image=''),
            [('cover_image', 'cover_image_width', 'cover_image_height')],
            dry_run,
        )
        stats['index_settings'] = self._fill_dimensions(
            IndexPageSettings.objects.all(),
            [
                ('hero_image', 'hero_image_width', 'hero_image_height'),
                ('hero_mobile_image', 'hero_mobile_image_width', 'hero_mobile_image_height'),
            ],
            dry_run,
        )
        stats['skus'] = self._fill_skus(dry_run)
        stats['alt_text'] = self._fill_alt_text(dry_run)

        for key, count in stats.items():
            self.stdout.write(f'{key}: {count}')
        if dry_run:
            self.stdout.write(self.style.WARNING('dry-run — هیچ تغییری ذخیره نشد'))
        else:
            self.stdout.write(self.style.SUCCESS('انجام شد'))

    def _fill_dimensions(self, queryset, field_specs, dry_run):
        updated = 0
        for obj in queryset.iterator():
            changed = []
            for image_attr, width_attr, height_attr in field_specs:
                image = getattr(obj, image_attr, None)
                if not image or getattr(obj, width_attr):
                    continue
                try:
                    # Touching .width opens the file through Pillow and, because
                    # the field declares width_field/height_field, writes the
                    # values back onto the instance.
                    width, height = image.width, image.height
                except (OSError, ValueError) as exc:
                    self.stderr.write(f'  ! {obj!r}.{image_attr}: {exc}')
                    continue
                setattr(obj, width_attr, width)
                setattr(obj, height_attr, height)
                changed += [width_attr, height_attr]
            if changed and not dry_run:
                obj.save(update_fields=changed)
            if changed:
                updated += 1
        return updated

    def _fill_skus(self, dry_run):
        products = Product.objects.filter(sku='')
        updated = 0
        with transaction.atomic():
            for product in products.iterator():
                if not dry_run:
                    Product.objects.filter(pk=product.pk).update(sku=f'VLX-{product.pk:05d}')
                updated += 1
        return updated

    def _fill_alt_text(self, dry_run):
        updated = 0
        for product in Product.objects.filter(cover_alt_text='').iterator():
            product.cover_alt_text = f'{product.name} — اسکوتر برقی {product.brand or "ولتکس"}'
            if not dry_run:
                product.save(update_fields=['cover_alt_text'])
            updated += 1
        for article in Article.objects.filter(cover_alt_text='').exclude(cover_image='').iterator():
            article.cover_alt_text = article.title[:200]
            if not dry_run:
                article.save(update_fields=['cover_alt_text'])
            updated += 1
        return updated
