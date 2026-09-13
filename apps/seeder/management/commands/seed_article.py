"""
Management command to seed realistic Scooter Articles and Guides with Pillow-generated cover images.
Usage:
    python manage.py seed-article --count 20
    python manage.py seed_article --count 50 --clear
"""

import random
import uuid
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify
from faker import Faker

from apps.home.models import Article, Tag
from apps.seeder.data_catalog import ARTICLE_TEMPLATES
from apps.seeder.image_factory import create_article_cover_image

fake = Faker('fa_IR')
fake_en = Faker('en_US')
User = get_user_model()


class Command(BaseCommand):
    help = "Seed realistic scooter articles, blog posts, tags, and Pillow-generated cover images."

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=20,
            help="Number of articles to generate (default: 20).",
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help="Delete all existing articles and related tags/comments before seeding.",
        )
        parser.add_argument(
            '--no-images',
            action='store_true',
            help="Skip cover image generation.",
        )

    def handle(self, *args, **options):
        count = options['count']
        clear_existing = options['clear']
        no_images = options['no_images']

        self.stdout.write(self.style.MIGRATE_HEADING(f">>> Seeding {count} Scooter Articles..."))

        if clear_existing:
            self.stdout.write(self.style.WARNING("Clearing existing articles..."))
            Article.objects.all().delete()
            Tag.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("All articles and tags cleared."))

        # Get or create author
        author = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if not author:
            author = User.objects.create_user(
                username='scooter_editor',
                email='editor@nexgo.ir',
                fullname='سردبیر مجله نکس‌گو',
                is_staff=True,
            )
            self.stdout.write(self.style.NOTICE("Created default author user: scooter_editor"))

        # Base tags
        common_tag_names = [
            "راهنمای خرید", "اسکوتر برقی", "اسکوتر مکانیکی", "باتری لیتیومی",
            "نگهداری و تعمیرات", "تجهیزات ایمنی", "بررسی تخصصی", "تردد شهری",
            "لاستیک و پنچری", "سیستم ترمز", "بدلکاری و Stunt", "سفر با اسکوتر"
        ]
        tag_objects = []
        for t_name in common_tag_names:
            tag, _ = Tag.objects.get_or_create(
                name=t_name,
                defaults={'slug': slugify(t_name, allow_unicode=True)}
            )
            tag_objects.append(tag)

        created_count = 0
        now = timezone.now()

        for i in range(count):
            if i < len(ARTICLE_TEMPLATES):
                tmpl = ARTICLE_TEMPLATES[i]
                title = tmpl["title"]
                category_tag = tmpl["category_tag"]
                excerpt = tmpl["excerpt"]
                content_html = tmpl["html"]
                tag_names = tmpl["tags"]
            else:
                eng_subject = fake_en.catch_phrase()
                fa_topics = [
                    f"راهنمای کامل نگهداری و عیب‌یابی مدل‌های {fake_en.word().upper()}",
                    f"بررسی عملکرد و تست پیمایش اسکوترهای سرعت بالای سری {fake_en.word().upper()}",
                    f"۵ ترفند ضروری برای افزایش ایمنی راکبان در ترافیک شبانه شهر",
                    f"مقایسه جامع چرخ‌های توپر هانی‌کامب و لاستیک‌های بادی اسکوتر",
                    f"چگونه شارژر مناسب اسکوتر برقی خود را انتخاب کنیم؟",
                    f"تاثیر وزن راکب بر سرعت و مسافت پیمایش اسکوترهای تک‌موتوره",
                ]
                title = random.choice(fa_topics)
                category_tag = random.choice(["GUIDE", "MAINTENANCE", "REVIEWS", "COMMUTE", "SAFETY"])
                excerpt = (
                    f"در این مقاله تخصصی به بررسی جامع {title} پرداخته‌ایم تا بتوانید "
                    f"با شناخت بهتر قطعات و نکات نگهداری، بهترین بازدهی را از اسکوتر خود دریافت کنید."
                )
                content_html = (
                    f"<p>{excerpt}</p>"
                    f"<h2>نکات فنی و کاربردی</h2>"
                    f"<p>بر اساس بررسی‌های تخصصی تیم فنی نکس‌گو، توجه به سرویس‌های دوره‌ای شامل بررسی فشار باد لاستیک‌ها، "
                    f"آچارکشی پیچ‌های فرمان و اتصالات تاشو، و روان‌کاری سیستم تعلیق می‌تواند از بروز هزینه‌های سنگین جلوگیری کند.</p>"
                    f"<h3>توصیه‌های مهم:</h3>"
                    f"<ul>"
                    f"<li>هرگز اسکوتر را با واترجت یا فشار مستقیم آب شستشو ندهید.</li>"
                    f"<li>سنسورهای ترمز و لنت‌ها را هر ۵۰۰ کیلومتر پیمایش بررسی نمایید.</li>"
                    f"<li>همواره از کلاه ایمنی استاندارد و لباس‌های دارای شب‌رنگ استفاده فرمایید.</li>"
                    f"</ul>"
                )
                tag_names = random.sample(common_tag_names, 3)

            # Unique slug
            base_slug = slugify(f"article-{uuid.uuid4().hex[:8]}-{i}", allow_unicode=True)

            published_date = now - timedelta(days=random.randint(1, 180), hours=random.randint(1, 23))

            article = Article(
                title=title,
                slug=base_slug,
                author=author,
                description=content_html,
                excerpt=excerpt[:290],
                meta_description=excerpt[:155],
                meta_keywords=", ".join(tag_names),
                is_published=True,
                published_at=published_date,
                view_count=random.randint(45, 3800),
            )

            # Pillow 1200x630 cover image
            if not no_images:
                cover_file = create_article_cover_image(
                    title=f"SCOOTER INSIGHT #{i + 1}: {category_tag}",
                    category_tag=category_tag,
                )
                article.cover_image.save(f"article-{base_slug}.webp", cover_file, save=False)

            article.save()

            # Attach tags
            matched_tags = [t for t in tag_objects if t.name in tag_names]
            if not matched_tags:
                matched_tags = random.sample(tag_objects, min(3, len(tag_objects)))
            article.tags.set(matched_tags)

            created_count += 1
            if created_count % 10 == 0 or created_count == count:
                self.stdout.write(f"  [{created_count}/{count}] Seeded Article: [{category_tag}] {article.slug[:40]}...")

        total_articles = Article.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"[OK] Successfully seeded {created_count} articles! (Total in DB: {total_articles})"
            )
        )
