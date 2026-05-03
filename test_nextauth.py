import os
import urllib.request
import urllib.parse
import json

TEST_EMAIL = os.environ.get("TEST_EMAIL", "test@example.com")
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "TestPassword123!")

# Use NextAuth signin endpoint
req = urllib.request.Request(
    'http://localhost:3000/api/auth/callback/credentials',
    data=urllib.parse.urlencode({
        'email': TEST_EMAIL,
        'password': TEST_PASSWORD,
        'csrfToken': 'dummy',
        'callbackUrl': 'http://localhost:3000/dashboard',
        'json': 'true'
    }).encode(),
    headers={
        'Content-Type': 'application/x-www-form-urlencoded',
    },
    method='POST'
)

try:
    resp = urllib.request.urlopen(req)
    print('Status:', resp.status)
    cookies = resp.headers.get_all('Set-Cookie') or []
    print('Cookies:')
    for c in cookies:
        print(' ', c[:200])
except Exception as e:
    print('Error:', e)
