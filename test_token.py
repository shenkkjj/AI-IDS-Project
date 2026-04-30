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
print('All cookies:')
for c in cookies:
    print(' ', c[:150])

# Find authjs.session-token
session_cookie = None
for c in cookies:
    if 'authjs.session-token' in c:
        session_cookie = c.split(';')[0]
        break

print('Session cookie:', session_cookie)

# Try to call API with session cookie
if session_cookie:
    req2 = urllib.request.Request('http://localhost:3000/api/backend/user/config')
    req2.add_header('Cookie', session_cookie)
    try:
        resp2 = urllib.request.urlopen(req2)
        print('Config status:', resp2.status)
        print('Config response:', resp2.read().decode()[:300])
    except Exception as e:
        print('Config error:', e)
