"""Schema.org JSON-LD builders.

These are built server-side rather than in JavaScript: Google will execute JS
before indexing, but rendering is queued and best-effort, so structured data
injected after load is routinely missed. Everything here ships in the initial
HTML response.
"""

from django.conf import settings
from django.templatetags.static import static
from django.urls import reverse

from .utils import absolute_url, clean_text, image_url, meta_description

#: Prices are stored and displayed in Iranian Toman; schema.org needs an
#: ISO 4217 code, and IRR is the only registered Iranian currency.
CURRENCY = 'IRR'


def _org_id(request):
    return f'{absolute_url("/", request)}#organization'


def organization(request):
    org = settings.SEO_ORGANIZATION
    data = {
        '@context': 'https://schema.org',
        '@type': 'Organization',
        '@id': _org_id(request),
        'name': org['name'],
        'url': absolute_url('/', request),
        'logo': {
            '@type': 'ImageObject',
            'url': absolute_url(static(org['logo']), request),
        },
    }
    if org.get('legal_name'):
        data['legalName'] = org['legal_name']
    if org.get('founding_date'):
        data['foundingDate'] = org['founding_date']

    contact = {}
    if org.get('telephone'):
        contact['telephone'] = org['telephone']
    if org.get('email'):
        contact['email'] = org['email']
    if contact:
        contact.update({'@type': 'ContactPoint', 'contactType': 'customer support',
                        'areaServed': 'IR', 'availableLanguage': ['fa', 'en']})
        data['contactPoint'] = [contact]

    profiles = [p for p in org.get('social_profiles', []) if p]
    if profiles:
        data['sameAs'] = profiles
    return data


def website(request):
    """WebSite node. ``potentialAction`` is omitted deliberately.

    Declaring a SearchAction that points at a URL template the site does not
    actually serve is worse than declaring none, and the sitewide search is
    intentionally kept out of the index.
    """
    return {
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        '@id': f'{absolute_url("/", request)}#website',
        'name': settings.SITE_NAME,
        'url': absolute_url('/', request),
        'inLanguage': 'fa-IR',
        'publisher': {'@id': _org_id(request)},
    }


def store(request):
    """Store / LocalBusiness node for the physical showroom."""
    cfg = settings.SEO_STORE
    org = settings.SEO_ORGANIZATION
    data = {
        '@context': 'https://schema.org',
        '@type': 'Store',
        '@id': f'{absolute_url(reverse("seo:contact"), request)}#store',
        'name': cfg['name'],
        'url': absolute_url(reverse('seo:contact'), request),
        'image': absolute_url(static(org['logo']), request),
        'parentOrganization': {'@id': _org_id(request)},
        'priceRange': cfg['price_range'],
        'currenciesAccepted': CURRENCY,
        'openingHours': cfg['opening_hours'],
    }
    if org.get('telephone'):
        data['telephone'] = org['telephone']
    if org.get('email'):
        data['email'] = org['email']

    address = {'@type': 'PostalAddress', 'addressCountry': cfg['country']}
    if cfg.get('street_address'):
        address['streetAddress'] = cfg['street_address']
    if cfg.get('locality'):
        address['addressLocality'] = cfg['locality']
    if cfg.get('region'):
        address['addressRegion'] = cfg['region']
    if cfg.get('postal_code'):
        address['postalCode'] = cfg['postal_code']
    data['address'] = address

    if cfg.get('latitude') and cfg.get('longitude'):
        data['geo'] = {
            '@type': 'GeoCoordinates',
            'latitude': cfg['latitude'],
            'longitude': cfg['longitude'],
        }
    return data


def breadcrumbs(trail, request):
    """BreadcrumbList from ``[(label, path), ...]``.

    A single-item trail (the home page itself) is skipped: Google ignores
    one-element breadcrumbs and emitting them only adds noise.
    """
    if not trail or len(trail) < 2:
        return None
    items = []
    for position, (name, path) in enumerate(trail, start=1):
        item = {
            '@type': 'ListItem',
            'position': position,
            'name': clean_text(name),
        }
        if path:
            item['item'] = absolute_url(path, request)
        items.append(item)
    return {
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        'itemListElement': items,
    }


def product(obj, request, reviews=None):
    """Product node including offer, brand, SKU and — when present — ratings."""
    url = absolute_url(obj.get_absolute_url(), request)
    images = [image_url(obj.cover_image, request)]
    for extra in getattr(obj, 'gallery_images', []):
        img = image_url(extra.image, request)
        if img and img not in images:
            images.append(img)

    availability = 'https://schema.org/InStock'
    if obj.is_discontinued:
        availability = 'https://schema.org/Discontinued'
    elif not obj.is_available or obj.stock <= 0:
        availability = 'https://schema.org/OutOfStock'

    data = {
        '@context': 'https://schema.org',
        '@type': 'Product',
        '@id': f'{url}#product',
        'name': obj.name,
        'description': meta_description(obj.meta_description, obj.description, length=500),
        'image': [i for i in images if i],
        'sku': obj.sku or f'NXG-{obj.pk}',
        'brand': {'@type': 'Brand', 'name': obj.brand or settings.SITE_NAME},
        'category': obj.category.name if obj.category_id else '',
        'url': url,
        'offers': {
            '@type': 'Offer',
            '@id': f'{url}#offer',
            'url': url,
            'price': str(obj.final_price),
            'priceCurrency': CURRENCY,
            'availability': availability,
            'itemCondition': 'https://schema.org/NewCondition',
            'seller': {'@id': _org_id(request)},
        },
    }
    if obj.mpn:
        data['mpn'] = obj.mpn

    # Only emit AggregateRating when real approved reviews back it up —
    # inventing one is a structured-data policy violation.
    rating_count = getattr(obj, 'approved_review_count', None)
    if rating_count is None:
        rating_count = obj.reviews_count
    if rating_count:
        average = getattr(obj, 'approved_review_average', None) or obj.average_rating
        if average:
            data['aggregateRating'] = {
                '@type': 'AggregateRating',
                'ratingValue': str(average),
                'reviewCount': rating_count,
                'bestRating': '5',
                'worstRating': '1',
            }

    if reviews:
        data['review'] = [
            {
                '@type': 'Review',
                'author': {'@type': 'Person', 'name': r.user.fullname or 'کاربر'},
                'datePublished': r.created_at.date().isoformat(),
                'name': r.title or f'نظر درباره {obj.name}',
                'reviewBody': clean_text(r.comment),
                'reviewRating': {
                    '@type': 'Rating',
                    'ratingValue': str(r.rating),
                    'bestRating': '5',
                    'worstRating': '1',
                },
            }
            for r in reviews
        ]
    return data


def item_list(products, request, name=''):
    """ItemList for a category / listing page, in the order shown to users."""
    if not products:
        return None
    return {
        '@context': 'https://schema.org',
        '@type': 'ItemList',
        'name': name or 'محصولات',
        'numberOfItems': len(products),
        'itemListElement': [
            {
                '@type': 'ListItem',
                'position': position,
                'url': absolute_url(p.get_absolute_url(), request),
                'name': p.name,
            }
            for position, p in enumerate(products, start=1)
        ],
    }


def article(obj, request):
    url = absolute_url(obj.get_absolute_url(), request)
    data = {
        '@context': 'https://schema.org',
        '@type': 'BlogPosting',
        '@id': f'{url}#article',
        'headline': clean_text(obj.title)[:110],
        'description': meta_description(obj.meta_description, obj.excerpt, obj.description),
        'mainEntityOfPage': {'@type': 'WebPage', '@id': obj.canonical_url or url},
        'url': url,
        'inLanguage': 'fa-IR',
        'author': {
            '@type': 'Person',
            'name': getattr(obj.author, 'fullname', '') or getattr(obj.author, 'username', ''),
        },
        'publisher': {'@id': _org_id(request)},
        'datePublished': (obj.published_at or obj.created_at).isoformat(),
        'dateModified': obj.updated_at.isoformat(),
    }
    cover = image_url(obj.cover_image, request)
    if cover:
        data['image'] = [cover]
    if obj.time_to_read:
        data['timeRequired'] = f'PT{obj.time_to_read}M'
    keywords = [t.name for t in obj.tags.all()]
    if keywords:
        data['keywords'] = keywords
    return data


def faq(entries):
    """FAQPage from ``[(question, answer), ...]``."""
    entries = [(q, a) for q, a in entries if q and a]
    if not entries:
        return None
    return {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        'mainEntity': [
            {
                '@type': 'Question',
                'name': clean_text(q),
                'acceptedAnswer': {'@type': 'Answer', 'text': clean_text(a)},
            }
            for q, a in entries
        ],
    }
