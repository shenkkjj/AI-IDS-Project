import urllib.request
import json

# First login to get cookies via frontend
req = urllib.request.Request(
    'http://localhost:3000/api/backend/auth/login/password',
    data=json.dumps({'email': '2762919805@qq.com', 'password': 'S2762919805s'}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST'
)

try:
    resp = urllib.request.urlopen(req)
    cookies = resp.headers.get('Set-Cookie', '')
    print('Login cookies:', cookies[:200])
    print('Login response:', resp.read().decode()[:200])

    # Now test config API with cookies
    req2 = urllib.request.Request('http://localhost:3000/api/backend/user/config')
    if cookies:
        req2.add_header('Cookie', cookies)
    resp2 = urllib.request.urlopen(req2)
    print('Config status:', resp2.status)
    print('Config response:', resp2.read().decode()[:300])

    # Test alerts API
    req3 = urllib.request.Request('http://localhost:3000/api/backend/alerts?limit=100')
    if cookies:
        req3.add_header('Cookie', cookies)
    resp3 = urllib.request.urlopen(req3)
    print('Alerts status:', resp3.status)
    print('Alerts response:', resp3.read().decode()[:300])

    # Test site health
    req4 = urllib.request.Request('http://localhost:3000/api/backend/site/health')
    if cookies:
        req4.add_header('Cookie', cookies)
    resp4 = urllib.request.urlopen(req4)
    print('Site health status:', resp4.status)
    print('Site health response:', resp4.read().decode()[:300])

except Exception as e:
    print('Error:', e)
