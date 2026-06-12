# 分支命名规范

## 格式

```
<type>/<scope>[-<short-desc>]
```

## 类型（type）

| 类型 | 用途 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat/copilot-stream-refactor` |
| `fix` | Bug 修复 | `fix/auth-cookie-samesite` |
| `refactor` | 重构（无新功能/无 Bug 修复） | `refactor/db-py-split` |
| `docs` | 文档 | `docs/branch-naming-guide` |
| `test` | 测试 | `test/refresh-token-coverage` |
| `chore` | 杂项（依赖、配置、CI） | `chore/bump-next-15-6` |
| `perf` | 性能优化 | `perf/alert-pipeline-batch-log` |
| `security` | 安全相关 | `security/rotate-smtp-creds` |

## 范围（scope，可选但推荐）

- `auth` 认证与授权
- `alerts` 告警管线
- `waf` WAF
- `ui` 前端
- `api` 后端 API
- `infra` 部署 / CI / 配置
- `deps` 依赖管理

## 命名示例

✅ 推荐：
```
feat/auth/add-totp-enforcement
fix/waf/ssrf-bypass
refactor/llm-provider-strategy
docs/contributing/setup-guide
chore/deps/upgrade-fastapi-0-115
```

❌ 避免：
```
new-feature               # 没有 type
Feature/New-Feature       # 大写不规范
fix_bug                   # 用 _ 而不是 -
my-changes                # 没有 type
```

## 受保护的分支

`main` 和 `release-*` 分支需要 PR Review。直接 push 到这些分支会被
pre-push hook 阻止。

## 强制校验

项目根目录 `.githooks/pre-push` 会在 push 之前自动校验当前分支名。
安装方式：

```bash
git config core.hooksPath .githooks
```
