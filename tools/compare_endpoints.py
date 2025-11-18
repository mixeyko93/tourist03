import sys
import re
from pathlib import Path

sys.path.insert(0, r'D:\PycharmProjects\Tourist03_win')
import importlib

mod = importlib.import_module('app')
app = getattr(mod, 'app')

routes = []
for r in app.routes:
    methods = getattr(r, 'methods', None) or getattr(r, 'methods', set())
    path = getattr(r, 'path', None)
    if path:
        routes.append((path, tuple(sorted(m for m in methods if m))))

routes_map = {}
for p, m in routes:
    routes_map.setdefault(p, set()).update(m)

print('Registered routes (path -> methods):')
for p in sorted(routes_map):
    print(f"{p} -> {sorted(routes_map[p])}")

# extract ACCOUNT_CREATE_ENDPOINTS from superadmin.html
html = Path(r'D:\PycharmProjects\Tourist03_win\superadmin.html').read_text(encoding='utf-8')
match = re.search(r'const\s+ACCOUNT_CREATE_ENDPOINTS\s*=\s*\[([^\]]+)\]', html, re.S)
frontend_endpoints = []
if match:
    inner = match.group(1)
    # extract strings
    frontend_endpoints = re.findall(r"'([^']+)'|\"([^\"]+)\"", inner)
    # flatten tuples
    frontend_endpoints = [a or b for a, b in frontend_endpoints]

print('\nFrontend ACCOUNT_CREATE_ENDPOINTS:')
for u in frontend_endpoints:
    print(u)

print('\nEndpoints present in frontend but not registered on backend:')
for u in frontend_endpoints:
    if u not in routes_map:
        print(' -', u)

print('\nEndpoints present in backend but not referenced in frontend (account-related):')
for p in sorted(routes_map):
    if p.startswith('/api/admin') or p.startswith('/api/superadmin'):
        if p not in frontend_endpoints:
            print(' -', p)

print('\nDone')
