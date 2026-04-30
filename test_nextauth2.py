import urllib.request
import urllib.parse
import json
import re

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

# Step 2: Login with CSRF token
req = urllib.request.Request(
    'http://localhost:3000/api/auth/callback/credentials',
    data=urllib.parse.urlencode({
        'email': '2762919805@qq.com',
        'password': 'S2762919805s',
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

try:
    resp = urllib.request.urlopen(req)
    print('Login status:', resp.status)
    login_cookies = resp.headers.get_all('Set-Cookie') or []
    print('Login cookies:')
    for c in login_cookies:
        print(' ', c[:200])

    # Combine all cookies
    all_cookies = cookie_str + '; ' + '; '.join([c.split(';')[0] for c in login_cookies])
    print('All cookies:', all_cookies[:300])

    # Test API with session
    req2 = urllib.request.Request('http://localhost:3000/api/test-token')
    req2.add_header('Cookie', all_cookies)
    resp2 = urllib.request.urlopen(req2)
    print('Token test:', resp2.read().decode())

    # Test config API
    req3 = urllib.request.Request('http://localhost:3000/api/backend/user/config')
    req3.add_header('Cookie', all_cookies)
    resp3 = urllib.request.urlopen(req3)
    print('Config status:', resp3.status)
    print('Config:', resp3.read().decode()[:300])

except Exception as e:
    print('Error:', e)
