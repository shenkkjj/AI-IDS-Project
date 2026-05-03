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

# Get cookies from CSRF response
cookies = csrf_resp.headers.get_all('Set-Cookie') or []
cookie_str = '; '.join([c.split(';')[0] for c in cookies])

# Step 2: Login with CSRF token - don't follow redirects
class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def http_error_302(self, req, fp, code, msg, headers):
        return fp
    def http_error_301(self, req, fp, code, msg, headers):
        return fp

opener = urllib.request.build_opener(NoRedirectHandler())

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

resp = opener.open(req)
login_cookies = resp.headers.get_all('Set-Cookie') or []

# Combine all cookies
all_cookies_list = [c.split(';')[0] for c in cookies] + [c.split(';')[0] for c in login_cookies]
all_cookies = '; '.join(all_cookies_list)
print('All cookies:', all_cookies[:300])

# Step 3: Test config API with session cookie
req2 = urllib.request.Request('http://localhost:3000/api/backend/user/config')
req2.add_header('Cookie', all_cookies)
try:
    resp2 = urllib.request.urlopen(req2)
    print('Config status:', resp2.status)
    print('Config:', resp2.read().decode()[:300])
except Exception as e:
    print('Config error:', e)

# Step 4: Test alerts API
req3 = urllib.request.Request('http://localhost:3000/api/backend/alerts?limit=100')
req3.add_header('Cookie', all_cookies)
try:
    resp3 = urllib.request.urlopen(req3)
    print('Alerts status:', resp3.status)
    print('Alerts:', resp3.read().decode()[:300])
except Exception as e:
    print('Alerts error:', e)

# Step 5: Test site health
req4 = urllib.request.Request('http://localhost:3000/api/backend/site/health')
req4.add_header('Cookie', all_cookies)
try:
    resp4 = urllib.request.urlopen(req4)
    print('Site health status:', resp4.status)
    print('Site health:', resp4.read().decode())
except Exception as e:
    print('Site health error:', e)
