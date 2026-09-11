"""robots.txt, error pages, and the About / Contact static pages."""

from django.conf import settings
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView

from . import schema
from .seo import SEOMixin
from .utils import absolute_url


@require_GET
@cache_control(max_age=60 * 60 * 24, public=True)
def robots_txt(request):
    return render(
        request,
        'seo/robots.txt',
        {'sitemap_url': absolute_url(reverse('sitemap-index'), request)},
        content_type='text/plain; charset=utf-8',
    )


class AboutPageView(SEOMixin, TemplateView):
    template_name = 'seo/about.html'
    seo_title = 'درباره نکس گو'
    seo_description = (
        'نکس گو تولیدکننده و فروشنده اسکوتر برقی پریمیوم است؛ با گارانتی ۳ ساله، '
        'خدمات پس از فروش سراسری و شوروم حضوری در تهران.'
    )

    #: Mirrors the questions rendered in seo/about.html. They must stay in
    #: sync — FAQPage markup that does not match visible page content is a
    #: structured-data policy violation, not just a mismatch.
    FAQ = [
        (
            'گارانتی اسکوترهای نکس گو چقدر است؟',
            'همه اسکوترهای نکس گو با گارانتی سه‌ساله موتور، کنترلر و باتری عرضه '
            'می‌شوند. قطعات مصرفی مانند لاستیک و لنت ترمز شامل گارانتی نیستند.',
        ),
        (
            'ارسال چقدر طول می‌کشد؟',
            'سفارش‌های ثبت‌شده در روزهای کاری معمولاً ظرف ۲۴ تا ۷۲ ساعت ارسال '
            'می‌شوند؛ زمان دقیق بسته به شهر مقصد متفاوت است.',
        ),
        (
            'آیا امکان تست حضوری اسکوتر وجود دارد؟',
            'بله. در شوروم نکس گو می‌توانید مدل‌های موجود را از نزدیک ببینید و '
            'پیش از خرید تست کنید.',
        ),
        (
            'باتری اسکوتر برقی چند سال عمر می‌کند؟',
            'با شارژ اصولی، باتری‌های لیتیوم‌یونی معمولاً بین ۵۰۰ تا ۸۰۰ چرخه '
            'شارژ کامل ظرفیت مفید خود را حفظ می‌کنند؛ یعنی حدود دو تا سه سال '
            'استفاده روزانه.',
        ),
    ]

    def get_breadcrumbs(self, context):
        return [('خانه', '/'), ('درباره ما', reverse('seo:about'))]

    def get_json_ld(self, context, seo):
        return [
            schema.organization(self.request),
            schema.faq(self.FAQ),
            schema.breadcrumbs(seo.breadcrumbs, self.request),
        ]


class ContactPageView(SEOMixin, TemplateView):
    """Contact page — carries the physical showroom's Store schema."""

    template_name = 'seo/contact.html'
    seo_title = 'تماس با نکس گو'
    seo_description = (
        'شماره تماس، ایمیل، ساعات کاری و آدرس شوروم نکس گو. برای مشاوره خرید '
        'اسکوتر برقی و خدمات پس از فروش با ما در ارتباط باشید.'
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['store'] = settings.SEO_STORE
        context['organization'] = settings.SEO_ORGANIZATION
        return context

    def get_breadcrumbs(self, context):
        return [('خانه', '/'), ('تماس با ما', reverse('seo:contact'))]

    def get_json_ld(self, context, seo):
        return [
            schema.store(self.request),
            schema.breadcrumbs(seo.breadcrumbs, self.request),
        ]


def page_not_found(request, exception=None):
    """Custom 404 that still returns a real 404 status and offers a way onward."""
    from apps.shop.models import Category

    context = {
        'categories': Category.objects.filter(is_active=True, parent__isnull=True)[:8],
        'seo': _error_seo(request, 'صفحه پیدا نشد'),
    }
    return render(request, '404.html', context, status=404)


def server_error(request):
    return render(request, '500.html', {'seo': _error_seo(request, 'خطای سرور')}, status=500)


def _error_seo(request, title):
    from .seo import PageSEO

    try:
        image_url = absolute_url(static(settings.SEO_DEFAULT_IMAGE), request)
    except Exception:
        image_url = ''

    return PageSEO(
        title=f'{title} | {settings.SITE_NAME}',
        description='',
        canonical='',
        # Error pages must never be indexed, even if something links to them.
        robots='noindex, nofollow',
        image=image_url,
    )
