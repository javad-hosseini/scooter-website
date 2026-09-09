import os
import re

SCAN_DIRS = ['apps', 'templates', 'static', 'config']
EXCLUDE_DIRS = {'venv', '.venv', '.git', '.idea', '.vscode', 'templates-backup', 'deprecated', 'front files', 'staticfiles', 'public'}

all_found = []

# Match any href="http..." or src="http..." or url("http...")
HREF_SRC_REGEX = re.compile(r'(?:href|src)=["\'](https?://[^"\']+)["\']', re.IGNORECASE)
CSS_URL_REGEX = re.compile(r'url\(["\']?(https?://[^"\'\)]+)["\']?\)', re.IGNORECASE)
IMPORT_REGEX = re.compile(r'@import\s+["\'](https?://[^"\']+)["\']', re.IGNORECASE)

for sdir in SCAN_DIRS:
    for root, dirs, files in os.walk(sdir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if f.endswith(('.html', '.js', '.css', '.py')):
                filepath = os.path.join(root, f)
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as fp:
                    content = fp.read()
                    for m in HREF_SRC_REGEX.finditer(content):
                        url = m.group(1)
                        if not any(ign in url for ign in ['schema.org', 'localhost', '127.0.0.1', 'testserver', 'voltex.test', 'voltex.ir', 'nexgo.test', 'nexgo.ir', 'AS-tech.company']):
                            all_found.append((filepath, url, 'href/src'))
                    for m in CSS_URL_REGEX.finditer(content):
                        url = m.group(1)
                        if not any(ign in url for ign in ['schema.org', 'localhost', '127.0.0.1', 'testserver', 'voltex.test', 'voltex.ir', 'nexgo.test', 'nexgo.ir', 'AS-tech.company']):
                            all_found.append((filepath, url, 'css-url'))
                    for m in IMPORT_REGEX.finditer(content):
                        url = m.group(1)
                        if not any(ign in url for ign in ['schema.org', 'localhost', '127.0.0.1', 'testserver', 'voltex.test', 'voltex.ir', 'nexgo.test', 'nexgo.ir', 'AS-tech.company']):
                            all_found.append((filepath, url, '@import'))

print(f"Total occurrences: {len(all_found)}\n")
by_domain = {}
for path, url, kind in all_found:
    domain = url.split('/')[2] if len(url.split('/')) > 2 else url
    by_domain.setdefault(domain, []).append((path, url, kind))

for domain, items in sorted(by_domain.items()):
    print(f"=== Domain: {domain} ({len(items)} hits) ===")
    unique_urls = set(x[1] for x in items)
    for u in sorted(unique_urls):
        files = sorted(set(x[0] for x in items if x[1] == u))
        print(f"  {u}")
        for fl in files:
            print(f"    - {fl}")
    print()
