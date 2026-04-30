import urllib.request
import json

# Test login to get token
req = urllib.request.Request(
    'http://localhost:8000/auth/login/password',
    data=json.dumps({'email': '2762919805@qq.com', 'password': 'S2762919805s'}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
try:
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read().decode())
    token = data.get('access_token', '')
    print('Login success, token:', token[:20] + '...' if token else 'NO TOKEN')

    # Test user config
    req2 = urllib.request.Request(
        'http://localhost:8000/user/config',
        headers={'Authorization': f'Bearer {token}'}
    )
    resp2 = urllib.request.urlopen(req2)
    print('Config:', resp2.read().decode()[:200])

    # Test alerts
    req3 = urllib.request.Request(
        'http://localhost:8000/alerts?limit=100',
        headers={'Authorization': f'Bearer {token}'}
    )
    resp3 = urllib.request.urlopen(req3)
    print('Alerts:', resp3.read().decode()[:200])

    # Test site health
    req4 = urllib.request.Request(
        'http://localhost:8000/site/health',
        headers={'Authorization': f'Bearer {token}'}
    )
    resp4 = urllib.request.urlopen(req4)
    print('Site health:', resp4.read().decode())

except Exception as e:
    print('Error:', e)
