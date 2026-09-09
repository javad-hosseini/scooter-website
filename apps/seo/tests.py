"""End-to-end checks for the SEO surface.

These assert the things a crawler actually sees in the *initial HTML response* —
no JavaScript — because that is precisely what regressed before: the metadata
existed, but only after hydration.
"""

import json
import re

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.home.models import Article
from apps.shop.models import Category, Product

JSON_LD_RE = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.S
)


def json_ld_blocks(html):
    return [json.loads(m) for m in JSON_LD_RE.findall(html)]


def types_in(html):
    return {block.get('@type') for block in json_ld_blocks(html)}


@override_settings(SITE_URL='https://nexgo.test')
class SEOPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username='writer',
            password='pw-for-tests-only',
            fullname='نویسنده تست',
            mobile='09120000000',
            email='writer@example.test',
        )
        cls.category = Category.objects.create(name='اسکوتر شهری', slug='city-scooter')
        cls.product = Product.objects.create(
            name='NexGo X100',
            slug='nexgo-x100',
            category=cls.category,
            description='اسکوتر برقی شهری با برد ۶۰ کیلومتر و شارژ سریع.',
            price=48000000,
            stock=5,
        )
        cls.article = Article.objects.create(
            title='راهنمای خرید اسکوتر برقی',
            slug='buying-guide',
            author=cls.user,
            description='<p>چطور اسکوتر برقی مناسب انتخاب کنیم.</p>',
        )

    # ---- product ----

    def test_product_page_ships_metadata_without_javascript(self):
        html = self.client.get(self.product.get_absolute_url()).content.decode()

        self.assertIn('<title id="page-title">NexGo X100 | NeX Go</title>', html)
        self.assertIn(
            '<link rel="canonical" id="meta-canonical" '
            'href="https://nexgo.test/shop/product/nexgo-x100/" />',
            html,
        )
        self.assertIn('اسکوتر برقی شهری', html)  # description, not an empty tag
        self.assertIn('<h1 class="hero-title" id="product-name">NexGo X100</h1>', html)

    def test_product_page_emits_product_and_breadcrumb_schema(self):
        html = self.client.get(self.product.get_absolute_url()).content.decode()
        self.assertEqual(types_in(html), {'Product', 'BreadcrumbList'})

        product_ld = next(b for b in json_ld_blocks(html) if b['@type'] == 'Product')
        self.assertEqual(product_ld['offers']['price'], '48000000')
        self.assertEqual(product_ld['offers']['priceCurrency'], 'IRR')
        self.assertEqual(
            product_ld['offers']['availability'], 'https://schema.org/InStock'
        )
        self.assertEqual(product_ld['sku'], f'NXG-{self.product.pk:05d}')

    def test_aggregate_rating_omitted_when_there_are_no_reviews(self):
        """Never claim a rating the site cannot show — it is a policy violation."""
        html = self.client.get(self.product.get_absolute_url()).content.decode()
        product_ld = next(b for b in json_ld_blocks(html) if b['@type'] == 'Product')
        self.assertNotIn('aggregateRating', product_ld)

    def test_out_of_stock_product_stays_indexable_and_links_onward(self):
        self.product.stock = 0
        self.product.is_available = False
        self.product.save()
        html = self.client.get(self.product.get_absolute_url()).content.decode()

        self.assertIn('content="index, follow"', html)
        product_ld = next(b for b in json_ld_blocks(html) if b['@type'] == 'Product')
        self.assertEqual(
            product_ld['offers']['availability'], 'https://schema.org/OutOfStock'
        )

    def test_discontinued_product_301s_to_its_replacement(self):
        replacement = Product.objects.create(
            name='NexGo X200', slug='nexgo-x200', category=self.category,
            description='نسل بعدی', price=52000000, stock=3,
        )
        self.product.is_discontinued = True
        self.product.replacement_product = replacement
        self.product.save()
        response = self.client.get(self.product.get_absolute_url())
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], replacement.get_absolute_url())

    def test_discontinued_product_without_replacement_301s_to_its_category(self):
        self.product.is_discontinued = True
        self.product.save()
        response = self.client.get(self.product.get_absolute_url())
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], self.category.get_absolute_url())

    # ---- category / listing ----

    def test_category_page_links_to_its_products_in_the_html(self):
        html = self.client.get(self.category.get_absolute_url()).content.decode()
        self.assertIn(f'href="{self.product.get_absolute_url()}"', html)
        self.assertIn('<h1 class="page-h1">اسکوتر شهری</h1>', html)
        self.assertIn('ItemList', types_in(html))

    def test_faceted_urls_are_noindex_and_canonicalise_to_the_clean_url(self):
        url = self.category.get_absolute_url()
        html = self.client.get(url, {'sort': 'price', 'color': 'blue'}).content.decode()

        self.assertIn('content="noindex, follow"', html)
        self.assertIn(f'href="https://nexgo.test{url}"', html)

    def test_clean_category_url_is_indexable(self):
        html = self.client.get(self.category.get_absolute_url()).content.decode()
        self.assertIn('content="index, follow"', html)

    def test_paginated_page_self_canonicalises_and_gets_its_own_title(self):
        for i in range(30):
            Product.objects.create(
                name=f'NexGo M{i}', slug=f'nexgo-m{i}', category=self.category,
                description='مدل آزمایشی', price=10000000 + i, stock=1,
            )
        url = self.category.get_absolute_url()
        html = self.client.get(url, {'page': 2}).content.decode()

        self.assertIn(f'href="https://nexgo.test{url}?page=2"', html)
        self.assertIn('صفحه 2', html)
        self.assertIn(f'<link rel="prev" href="https://nexgo.test{url}" />', html)

    # ---- articles ----

    def test_article_body_is_in_the_html_and_carries_blogposting_schema(self):
        html = self.client.get(self.article.get_absolute_url()).content.decode()

        self.assertIn('چطور اسکوتر برقی مناسب انتخاب کنیم', html)
        self.assertIn('BlogPosting', types_in(html))
        self.assertIn(
            f'href="https://nexgo.test{self.article.get_absolute_url()}"', html
        )

    def test_syndicated_article_points_its_canonical_at_the_original(self):
        self.article.canonical_url = 'https://example.org/original/'
        self.article.save()
        html = self.client.get(self.article.get_absolute_url()).content.decode()
        self.assertIn('href="https://example.org/original/"', html)

    def test_tag_filtered_article_list_is_noindex(self):
        html = self.client.get(
            reverse('home_app:articles'), {'tag': 'battery'}
        ).content.decode()
        self.assertIn('content="noindex, follow"', html)

    # ---- home ----

    def test_home_page_has_one_h1_and_organization_schema(self):
        html = self.client.get('/').content.decode()

        self.assertEqual(len(re.findall(r'<h1[ >]', html)), 1)
        self.assertEqual(types_in(html), {'Organization', 'WebSite'})

    def test_home_page_links_to_products_and_articles(self):
        """The nav used to be all href="#", leaving the home page a dead end."""
        html = self.client.get('/').content.decode()
        self.assertIn(f'href="{self.category.get_absolute_url()}"', html)
        self.assertIn(f'href="{reverse("home_app:articles")}"', html)

    # ---- crawling & indexation ----

    def test_robots_txt_disallows_facets_and_advertises_the_sitemap(self):
        response = self.client.get('/robots.txt')
        body = response.content.decode()

        self.assertEqual(response['Content-Type'], 'text/plain; charset=utf-8')
        self.assertIn('Disallow: /admin/', body)
        self.assertIn('Disallow: /*?*sort=', body)
        self.assertIn('Sitemap: https://nexgo.test/sitemap.xml', body)

    def test_sitemap_index_lists_every_section(self):
        body = self.client.get('/sitemap.xml').content.decode()
        for section in ('static', 'categories', 'products', 'articles'):
            self.assertIn(f'/sitemap-{section}.xml', body)

    def test_product_sitemap_contains_the_product_with_a_lastmod(self):
        body = self.client.get('/sitemap-products.xml').content.decode()
        self.assertIn(self.product.get_absolute_url(), body)
        self.assertIn('<lastmod>', body)

    def test_discontinued_products_are_dropped_from_the_sitemap(self):
        self.product.is_discontinued = True
        self.product.save()
        body = self.client.get('/sitemap-products.xml').content.decode()
        self.assertNotIn(self.product.get_absolute_url(), body)

    def test_legacy_paths_301_instead_of_404ing(self):
        for source, target in [
            ('/products/', '/shop/'),
            ('/blog/', '/articles/'),
            ('/register/', '/accounts/register/'),
            (f'/product/{self.product.slug}/', self.product.get_absolute_url()),
        ]:
            with self.subTest(source=source):
                response = self.client.get(source)
                self.assertEqual(response.status_code, 301)
                self.assertEqual(response['Location'], target)

    def test_legacy_shop_slug_301s_onto_the_product_url(self):
        response = self.client.get(f'/shop/{self.product.slug}/')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], self.product.get_absolute_url())

    def test_mixed_case_urls_301_to_lowercase(self):
        response = self.client.get('/shop/product/NexGo-X100/')
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response['Location'].endswith('/shop/product/nexgo-x100/'))

    def test_missing_page_returns_a_real_404_with_navigation(self):
        response = self.client.get('/shop/product/does-not-exist/')
        self.assertEqual(response.status_code, 404)
        html = response.content.decode()
        self.assertIn('noindex', html)
        self.assertIn(reverse('shop:product_list'), html)

    def test_json_endpoints_are_crawlable_but_not_indexable(self):
        response = self.client.get('/shop/api/products/')
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')

    def test_html_pages_are_cacheable_for_anonymous_visitors(self):
        response = self.client.get(self.product.get_absolute_url())
        self.assertIn('s-maxage', response['Cache-Control'])

    def test_signed_in_pages_are_never_stored_in_a_shared_cache(self):
        self.client.force_login(self.user)
        response = self.client.get(self.product.get_absolute_url())
        self.assertIn('private', response['Cache-Control'])

    # ---- static pages ----

    def test_contact_page_carries_store_schema(self):
        html = self.client.get(reverse('seo:contact')).content.decode()
        self.assertIn('Store', types_in(html))

    def test_about_page_faq_schema_matches_the_visible_questions(self):
        html = self.client.get(reverse('seo:about')).content.decode()
        faq = next(b for b in json_ld_blocks(html) if b['@type'] == 'FAQPage')
        for entry in faq['mainEntity']:
            self.assertIn(entry['name'], html)


@override_settings(SITE_URL='https://nexgo.test')
class MetaTextTests(TestCase):
    def test_titles_stay_within_the_serp_display_limit(self):
        from apps.seo.utils import meta_title

        title = meta_title('ا' * 200)
        self.assertLessEqual(len(title), 60)
        self.assertTrue(title.endswith('| NeX Go'))

    def test_descriptions_are_stripped_of_markup_and_truncated(self):
        from apps.seo.utils import meta_description

        text = meta_description('<p>سلام <b>دنیا</b></p>' + 'ب' * 400)
        self.assertNotIn('<', text)
        self.assertLessEqual(len(text), 158)

    def test_json_ld_filter_escapes_script_terminators(self):
        from apps.seo.templatetags.seo_tags import json_ld

        rendered = json_ld({'name': '</script><script>alert(1)</script>'})
        self.assertNotIn('</script>', rendered)
