import os
import urllib.request

ASSETS = [
    # Bootstrap
    (
        "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.rtl.min.css",
        "static/vendor/bootstrap/css/bootstrap.rtl.min.css",
    ),
    (
        "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js",
        "static/vendor/bootstrap/js/bootstrap.bundle.min.js",
    ),
    # Bootstrap Icons
    (
        "https://cdnjs.cloudflare.com/ajax/libs/bootstrap-icons/1.11.3/font/bootstrap-icons.min.css",
        "static/vendor/bootstrap-icons/font/bootstrap-icons.min.css",
    ),
    (
        "https://cdnjs.cloudflare.com/ajax/libs/bootstrap-icons/1.11.3/font/fonts/bootstrap-icons.woff2",
        "static/vendor/bootstrap-icons/font/fonts/bootstrap-icons.woff2",
    ),
    (
        "https://cdnjs.cloudflare.com/ajax/libs/bootstrap-icons/1.11.3/font/fonts/bootstrap-icons.woff",
        "static/vendor/bootstrap-icons/font/fonts/bootstrap-icons.woff",
    ),
    # Font Awesome 6.5.1
    (
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css",
        "static/vendor/font-awesome/css/all.min.css",
    ),
    (
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/webfonts/fa-solid-900.woff2",
        "static/vendor/font-awesome/webfonts/fa-solid-900.woff2",
    ),
    (
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/webfonts/fa-solid-900.ttf",
        "static/vendor/font-awesome/webfonts/fa-solid-900.ttf",
    ),
    (
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/webfonts/fa-regular-400.woff2",
        "static/vendor/font-awesome/webfonts/fa-regular-400.woff2",
    ),
    (
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/webfonts/fa-regular-400.ttf",
        "static/vendor/font-awesome/webfonts/fa-regular-400.ttf",
    ),
    (
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/webfonts/fa-brands-400.woff2",
        "static/vendor/font-awesome/webfonts/fa-brands-400.woff2",
    ),
    (
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/webfonts/fa-brands-400.ttf",
        "static/vendor/font-awesome/webfonts/fa-brands-400.ttf",
    ),
    (
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/webfonts/fa-v4compat.woff2",
        "static/vendor/font-awesome/webfonts/fa-v4compat.woff2",
    ),
    (
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/webfonts/fa-v4compat.ttf",
        "static/vendor/font-awesome/webfonts/fa-v4compat.ttf",
    ),
    # ApexCharts
    (
        "https://cdn.jsdelivr.net/npm/apexcharts@3.49.1/dist/apexcharts.min.js",
        "static/vendor/apexcharts/apexcharts.min.js",
    ),
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

print(f"Vendorizing {len(ASSETS)} assets...")

for url, dest in ASSETS:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        print(f"  [EXISTS] {dest} ({os.path.getsize(dest)} bytes)")
        continue
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            with open(dest, "wb") as out:
                out.write(data)
            print(f"  [DOWNLOADED] {url} -> {dest} ({len(data)} bytes)")
    except Exception as e:
        print(f"  [ERROR] Failed downloading {url}: {e}")

print("Done vendorizing!")
