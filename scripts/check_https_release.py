"""Read-only release identity: HTML, referenced JS graph, styles and local fonts."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
from time import perf_counter
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


class Assets(HTMLParser):
    def __init__(self): super().__init__(); self.urls = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script' and attrs.get('src'): self.urls.append(attrs['src'])
        if tag == 'link' and attrs.get('rel') == 'stylesheet': self.urls.append(attrs['href'])


def inspect(base, refs):
    origin = urlparse(base).netloc
    if urlparse(base).scheme != 'https': raise ValueError('Verified HTTPS required')
    pending = {urljoin(base, '/')}
    observed = {}
    def fetch(url):
        started = perf_counter()
        with urlopen(Request(url, headers={'User-Agent': 'Agent4K-release-check'}), timeout=20) as response:
            data = response.read()
            return url, data, {'path': urlparse(url).path, 'status': response.status, 'bytes': len(data),
                              'sha256': hashlib.sha256(data).hexdigest(),
                              'duration_ms': round((perf_counter() - started) * 1000, 2),
                              'cache_control': response.headers.get('Cache-Control')}
    with ThreadPoolExecutor(max_workers=8) as executor:
        while pending:
            batch = sorted(pending - observed.keys())
            if not batch: break
            pending = set()
            for url, data, item in executor.map(fetch, batch):
                observed[url] = item
                pathname = urlparse(url).path
                text = data.decode('utf-8') if pathname == '/' or pathname.endswith(('.js', '.css')) else ''
                links = []
                if pathname == '/':
                    parser = Assets(); parser.feed(text); links = parser.urls
                elif pathname.endswith('.js'):
                    links = re.findall(r'''["']((?:/web/dist/|\./)[^"'\s]+\.js)["']''', text)
                elif pathname.endswith('.css'):
                    links = re.findall(r'''url\(["']?([^\s)'";]+)''', text)
                for link in links:
                    candidate = urljoin(url, link)
                    if urlparse(candidate).netloc == origin and urlparse(candidate).path.startswith('/web/'):
                        pending.add(candidate)
    for item in observed.values():
        path = 'web/index.html' if item['path'] == '/' else item['path'].lstrip('/')
        item['matching_refs'] = []
        for ref in refs:
            result = subprocess.run(['git', 'show', f'{ref}:{path}'], capture_output=True)
            if result.returncode == 0 and hashlib.sha256(result.stdout).hexdigest() == item['sha256']:
                item['matching_refs'].append(ref)
    with urlopen(urljoin(base, '/users/version'), timeout=20) as response:
        backend = json.load(response)['version']
    complete = [ref for ref in refs if all(ref in item['matching_refs'] for item in observed.values())]
    return {'url': base, 'backend_version': backend, 'matching_complete_frontend_refs': complete,
            'scope': 'Public bytes only; identical frontend bytes do not identify a unique backend SHA',
            'assets': sorted(observed.values(), key=lambda item: item['path'])}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--ref', action='append', required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = inspect(args.url, args.ref)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(json.dumps({key: value for key, value in result.items() if key != 'assets'}, ensure_ascii=False))
    print('verified_assets=' + str(len(result['assets'])))
