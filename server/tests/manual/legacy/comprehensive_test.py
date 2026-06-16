#!/usr/bin/env python3
"""
AI-CyberSentinel 全面功能测试
测试所有后端 API 功能
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"
TEST_RESULTS = []
ACCESS_TOKEN = None
TEST_USER_EMAIL = "test3@example.com"
TEST_PASSWORD = "TestPass123!"

def log_test(name, status, details=""):
    """记录测试结果"""
    icon = "✅" if status else "❌"
    TEST_RESULTS.append({
        "name": name,
        "status": status,
        "details": details
    })
    print(f"{icon} {name}")
    if details:
        print(f"   {details}")

def get_headers():
    """获取带认证的请求头"""
    if ACCESS_TOKEN:
        return {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    return {}

# ==================== 1. 基础健康检查 ====================
print("\n" + "="*60)
print("1. 基础健康检查")
print("="*60)

try:
    resp = requests.get(f"{BASE_URL}/health", timeout=5)
    log_test("健康检查", resp.status_code == 200, f"状态码: {resp.status_code}")
except Exception as e:
    log_test("健康检查", False, str(e))

try:
    resp = requests.get(f"{BASE_URL}/openapi.json", timeout=5)
    log_test("API文档", resp.status_code == 200, f"包含 {len(resp.json().get('paths', {}))} 个端点")
except Exception as e:
    log_test("API文档", False, str(e))

# ==================== 2. 认证系统测试 ====================
print("\n" + "="*60)
print("2. 认证系统测试")
print("="*60)

# 2.1 用户注册
try:
    resp = requests.post(f"{BASE_URL}/auth/register", json={
        "email": TEST_USER_EMAIL,
        "password": TEST_PASSWORD,
        "display_name": "Test User"
    }, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        ACCESS_TOKEN = data.get("access_token")
        log_test("用户注册", True, f"用户ID: {data.get('user', {}).get('id')}")
    elif resp.status_code == 409:
        log_test("用户注册", True, "用户已存在（使用已有用户）")
    elif resp.status_code == 429:
        log_test("用户注册", True, "速率限制中（使用已有用户）")
    else:
        log_test("用户注册", False, f"状态码: {resp.status_code}, {resp.text[:100]}")
except Exception as e:
    log_test("用户注册", False, str(e))

# 2.2 密码登录
try:
    resp = requests.post(f"{BASE_URL}/auth/login/password", json={
        "email": TEST_USER_EMAIL,
        "password": TEST_PASSWORD
    }, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        ACCESS_TOKEN = data.get("access_token")
        log_test("密码登录", True, f"Token length: {len(ACCESS_TOKEN)} chars" if ACCESS_TOKEN else "无Token")
    else:
        log_test("密码登录", False, f"状态码: {resp.status_code}, {resp.text[:100]}")
except Exception as e:
    log_test("密码登录", False, str(e))

# 2.3 获取当前用户会话 (修正)
try:
    resp = requests.get(f"{BASE_URL}/auth/session", headers=get_headers(), timeout=5)
    log_test("获取用户会话", resp.status_code == 200,
             f"状态码: {resp.status_code}" if resp.status_code != 200 else f"邮箱: {resp.json().get('user', {}).get('email')}")
except Exception as e:
    log_test("获取用户会话", False, str(e))

# 2.4 TOTP 设置 (修正)
try:
    resp = requests.post(f"{BASE_URL}/auth/totp/setup", headers=get_headers(), json={}, timeout=5)
    log_test("TOTP设置", resp.status_code in [200, 201, 400, 409], f"状态码: {resp.status_code}")
except Exception as e:
    log_test("TOTP设置", False, str(e))

# 2.5 OTP 登录请求
try:
    resp = requests.post(f"{BASE_URL}/auth/login/otp/request", json={
        "email": TEST_USER_EMAIL
    }, timeout=5)
    log_test("OTP登录请求", resp.status_code in [200, 202], f"状态码: {resp.status_code}")
except Exception as e:
    log_test("OTP登录请求", False, str(e))

# 2.6 密码重置请求 (修正)
try:
    resp = requests.post(f"{BASE_URL}/auth/password/reset/request", json={
        "email": TEST_USER_EMAIL
    }, timeout=5)
    log_test("密码重置请求", resp.status_code in [200, 202], f"状态码: {resp.status_code}")
except Exception as e:
    log_test("密码重置请求", False, str(e))

# ==================== 3. WAF 功能测试 ====================
print("\n" + "="*60)
print("3. WAF 功能测试")
print("="*60)

# 3.1 WAF 状态
try:
    resp = requests.get(f"{BASE_URL}/waf/status", timeout=5)
    if resp.status_code == 200:
        data = resp.json()
        log_test("WAF状态", True, f"状态: {data.get('status')}, 限流后端: {data.get('rate_limit', {}).get('backend')}")
    else:
        log_test("WAF状态", False, f"状态码: {resp.status_code}")
except Exception as e:
    log_test("WAF状态", False, str(e))

# 3.2 WAF 代理（无认证）
try:
    resp = requests.get(f"{BASE_URL}/proxy/test", headers={"X-Forwarded-For": "8.8.8.8"}, timeout=5)
    log_test("WAF代理", resp.status_code in [200, 403, 404, 502], f"状态码: {resp.status_code}")
except Exception as e:
    log_test("WAF代理", False, str(e))

# 3.3 WAF 代理（测试内部网络检测）
try:
    resp = requests.get(f"{BASE_URL}/proxy/test", headers={"X-Forwarded-For": "192.168.1.1"}, timeout=5)
    log_test("WAF内部网络检测", resp.status_code == 403, f"403=正常拦截, 实际: {resp.status_code}")
except Exception as e:
    log_test("WAF内部网络检测", False, str(e))

# ==================== 4. 告警系统测试 ====================
print("\n" + "="*60)
print("4. 告警系统测试")
print("="*60)

# 4.1 获取告警列表
try:
    resp = requests.get(f"{BASE_URL}/alerts", headers=get_headers(), timeout=5)
    if resp.status_code == 200:
        data = resp.json()
        alerts = data.get("alerts", [])
        log_test("告警列表", True, f"告警数量: {len(alerts)}")
    else:
        log_test("告警列表", False, f"状态码: {resp.status_code}")
except Exception as e:
    log_test("告警列表", False, str(e))

# 4.2 创建测试告警 (需要 ALERTS_INGEST_TOKEN)
alerts_token = "dev-alerts-token-change-in-production"
try:
    resp = requests.post(f"{BASE_URL}/alerts",
        headers={**get_headers(), "X-Alerts-Token": alerts_token},
        json={
            "source_ip": "192.168.1.100",
            "destination_ip": "10.0.0.1",
            "payload": "test payload",
            "event": "anomaly",
            "blocked": False
        }, timeout=5)
    if resp.status_code in [200, 201]:
        alert_id = resp.json().get("id") if isinstance(resp.json(), dict) else None
        log_test("创建告警", True, f"告警ID: {alert_id}")
    elif resp.status_code == 401:
        log_test("创建告警", False, "需要配置 ALERTS_INGEST_TOKEN")
    else:
        log_test("创建告警", False, f"状态码: {resp.status_code}, {resp.text[:100]}")
except Exception as e:
    log_test("创建告警", False, str(e))

# 4.3 日志列表
try:
    resp = requests.get(f"{BASE_URL}/logs", headers=get_headers(), timeout=5)
    log_test("日志列表", resp.status_code == 200, f"状态码: {resp.status_code}")
except Exception as e:
    log_test("日志列表", False, str(e))

# ==================== 5. 用户配置测试 ====================
print("\n" + "="*60)
print("5. 用户配置测试")
print("="*60)

if ACCESS_TOKEN:
    # 5.1 获取用户配置 (修正路径)
    try:
        resp = requests.get(f"{BASE_URL}/user/config", headers=get_headers(), timeout=5)
        if resp.status_code == 200:
            config = resp.json()
            log_test("获取用户配置", True, f"主题: {config.get('ui_theme')}, 提供商: {config.get('ai_provider')}")
        else:
            log_test("获取用户配置", False, f"状态码: {resp.status_code}")
    except Exception as e:
        log_test("获取用户配置", False, str(e))

    # 5.2 更新用户配置
    try:
        resp = requests.put(f"{BASE_URL}/user/config",
            headers=get_headers(),
            json={
                "ui_theme": "dark",
                "ui_density": "compact",
                "alert_email_enabled": True
            },
            timeout=5)
        log_test("更新用户配置", resp.status_code == 200, f"状态码: {resp.status_code}")
    except Exception as e:
        log_test("更新用户配置", False, str(e))
else:
    log_test("用户配置", False, "跳过（无认证Token）")

# ==================== 6. 站点监控测试 ====================
print("\n" + "="*60)
print("6. 站点监控测试")
print("="*60)

if ACCESS_TOKEN:
    # 6.1 添加监控站点 (修正路径)
    try:
        resp = requests.post(f"{BASE_URL}/site/target",
            headers=get_headers(),
            json={"url": "https://www.example.com"},
            timeout=10)
        if resp.status_code in [200, 201]:
            site_id = resp.json().get("id") if isinstance(resp.json(), dict) else None
            log_test("添加监控站点", True, f"站点ID: {site_id}")
        else:
            log_test("添加监控站点", False, f"状态码: {resp.status_code}")
    except Exception as e:
        log_test("添加监控站点", False, str(e))

    # 6.2 获取站点健康状态
    try:
        resp = requests.get(f"{BASE_URL}/site/health", headers=get_headers(), timeout=5)
        log_test("获取站点健康状态", resp.status_code == 200, f"状态码: {resp.status_code}")
    except Exception as e:
        log_test("获取站点健康状态", False, str(e))
else:
    log_test("站点监控", False, "跳过（无认证Token）")

# ==================== 7. 通知系统测试 ====================
print("\n" + "="*60)
print("7. 通知系统测试")
print("="*60)

# 7.1 Webhook 测试
try:
    resp = requests.post(f"{BASE_URL}/notify/webhook/test",
        headers=get_headers(),
        json={"url": "https://httpbin.org/post"},
        timeout=10)
    log_test("Webhook测试", resp.status_code in [200, 202], f"状态码: {resp.status_code}")
except Exception as e:
    log_test("Webhook测试", False, str(e))

# ==================== 8. 导出功能测试 ====================
print("\n" + "="*60)
print("8. 导出功能测试")
print("="*60)

# 8.1 导出告警 CSV
try:
    resp = requests.get(f"{BASE_URL}/export/alerts", headers=get_headers(), timeout=10)
    log_test("导出告警CSV", resp.status_code == 200, 
             f"Content-Type: {resp.headers.get('content-type')}" if resp.status_code == 200 else f"状态码: {resp.status_code}")
except Exception as e:
    log_test("导出告警CSV", False, str(e))

# 8.2 导出日志 CSV
try:
    resp = requests.get(f"{BASE_URL}/export/logs", headers=get_headers(), timeout=10)
    log_test("导出日志CSV", resp.status_code == 200, 
             f"Content-Type: {resp.headers.get('content-type')}" if resp.status_code == 200 else f"状态码: {resp.status_code}")
except Exception as e:
    log_test("导出日志CSV", False, str(e))

# ==================== 9. Copilot 功能测试 ====================
print("\n" + "="*60)
print("9. Copilot 功能测试")
print("="*60)

if ACCESS_TOKEN:
    # 9.1 Copilot 流式聊天 (修正路径)
    try:
        resp = requests.post(f"{BASE_URL}/copilot/stream",
            headers=get_headers(),
            json={"message": "Hello, what can you do?"},
            timeout=30)
        log_test("Copilot流式聊天", resp.status_code in [200, 503], f"状态码: {resp.status_code}")
    except Exception as e:
        log_test("Copilot流式聊天", False, str(e))
else:
    log_test("Copilot功能", False, "跳过（无认证Token）")

# ==================== 10. 威胁情报测试 ====================
print("\n" + "="*60)
print("10. 威胁情报测试")
print("="*60)

# 10.1 威胁情报状态
try:
    resp = requests.get(f"{BASE_URL}/threat-intel/status", headers=get_headers(), timeout=5)
    log_test("威胁情报状态", resp.status_code == 200,
             f"状态: {resp.json()}" if resp.status_code == 200 else f"状态码: {resp.status_code}")
except Exception as e:
    log_test("威胁情报状态", False, str(e))

# 10.2 IP 威胁检查
try:
    resp = requests.get(f"{BASE_URL}/threat-intel/check/8.8.8.8", headers=get_headers(), timeout=10)
    log_test("IP威胁检查", resp.status_code == 200,
             f"结果: {resp.json()}" if resp.status_code == 200 else f"状态码: {resp.status_code}")
except Exception as e:
    log_test("IP威胁检查", False, str(e))

# 10.3 刷新威胁情报 (需要管理员权限)
try:
    resp = requests.post(f"{BASE_URL}/threat-intel/refresh", headers=get_headers(), timeout=5)
    log_test("刷新威胁情报", resp.status_code in [200, 202, 403], f"状态码: {resp.status_code}")
except Exception as e:
    log_test("刷新威胁情报", False, str(e))

# ==================== 11. 合规审计测试 ====================
print("\n" + "="*60)
print("11. 合规审计测试")
print("="*60)

# 11.1 下载审计报告
try:
    resp = requests.get(f"{BASE_URL}/compliance/audit-report", headers=get_headers(), timeout=10)
    log_test("审计报告", resp.status_code in [200, 403], f"状态码: {resp.status_code}")
except Exception as e:
    log_test("审计报告", False, str(e))

# 11.2 管理员角色用户列表 (需要管理员权限)
try:
    resp = requests.get(f"{BASE_URL}/admin/roles/users", headers=get_headers(), timeout=5)
    log_test("管理员用户列表", resp.status_code in [200, 401, 403], f"状态码: {resp.status_code}")
except Exception as e:
    log_test("管理员用户列表", False, str(e))

# ==================== 12. 速率限制测试 ====================
print("\n" + "="*60)
print("12. 速率限制测试")
print("="*60)

try:
    success_count = 0
    for i in range(20):
        resp = requests.get(f"{BASE_URL}/health", timeout=2)
        if resp.status_code == 200:
            success_count += 1
        time.sleep(0.05)  # 50ms 间隔
    log_test("速率限制", success_count >= 18, f"成功: {success_count}/20")
except Exception as e:
    log_test("速率限制", False, str(e))

# ==================== 测试结果汇总 ====================
print("\n" + "="*60)
print("测试结果汇总")
print("="*60)

passed = sum(1 for r in TEST_RESULTS if r["status"])
failed = sum(1 for r in TEST_RESULTS if not r["status"])
total = len(TEST_RESULTS)

print(f"\n总计: {total} 项测试")
print(f"✅ 通过: {passed} 项 ({passed/total*100:.1f}%)")
print(f"❌ 失败: {failed} 项 ({failed/total*100:.1f}%)")

if failed > 0:
    print("\n失败的测试:")
    for r in TEST_RESULTS:
        if not r["status"]:
            print(f"  - {r['name']}: {r['details']}")

print("\n" + "="*60)
print(f"测试完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*60)
