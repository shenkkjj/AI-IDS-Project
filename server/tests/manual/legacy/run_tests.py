import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_health():
    print("\n" + "="*50)
    print("1. 测试健康检查")
    print("="*50)
    resp = requests.get(f"{BASE_URL}/health")
    print(f"状态码: {resp.status_code}")
    print(f"响应: {resp.json()}")
    return resp.status_code == 200

def test_waf_status():
    print("\n" + "="*50)
    print("2. 测试 WAF 状态")
    print("="*50)
    resp = requests.get(f"{BASE_URL}/waf/status")
    print(f"状态码: {resp.status_code}")
    print(f"响应: {json.dumps(resp.json(), indent=2, ensure_ascii=False)}")
    return resp.status_code == 200

def test_register():
    print("\n" + "="*50)
    print("3. 测试用户注册")
    print("="*50)
    data = {
        "email": "test3@example.com",
        "password": "TestPass123!",
        "display_name": "Test User"
    }
    resp = requests.post(f"{BASE_URL}/auth/register", json=data)
    print(f"状态码: {resp.status_code}")
    print(f"响应: {resp.text[:500]}")
    return resp.status_code in [200, 201, 400, 409]

def test_login():
    print("\n" + "="*50)
    print("4. 测试用户登录")
    print("="*50)
    data = {
        "email": "test@example.com",
        "password": "TestPass123!"
    }
    resp = requests.post(f"{BASE_URL}/auth/login/password", json=data)
    print(f"状态码: {resp.status_code}")
    if resp.status_code == 200:
        result = resp.json()
        print(f"登录成功! Token length: {len(result.get('access_token', ''))} chars")
        return result.get('access_token')
    else:
        print(f"响应: {resp.text[:500]}")
        return None

def test_waf_proxy():
    print("\n" + "="*50)
    print("5. 测试 WAF 代理")
    print("="*50)
    headers = {"X-Forwarded-For": "8.8.8.8"}
    resp = requests.get(f"{BASE_URL}/waf/proxy/test", headers=headers)
    print(f"状态码: {resp.status_code}")
    print(f"响应: {resp.text[:300]}")
    return resp.status_code in [200, 404, 502]

def test_sql_injection_detection():
    print("\n" + "="*50)
    print("6. 测试 SQL 注入检测")
    print("="*50)
    test_payloads = [
        "1 OR 1=1",
        "' OR '1'='1",
        "'; DROP TABLE users;--"
    ]
    for payload in test_payloads:
        resp = requests.post(
            f"{BASE_URL}/waf/detect",
            json={"payload": payload, "source_ip": "8.8.8.8", "destination_ip": "127.0.0.1"}
        )
        result = resp.json()
        print(f"Payload: {payload[:30]}...")
        print(f"  检测结果: {result.get('is_malicious', result.get('is_attack', 'unknown'))}")
        print(f"  攻击类型: {result.get('attack_types', [])}")

def test_llm_config():
    print("\n" + "="*50)
    print("7. 测试 LLM 配置接口")
    print("="*50)
    resp = requests.get(f"{BASE_URL}/llm/config")
    print(f"状态码: {resp.status_code}")
    if resp.status_code == 200:
        result = resp.json()
        print(f"可用提供商: {result.get('providers', [])}")
    else:
        print(f"响应: {resp.text[:300]}")

def test_rate_limit():
    print("\n" + "="*50)
    print("8. 测试速率限制 (快速发送10个请求)")
    print("="*50)
    success_count = 0
    for i in range(10):
        resp = requests.get(f"{BASE_URL}/health")
        if resp.status_code == 200:
            success_count += 1
    print(f"成功请求数: {success_count}/10")
    print("速率限制正常" if success_count == 10 else "可能触发了限流")

if __name__ == "__main__":
    print("="*60)
    print("AI-CyberSentinel 功能测试")
    print("="*60)

    results = []

    results.append(("健康检查", test_health()))
    results.append(("WAF 状态", test_waf_status()))
    results.append(("用户注册", test_register()))
    token = test_login()
    results.append(("用户登录", token is not None))
    results.append(("WAF 代理", test_waf_proxy()))
    test_sql_injection_detection()
    test_llm_config()
    test_rate_limit()

    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
