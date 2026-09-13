"""
Management command to reset and wipe out mock data (products, articles, categories)
and optionally remove generated mock media files from disk.
Usage:
    python manage.py seed-clear --all --yes
    python manage.py seed-reset --products --clean-media
"""

import os
import shutil
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.shop.models import Category, Product, ProductImage, ProductSpec, TrustBadge
from apps.home.models import Article, Tag, Comment, CategoryImage, CategoryFeature, CategoryBadge


class Command(BaseCommand):
    help = "Wipe and reset mock data (products, articles, categories) and optionally clean media files."

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help="Wipe all mock data: products, articles, categories, tags, and comments.",
        )
        parser.add_argument(
            '--products',
            action='store_true',
            help="Wipe only products, product images, specs, and trust badges.",
        )
        parser.add_argument(
            '--articles',
            action='store_true',
            help="Wipe only articles, article comments, and tags.",
        )
        parser.add_argument(
            '--categories',
            action='store_true',
            help="Wipe categories, category images, and category features (will also delete dependent products).",
        )
        parser.add_argument(
            '--clean-media',
            action='store_true',
            help="Delete generated mock image files from media/ storage.",
        )
        parser.add_argument(
            '--yes', '-y',
            action='store_true',
            help="Skip interactive confirmation prompt.",
        )

    def handle(self, *args, **options):
        wipe_all = options['all']
        wipe_products = options['products']
        wipe_articles = options['articles']
        wipe_categories = options['categories']
        clean_media = options['clean_media']
        skip_confirm = options['yes']

        # Default to wiping all if none explicitly specified
        if not (wipe_products or wipe_articles or wipe_categories):
            wipe_all = True

        targets = []
        if wipe_all or wipe_products or wipe_categories:
            targets.append("Products & related records")
        if wipe_all or wipe_articles:
            targets.append("Articles & related tags/comments")
        if wipe_all or wipe_categories:
            targets.append("Categories & related category badges/features")
        if clean_media:
            targets.append("Mock media files in media directory")

        self.stdout.write(self.style.WARNING("=" * 60))
        self.stdout.write(self.style.WARNING("MOCK DATA RESET & WIPE OPERATION"))
        self.stdout.write(self.style.WARNING("=" * 60))
        self.stdout.write(f"The following items will be wiped:\n  - " + "\n  - ".join(targets))

        if not skip_confirm:
            confirm = input("\nAre you sure you want to proceed? [y/N]: ").strip().lower()
            if confirm not in ('y', 'yes'):
                self.stdout.write(self.style.NOTICE("Operation cancelled by user."))
                return

        with transaction.atomic():
            # 1. Wipe Products
            if wipe_all or wipe_products or wipe_categories:
                p_count = Product.objects.count()
                img_count = ProductImage.objects.count()
                spec_count = ProductSpec.objects.count()
                badge_count = TrustBadge.objects.count()

                ProductImage.objects.all().delete()
                ProductSpec.objects.all().delete()
                TrustBadge.objects.all().delete()
                Product.objects.all().delete()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"[OK] Deleted {p_count} products, {img_count} gallery images, {spec_count} specs, {badge_count} badges."
                    )
                )

            # 2. Wipe Articles
            if wipe_all or wipe_articles:
                a_count = Article.objects.count()
                c_count = Comment.objects.count()
                t_count = Tag.objects.count()

                Comment.objects.all().delete()
                Article.objects.all().delete()
                Tag.objects.all().delete()

                self.stdout.write(
                    self.style.SUCCESS(f"[OK] Deleted {a_count} articles, {c_count} comments, {t_count} tags.")
                )

            # 3. Wipe Categories
            if wipe_all or wipe_categories:
                cat_count = Category.objects.count()
                cat_img_count = CategoryImage.objects.count()
                cat_feat_count = CategoryFeature.objects.count()
                cat_badge_count = CategoryBadge.objects.count()

                CategoryImage.objects.all().delete()
                CategoryFeature.objects.all().delete()
                CategoryBadge.objects.all().delete()
                Category.objects.all().delete()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"[OK] Deleted {cat_count} categories, {cat_img_count} images, {cat_feat_count} features, {cat_badge_count} badges."
                    )
                )

        # 4. Clean Media files from disk if requested
        if clean_media:
            media_root = getattr(settings, 'MEDIA_ROOT', None)
            if media_root and os.path.isdir(media_root):
                dirs_to_clean = [
                    os.path.join(media_root, 'products', 'covers'),
                    os.path.join(media_root, 'products', 'grid'),
                    os.path.join(media_root, 'products', 'gallery'),
                    os.path.join(media_root, 'home', 'articles'),
                    os.path.join(media_root, 'categories'),
                ]
                removed_files = 0
                for folder in dirs_to_clean:
                    if os.path.isdir(folder):
                        for root, _, files in os.walk(folder):
                            for f in files:
                                try:
                                    os.remove(os.path.join(root, f))
                                    removed_files += 1
                                except OSError:
                                    pass
                self.stdout.write(
                    self.style.SUCCESS(f"[OK] Cleaned {removed_files} mock image files from media directories.")
                )

        self.stdout.write(self.style.SUCCESS("\n[OK] Reset complete! Database is clean."))
