# Legacy Manual Integration Scripts

These are pre-pytest era manual integration scripts. They were previously
sitting at the project root and were moved here during the 2026-06-12
refactor cleanup (M1 in the refactor insight report).

They are not invoked by `pytest` and have no automatic CI hook. Use the
modern pytest suite in `server/tests/` for new coverage.

安全说明：这些脚本只作为 legacy 手工脚本保留，只能使用 fake/test
凭据。不要把真实 API key、生产密码、access token 或客户数据写入本目录。
如果手工运行确实需要真实 provider key，请通过本地环境变量传入，并确保
它不会进入 git。

| File | Purpose | Replacement |
|------|---------|-------------|
| `audit_test.py` | Hand-rolled full-stack audit. | `pytest server/tests/test_e2e.py` |
| `check_db.py` | SQLite query helper for ad-hoc lookups. | Use `sqlite3 data/app.db` directly, or pytest fixtures. |
| `comprehensive_test.py` | Manual API smoke test. | `pytest server/tests/test_api_security.py` |
| `run_tests.py` | requests-based smoke runner. | `pytest server/tests/` |
