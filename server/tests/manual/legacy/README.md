# Legacy Manual Integration Scripts

These are pre-pytest era manual integration scripts. They were previously
sitting at the project root and were moved here during the 2026-06-12
refactor cleanup (M1 in the refactor insight report).

They are not invoked by `pytest` and have no automatic CI hook. Use the
modern pytest suite in `server/tests/` for new coverage.

| File | Purpose | Replacement |
|------|---------|-------------|
| `audit_test.py` | Hand-rolled full-stack audit. | `pytest server/tests/test_e2e.py` |
| `check_db.py` | SQLite query helper for ad-hoc lookups. | Use `sqlite3 data/app.db` directly, or pytest fixtures. |
| `comprehensive_test.py` | Manual API smoke test. | `pytest server/tests/test_api_security.py` |
| `run_tests.py` | requests-based smoke runner. | `pytest server/tests/` |
