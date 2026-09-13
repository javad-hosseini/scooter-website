"""
Management command to seed everything (categories, products, and articles) in sequence.
Usage:
    python manage.py seed-all --count-products 50 --count-articles 20
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run category, product, and article seeders in sequence."

    def add_arguments(self, parser):
        parser.add_argument(
            '--count-categories',
            type=int,
            default=0,
            help="Total number of categories to ensure (default: full catalog).",
        )
        parser.add_argument(
            '--count-products',
            type=int,
            default=30,
            help="Number of products to generate (default: 30).",
        )
        parser.add_argument(
            '--count-articles',
            type=int,
            default=15,
            help="Number of articles to generate (default: 15).",
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help="Clear all existing mock data before seeding.",
        )
        parser.add_argument(
            '--no-images',
            action='store_true',
            help="Skip image generation for all seeders.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("==========================================="))
        self.stdout.write(self.style.MIGRATE_HEADING("      SCOOTER WEBSITE FULL DATA SEEDER     "))
        self.stdout.write(self.style.MIGRATE_HEADING("==========================================="))

        if options['clear']:
            call_command('seed_clear', all=True, yes=True)

        # 1. Seed Categories
        call_command(
            'seed_category',
            count=options['count_categories'],
            no_images=options['no_images'],
        )

        # 2. Seed Products
        call_command(
            'seed_product',
            count=options['count_products'],
            no_images=options['no_images'],
        )

        # 3. Seed Articles
        call_command(
            'seed_article',
            count=options['count_articles'],
            no_images=options['no_images'],
        )

        self.stdout.write(self.style.SUCCESS("\n==========================================="))
        self.stdout.write(self.style.SUCCESS("✓ ALL MOCK DATA SEEDED SUCCESSFULLY!"))
        self.stdout.write(self.style.SUCCESS("==========================================="))
