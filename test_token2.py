import urllib.request
import json

# Login
req = urllib.request.Request(
    'http://localhost:3000/api/backend/auth/login/password',
    data=json.dumps({'email': '2762919805@qq.com', 'password': 'S2762919805s'}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
resp = urllib.request.urlopen(req)
cookies = resp.headers.get_all('Set-Cookie') or []
print('All cookies after login:')
for c in cookies:
    print(' ', c[:200])

# Collect all cookies
all_cookies = '; '.join([c.split(';')[0] for c in cookies])
print('Cookie string:', all_cookies[:200])

# Test token endpoint
req2 = urllib.request.Request('http://localhost:3000/api/test-token')
req2.add_header('Cookie', all_cookies)
try:
    resp2 = urllib.request.urlopen(req2)
    print('Token endpoint:', resp2.read().decode())
except Exception as e:
    print('Token endpoint error:', e)
