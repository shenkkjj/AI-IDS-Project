# HTTPS 证书目录（opt-in）

> 状态：M2-07 默认不启用 HTTPS。本地 HTTP 入口（`http://127.0.0.1`）已通过 `docker-compose.yml` + `nginx/nginx.conf` 走通。
> 本目录仅在你 **明确要启用 HTTPS** 时使用；启用方式见下方。

## 何时需要放证书

- 你想让外部用户通过 `https://...` 访问服务。
- 你的部署目标是公网或需要 HSTS preload 的环境。
- 你需要 OCSP stapling 等 TLS 优化。

## 不需要放证书

- 本地开发 / 内部 demo / CI smoke。
- 已经有外部反向代理（CloudFront / nginx-ingress）终止 TLS，本服务只在 80 上 serve。

## 启用 HTTPS 步骤

1. 把 `fullchain.pem`（leaf + chain）和 `privkey.pem`（私钥）放到本目录。
2. 打开 `nginx/nginx.conf`，把 **HTTPS server 块**（被 `#` 注释掉的那一段）的注释取消。
3. 重新构建：

   ```powershell
   docker compose --env-file .env.compose.local build nginx
   docker compose --env-file .env.compose.local up -d
   ```

4. 验证：

   ```powershell
   curl -kI https://127.0.0.1/health
   ```

## 本地自签证书（仅供本地测试）

```powershell
openssl req -x509 -nodes -days 365 -newkey rsa:2048 `
  -keyout nginx/certs/privkey.pem `
  -out nginx/certs/fullchain.pem `
  -subj "/CN=localhost"
```

## 安全提醒

- 不要把真实生产证书提交到 git。
- 真实私钥应该通过 secret manager / volume mount 注入，不应进仓库。
- 本目录在 `.gitignore` 中已被忽略（参考项目根 `.gitignore`）。
