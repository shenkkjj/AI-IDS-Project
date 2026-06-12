# 安全加固检查清单

> 本文件由重构洞察行动（2026-06-12）创建。
> 用于追踪项目安全相关的关键发现和修复状态。

## ✅ C3 — `.env` 凭据泄露（已验证安全）

**检查日期：** 2026-06-12

**验证结果：**

| 检查项 | 命令 | 结果 |
|--------|------|------|
| `.env` 是否在 `.gitignore` | `git check-ignore -v .env` | ✅ 命中 `.gitignore:8:.env` |
| `.env` 是否被 git 跟踪 | `git ls-files .env` | ❌ 未跟踪 |
| `.env` 是否在历史中 | `git log --all -- .env` | ❌ 历史中无此文件 |
| `.env.example` 是否提供 | `ls .env.example` | ✅ 已提供 |

**结论：** `.env` 文件从未进入版本控制。`asmd9364@163.com` 凭据只存在于本地开发环境。

## ⚠️ 建议立即执行的轮换操作

由于开发环境日志、IDE 历史、终端历史可能记录了凭据，仍建议防御性轮换：

### 1. 轮换 SMTP 邮箱密码

1. 登录 [mail.163.com](https://mail.163.com)
2. 进入 **设置 → 客户端授权码**
3. 删除旧的授权码：`DKmbLwQDzXvYWDtF`
4. 生成新的授权码（替换 `.env` 中的 `SMTP_PASSWORD`）
5. 同步更新到部署环境（`.env.production`、K8s Secret、Docker Secret）

### 2. 检查其他可能泄露的渠道

```bash
# 检查 shell 历史
grep "DKmbLwQDzXvYWDtF" ~/.bash_history 2>/dev/null
grep "DKmbLwQDzXvYWDtF" ~/.zsh_history 2>/dev/null

# 检查 IDE 工作区文件
find D:/Users/27629/Desktop/Claude/AI-IDS-Project -name "*.log" \
  -exec grep -l "DKmbLwQDzXvYWDtF" {} \; 2>/dev/null
```

如有命中，清理后重启终端。

### 3. 预提交保护

`.gitignore` 已正确配置 `.env`。建议在 `.git/hooks/pre-commit` 中添加：

```bash
#!/bin/bash
# 防止敏感信息误提交
if git diff --cached --name-only | grep -E "^\.env$|^\.env\.local$|^\.env\.production$"; then
  echo "❌ 检测到 .env 文件，禁止提交"
  exit 1
fi
```

## ✅ C1 — 管理端点认证（已修复）

**修复日期：** 2026-06-12

**修改文件：**
- `server/routers/admin_router.py`：移除自定义 `_get_admin()`，改用 `require_admin` 标准依赖。

**修复前问题：** `token: str | None = None` 被 FastAPI 默认为 Query 参数，所有管理端点通过 URL `?token=xxx` 传递 JWT。

**修复后：** 统一从 `Authorization: Bearer <token>` Header 或 `access_token` Cookie 提取。

## ✅ C2 — JWT Secret 硬编码（已修复）

**修复日期：** 2026-06-12

**修改文件：**
- `web-next/lib/auth.ts`：移除 `dev-insecure-secret-do-not-use-in-production` fallback。

**修复后行为：**
- 运行时未设置 `AUTH_SECRET`：抛出明确错误提示
- 任何环境 `AUTH_SECRET` 长度 < 32 字符：抛出错误
- 仅在 `NEXT_PHASE=phase-production-build` 静态构建阶段使用占位符（且占位符长度也达到 64 字符，避免触发长度校验）

## 待办（其余 Critical 修复）

- [ ] C4: 拆分 `APP_SECRET` 为独立 JWT 密钥和 API Key 加密密钥
