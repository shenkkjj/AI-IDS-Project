import os
import sys
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio  # noqa: F401

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / ".env"
if _ENV_FILE.exists():
    with open(_ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key.strip() and key.strip() not in os.environ:
                os.environ[key.strip()] = value.strip().strip('"').strip("'")

os.environ.setdefault("APP_SECRET", "test-secret-key-for-unit-tests-only-32b")
os.environ.setdefault("AUTH_SECRET", "test-auth-secret-for-unit-tests-only-32b")
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_PROJECT_ROOT / 'data' / 'test.db'}")

sys.path.insert(0, str(_PROJECT_ROOT))


def pytest_addoption(parser):
    parser.addoption(
        "--run-e2e",
        action="store_true",
        default=False,
        help="run optional Playwright end-to-end tests",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: optional Playwright end-to-end tests")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-e2e"):
        return

    skip_e2e = pytest.mark.skip(reason="E2E 测试默认跳过；使用 --run-e2e 显式运行。")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip_e2e)


@pytest.fixture(scope="session")
def project_root():
    return _PROJECT_ROOT


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)
