import os
import urllib.request
import urllib.parse
import json

TEST_EMAIL = os.environ.get("TEST_EMAIL", "test@example.com")
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "TestPassword123!")

# Step 1: Get CSRF token
csrf_req = urllib.request.Request('http://localhost:3000/api/auth/csrf')
csrf_resp = urllib.request.urlopen(csrf_req)
csrf_data = json.loads(csrf_resp.read().decode())
csrf_token = csrf_data.get('csrfToken', '')
print('CSRF token:', csrf_token[:30] + '...')

# Get cookies from CSRF response
cookies = csrf_resp.headers.get_all('Set-Cookie') or []
cookie_str = '; '.join([c.split(';')[0] for c in cookies])
print('CSRF cookies:', cookie_str[:200])

# Step 2: Login with CSRF token - follow redirects manually
req = urllib.request.Request(
    'http://localhost:3000/api/auth/callback/credentials',
    data=urllib.parse.urlencode({
        'email': TEST_EMAIL,
        'password': TEST_PASSWORD,
        'csrfToken': csrf_token,
        'callbackUrl': 'http://localhost:3000/dashboard',
        'json': 'true'
    }).encode(),
    headers={
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cookie': cookie_str,
    },
    method='POST'
)

# Don't follow redirects
class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def http_error_302(self, req, fp, code, msg, headers):
        return fp
    def http_error_301(self, req, fp, code, msg, headers):
        return fp
    def http_error_307(self, req, fp, code, msg, headers):
        return fp
    def http_error_308(self, req, fp, code, msg, headers):
        return fp

opener = urllib.request.build_opener(NoRedirectHandler())

try:
    resp = opener.open(req)
    print('Login status:', resp.status)
    print('Login headers:')
    for h, v in resp.headers.items():
        if 'cookie' in h.lower() or 'set-cookie' in h.lower() or 'location' in h.lower():
            print(f'  {h}: {v[:200]}')

    login_cookies = resp.headers.get_all('Set-Cookie') or []
    print('Login Set-Cookie:')
    for c in login_cookies:
        print(' ', c[:200])

    # Read body
    body = resp.read().decode()
    print('Body:', body[:500])

except Exception as e:
    print('Error:', e)
